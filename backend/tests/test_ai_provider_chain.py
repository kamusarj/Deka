import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.services.ai_provider_chain import (
    AIProviderChain,
    PROVIDER_ORDER,
    provider_operation_timeout_seconds,
    reset_provider_fallback_allowed,
    set_provider_fallback_allowed,
)
from app.services.openai_service import OpenAIService


class FakeProvider:
    def __init__(self, model, *, configured=True, text="ok", error=None, json_value=None):
        self.model = model
        self.verify_model = f"{model}-verify"
        self.configured = configured
        self.text = text
        self.error = error
        self.json_value = json_value if json_value is not None else {"ok": True}
        self.calls = []
        self.response_models = []

    def available(self):
        return self.configured

    def _call(self, operation):
        self.calls.append(operation)
        if self.error:
            raise self.error

    def generate_text(self, _prompt):
        self._call("text")
        return self.text

    def generate_json(self, _prompt, response_model=None):
        self.response_models.append(response_model)
        self._call("json")
        return self.json_value

    def generate_verification_json(self, _prompt, response_model=None):
        self.response_models.append(response_model)
        self._call("verify")
        return self.json_value


def test_provider_order_is_exact_and_immutable():
    assert PROVIDER_ORDER == ("openai", "gemini", "deepseek")


def test_primary_success_stops_before_fallbacks():
    openai = FakeProvider("gpt", text="primary")
    gemini = FakeProvider("gemini")
    deepseek = FakeProvider("deepseek")
    chain = AIProviderChain([
        ("openai", openai),
        ("gemini", gemini),
        ("deepseek", deepseek),
    ])

    result = chain.generate_text_result("prompt")

    assert (result.provider, result.model, result.value) == ("openai", "gpt", "primary")
    assert openai.calls == ["text"]
    assert gemini.calls == []
    assert deepseek.calls == []


def test_unconfigured_primary_and_failed_gemini_fall_back_to_deepseek(caplog):
    openai = FakeProvider("gpt", configured=False)
    gemini = FakeProvider("gemini", error=TimeoutError("secret provider body"))
    deepseek = FakeProvider("deepseek", text="backup")
    chain = AIProviderChain([
        ("openai", openai),
        ("gemini", gemini),
        ("deepseek", deepseek),
    ])

    result = chain.generate_text_result("private prompt")

    assert result.provider == "deepseek"
    assert result.value == "backup"
    assert openai.calls == []
    assert gemini.calls == ["text"]
    assert deepseek.calls == ["text"]
    assert "failed_provider=gemini" in caplog.text
    assert "next_provider=deepseek" in caplog.text
    assert "private prompt" not in caplog.text
    assert "secret provider body" not in caplog.text


def test_json_parse_failure_advances_to_next_provider():
    openai = FakeProvider("gpt", error=ValueError("invalid json"))
    gemini = FakeProvider("gemini", json_value={"provider": "gemini"})
    deepseek = FakeProvider("deepseek")
    chain = AIProviderChain([
        ("openai", openai),
        ("gemini", gemini),
        ("deepseek", deepseek),
    ])

    assert chain.generate_json("prompt") == {"provider": "gemini"}
    assert openai.calls == ["json"]
    assert gemini.calls == ["json"]
    assert deepseek.calls == []


def test_structured_contract_is_forwarded_across_failover():
    class OutputContract:
        pass

    openai = FakeProvider("gpt", error=ValueError("schema refusal"))
    gemini = FakeProvider("gemini", json_value={"provider": "gemini"})
    chain = AIProviderChain([
        ("openai", openai),
        ("gemini", gemini),
    ])

    assert chain.generate_json("prompt", response_model=OutputContract) == {
        "provider": "gemini"
    }
    assert openai.response_models == [OutputContract]
    assert gemini.response_models == [OutputContract]


def test_all_provider_failures_return_sanitized_gateway_error():
    services = [
        (name, FakeProvider(name, error=RuntimeError(f"{name}-secret")))
        for name in PROVIDER_ORDER
    ]
    chain = AIProviderChain(services)

    with pytest.raises(HTTPException) as exc_info:
        chain.generate_text("prompt")

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "OpenAI, Gemini và DeepSeek đều không thể xử lý yêu cầu."
    assert "secret" not in exc_info.value.detail


def test_no_configured_provider_reports_required_keys():
    services = [
        (name, FakeProvider(name, configured=False)) for name in PROVIDER_ORDER
    ]
    chain = AIProviderChain(services)

    with pytest.raises(HTTPException) as exc_info:
        chain.generate_text("prompt")

    assert exc_info.value.status_code == 400
    assert "OpenAI, Gemini hoặc DeepSeek" in exc_info.value.detail


class RateLimitError(Exception):
    pass


class RateLimitedThenSuccessfulProvider(FakeProvider):
    def __init__(self, model, failures):
        super().__init__(model)
        self.failures = failures

    def _call(self, operation):
        self.calls.append(operation)
        if self.failures:
            self.failures -= 1
            raise RateLimitError("private rate-limit detail")


