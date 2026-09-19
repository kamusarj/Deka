"""Transport policy and telemetry shared by every AI provider client."""

import logging
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.core.config import settings
from app.services import ai_runtime


def test_transport_phases_fit_below_the_application_ceiling(monkeypatch):
    """The SDK must give up before asyncio.wait_for cancels the task, otherwise
    the failure surfaces as a cancellation instead of a real provider error."""
    monkeypatch.setattr(settings, "AI_READ_TIMEOUT_SECONDS", 120)
    monkeypatch.setattr(settings, "AI_REQUEST_TIMEOUT_SECONDS", 30)

    assert ai_runtime.connect_timeout() + ai_runtime.read_timeout() == 29.0


def test_httpx_timeout_separates_connect_from_read(monkeypatch):
    monkeypatch.setattr(settings, "AI_CONNECT_TIMEOUT_SECONDS", 7)
    monkeypatch.setattr(settings, "AI_READ_TIMEOUT_SECONDS", 19)
    monkeypatch.setattr(settings, "AI_REQUEST_TIMEOUT_SECONDS", 30)

    timeout = ai_runtime.httpx_timeout()

    assert isinstance(timeout, httpx.Timeout)
    assert timeout.connect == 7.0
    assert timeout.read == 19.0


def test_timeout_ms_finishes_before_application_ceiling(monkeypatch):
    monkeypatch.setattr(settings, "AI_CONNECT_TIMEOUT_SECONDS", 10)
    monkeypatch.setattr(settings, "AI_READ_TIMEOUT_SECONDS", 25)
    monkeypatch.setattr(settings, "AI_REQUEST_TIMEOUT_SECONDS", 30)

    assert ai_runtime.timeout_ms() == 29_000
    assert ai_runtime.timeout_ms() < settings.AI_REQUEST_TIMEOUT_SECONDS * 1000


def test_track_call_logs_latency_and_tokens(monkeypatch, caplog):
    monkeypatch.setattr(settings, "AI_LOG_TELEMETRY", True)
    usage = MagicMock(prompt_tokens=11, completion_tokens=22, total_tokens=33)
    response = MagicMock(usage=usage)

    with caplog.at_level(logging.INFO, logger="app.ai"):
        with ai_runtime.track_call("openai", "gpt-test", "chat_completion") as call:
            call["response"] = response

    record = caplog.text
    assert "provider=openai" in record
    assert "model=gpt-test" in record
    assert "outcome=ok" in record
    assert "latency_ms=" in record
    assert "prompt_tokens=11" in record
    assert "completion_tokens=22" in record
    assert "total_tokens=33" in record


def test_track_call_reads_gemini_style_usage_metadata(monkeypatch, caplog):
    monkeypatch.setattr(settings, "AI_LOG_TELEMETRY", True)
    # google-genai names the fields differently; telemetry must still find them.
    usage = MagicMock(
        spec=["prompt_token_count", "candidates_token_count", "total_token_count"],
        prompt_token_count=5,
        candidates_token_count=6,
        total_token_count=11,
    )
    response = MagicMock(spec=["usage_metadata"], usage_metadata=usage)

    with caplog.at_level(logging.INFO, logger="app.ai"):
        with ai_runtime.track_call("gemini", "gemini-test", "generate_text") as call:
            call["response"] = response

    assert "prompt_tokens=5" in caplog.text
    assert "completion_tokens=6" in caplog.text
    assert "total_tokens=11" in caplog.text


def test_track_call_records_failure_and_reraises(monkeypatch, caplog):
    monkeypatch.setattr(settings, "AI_LOG_TELEMETRY", True)

    with caplog.at_level(logging.INFO, logger="app.ai"):
        with pytest.raises(TimeoutError):
            with ai_runtime.track_call("mistral", "mistral-test", "generate_text"):
                raise TimeoutError("provider took too long")

    assert "outcome=TimeoutError" in caplog.text


def test_telemetry_can_be_switched_off(monkeypatch, caplog):
    monkeypatch.setattr(settings, "AI_LOG_TELEMETRY", False)

    with caplog.at_level(logging.INFO, logger="app.ai"):
        with ai_runtime.track_call("openai", "gpt-test", "chat_completion"):
            pass

    assert "ai_call" not in caplog.text


def test_gemini_client_receives_transport_timeout():
    from app.services.gemini_service import GeminiService

    with patch.object(settings, "GEMINI_API_KEY", "test-key"):
        client = MagicMock()
        client.models.generate_content.return_value = MagicMock(text="xin chào", usage=None)

        with patch("app.services.gemini_service.genai.Client", return_value=client) as factory:
            assert GeminiService(model="gemini-test").generate_text("Chào") == "xin chào"

    http_options = factory.call_args.kwargs["http_options"]
    assert http_options.timeout == ai_runtime.timeout_ms()


def test_gemini_fallback_validates_the_shared_output_contract():
    from pydantic import BaseModel, ConfigDict, ValidationError

    from app.services.gemini_service import GeminiService

    class StrictPayload(BaseModel):
        model_config = ConfigDict(extra="forbid")
        is_valid: bool

    service = GeminiService(model="gemini-test")
    service.generate_text = lambda _prompt: '{"is_valid": true, "invented": 1}'

    with pytest.raises(ValidationError):
        service.generate_json("Kiểm tra", response_model=StrictPayload)


def test_mistral_client_receives_transport_timeout():
    from app.services.mistral_service import MistralService

    with patch.object(settings, "MISTRAL_API_KEY", "test-key"):
        client = MagicMock()
        client.chat.complete.return_value.choices = [
            MagicMock(message=MagicMock(content="xin chào"))
        ]

        with patch("app.services.mistral_service.Mistral", return_value=client) as factory:
            assert MistralService(model="mistral-test").generate_text("Chào") == "xin chào"

    kwargs = factory.call_args.kwargs
    assert kwargs["timeout_ms"] == ai_runtime.timeout_ms()
    assert isinstance(kwargs["client"], httpx.Client)


def test_mistral_json_uses_structured_response_mode():
    from app.services.mistral_service import MistralService

    with patch.object(settings, "MISTRAL_API_KEY", "test-key"):
        client = MagicMock()
        client.chat.complete.return_value.choices = [
            MagicMock(message=MagicMock(content='{"valid": true}'))
        ]

        with patch("app.services.mistral_service.Mistral", return_value=client):
            result = MistralService(model="mistral-test").generate_json("JSON")

    assert result == {"valid": True}
    assert client.chat.complete.call_args.kwargs["response_format"] == {
        "type": "json_object"
    }
