from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterator, TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.core.config import (
    AI_API_KEY,
    AI_BASE_URL,
    AI_DISABLE_THINKING,
    AI_MODEL,
    AI_PROVIDER,
    AI_THINKING_EFFORT,
    AI_TIMEOUT_SECONDS,
)
from app.models import AIModelCall, AIValidationError, AgentRun
from app.services.ai_output_parser import AIParseError, parse_json_output

T = TypeVar("T", bound=BaseModel)
MAX_CAPTURE_BYTES = 20 * 1024
logger = logging.getLogger(__name__)


class AIServiceError(RuntimeError):
    def __init__(self, code: str, message: str, *, stage: str, retryable: bool = True):
        super().__init__(message)
        self.code, self.stage, self.retryable = code, stage, retryable


@dataclass
class StructuredResult:
    value: BaseModel
    degraded: bool = False


def _truncate(value: str | None) -> str | None:
    if value is None:
        return None
    return value.encode("utf-8")[:MAX_CAPTURE_BYTES].decode("utf-8", errors="ignore")


def _usage_value(usage: Any, name: str) -> Any:
    if usage is None:
        return None
    return usage.get(name) if isinstance(usage, dict) else getattr(usage, name, None)


def _provider_usage(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    details = _usage_value(usage, "completion_tokens_details")
    return {
        "input_tokens": _usage_value(usage, "prompt_tokens"),
        "output_tokens": _usage_value(usage, "completion_tokens"),
        "total_tokens": _usage_value(usage, "total_tokens"),
        "reasoning_tokens": _usage_value(details, "reasoning_tokens"),
    }


class AIService:
    model_name = AI_MODEL

    def _record_call(
        self,
        db: Session,
        run: AgentRun,
        *,
        call_type: str,
        started: float,
        raw: str | None = None,
        finish_reason: str | None = None,
        request_id: str | None = None,
        error: str | None = None,
    ) -> AIModelCall:
        call = AIModelCall(
            agent_run_id=run.id,
            provider=AI_PROVIDER,
            model=AI_MODEL,
            call_type=call_type,
            request_id=request_id,
            prompt_version=run.prompt_version,
            raw_response=_truncate(raw),
            finish_reason=finish_reason,
            latency_ms=round((time.perf_counter() - started) * 1000),
            error_message=_truncate(error),
        )
        db.add(call)
        db.flush()
        return call

    def _record_validation(
        self,
        db: Session,
        run: AgentRun,
        call: AIModelCall,
        error: AIServiceError,
        parsed: dict[str, Any] | None,
        response_model: type[T],
        repair_attempted: bool,
    ) -> None:
        db.add(
            AIValidationError(
                agent_run_id=run.id,
                model_call_id=call.id,
                stage=error.stage,
                error_type=error.code,
                error_message=_truncate(str(error)) or "",
                parsed_output=parsed,
                schema_name=response_model.__name__,
                repair_attempted=repair_attempted,
            )
        )
        db.flush()

    def _call_provider(
        self, messages: list[dict[str, str]]
    ) -> tuple[str, str | None, str | None]:
        if not AI_API_KEY:
            raise AIServiceError(
                "AI_CONFIGURATION_ERROR",
                "AI 服务未配置。",
                stage="provider",
                retryable=False,
            )
        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=AI_API_KEY, base_url=AI_BASE_URL, timeout=AI_TIMEOUT_SECONDS
            )
            # DeepSeek V4 起 thinking 默认开启（默认 effort=high）；
            # 通过 extra_body 显式关闭/调强度。reasoning_effort 是顶层参数。
            extra_body: dict[str, dict[str, str]] = {
                "thinking": {
                    "type": "disabled" if AI_DISABLE_THINKING else "enabled",
                }
            }
            kwargs: dict = {
                "model": AI_MODEL,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": messages,
                "extra_body": extra_body,
            }
            if not AI_DISABLE_THINKING:
                kwargs["reasoning_effort"] = AI_THINKING_EFFORT
            provider_started = time.perf_counter()
            response = client.chat.completions.create(**kwargs)
            provider_latency_ms = round((time.perf_counter() - provider_started) * 1000)
            choice = response.choices[0]
            logger.info(
                json.dumps(
                    {
                        "event": "ai_provider_completed",
                        "provider": AI_PROVIDER,
                        "model": AI_MODEL,
                        "provider_latency_ms": provider_latency_ms,
                        "thinking_enabled": not AI_DISABLE_THINKING,
                        "thinking_effort": None if AI_DISABLE_THINKING else AI_THINKING_EFFORT,
                        "finish_reason": choice.finish_reason,
                        **_provider_usage(response),
                    },
                    ensure_ascii=False,
                )
            )
            return (
                choice.message.content or "",
                choice.finish_reason,
                getattr(response, "_request_id", None),
            )
        except Exception as exc:
            name = type(exc).__name__.lower()
            code, message = (
                ("AI_TIMEOUT", "AI 服务响应超时。")
                if "timeout" in name
                else (
                    ("AI_RATE_LIMIT", "AI 服务当前繁忙。")
                    if "ratelimit" in name or "rate_limit" in name
                    else ("AI_PROVIDER_ERROR", "AI 服务调用失败。")
                )
            )
            raise AIServiceError(
                code, message, stage="provider", retryable=True
            ) from exc

    def _parse_and_validate(
        self,
        raw: str,
        response_model: type[T],
        semantic_validator: Callable[[T], None] | None,
    ) -> tuple[T, dict[str, Any] | None]:
        try:
            parsed = parse_json_output(raw)
        except AIParseError as exc:
            raise AIServiceError(
                exc.code, str(exc), stage="parse", retryable=True
            ) from exc
        try:
            result = response_model.model_validate(parsed)
        except ValidationError as exc:
            raise AIServiceError(
                "AI_SCHEMA_VALIDATION_ERROR",
                "模型输出字段不符合要求。",
                stage="schema_validation",
                retryable=True,
            ) from exc
        if semantic_validator:
            try:
                semantic_validator(result)
            except ValueError as exc:
                raise AIServiceError(
                    "AI_SEMANTIC_VALIDATION_ERROR",
                    str(exc),
                    stage="semantic_validation",
                    retryable=True,
                ) from exc
        return result, parsed

    def stream_structured(
        self,
        *,
        db: Session,
        run: AgentRun,
        messages: list[dict[str, str]],
        response_model: type[T],
        semantic_validator: Callable[[T], None] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Stream provider progress, while exposing a result only after full validation."""
        if not AI_API_KEY:
            raise AIServiceError("AI_CONFIGURATION_ERROR", "AI 服务未配置。", stage="provider", retryable=False)
        started, raw_parts, finish_reason, request_id = time.perf_counter(), [], None, None
        try:
            from openai import OpenAI
            client = OpenAI(api_key=AI_API_KEY, base_url=AI_BASE_URL, timeout=AI_TIMEOUT_SECONDS)
            extra_body = {"thinking": {"type": "disabled" if AI_DISABLE_THINKING else "enabled"}}
            kwargs: dict[str, Any] = {"model": AI_MODEL, "temperature": 0, "response_format": {"type": "json_object"}, "messages": messages, "extra_body": extra_body, "stream": True}
            if not AI_DISABLE_THINKING:
                kwargs["reasoning_effort"] = AI_THINKING_EFFORT
            yield {"event": "status", "stage": "calling_model", "message": "正在连接 AI 模型…"}
            stream = client.chat.completions.create(**kwargs)
            emitted_chars = 0
            for chunk in stream:
                request_id = request_id or getattr(chunk, "_request_id", None)
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                finish_reason = choice.finish_reason or finish_reason
                content = choice.delta.content or ""
                if content:
                    raw_parts.append(content)
                    received_chars = sum(len(part) for part in raw_parts)
                    if received_chars - emitted_chars >= 120:
                        emitted_chars = received_chars
                        yield {"event": "progress", "stage": "receiving", "received_chars": received_chars, "message": "正在整理岗位要求…"}
            raw = "".join(raw_parts)
            latency_ms = round((time.perf_counter() - started) * 1000)
            logger.info(json.dumps({"event": "ai_provider_stream_completed", "provider": AI_PROVIDER, "model": AI_MODEL, "provider_latency_ms": latency_ms, "thinking_enabled": not AI_DISABLE_THINKING, "finish_reason": finish_reason, "received_chars": len(raw)}, ensure_ascii=False))
            call = self._record_call(db, run, call_type="primary", started=started, raw=raw, finish_reason=finish_reason, request_id=request_id)
            if finish_reason == "length":
                raise AIServiceError("AI_OUTPUT_TRUNCATED", "模型输出被截断。", stage="response", retryable=True)
            yield {"event": "status", "stage": "validating", "message": "正在校验生成结果…"}
            value, _ = self._parse_and_validate(raw, response_model, semantic_validator)
            yield {"event": "result", "result": StructuredResult(value)}
        except AIServiceError as exc:
            call = locals().get("call")
            if call is None:
                call = self._record_call(db, run, call_type="primary", started=started, error=exc.code)
            parsed = None
            if call.raw_response:
                try: parsed = parse_json_output(call.raw_response)
                except AIParseError: pass
            self._record_validation(db, run, call, exc, parsed, response_model, False)
            raise
        except Exception as exc:
            name = type(exc).__name__.lower()
            code = "AI_TIMEOUT" if "timeout" in name else ("AI_RATE_LIMIT" if "ratelimit" in name or "rate_limit" in name else "AI_PROVIDER_ERROR")
            error = AIServiceError(code, "AI 服务调用失败。", stage="provider", retryable=True)
            call = self._record_call(db, run, call_type="primary", started=started, error=code)
            self._record_validation(db, run, call, error, None, response_model, False)
            raise error from exc

    def generate_structured(
        self,
        *,
        db: Session,
        run: AgentRun,
        task_type: str,
        messages: list[dict[str, str]],
        response_model: type[T],
        semantic_validator: Callable[[T], None] | None = None,
        allow_repair: bool = True,
    ) -> StructuredResult:
        started, primary_call = time.perf_counter(), None
        try:
            raw, reason, request_id = self._call_provider(messages)
            primary_call = self._record_call(
                db,
                run,
                call_type="primary",
                started=started,
                raw=raw,
                finish_reason=reason,
                request_id=request_id,
            )
            if reason == "length":
                raise AIServiceError(
                    "AI_OUTPUT_TRUNCATED",
                    "模型输出被截断。",
                    stage="response",
                    retryable=True,
                )
            value, _ = self._parse_and_validate(raw, response_model, semantic_validator)
            return StructuredResult(value)
        except AIServiceError as exc:
            if primary_call is None:
                primary_call = self._record_call(
                    db, run, call_type="primary", started=started, error=exc.code
                )
            parsed = None
            if primary_call.raw_response:
                try:
                    parsed = parse_json_output(primary_call.raw_response)
                except AIParseError:
                    pass
            should_repair = allow_repair and exc.code in {
                "AI_JSON_PARSE_ERROR",
                "AI_SCHEMA_VALIDATION_ERROR",
            }
            self._record_validation(
                db, run, primary_call, exc, parsed, response_model, should_repair
            )
            if not should_repair:
                raise
            run.repair_attempted = True
            repair_messages = [
                {
                    "role": "system",
                    "content": "你是 JSON 修复器。只返回合法 JSON；只修复结构，不得增加任何新事实。",
                },
                {
                    "role": "user",
                    "content": "原始输出：\n"
                    + (primary_call.raw_response or "")
                    + "\n\n校验错误：\n"
                    + str(exc)
                    + "\n\n目标 JSON Schema：\n"
                    + json.dumps(
                        response_model.model_json_schema(), ensure_ascii=False
                    ),
                },
            ]
            repair_started, repair_call = time.perf_counter(), None
            try:
                repaired, reason, request_id = self._call_provider(repair_messages)
                repair_call = self._record_call(
                    db,
                    run,
                    call_type="repair",
                    started=repair_started,
                    raw=repaired,
                    finish_reason=reason,
                    request_id=request_id,
                )
                if reason == "length":
                    raise AIServiceError(
                        "AI_OUTPUT_TRUNCATED",
                        "模型输出被截断。",
                        stage="response",
                        retryable=True,
                    )
                value, _ = self._parse_and_validate(
                    repaired, response_model, semantic_validator
                )
                return StructuredResult(value, degraded=True)
            except AIServiceError as repair_error:
                if repair_call is None:
                    repair_call = self._record_call(
                        db,
                        run,
                        call_type="repair",
                        started=repair_started,
                        error=repair_error.code,
                    )
                parsed = None
                if repair_call.raw_response:
                    try:
                        parsed = parse_json_output(repair_call.raw_response)
                    except AIParseError:
                        pass
                self._record_validation(
                    db, run, repair_call, repair_error, parsed, response_model, True
                )
                raise repair_error


class FakeAIService:
    model_name = "fake-model"

    def __init__(self, result: dict[str, Any] | None = None):
        self.result = result

    def generate_structured(self, **kwargs) -> StructuredResult:
        response_model = kwargs["response_model"]
        result = self.result or (
            {
                "must_have": [],
                "preferred": [],
                "skills": ["测试"],
                "soft_skills": [],
                "negative_signals": [],
                "verification_questions": [],
                "summary": "测试招聘画像",
            }
            if response_model.__name__ == "RequirementProfileAIResult"
            else {
                "recommendation": "review",
                "overall_score": 50,
                "strengths": [],
                "gaps": [],
                "risks": [],
                "missing_information": [],
                "verification_questions": [],
                "summary": "测试分析结果",
            }
        )
        return StructuredResult(response_model.model_validate(result))
