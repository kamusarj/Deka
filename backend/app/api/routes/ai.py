import asyncio
from app.services.ai.operations import run_billable

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.config import settings
from app.schemas.exam import GeminiTestRequest, GeminiTestResponse
from app.services.auth_service import require_ai_metadata_viewer, require_super_admin
from app.services.ai_provider_chain import (
    AIProviderChain,
    PROVIDER_ORDER,
    ProviderName,
    get_provider_service,
)
from app.services.gemini_service import GeminiService
from app.services.rate_limit import ai_limiter

router = APIRouter(prefix="/ai", tags=["ai"])
gemini_service = GeminiService()
_provider_mutation_lock = asyncio.Lock()

# ── Suggested models per provider ─────────────────────
SUGGESTED_MODELS: dict[str, list[str]] = {
    "openai": [
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4o",
        "gpt-4o-mini",
        "o3-mini",
    ],
    "gemini": [
        "gemini-2.0-flash",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-1.5-pro",
    ],
    "deepseek": [
        "deepseek-chat",
        "deepseek-reasoner",
    ],
}


class ActiveProviderRequest(BaseModel):
    provider: ProviderName


class SetModelRequest(BaseModel):
    provider: ProviderName
    model: str
    verify_model: str | None = None


def _get_service(provider: str):
    """Return a configured service without exposing any credential to the client."""
    if provider not in PROVIDER_ORDER:
        raise HTTPException(status_code=400, detail="Provider không thuộc chuỗi AI được phép.")
    service = get_provider_service(provider)
    return service, service.model


def _get_active_service():
    return AIProviderChain()


def _refresh_exam_services() -> None:
    """Rebuild every process-wide exam service after runtime AI changes."""
    from app.api.routes import exams as exam_routes
    from app.api.routes import mvp_flow as mvp_routes

    # Construct both first so a constructor failure cannot leave only one route
    # module refreshed.
    next_exam_service = exam_routes.ExamService()
    next_mvp_service = mvp_routes.ExamService()
    exam_routes.exam_service = next_exam_service
    mvp_routes.exam_service = next_mvp_service


def _status_payload(provider: str | None = None):
    provider = provider or "openai"
    service, model = _get_service(provider)
    verify_models = {
        "openai": settings.OPENAI_VERIFY_MODEL or settings.OPENAI_MODEL,
        "gemini": settings.GEMINI_VERIFY_MODEL or settings.GEMINI_MODEL,
        "deepseek": settings.DEEPSEEK_VERIFY_MODEL or settings.DEEPSEEK_MODEL,
    }
    priority = PROVIDER_ORDER.index(provider) + 1
    return {
        "provider": provider,
        "model": model,
        "verify_model": verify_models[provider],
        "configured": service.available(),
        "key_exposed": False,
        "priority": priority,
        "role": "primary" if priority == 1 else "fallback",
    }


@router.post("/test-llm", response_model=GeminiTestResponse)
async def test_llm(
    request: GeminiTestRequest,
    admin=Depends(require_super_admin),
):
    """Test the configured LLM provider."""
    ai_limiter.check(
        f"{admin.id}:test-llm",
        limit=settings.AI_RATE_LIMIT_REQUESTS,
        window_seconds=settings.AI_RATE_LIMIT_WINDOW_SECONDS,
    )
    service = _get_active_service()
    result = await run_billable(admin, lambda: asyncio.wait_for(
        asyncio.to_thread(service.generate_text_result, request.prompt),
        timeout=settings.AI_FAILOVER_TIMEOUT_SECONDS,
    ), "provider_test")
    return GeminiTestResponse(
        provider=result.provider,
        model=result.model,
        text=result.value,
    )


@router.get("/status")
async def llm_status(_viewer=Depends(require_ai_metadata_viewer)):
    """Expose safe provider metadata for the teacher workspace; never expose keys."""
    return _status_payload()


@router.get("/providers")
async def list_providers(_viewer=Depends(require_ai_metadata_viewer)):
    """List only provider metadata; credentials remain exclusively on the server."""
    return {
        "active_provider": "openai",
        "providers": [_status_payload(name) for name in PROVIDER_ORDER],
        "configuration_source": "environment" if settings.ENV.lower() not in {'dev', 'development', 'test', 'testing'} else "process",
        "effective_config": {
            "primary_only_model": settings.OPENAI_PRIMARY_ONLY_MODEL,
            "review_mode": settings.AI_INTERACTIVE_REVIEW_MODE,
            "embedding_model": settings.RAG_EMBEDDING_MODEL,
            "default_provider_override": settings.AI_DEFAULT_PROVIDER,
            "tier_overrides": {"fast": settings.AI_MODEL_FAST, "balanced": settings.AI_MODEL_BALANCED, "premium": settings.AI_MODEL_PREMIUM},
        },
    }


