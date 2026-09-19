"""Normalized AI boundary over existing, tested SDK transports."""
from contextvars import ContextVar
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

from app.services import ai_runtime
from app.services.ai.errors import normalize_error
from app.services.ai.registry import ModelRouter

# Request-owned callback copied by asyncio.to_thread, never a global user/session.
usage_sink: ContextVar[Any] = ContextVar('ai_usage_sink', default=None)


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_tokens: int | None = None


@dataclass(frozen=True)
class AIResponse:
    content: Any
    provider: str
    model: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    latency_ms: int = 0
    request_id: str | None = None

    @property
    def value(self):  # Existing agents/ProviderCallResult compatibility.
        return self.content


class ProviderAdapter:
    provider: str

    def __init__(self, service, model=None):
        self.service = service
        self.model = model

    def generate(self, prompt, *, method='generate_text', response_model=None):
        from app.services.ai.lifecycle import checkpoint
        checkpoint()
        model = self.model or (self.service.verify_model if method == 'generate_verification_json' else self.service.model)
        captured = []
        token = ai_runtime.response_capture.set(captured)
        start = perf_counter()
        error = None
        content = None
        try:
            invoke = getattr(self.service, method)
            content = invoke(prompt, response_model=response_model) if response_model is not None else invoke(prompt)
            if content is None or (isinstance(content, str) and not content.strip()):
                raise ValueError('Empty AI response')
        except Exception as exc:
            error = normalize_error(exc)
        finally:
            ai_runtime.response_capture.reset(token)
        raw = captured[-1] if captured else {}
        upstream_id = raw.get('request_id')
        result = AIResponse(
            content=content, provider=self.provider, model=raw.get('model', model),
            usage=TokenUsage(**raw.get('usage', {})),
            latency_ms=round((perf_counter() - start) * 1000),
            request_id=upstream_id if isinstance(upstream_id, str) and upstream_id else None,
        )
        sink = usage_sink.get()
        if sink:
            sink(result, error)
        if error:
            raise error from None
        return result


class OpenAIProvider(ProviderAdapter):
    provider = 'openai'


class GeminiProvider(ProviderAdapter):
    provider = 'gemini'


class DeepSeekProvider(ProviderAdapter):
    provider = 'deepseek'


ADAPTERS = {'openai': OpenAIProvider, 'gemini': GeminiProvider, 'deepseek': DeepSeekProvider}


class AIGateway:
    def __init__(self, router=None):
        self.router = router or ModelRouter()

    def generate(self, *, prompt, task='exam_generation', quality=None, user_plan='FREE',
                 method='generate_text', response_model=None, provider=None, service=None, model=None):
        if service is None:
            route = self.router.route(task=task, quality=quality, user_plan=user_plan)
            provider = route.provider
            service = configured_service(provider, route.model)
        return ADAPTERS[provider](service, model).generate(prompt, method=method, response_model=response_model)


def configured_service(provider, model):
    # Imports stay lazy to avoid coupling agent startup to SDK client creation.
    from app.core.config import settings
    from app.services.openai_service import OpenAIService
    from app.services.gemini_service import GeminiService
    from app.services.openai_compatible_service import OpenAICompatibleService
    if provider == 'openai':
        return OpenAIService(model=model, verify_model=model)
    if provider == 'gemini':
        service = GeminiService(model=model)
        service.verify_model = model
        return service
    return OpenAICompatibleService(api_key=settings.DEEPSEEK_API_KEY, model=model,
                                   verify_model=model, provider='deepseek', base_url=settings.DEEPSEEK_BASE_URL)
