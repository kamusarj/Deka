"""Shared transport policy and telemetry for AI provider calls.

Two separate protections exist and they are not interchangeable:

* The **application timeout** (``AI_REQUEST_TIMEOUT_SECONDS``) wraps the awaited
  task. It keeps the event loop responsive, but a cancelled ``asyncio.to_thread``
  leaves the underlying SDK request running in its worker thread.
* The **transport timeout** built here is handed to the provider SDK itself. It
  is what actually aborts an in-flight HTTP request and releases the thread.

Both are needed: the transport timeout is set slightly below the application
ceiling so the SDK surfaces a real provider error before the outer wait gives up.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

import httpx

from app.core.config import settings

logger = logging.getLogger("app.ai")
response_capture: ContextVar[list | None] = ContextVar("ai_response_capture", default=None)


def normalized_usage(response: Any) -> dict:
    usage = getattr(response, "usage", None) or getattr(response, "usage_metadata", None)
    def read(obj, name):
        return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)
    def pick(*names):
        for name in names:
            value = read(usage, name)
            if type(value) is int and value >= 0:
                return value
        return None
    details = read(usage, "input_tokens_details") or read(usage, "prompt_tokens_details")
    cached = read(details, "cached_tokens")
    if type(cached) is not int or cached < 0:
        cached = pick("cached_content_token_count", "prompt_cache_hit_tokens")
    output = pick("output_tokens", "completion_tokens", "candidates_token_count")
    thoughts = pick("thoughts_token_count")
    if output is not None and thoughts is not None:
        output += thoughts
    return {"input_tokens": pick("input_tokens", "prompt_tokens", "prompt_token_count"),
            "output_tokens": output, "cached_tokens": cached}


def connect_timeout() -> float:
    budget = _transport_budget()
    return float(min(settings.AI_CONNECT_TIMEOUT_SECONDS, budget / 2))


def read_timeout() -> float:
    """Read budget after reserving connect time below the app ceiling."""
    return float(min(settings.AI_READ_TIMEOUT_SECONDS, _transport_budget() - connect_timeout()))


def _transport_budget() -> float:
    """Leave one second for SDK cleanup/error propagation before wait_for fires."""
    return max(1.0, float(settings.AI_REQUEST_TIMEOUT_SECONDS) - 1.0)


def timeout_ms() -> int:
    """Total transport budget in milliseconds, for SDKs that want one number."""
    return int((connect_timeout() + read_timeout()) * 1000)


def httpx_timeout() -> httpx.Timeout:
    return httpx.Timeout(
        read_timeout(),
        connect=connect_timeout(),
        read=read_timeout(),
        write=read_timeout(),
        pool=connect_timeout(),
    )


def httpx_client() -> httpx.Client:
    """A client carrying this app's transport policy, for SDKs that accept one."""
    return httpx.Client(timeout=httpx_timeout())


def _usage_fields(response: Any) -> dict[str, int]:
    """Best-effort token counts across provider response shapes."""
    usage = getattr(response, "usage", None) or getattr(response, "usage_metadata", None)
    if usage is None:
        return {}

    def pick(*names: str) -> int | None:
        for name in names:
            value = getattr(usage, name, None)
            if isinstance(value, int):
                return value
        return None

    fields = {
        "prompt_tokens": pick("prompt_tokens", "prompt_token_count", "input_tokens"),
        "completion_tokens": pick(
            "completion_tokens", "candidates_token_count", "output_tokens"
        ),
        "total_tokens": pick("total_tokens", "total_token_count"),
    }
    return {key: value for key, value in fields.items() if value is not None}


@contextmanager
def track_call(provider: str, model: str, operation: str) -> Iterator[dict[str, Any]]:
    """Time one provider call and log the outcome.

    Yields a mutable dict; assign ``slot["response"]`` so token usage can be
    read off the provider response when the call succeeds.
    """
    from app.services.ai.lifecycle import checkpoint
    checkpoint()
    from app.services.ai.gateway import usage_sink
    from app.services.ai.errors import AIError
    if settings.deployed and usage_sink.get() is None:
        raise AIError('AI_ACCOUNTING_ERROR', 503)
    if (settings.deployed or usage_sink.get() is not None or provider in {'openai', 'gemini', 'deepseek'}) and provider not in settings.AI_ALLOWED_PROVIDERS:
        raise AIError('AI_PROVIDER_NOT_ALLOWED', 503)
    slot: dict[str, Any] = {"response": None}
    started = time.perf_counter()
    outcome = "ok"
    failure = None
    try:
        from app.services.resource_capacity import provider_slot
        with provider_slot():
            yield slot
    except Exception as exc:
        outcome = type(exc).__name__
        failure = exc
        raise
    finally:
        capture = response_capture.get()
        if capture is not None:
            response = slot.get("response")
            capture.append({"model": model, "usage": normalized_usage(response),
                            "request_id": getattr(response, "id", None) or getattr(response, "response_id", None)})
        else:
            # RAG remains its existing vector interface; account for its SDK
            # calls in the same request without wrapping vectors as text.
            from app.services.ai.gateway import AIResponse, TokenUsage, usage_sink
            from app.services.ai.errors import normalize_error
            sink = usage_sink.get()
            if sink:
                response = slot.get("response")
                sink(AIResponse(None, provider, model, TokenUsage(**normalized_usage(response)),
                                round((time.perf_counter() - started) * 1000), None),
                     normalize_error(failure) if failure else None, operation=sink.operation)
        if settings.AI_LOG_TELEMETRY:
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            details = {
                "provider": provider,
                "model": model,
                "operation": operation,
                "outcome": outcome,
                "latency_ms": elapsed_ms,
                **_usage_fields(slot.get("response")),
            }
            logger.info(
                "ai_call %s",
                " ".join(f"{key}={value}" for key, value in details.items()),
            )
