"""First-class OpenAI Responses API adapter."""

from __future__ import annotations

import json
import re
from typing import Any

from fastapi import HTTPException
from openai import OpenAI
from pydantic import BaseModel

from app.core.config import settings
from app.services import ai_runtime


class OpenAIService:
    """Call OpenAI directly; custom compatible endpoints are intentionally excluded."""

    provider = "openai"

    def __init__(
        self,
        model: str | None = None,
        verify_model: str | None = None,
        *,
        reasoning_effort: str | None = None,
        verbosity: str | None = None,
    ):
        self.model = model or settings.OPENAI_MODEL
        self.verify_model = verify_model or settings.OPENAI_VERIFY_MODEL or self.model
        self.reasoning_effort = reasoning_effort
        self.verbosity = verbosity

    def generate_text(self, prompt: str) -> str:
        return self._generate_text(prompt, self.model)

    def generate_json(
        self,
        prompt: str,
        response_model: type[BaseModel] | None = None,
    ) -> Any:
        if response_model is None:
            return self._decode_json(self.generate_text(prompt))
        return self._generate_structured_json(prompt, self.model, response_model)

    def generate_verification_json(
        self,
        prompt: str,
        response_model: type[BaseModel] | None = None,
    ) -> Any:
        if response_model is None:
            return self._decode_json(self._generate_text(prompt, self.verify_model))
        return self._generate_structured_json(
            prompt, self.verify_model, response_model
        )

    def available(self) -> bool:
        return bool(self._usable_api_key() and self.model)

    @staticmethod
    def _usable_api_key() -> str:
        key = str(settings.OPENAI_API_KEY or "").strip()
        normalized = key.lower()
        placeholder_markers = (
            "sk-xxxxx",
            "your_openai_api_key",
            "replace-with-openai",
            "replace_me",
            "changeme",
        )
        return "" if any(marker in normalized for marker in placeholder_markers) else key

    def _require_api_key(self) -> str:
        key = self._usable_api_key()
        if not key:
            raise HTTPException(
                status_code=400,
                detail="OPENAI_API_KEY đang thiếu hoặc vẫn là giá trị mẫu trong backend/.env",
            )
        return key

    def _generate_text(self, prompt: str, model: str) -> str:
        api_key = self._require_api_key()
        if not model:
            raise HTTPException(status_code=400, detail="Chưa cấu hình OPENAI_MODEL")

        try:
            client = OpenAI(
                api_key=api_key,
                timeout=ai_runtime.httpx_timeout(),
                max_retries=settings.AI_MAX_RETRIES,
            )
            with ai_runtime.track_call("openai", model, "responses.create") as call:
                response = client.responses.create(
                    model=model,
                    input=prompt,
                    store=False,
                    **self._create_cost_control_args(),
                )
                call["response"] = response
            text = response.output_text or ""
            if not text.strip():
                raise ValueError("OpenAI returned an empty response")
            return text
        except HTTPException:
            raise
        except Exception as exc:
            status_code = getattr(exc, "status_code", None) or 502
            raise HTTPException(
                status_code=status_code,
                detail=f"OpenAI API error: {exc}",
            ) from exc

    def _generate_structured_json(
        self,
        prompt: str,
        model: str,
        response_model: type[BaseModel],
    ) -> Any:
        api_key = self._require_api_key()
        if not model:
            raise HTTPException(status_code=400, detail="Chưa cấu hình OPENAI_MODEL")

        try:
            client = OpenAI(
                api_key=api_key,
                timeout=ai_runtime.httpx_timeout(),
                max_retries=settings.AI_MAX_RETRIES,
            )
            with ai_runtime.track_call("openai", model, "responses.parse") as call:
                response = client.responses.parse(
                    model=model,
                    input=prompt,
                    store=False,
                    text_format=response_model,
                    **self._parse_cost_control_args(),
                )
                call["response"] = response
            parsed = response.output_parsed
            if parsed is None:
                raise ValueError("OpenAI returned no schema-conformant output")
            if isinstance(parsed, BaseModel):
                return parsed.model_dump(mode="json")
            return parsed
        except HTTPException:
            raise
        except Exception as exc:
            status_code = getattr(exc, "status_code", None) or 502
            raise HTTPException(
                status_code=status_code,
                detail=f"OpenAI API error: {exc}",
            ) from exc

    @staticmethod
    def _decode_json(text: str) -> Any:
        match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        cleaned = match.group(1).strip() if match else text.strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"OpenAI did not return valid JSON: {text[:500]}") from exc

    def _reasoning_args(self) -> dict[str, Any]:
        args: dict[str, Any] = {}
        if self.reasoning_effort:
            args["reasoning"] = {"effort": self.reasoning_effort}
        return args

    def _create_cost_control_args(self) -> dict[str, Any]:
        args = self._reasoning_args()
        if self.verbosity:
            args["text"] = {"verbosity": self.verbosity}
        return args

    def _parse_cost_control_args(self) -> dict[str, Any]:
        args = self._reasoning_args()
        if self.verbosity:
            # Responses API accepts verbosity under text for both create and
            # parse. A top-level verbosity value is rejected with HTTP 400.
            args["text"] = {"verbosity": self.verbosity}
        return args
