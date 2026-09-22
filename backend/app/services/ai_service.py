from __future__ import annotations

import json
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.config import AI_API_KEY, AI_BASE_URL, AI_MODEL, AI_TIMEOUT_SECONDS

T = TypeVar("T", bound=BaseModel)


class AIServiceError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class AIService:
    model_name = AI_MODEL

    def generate_structured(self, system: str, user: str, response_model: type[T]) -> T:
        if not AI_API_KEY:
            raise AIServiceError("AI_MODEL_ERROR", "未配置 AI_API_KEY。")
        try:
            from openai import OpenAI
            client = OpenAI(api_key=AI_API_KEY, base_url=AI_BASE_URL, timeout=AI_TIMEOUT_SECONDS)
            response = client.chat.completions.create(
                model=AI_MODEL,
                temperature=0.1,
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            )
            content = response.choices[0].message.content or ""
            try:
                return response_model.model_validate(json.loads(content))
            except (json.JSONDecodeError, ValidationError) as exc:
                raise AIServiceError("AI_INVALID_JSON", "模型返回内容不是有效的结构化 JSON。") from exc
        except AIServiceError:
            raise
        except Exception as exc:
            raise AIServiceError("AI_MODEL_ERROR", str(exc)) from exc


class FakeAIService:
    model_name = "fake-model"

    def __init__(self, result: dict[str, Any] | None = None):
        self.result = result

    def generate_structured(self, system: str, user: str, response_model: type[T]) -> T:
        if self.result is not None:
            return response_model.model_validate(self.result)
        name = response_model.__name__
        if name == "RequirementProfileAIResult":
            return response_model.model_validate({"must_have": [], "preferred": [], "skills": [], "soft_skills": [], "negative_signals": [], "verification_questions": [], "summary": "测试招聘画像"})
        return response_model.model_validate({"recommendation": "review", "overall_score": 50, "strengths": [], "gaps": [], "risks": [], "missing_information": [], "verification_questions": [], "summary": "测试分析结果"})