def test_primary_only_retries_openai_without_calling_fallbacks(monkeypatch, caplog):
    monkeypatch.setattr(settings, "AI_PRIMARY_RATE_LIMIT_RETRIES", 2)
    monkeypatch.setattr(settings, "AI_PRIMARY_RETRY_BASE_SECONDS", 0)
    openai = RateLimitedThenSuccessfulProvider("gpt", failures=1)
    gemini = FakeProvider("gemini")
    deepseek = FakeProvider("deepseek")
    chain = AIProviderChain([
        ("openai", openai),
        ("gemini", gemini),
        ("deepseek", deepseek),
    ])

    token = set_provider_fallback_allowed(False)
    try:
        result = chain.generate_text_result("private prompt")
    finally:
        reset_provider_fallback_allowed(token)

    assert result.provider == "openai"
    assert openai.calls == ["text", "text"]
    assert gemini.calls == []
    assert deepseek.calls == []
    assert "ai_primary_retry" in caplog.text
    assert "private prompt" not in caplog.text
    assert "private rate-limit detail" not in caplog.text


def test_primary_only_exhaustion_fails_closed_without_fallback(monkeypatch):
    monkeypatch.setattr(settings, "AI_PRIMARY_RATE_LIMIT_RETRIES", 1)
    monkeypatch.setattr(settings, "AI_PRIMARY_RETRY_BASE_SECONDS", 0)
    openai = RateLimitedThenSuccessfulProvider("gpt", failures=2)
    gemini = FakeProvider("gemini")
    deepseek = FakeProvider("deepseek")
    chain = AIProviderChain([
        ("openai", openai),
        ("gemini", gemini),
        ("deepseek", deepseek),
    ])

    token = set_provider_fallback_allowed(False)
    try:
        with pytest.raises(HTTPException) as exc_info:
            chain.generate_text("private prompt")
    finally:
        reset_provider_fallback_allowed(token)

    assert exc_info.value.status_code == 503
    assert "không chuyển sang provider khác" in exc_info.value.detail
    assert openai.calls == ["text", "text"]
    assert gemini.calls == []
    assert deepseek.calls == []


def test_primary_only_retries_adapter_wrapped_http_429(monkeypatch):
    monkeypatch.setattr(settings, "AI_PRIMARY_RATE_LIMIT_RETRIES", 1)
    monkeypatch.setattr(settings, "AI_PRIMARY_RETRY_BASE_SECONDS", 0)

    class WrappedRateLimitProvider(FakeProvider):
        def _call(self, operation):
            self.calls.append(operation)
            if len(self.calls) == 1:
                raise HTTPException(status_code=429, detail="private rate-limit detail")

    openai = WrappedRateLimitProvider("gpt")
    gemini = FakeProvider("gemini")
    chain = AIProviderChain([("openai", openai), ("gemini", gemini)])

    token = set_provider_fallback_allowed(False)
    try:
        result = chain.generate_text_result("prompt")
    finally:
        reset_provider_fallback_allowed(token)

    assert result.provider == "openai"
    assert openai.calls == ["text", "text"]
    assert gemini.calls == []


def test_primary_only_retries_adapter_wrapped_timeout(monkeypatch):
    monkeypatch.setattr(settings, "AI_PRIMARY_RATE_LIMIT_RETRIES", 1)
    monkeypatch.setattr(settings, "AI_PRIMARY_TIMEOUT_RETRY_BASE_SECONDS", 0)

    class APITimeoutError(Exception):
        pass

    class WrappedTimeoutProvider(FakeProvider):
        def _call(self, operation):
            self.calls.append(operation)
            if len(self.calls) == 1:
                try:
                    raise APITimeoutError("private timeout detail")
                except APITimeoutError as cause:
                    raise HTTPException(status_code=502, detail="OpenAI API error") from cause

    openai = WrappedTimeoutProvider("gpt")
    deepseek = FakeProvider("deepseek")
    chain = AIProviderChain([("openai", openai), ("deepseek", deepseek)])

    token = set_provider_fallback_allowed(False)
    try:
        result = chain.generate_text_result("prompt")
    finally:
        reset_provider_fallback_allowed(token)

    assert result.provider == "openai"
    assert openai.calls == ["text", "text"]
    assert deepseek.calls == []


def test_primary_only_uses_dedicated_openai_model(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "OPENAI_PRIMARY_ONLY_MODEL", "gpt-primary-mini")
    monkeypatch.setattr(settings, "OPENAI_PRIMARY_ONLY_REASONING_EFFORT", "low")
    monkeypatch.setattr(settings, "OPENAI_PRIMARY_ONLY_VERBOSITY", "low")
    monkeypatch.setattr(
        OpenAIService,
        "generate_text",
        lambda service, _prompt: (
            service.model,
            service.reasoning_effort,
            service.verbosity,
        ),
    )
    openai = OpenAIService(model="gpt-default")
    gemini = FakeProvider("gemini")
    chain = AIProviderChain([("openai", openai), ("gemini", gemini)])

    token = set_provider_fallback_allowed(False)
    try:
        result = chain.generate_text_result("prompt")
    finally:
        reset_provider_fallback_allowed(token)

    assert result.provider == "openai"
    assert result.model == "gpt-primary-mini"
    assert result.value == ("gpt-primary-mini", "low", "low")
    assert gemini.calls == []


def test_primary_only_uses_extended_operation_timeout(monkeypatch):
    monkeypatch.setattr(settings, "AI_FAILOVER_TIMEOUT_SECONDS", 90)
    monkeypatch.setattr(settings, "AI_PRIMARY_ONLY_TIMEOUT_SECONDS", 180)
    assert provider_operation_timeout_seconds() == 90

    token = set_provider_fallback_allowed(False)
    try:
        assert provider_operation_timeout_seconds() == 180
    finally:
        reset_provider_fallback_allowed(token)
