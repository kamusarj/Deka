"""Fixed OpenAI -> Gemini -> DeepSeek provider failover policy."""

from __future__ import annotations

import logging
import time
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from fastapi import HTTPException
from pydantic import BaseModel

from app.core.config import settings
from app.services.gemini_service import GeminiService
from app.services.openai_compatible_service import OpenAICompatibleService
from app.services.openai_service import OpenAIService
from app.services.ai.gateway import AIGateway, configured_service, usage_sink
from app.services.ai.registry import ModelRouter
from app.services.ai.errors import AccountingError, AIError

ProviderName = Literal["openai", "gemini", "deepseek"]
PROVIDER_ORDER: tuple[ProviderName, ...] = ("openai", "gemini", "deepseek")

logger = logging.getLogger("app.ai")
_provider_fallback_allowed: ContextVar[bool] = ContextVar(
    "provider_fallback_allowed",
    default=True,
)


def set_provider_fallback_allowed(allowed: bool) -> Token:
    return _provider_fallback_allowed.set(bool(allowed))


def reset_provider_fallback_allowed(token: Token) -> None:
    _provider_fallback_allowed.reset(token)


def provider_fallback_allowed() -> bool:
    """Expose the request-scoped generation policy to verification orchestration."""
    return _provider_fallback_allowed.get()


def provider_operation_timeout_seconds() -> int:
    return (
        settings.AI_FAILOVER_TIMEOUT_SECONDS
        if _provider_fallback_allowed.get()
        else settings.AI_PRIMARY_ONLY_TIMEOUT_SECONDS
    )


def _is_rate_limit_error(exc: Exception) -> bool:
    cause = getattr(exc, "__cause__", None)
    return (
        getattr(exc, "status_code", None) == 429
        or type(exc).__name__ == "RateLimitError"
        or type(cause).__name__ == "RateLimitError"
    )


def _is_retryable_primary_error(exc: Exception) -> bool:
    cause = getattr(exc, "__cause__", None)
    return (
        _is_rate_limit_error(exc)
        or getattr(exc, "status_code", None) in {408, 502, 503, 504}
        or type(exc).__name__ in {"APITimeoutError", "APIConnectionError", "TimeoutError"}
        or type(cause).__name__ in {"APITimeoutError", "APIConnectionError", "TimeoutError"}
    )


class ProviderService(Protocol):
    model: str
    verify_model: str

    def available(self) -> bool: ...
    def generate_text(self, prompt: str) -> str: ...
    def generate_json(
        self, prompt: str, response_model: type[BaseModel] | None = None
    ) -> Any: ...
    def generate_verification_json(
        self, prompt: str, response_model: type[BaseModel] | None = None
    ) -> Any: ...


@dataclass(frozen=True)
class ProviderCallResult:
    value: Any
    provider: ProviderName
    model: str


def get_provider_service(provider: ProviderName) -> ProviderService:
    if provider == "openai":
        return OpenAIService()
    if provider == "gemini":
        return GeminiService()
    if provider == "deepseek":
        return OpenAICompatibleService(
            api_key=settings.DEEPSEEK_API_KEY,
            model=settings.DEEPSEEK_MODEL,
            provider="deepseek",
            base_url=settings.DEEPSEEK_BASE_URL,
            verify_model=settings.DEEPSEEK_VERIFY_MODEL,
        )
    raise ValueError(f"Unsupported AI provider: {provider}")