@router.post("/active")
async def set_active_provider(
    request: ActiveProviderRequest,
    admin=Depends(require_super_admin),
):
    """Compatibility endpoint; the provider order is fixed and cannot be changed."""
    ai_limiter.check(
        f"{admin.id}:provider-mutation",
        limit=settings.AI_RATE_LIMIT_REQUESTS,
        window_seconds=settings.AI_RATE_LIMIT_WINDOW_SECONDS,
    )
    if request.provider != "openai":
        raise HTTPException(
            status_code=409,
            detail=(
                "Thứ tự provider được cố định: OpenAI chính, Gemini dự phòng 1, "
                "DeepSeek dự phòng 2."
            ),
        )
    return _status_payload("openai")


@router.post("/test-gemini", response_model=GeminiTestResponse)
async def test_gemini(
    request: GeminiTestRequest,
    admin=Depends(require_super_admin),
):
    """Kiểm tra kết nối Gemini (giữ lại để backward-compatible)."""
    ai_limiter.check(
        f"{admin.id}:test-gemini",
        limit=settings.AI_RATE_LIMIT_REQUESTS,
        window_seconds=settings.AI_RATE_LIMIT_WINDOW_SECONDS,
    )
    text = await run_billable(admin, lambda: asyncio.wait_for(
        asyncio.to_thread(gemini_service.generate_text, request.prompt),
        timeout=settings.AI_REQUEST_TIMEOUT_SECONDS,
    ), "provider_test")
    return GeminiTestResponse(model=settings.GEMINI_MODEL, text=text)


@router.get("/models")
async def list_models(_viewer=Depends(require_ai_metadata_viewer)):
    """Trả về danh sách model gợi ý cho mỗi provider."""
    return {
        provider: {
            "suggested": models,
            "current": _get_current_model(provider),
            "current_verify": _get_current_verify_model(provider),
        }
        for provider, models in SUGGESTED_MODELS.items()
    }


@router.post("/model")
async def set_model(
    request: SetModelRequest,
    admin=Depends(require_super_admin),
):
    """Đổi model của provider tại runtime (không cần restart)."""
    ai_limiter.check(
        f"{admin.id}:model-mutation",
        limit=settings.AI_RATE_LIMIT_REQUESTS,
        window_seconds=settings.AI_RATE_LIMIT_WINDOW_SECONDS,
    )
    if settings.ENV.lower() not in {'dev', 'development', 'test', 'testing'}:
        raise HTTPException(409, 'Model do environment quản lý. Cập nhật cấu hình và khởi động lại để áp dụng.')
    async with _provider_mutation_lock:
        provider = request.provider
        model = request.model.strip()
        if not model:
            raise HTTPException(status_code=400, detail="Tên model không được trống")

        # Update settings at runtime
        model_attr = {
            "openai": "OPENAI_MODEL",
            "gemini": "GEMINI_MODEL",
            "deepseek": "DEEPSEEK_MODEL",
        }[provider]

        verify_attr = {
            "openai": "OPENAI_VERIFY_MODEL",
            "gemini": "GEMINI_VERIFY_MODEL",
            "deepseek": "DEEPSEEK_VERIFY_MODEL",
        }[provider]

        previous_model = getattr(settings, model_attr)
        previous_verify_model = getattr(settings, verify_attr)
        setattr(settings, model_attr, model)
        if request.verify_model is not None:
            setattr(settings, verify_attr, request.verify_model.strip())

        try:
            # Refresh all route services so agents pick up the new model.
            _refresh_exam_services()
        except Exception:
            setattr(settings, model_attr, previous_model)
            setattr(settings, verify_attr, previous_verify_model)
            raise

        return {
            "provider": provider,
            "model": model,
            "verify_model": getattr(settings, verify_attr) or model,
            "message": f"Đã đổi model {provider} → {model}",
        }


def _get_current_model(provider: str) -> str:
    return {
        "openai": settings.OPENAI_MODEL,
        "gemini": settings.GEMINI_MODEL,
        "deepseek": settings.DEEPSEEK_MODEL,
    }.get(provider, "")


def _get_current_verify_model(provider: str) -> str:
    current = _get_current_model(provider)
    verify = {
        "openai": settings.OPENAI_VERIFY_MODEL,
        "gemini": settings.GEMINI_VERIFY_MODEL,
        "deepseek": settings.DEEPSEEK_VERIFY_MODEL,
    }.get(provider, "")
    return verify or current
