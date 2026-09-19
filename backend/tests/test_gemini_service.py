from unittest.mock import MagicMock, patch

from pydantic import BaseModel, ConfigDict

from app.services.gemini_service import GeminiService


class StrictPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    is_valid: bool


def test_structured_generation_uses_schema_and_json_mime_type(monkeypatch):
    monkeypatch.setattr("app.services.gemini_service.settings.GEMINI_API_KEY", "test-key")
    client = MagicMock()
    client.models.generate_content.return_value.text = '{"is_valid": true}'

    with patch("app.services.gemini_service.genai.Client", return_value=client):
        result = GeminiService(model="gemini-3.7-flash").generate_verification_json(
            "Kiểm tra", response_model=StrictPayload
        )

    assert result == {"is_valid": True}
    call = client.models.generate_content.call_args.kwargs
    assert call["model"] == "gemini-3.7-flash"
    assert call["config"].response_mime_type == "application/json"
    assert call["config"].response_schema is StrictPayload
