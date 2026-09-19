"""Regression proof for runtime boundaries reported by the reliability scan."""

import asyncio
import logging
import time
from types import SimpleNamespace

import pytest

from app.api.routes import ai as ai_routes
from app.api.routes import rag as rag_routes
from app.schemas.rag import RagQueryRequest
from app.services.exam_service import ExamService


@pytest.mark.asyncio
async def test_rag_query_route_does_not_block_event_loop(monkeypatch, auth_context):
    callback_ran = False

    def mark_callback():
        nonlocal callback_ran
        callback_ran = True

    def blocking_query(**_kwargs):
        time.sleep(0.05)
        return [], "bm25"

    monkeypatch.setattr(rag_routes.kb_service, "query_with_backend", blocking_query)
    asyncio.get_running_loop().call_later(0.01, mark_callback)

    response = await rag_routes.query_index(
        RagQueryRequest(query="phản ứng hóa học"),
        user=auth_context["user"],
    )

    assert callback_ran is True
    assert response.count == 0


@pytest.mark.asyncio
async def test_provider_chain_cannot_be_reordered():
    with pytest.raises(Exception) as exc_info:
        await ai_routes.set_active_provider(
            ai_routes.ActiveProviderRequest(provider="gemini"),
            admin=SimpleNamespace(id=1, role="super_admin"),
        )

    assert getattr(exc_info.value, "status_code", None) == 409
    assert "OpenAI chính" in getattr(exc_info.value, "detail", "")


@pytest.mark.asyncio
async def test_openai_compatibility_selection_is_a_noop(monkeypatch):
    class ConfiguredService:
        model = "gpt-test"
        verify_model = "gpt-test"

        @staticmethod
        def available():
            return True

    monkeypatch.setattr(ai_routes, "_get_service", lambda _provider: (ConfiguredService(), "gpt-test"))

    result = await ai_routes.set_active_provider(
        ai_routes.ActiveProviderRequest(provider="openai"),
        admin=SimpleNamespace(id=1, role="super_admin"),
    )

    assert result["provider"] == "openai"
    assert result["priority"] == 1
    assert result["role"] == "primary"


@pytest.mark.asyncio
async def test_sse_logs_exception_without_exposing_details(caplog):
    service = ExamService()

    async def fail_resource_collection(**_kwargs):
        raise RuntimeError("provider-secret-sentinel")

    service.resource_agent.run = fail_resource_collection
    request = SimpleNamespace(
        grade=8,
        subject="Khoa học tự nhiên",
        exam_type="Giữa học kì I",
    )

    with caplog.at_level(logging.ERROR, logger="app.exam"):
        events = [event async for event in service.generate_full_exam_stream(request)]

    payload = "".join(events)
    assert '"stage": "error"' in payload
    assert "Không thể tạo đề kiểm tra" in payload
    assert "provider-secret-sentinel" not in payload
    assert "provider-secret-sentinel" not in caplog.text
    assert "Full-exam SSE generation failed" in caplog.text
