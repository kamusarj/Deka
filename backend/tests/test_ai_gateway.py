from types import SimpleNamespace as NS
import pytest
from fastapi import HTTPException
from app.core.config import settings
from app.services import ai_runtime
from app.services.ai.errors import AIError
from app.services.ai.gateway import AIGateway
from app.services.ai.registry import ModelRouter

class Transport:
    model = 'test-model'
    verify_model = 'test-review'
    def generate_text(self, prompt):
        with ai_runtime.track_call('openai', self.model, 'test') as slot:
            slot['response'] = NS(id='upstream-id', usage=NS(input_tokens=100,
                output_tokens=20, input_tokens_details=NS(cached_tokens=40)))
        return 'generated'

@pytest.mark.parametrize('provider', ['openai', 'gemini', 'deepseek'])
def test_adapter_normalizes_and_dispatches(provider):
    response = AIGateway().generate(prompt='private', provider=provider, service=Transport())
    assert (response.provider, response.model, response.content) == (provider, 'test-model', 'generated')
    assert response.usage.input_tokens == 100
    assert response.usage.cached_tokens == 40
    assert response.request_id == 'upstream-id'
    assert response.latency_ms >= 0

@pytest.mark.parametrize('error,code', [(TimeoutError('secret'), 'AI_TIMEOUT'),
    (HTTPException(429, 'secret'), 'AI_RATE_LIMITED'),
    (HTTPException(401, 'secret'), 'AI_AUTH_ERROR'),
    (ValueError('secret'), 'AI_INVALID_RESPONSE'),
    (RuntimeError('secret'), 'AI_PROVIDER_ERROR')])
def test_errors_are_sanitized(error, code):
    class Broken(Transport):
        def generate_text(self, prompt):
            raise error
    with pytest.raises(AIError) as caught:
        AIGateway().generate(prompt='private', provider='gemini', service=Broken())
    assert caught.value.code == code
    assert 'secret' not in str(caught.value.detail)

@pytest.mark.parametrize('quality', ['fast', 'balanced', 'premium'])
def test_router_tiers(monkeypatch, quality):
    monkeypatch.setattr(settings, f'AI_MODEL_{quality.upper()}', f'deepseek:{quality}-configured')
    route = ModelRouter().route(quality=quality, user_plan='FREE')
    assert (route.provider, route.model) == ('deepseek', f'{quality}-configured')

def test_missing_usage_is_unknown():
    assert ai_runtime.normalized_usage(NS()) == dict(input_tokens=None, output_tokens=None, cached_tokens=None)
    usage = NS(prompt_token_count=10, candidates_token_count=3, thoughts_token_count=7,
               cached_content_token_count=2)
    assert ai_runtime.normalized_usage(NS(usage_metadata=usage)) == dict(input_tokens=10, output_tokens=10, cached_tokens=2)

def test_gateway_router_selects_configured_provider(monkeypatch):
    import app.services.ai.gateway as module
    monkeypatch.setattr(settings, 'AI_MODEL_BALANCED', 'gemini:test-model')
    calls = []
    def factory(provider, model):
        calls.append((provider, model))
        return Transport()
    monkeypatch.setattr(module, 'configured_service', factory)
    assert AIGateway().generate(prompt='private').provider == 'gemini'
    assert calls == [('gemini', 'test-model')]

@pytest.mark.parametrize('task,category', [('question_regeneration','fast'), ('exam_generation','balanced'), ('exam_review','premium')])
def test_task_routes(task, category):
    assert ModelRouter().route(task=task).category == category


def test_chain_override_keeps_no_fallback_policy(monkeypatch):
    import app.services.ai_provider_chain as module
    from tests.test_ai_provider_chain import FakeProvider
    monkeypatch.setattr(settings, 'AI_MODEL_BALANCED', 'deepseek:configured-model')
    calls = []
    def factory(provider, model):
        calls.append((provider, model))
        return FakeProvider(model, text='routed')
    monkeypatch.setattr(module, 'configured_service', factory)
    primary = FakeProvider('old-primary')
    token = module.set_provider_fallback_allowed(False)
    try:
        result = module.AIProviderChain([('openai', primary)]).generate_text_result('private')
    finally:
        module.reset_provider_fallback_allowed(token)
    assert (result.provider, result.model, result.value) == ('deepseek', 'configured-model', 'routed')
    assert calls == [('deepseek', 'configured-model')]
    assert primary.calls == []
