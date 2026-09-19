import json
import re
from typing import Any

from fastapi import HTTPException
from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from app.core.config import settings
from app.services import ai_runtime


class GeminiService:
    def __init__(self, model: str | None = None, *, timeout_seconds: int | None = None):
        self.model = model or settings.GEMINI_MODEL
        self.verify_model = settings.GEMINI_VERIFY_MODEL or self.model
        self.timeout_seconds = timeout_seconds

    def generate_text(self, prompt: str) -> str:
        if not settings.GEMINI_API_KEY:
            raise HTTPException(
                status_code=400,
                detail="Chưa cấu hình GEMINI_API_KEY trong backend/.env",
            )

        # HttpOptions.timeout is milliseconds and is enforced by the SDK's
        # transport, so a hung provider aborts here rather than pinning a thread.
        client = genai.Client(
            api_key=settings.GEMINI_API_KEY,
            http_options=types.HttpOptions(timeout=self._timeout_ms()),
        )
        try:
            with ai_runtime.track_call("gemini", self.model, "generate_text") as call:
                response = client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                )
                call["response"] = response
        except errors.ClientError as exc:
            status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None) or 502
            message = getattr(exc, "message", None) or str(exc)
            raise HTTPException(
                status_code=status_code,
                detail=f"Gemini API error: {message}",
            ) from exc
        except errors.APIError as exc:
            # Server-side and transport failures (including timeouts) surface as
            # a gateway error rather than a 500 from an unhandled exception.
            message = getattr(exc, "message", None) or str(exc)
            raise HTTPException(
                status_code=502,
                detail=f"Gemini API error: {message}",
            ) from exc
        return response.text or ""

    def generate_json(
        self,
        prompt: str,
        response_model: type[BaseModel] | None = None,
    ) -> Any:
        text = self.generate_text(prompt)
        cleaned = self._strip_code_fence(text)
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Gemini did not return valid JSON: {text[:500]}") from exc
        if response_model is None:
            return payload
        return response_model.model_validate(payload).model_dump(mode="json")

    def _generate_structured_text(
        self,
        prompt: str,
        response_model: type[BaseModel],
    ) -> str:
        if not settings.GEMINI_API_KEY:
            raise HTTPException(
                status_code=400,
                detail="Chưa cấu hình GEMINI_API_KEY trong backend/.env",
            )
        client = genai.Client(
            api_key=settings.GEMINI_API_KEY,
            http_options=types.HttpOptions(timeout=ai_runtime.timeout_ms()),
        )
        try:
            with ai_runtime.track_call("gemini", self.model, "generate_json") as call:
                response = client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=response_model,
                    ),
                )
                call["response"] = response
        except errors.ClientError as exc:
            status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None) or 502
            message = getattr(exc, "message", None) or str(exc)
            raise HTTPException(status_code=status_code, detail=f"Gemini API error: {message}") from exc
        except errors.APIError as exc:
            message = getattr(exc, "message", None) or str(exc)
            raise HTTPException(status_code=502, detail=f"Gemini API error: {message}") from exc
        return response.text or ""

    def generate_verification_json(
        self,
        prompt: str,
        response_model: type[BaseModel] | None = None,
    ) -> Any:
        """Run a verification prompt with the configured verification model."""
        model = self.verify_model
        service = self if model == self.model else GeminiService(
            model=model, timeout_seconds=self.timeout_seconds
        )
        if response_model is None:
            return service.generate_json(prompt)
        text = service._generate_structured_text(prompt, response_model)
        cleaned = service._strip_code_fence(text)
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Gemini did not return valid JSON: {text[:500]}") from exc
        return response_model.model_validate(payload).model_dump(mode="json")

    def available(self) -> bool:
        return bool(settings.GEMINI_API_KEY)

    def _timeout_ms(self) -> int:
        if self.timeout_seconds is None:
            return ai_runtime.timeout_ms()
        return int(max(1.0, float(self.timeout_seconds) - 1.0) * 1000)

    def _strip_code_fence(self, text: str) -> str:
        match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text.strip()
