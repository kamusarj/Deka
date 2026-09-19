"""Required independent reviewers for interactive full-exam authoring."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from app.core.config import settings
from app.services.gemini_service import GeminiService
from app.services.openai_compatible_service import OpenAICompatibleService
from app.services.ai.gateway import AIGateway

logger = logging.getLogger("smart-exam-ai")


class MandatoryReviewUnavailable(RuntimeError):
    """Raised when every reviewer required by the active mode cannot complete."""


@dataclass(frozen=True)
class Reviewer:
    key: str
    label: str
    provider: str
    model: str
    service: Any


class DualVerificationService:
    """Call the configured required reviewers without provider substitution."""

    def __init__(
        self,
        reviewers: list[Reviewer] | None = None,
        *,
        mode: str | None = None,
    ):
        self.mode = mode or (
            settings.AI_INTERACTIVE_REVIEW_MODE
            if reviewers is None
            else ("dual" if len(reviewers) == 2 else "deepseek_only")
        )
        self.reviewers = reviewers if reviewers is not None else self._default_reviewers()

    def _default_reviewers(self) -> list[Reviewer]:
        reviewers = [
            Reviewer(
                key="deepseek",
                label="DeepSeek V4 Pro",
                provider="deepseek",
                model=settings.DEEPSEEK_VERIFY_MODEL,
                service=OpenAICompatibleService(
                    api_key=settings.DEEPSEEK_API_KEY,
                    model=settings.DEEPSEEK_MODEL,
                    verify_model=settings.DEEPSEEK_VERIFY_MODEL,
                    provider="deepseek",
                    base_url=settings.DEEPSEEK_BASE_URL,
                    timeout_seconds=settings.AI_DUAL_REVIEW_TIMEOUT_SECONDS,
                    max_retries=0,
                ),
            )
        ]
        if self.mode == "dual":
            reviewers.append(Reviewer(
                key="gemini",
                label="Gemini 3.7 Flash",
                provider="gemini",
                model=settings.GEMINI_VERIFY_MODEL,
                service=GeminiService(
                    model=settings.GEMINI_VERIFY_MODEL,
                    timeout_seconds=settings.AI_DUAL_REVIEW_TIMEOUT_SECONDS,
                ),
            ))
        return reviewers

    def required_reviewer_labels(self) -> list[str]:
        return [reviewer.label for reviewer in self.reviewers]

    def available(self) -> bool:
        expected_count = 2 if self.mode == "dual" else 1
        return len(self.reviewers) == expected_count and all(
            reviewer.model and reviewer.service.available()
            for reviewer in self.reviewers
        )

    async def review(
        self,
        prompt: str,
        *,
        response_model: type[BaseModel],
    ) -> dict[str, dict[str, Any]]:
        if not self.available():
            required = " và ".join(self.required_reviewer_labels())
            raise MandatoryReviewUnavailable(
                f"Cần cấu hình đủ {required} để kiểm định."
            )

        async def invoke(reviewer: Reviewer):
            try:
                reviewer_prompt = prompt
                if reviewer.provider == "deepseek":
                    reviewer_prompt += (
                        "\nJSON Schema bắt buộc:\n"
                        + json.dumps(
                            response_model.model_json_schema(),
                            ensure_ascii=False,
                        )
                    )
                value = await asyncio.wait_for(
                    asyncio.to_thread(
                        AIGateway().generate,
                        prompt=reviewer_prompt,
                        provider=reviewer.provider,
                        service=reviewer.service,
                        model=reviewer.model,
                        method="generate_verification_json",
                        response_model=response_model,
                    ),
                    timeout=float(settings.AI_DUAL_REVIEW_TIMEOUT_SECONDS),
                )
                return reviewer, value.content, None
            except Exception as exc:  # Provider details stay in server logs only.
                logger.warning(
                    "mandatory_reviewer_failed provider=%s model=%s outcome=%s",
                    reviewer.provider,
                    reviewer.model,
                    type(exc).__name__,
                )
                return reviewer, None, exc

        results = await asyncio.gather(*(invoke(item) for item in self.reviewers))
        failed = [reviewer.label for reviewer, _value, error in results if error]
        if failed:
            raise MandatoryReviewUnavailable(
                "Không thể hoàn tất các lượt kiểm định bắt buộc: "
                + ", ".join(failed)
            )

        return {
            reviewer.key: {
                "label": reviewer.label,
                "provider": reviewer.provider,
                "model": reviewer.model,
                "result": value,
            }
            for reviewer, value, _error in results
        }
