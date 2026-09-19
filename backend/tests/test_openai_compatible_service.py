from unittest.mock import MagicMock, patch

import httpx
import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from app.core.config import settings
from app.services import ai_runtime
from app.services.openai_compatible_service import OpenAICompatibleService


class StrictPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_valid: bool


@pytest.mark.parametrize(
    ("provider", "base_url"),
    [
        ("openai", None),
        ("openrouter", "https://openrouter.ai/api/v1"),
        ("deepseek", "https://api.deepseek.com/v1"),
        ("openai_compatible", "https://llm.example.com/v1"),
    ],
)
def test_openai_compatible_service_sends_prompt_to_configured_endpoint(provider, base_url):
    service = OpenAICompatibleService(
        api_key="test-key",
        model="test-model",
        provider=provider,
        base_url=base_url,
    )
    client = MagicMock()
    client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content="xin chào"))
    ]

    with patch("app.services.openai_compatible_service.OpenAI", return_value=client) as factory:
        assert service.generate_text("Chào") == "xin chào"

    kwargs = factory.call_args.kwargs
    assert kwargs["api_key"] == "test-key"
    assert kwargs["base_url"] == base_url
    client.chat.completions.create.assert_called_once_with(
        model="test-model",
        messages=[{"role": "user", "content": "Chào"}],
    )


def test_client_is_constructed_with_transport_timeouts():
    """The SDK must carry its own timeouts; the outer asyncio.wait_for cannot
    abort a request that already started in a worker thread."""
    service = OpenAICompatibleService(
        api_key="test-key",
        model="test-model",
        provider="openai",
    )
    client = MagicMock()
    client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content="ok"))
    ]

    with patch("app.services.openai_compatible_service.OpenAI", return_value=client) as factory:
        service.generate_text("Chào")

    kwargs = factory.call_args.kwargs
    timeout = kwargs["timeout"]
    assert isinstance(timeout, httpx.Timeout)
    assert timeout.connect == ai_runtime.connect_timeout()
    assert timeout.read == ai_runtime.read_timeout()
    assert kwargs["max_retries"] == settings.AI_MAX_RETRIES


def test_verification_uses_dedicated_model_and_json_decoding():
    service = OpenAICompatibleService(
        api_key="test-key",
        model="generation-model",
        verify_model="verification-model",
        provider="openrouter",
        base_url="https://openrouter.ai/api/v1",
    )
    client = MagicMock()
    client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content='{"is_valid": true}'))
    ]

    with patch("app.services.openai_compatible_service.OpenAI", return_value=client):
        assert service.generate_verification_json("Kiểm tra") == {"is_valid": True}

    assert client.chat.completions.create.call_args.kwargs["model"] == "verification-model"


def test_structured_verification_requests_json_object_mode():
    service = OpenAICompatibleService(
        api_key="test-key",
        model="generation-model",
        verify_model="deepseek-v4-pro",
        provider="deepseek",
        base_url="https://api.deepseek.com/v1",
    )
    client = MagicMock()
    client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content='{"is_valid": true}'))
    ]

    with patch("app.services.openai_compatible_service.OpenAI", return_value=client):
        assert service.generate_verification_json(
            "Kiểm tra", response_model=StrictPayload
        ) == {"is_valid": True}

    assert client.chat.completions.create.call_args.kwargs["response_format"] == {
        "type": "json_object"
    }


def test_deepseek_fallback_validates_the_shared_output_contract():
    service = OpenAICompatibleService(
        api_key="test-key",
        model="deepseek-test",
        provider="deepseek",
        base_url="https://api.deepseek.com/v1",
    )
    service.generate_text = lambda _prompt: '{"is_valid": true, "invented": 1}'

    with pytest.raises(ValidationError):
        service.generate_json("Kiểm tra", response_model=StrictPayload)
