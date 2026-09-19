"""Configured model identities and task routing, separate from exam agents."""
from dataclasses import dataclass
from app.core.config import settings


@dataclass(frozen=True)
class ModelRoute:
    provider: str
    model: str
    category: str


class ModelRegistry:
    def resolve(self, category: str, *, primary_only: bool = False) -> ModelRoute:
        if category == 'embedding':
            return ModelRoute('gemini', settings.RAG_EMBEDDING_MODEL, category)
        if category not in {'fast', 'balanced', 'premium'}:
            raise ValueError('Unknown model quality')
        provider = settings.AI_DEFAULT_PROVIDER or 'openai'
        model = getattr(settings, f'AI_MODEL_{category.upper()}')
        if ':' in model:
            provider, model = model.split(':', 1)
        if provider not in {'openai', 'gemini', 'deepseek'}:
            raise ValueError('Unknown configured provider')
        if not model:
            prefix = provider.upper()
            model = getattr(settings, f'{prefix}_MODEL')
            if category == 'premium':
                model = getattr(settings, f'{prefix}_VERIFY_MODEL') or model
            elif primary_only and provider == 'openai':
                model = settings.OPENAI_PRIMARY_ONLY_MODEL
        return ModelRoute(provider, model, category)

    @staticmethod
    def has_override(category: str = 'balanced') -> bool:
        return bool(settings.AI_DEFAULT_PROVIDER or getattr(settings, f'AI_MODEL_{category.upper()}'))


class ModelRouter:
    def __init__(self, registry=None):
        self.registry = registry or ModelRegistry()

    @staticmethod
    def quality_for(task: str) -> str:
        if task == 'exam_review':
            return 'premium'
        if task in {'rag_query', 'answer_generation', 'question_regeneration'}:
            return 'fast'
        return 'balanced'

    def route(self, *, task='exam_generation', quality=None, user_plan='FREE', primary_only=False):
        # Plans currently differ only in allowance. No invented premium paywall.
        return self.registry.resolve(quality or self.quality_for(task), primary_only=primary_only)

    has_override = staticmethod(ModelRegistry.has_override)