class AIProviderChain:
    """Try only the approved providers, sequentially and in a fixed order."""

    provider: ProviderName = "openai"

    def __init__(
        self,
        services: list[tuple[ProviderName, ProviderService]] | None = None,
    ):
        self.services = services or [
            (provider, get_provider_service(provider)) for provider in PROVIDER_ORDER
        ]
        self.model = settings.OPENAI_MODEL
        self.verify_model = settings.OPENAI_VERIFY_MODEL or settings.OPENAI_MODEL

    def available(self) -> bool:
        return any(service.available() for _, service in self.services)

    def generate_text(self, prompt: str) -> str:
        return self.generate_text_result(prompt).value

    def generate_text_result(self, prompt: str) -> ProviderCallResult:
        return self._execute("generate_text", prompt)

    def generate_json(
        self,
        prompt: str,
        response_model: type[BaseModel] | None = None,
    ) -> Any:
        return self._execute(
            "generate_json", prompt, response_model=response_model
        ).value

    def generate_verification_json(
        self,
        prompt: str,
        response_model: type[BaseModel] | None = None,
    ) -> Any:
        return self._execute(
            "generate_verification_json", prompt, response_model=response_model
        ).value

    def _execute(
        self,
        operation: str,
        prompt: str,
        *,
        response_model: type[BaseModel] | None = None,
    ) -> ProviderCallResult:
        configured = [
            (provider, service)
            for provider, service in self.services
            if service.available()
        ]
        allow_fallback = _provider_fallback_allowed.get()
        task = getattr(usage_sink.get(), "operation", "exam_generation")
        quality = "premium" if operation == "generate_verification_json" else ModelRouter.quality_for(task)
        override = ModelRouter.has_override(quality)
        if override:
            route = ModelRouter().route(quality=quality, primary_only=not allow_fallback)
            selected = configured_service(route.provider, route.model)
            configured = [(route.provider, selected)] + (
                [(p, s) for p, s in configured if p != route.provider] if allow_fallback else []
            )
        elif not allow_fallback:
            configured = [
                (provider, service)
                for provider, service in configured
                if provider == "openai"
            ]
        if not configured:
            raise AIError(
                "AI_AUTH_ERROR",
                status_code=400,
                message=(
                    "Chưa cấu hình API key OpenAI cho chế độ không fallback."
                    if not allow_fallback
                    else "Chưa cấu hình API key cho OpenAI, Gemini hoặc DeepSeek trong backend/.env"
                ),
            )

        for index, (provider, service) in enumerate(configured):
            if (
                not allow_fallback
                and not override
                and provider == "openai"
                and isinstance(service, OpenAIService)
            ):
                service = OpenAIService(
                    model=settings.OPENAI_PRIMARY_ONLY_MODEL,
                    verify_model=settings.OPENAI_PRIMARY_ONLY_MODEL,
                    reasoning_effort=settings.OPENAI_PRIMARY_ONLY_REASONING_EFFORT,
                    verbosity=settings.OPENAI_PRIMARY_ONLY_VERBOSITY,
                )
            retry_limit = (
                settings.AI_PRIMARY_RATE_LIMIT_RETRIES
                if not allow_fallback and provider == "openai"
                else 0
            )
            for attempt in range(retry_limit + 1):
                try:
                    return AIGateway().generate(prompt=prompt, provider=provider,
                                                service=service, method=operation,
                                                response_model=response_model)
                except Exception as exc:
                    if isinstance(exc, AccountingError):
                        raise
                    retryable = (
                        not allow_fallback
                        and provider == "openai"
                        and _is_retryable_primary_error(exc)
                        and attempt < retry_limit
                    )
                    if retryable:
                        base_delay = (
                            settings.AI_PRIMARY_RETRY_BASE_SECONDS
                            if _is_rate_limit_error(exc)
                            else settings.AI_PRIMARY_TIMEOUT_RETRY_BASE_SECONDS
                        )
                        delay = base_delay * (2 ** attempt)
                        logger.warning(
                            "ai_primary_retry operation=%s attempt=%s delay_seconds=%s",
                            operation,
                            attempt + 1,
                            delay,
                        )
                        time.sleep(delay)
                        continue
                    if not allow_fallback:
                        logger.warning(
                            "ai_primary_failed operation=%s outcome=%s",
                            operation,
                            type(exc).__name__,
                        )
                        raise AIError(
                            exc.code if isinstance(exc, AIError) else "AI_PROVIDER_ERROR",
                            status_code=503,
                            message=(
                                f"{dict(openai='OpenAI', gemini='Gemini', deepseek='DeepSeek')[provider]} đang giới hạn hoặc chưa thể xử lý yêu cầu. "
                                "Hệ thống không chuyển sang provider khác. Vui lòng thử lại sau."
                            ),
                        ) from None
                    next_provider = (
                        configured[index + 1][0] if index + 1 < len(configured) else "none"
                    )
                    logger.warning(
                        "ai_provider_fallback failed_provider=%s operation=%s "
                        "outcome=%s next_provider=%s",
                        provider,
                        operation,
                        type(exc).__name__,
                        next_provider,
                    )
                    break

        raise AIError(
            "AI_PROVIDER_ERROR",
            status_code=502,
            message="OpenAI, Gemini và DeepSeek đều không thể xử lý yêu cầu.",
        )
