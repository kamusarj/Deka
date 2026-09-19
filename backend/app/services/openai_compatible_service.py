"""Client for OpenAI and providers compatible with OpenAI Chat Completions."""

import json
import re
from typing import Any

from fastapi import HTTPException
import httpx
from openai import OpenAI
from pydantic import BaseModel

from app.core.config import settings
from app.services import ai_runtime


class OpenAICompatibleService:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        provider: str,
        base_url: str | None = None,
        verify_model: str | None = None,
        timeout_seconds: int | None = None,
        max_retries: int | None = None,
    ):
        self.api_key = api_key
        self.model = model
        self.provider = provider
        self.base_url = base_url or None
        self.verify_model = verify_model or model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def generate_text(self, prompt: str) -> str:
        return self._generate_text(prompt, self.model)

    def generate_json(
        self,
        prompt: str,
        response_model: type[BaseModel] | None = None,
    ) -> Any:
        return self._validated_json(
            self._decode_json(self.generate_text(prompt)),
            response_model,
        )

    def generate_verification_json(
        self,
        prompt: str,
        response_model: type[BaseModel] | None = None,
    ) -> Any:
        return self._validated_json(
            self._decode_json(
                self._generate_text(
                    prompt,
                    self.verify_model,
                    json_object=response_model is not None,
                )
            ),
            response_model,
        )

    def available(self) -> bool:
        return bool(self.api_key and self.model)

    def _generate_text(self, prompt: str, model: str, *, json_object: bool = False) -> str:
        if not self.api_key:
            raise HTTPException(status_code=400, detail=f"Chưa cấu hình API key cho provider {self.provider}")
        if not model:
            raise HTTPException(status_code=400, detail=f"Chưa cấu hình model cho provider {self.provider}")
        try:
            # httpx.Timeout separates connect from read; max_retries is bounded
            # because each retry spends the same wall-clock budget again.
            client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self._timeout(),
                max_retries=(
                    settings.AI_MAX_RETRIES
                    if self.max_retries is None
                    else self.max_retries
                ),
            )
            with ai_runtime.track_call(self.provider, model, "chat_completion") as call:
                request = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                }
                if json_object:
                    request["response_format"] = {"type": "json_object"}
                response = client.chat.completions.create(
                    **request,
                )
                call["response"] = response
        except Exception as exc:
            status_code = getattr(exc, "status_code", None) or 502
            raise HTTPException(status_code=status_code, detail=f"{self.provider} API error: {exc}") from exc
        return response.choices[0].message.content or ""

    def _timeout(self) -> httpx.Timeout:
        if self.timeout_seconds is None:
            return ai_runtime.httpx_timeout()
        budget = max(1.0, float(self.timeout_seconds) - 1.0)
        connect = min(float(settings.AI_CONNECT_TIMEOUT_SECONDS), budget / 2)
        read = max(1.0, budget - connect)
        return httpx.Timeout(
            read,
            connect=connect,
            read=read,
            write=read,
            pool=connect,
        )

    @staticmethod
    def _decode_json(text: str) -> Any:
        match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        cleaned = match.group(1).strip() if match else text.strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Provider did not return valid JSON: {text[:500]}") from exc

    @staticmethod
    def _validated_json(
        payload: Any,
        response_model: type[BaseModel] | None,
    ) -> Any:
        if response_model is None:
            return payload
        return response_model.model_validate(payload).model_dump(mode="json")
