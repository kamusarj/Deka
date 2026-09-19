from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.schemas.ai_outputs import SolveVerificationOutput
from app.services import ai_runtime
from app.services.openai_service import OpenAIService


def test_openai_placeholder_key_is_not_treated_as_configured(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", ''.join(['sk-x', 'xxxx', 'xxxx', 'xxxx', 'xxxx', 'xxx']))
    service = OpenAIService(model="gpt-test")

    assert service.available() is False
    with pytest.raises(HTTPException) as exc_info:
        service.generate_text("Chào")

    assert exc_info.value.status_code == 400
    assert "giá trị mẫu" in exc_info.value.detail


def test_openai_service_uses_official_responses_api(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-openai-key")
    service = OpenAIService(model="gpt-test")
    client = MagicMock()
    client.responses.create.return_value = MagicMock(output_text="xin chào", usage=None)

    with patch("app.services.openai_service.OpenAI", return_value=client) as factory:
        assert service.generate_text("Chào") == "xin chào"

    kwargs = factory.call_args.kwargs
    assert kwargs["api_key"] == "test-openai-key"
    assert "base_url" not in kwargs
    assert isinstance(kwargs["timeout"], httpx.Timeout)
    assert kwargs["timeout"].connect == ai_runtime.connect_timeout()
    assert kwargs["max_retries"] == settings.AI_MAX_RETRIES
    client.responses.create.assert_called_once_with(model="gpt-test", input="Chào", store=False)


def test_openai_text_applies_cost_controls(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-openai-key")
    service = OpenAIService(
        model="gpt-5.6-luna",
        reasoning_effort="low",
        verbosity="low",
    )
    client = MagicMock()
    client.responses.create.return_value = MagicMock(output_text="xin chào", usage=None)

    with patch("app.services.openai_service.OpenAI", return_value=client):
        assert service.generate_text("Chào") == "xin chào"

    client.responses.create.assert_called_once_with(
        model="gpt-5.6-luna",
        input="Chào",
        store=False,
        reasoning={"effort": "low"},
        text={"verbosity": "low"},
    )


def test_openai_verification_uses_dedicated_model_and_decodes_json(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-openai-key")
    service = OpenAIService(model="generation-model", verify_model="verification-model")
    client = MagicMock()
    client.responses.create.return_value = MagicMock(
        output_text='{"is_valid": true}',
        usage=None,
    )

    with patch("app.services.openai_service.OpenAI", return_value=client):
        assert service.generate_verification_json("Kiểm tra") == {"is_valid": True}

    assert client.responses.create.call_args.kwargs["model"] == "verification-model"


def test_openai_structured_output_uses_responses_parse(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-openai-key")
    service = OpenAIService(model="generation-model", verify_model="verification-model")
    parsed = SolveVerificationOutput(
        your_answer="C",
        statement_answers=[],
        multiple_correct=False,
        confidence=0.95,
        reasoning="Tim người có bốn ngăn.",
        detected_issues=[],
    )
    client = MagicMock()
    client.responses.parse.return_value = MagicMock(output_parsed=parsed, usage=None)

    with patch("app.services.openai_service.OpenAI", return_value=client):
        result = service.generate_verification_json(
            "Kiểm tra",
            response_model=SolveVerificationOutput,
        )

    assert result["your_answer"] == "C"
    client.responses.parse.assert_called_once_with(
        model="verification-model",
        input="Kiểm tra",
        store=False,
        text_format=SolveVerificationOutput,
    )
    client.responses.create.assert_not_called()


def test_openai_structured_output_applies_cost_controls(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-openai-key")
    service = OpenAIService(
        model="gpt-5.6-luna",
        reasoning_effort="low",
        verbosity="low",
    )
    parsed = SolveVerificationOutput(
        your_answer="C",
        statement_answers=[],
        multiple_correct=False,
        confidence=0.95,
        reasoning="Tim người có bốn ngăn.",
        detected_issues=[],
    )
    client = MagicMock()
    client.responses.parse.return_value = MagicMock(output_parsed=parsed, usage=None)

    with patch("app.services.openai_service.OpenAI", return_value=client):
        service.generate_json("Kiểm tra", response_model=SolveVerificationOutput)

    client.responses.parse.assert_called_once_with(
        model="gpt-5.6-luna",
        input="Kiểm tra",
        store=False,
        text_format=SolveVerificationOutput,
        reasoning={"effort": "low"},
        text={"verbosity": "low"},
    )


def test_openai_structured_output_rejects_missing_parsed_payload(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-openai-key")
    service = OpenAIService(model="generation-model")
    client = MagicMock()
    client.responses.parse.return_value = MagicMock(output_parsed=None, usage=None)

    with patch("app.services.openai_service.OpenAI", return_value=client):
        with pytest.raises(HTTPException) as exc_info:
            service.generate_json(
                "Tạo JSON",
                response_model=SolveVerificationOutput,
            )

    assert exc_info.value.status_code == 502
    assert "schema-conformant" in exc_info.value.detail
