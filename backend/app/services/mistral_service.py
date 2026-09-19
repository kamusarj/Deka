import json
import re
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel
from mistralai.client import Mistral

from app.core.config import settings
from app.services import ai_runtime


class MistralService:
    def __init__(self, model: str | None = None):
        self.model = model or settings.MISTRAL_MODEL

    def generate_text(self, prompt: str) -> str:
        return self._generate_text(prompt)

    def _generate_text(
        self,
        prompt: str,
        *,
        response_format: dict[str, str] | None = None,
    ) -> str:
        if not settings.MISTRAL_API_KEY:
            raise HTTPException(
                status_code=400,
                detail="Chưa cấu hình MISTRAL_API_KEY trong backend/.env",
            )

        # timeout_ms is the SDK's own transport budget; the injected httpx client
        # additionally caps connect time separately from read time.
        client = Mistral(
            api_key=settings.MISTRAL_API_KEY,
            timeout_ms=ai_runtime.timeout_ms(),
            client=ai_runtime.httpx_client(),
        )
        try:
            operation = "generate_json" if response_format else "generate_text"
            with ai_runtime.track_call("mistral", self.model, operation) as call:
                request = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                }
                if response_format:
                    request["response_format"] = response_format
                response = client.chat.complete(
                    **request,
                )
                call["response"] = response
        except Exception as exc:
            status_code = getattr(exc, "status_code", None) or getattr(exc, "http_status", None) or 502
            message = getattr(exc, "message", None) or str(exc)
            raise HTTPException(
                status_code=status_code,
                detail=f"Mistral API error: {message}",
            ) from exc

        if response and response.choices:
            return response.choices[0].message.content or ""
        return ""

    def generate_json(
        self,
        prompt: str,
        response_model: type[BaseModel] | None = None,
    ) -> Any:
        del response_model
        text = self._generate_text(
            prompt,
            response_format={"type": "json_object"},
        )
        cleaned = self._strip_code_fence(text)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Mistral did not return valid JSON: {text[:500]}") from exc

    def generate_verification_json(
        self,
        prompt: str,
        response_model: type[BaseModel] | None = None,
    ) -> Any:
        """Run a verification prompt with the configured verification model."""
        model = settings.MISTRAL_VERIFY_MODEL or settings.MISTRAL_MODEL
        if model == self.model:
            return self.generate_json(prompt, response_model=response_model)
        return MistralService(model=model).generate_json(
            prompt, response_model=response_model
        )

    def available(self) -> bool:
        return bool(settings.MISTRAL_API_KEY)

    def _strip_code_fence(self, text: str) -> str:
        match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text.strip()
