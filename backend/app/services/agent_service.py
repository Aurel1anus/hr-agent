from __future__ import annotations

from datetime import datetime, timedelta
import json
import logging
from typing import Any, Iterator

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import AI_PROVIDER, AI_TIMEOUT_SECONDS
from app.core.enums import Priority, TaskStatus
from app.models import (
    AgentRun,
    AgentToolCall,
    Application,
    Memory,
    RequirementProfile,
    Resume,
    ResumeAssessment,
    Task,
)
from app.schemas import (
    AssessmentGap,
    AssessmentResult,
    AssessmentStrength,
    RequirementItem,
    ToolApproval,
)
from app.services.ai_service import AIService, AIServiceError, StructuredResult
from app.services.service import task_view

PROMPT_VERSION = "v4"
JSON_ONLY = """
你必须只返回符合目标 Schema 的合法 JSON。

输出要求：
1. 只输出 JSON，不得输出 Markdown 代码块、前言、后记、解释、注释或其他文本。
2. 不得创建目标 Schema 中未定义的字段。
3. 字段类型必须严格符合 Schema。
4. 信息未知时，按照 Schema 要求使用 null、[]、空字符串或指定枚举值，不得自行编造信息。

长度与数量限制：
5. 任意数组最多包含 20 项。
6. 当候选内容超过 20 项时：
   - 先删除重复项；
   - 再合并语义相近或存在包含关系的项目；
   - 再按照对当前任务的重要程度从高到低排序；
   - 最终只输出最重要的前 20 项。
7. 信息完整性与数量限制冲突时，必须优先满足数量限制，绝对不得输出超过 20 项。
8. 数组中的普通字符串每项最多 500 个字符；超过时必须归纳压缩。
9. summary 最多 2000 个字符；超过时必须归纳，只保留最重要的信息。

输出前必须自行检查：
- JSON 是否合法；
- 是否存在 Schema 之外的字段；
- 所有字段类型是否正确；
- 每个数组长度是否 <= 20；
- 字符串是否超过规定长度。

如果存在违反上述约束的内容，必须先在内部完成删减、合并或归纳，再输出最终 JSON。
"""

logger = logging.getLogger(__name__)


class RequirementProfileAIResult(BaseModel):
    must_have: list[RequirementItem] = []
    preferred: list[RequirementItem] = []
    skills: list[str] = []
    soft_skills: list[str] = []
    negative_signals: list[str] = []
    verification_questions: list[str] = []
    summary: str


class CopilotAIResult(BaseModel):
    """Copilot is advisory and does not need an assessment recommendation or score."""
    strengths: list[AssessmentStrength] = []
    risks: list[str] = []
    missing_information: list[str] = []
    verification_questions: list[str] = []
    summary: str


class AIOperationError(Exception):
    def __init__(self, error: AIServiceError, run_id: int, status_code: int = 502):
        self.status_code, self.error, self.run_id = status_code, error, run_id

    def body(self) -> dict[str, Any]:
        message = (
            "AI 服务暂不可用，请联系管理员。"
            if not self.error.retryable
            else "AI 分析暂时失败，请重试。"
        )
        return {
            "code": self.error.code,
            "message": message,
            "run_id": self.run_id,
            "retryable": self.error.retryable,
        }


def _ai_meta(run: AgentRun) -> dict[str, Any]:
    return {"run_id": run.id, "status": run.status}


def profile_view(p: RequirementProfile, run: AgentRun | None = None) -> dict:
    value = {
        "id": p.id,
        "job_id": p.job_id,
        "revision": p.revision,
        "raw_jd": p.raw_jd,
        "raw_notes": p.raw_notes,
        "must_have": p.must_have_json or [],
        "preferred": p.preferred_json or [],
        "skills": p.skills_json or [],
        "soft_skills": p.soft_skills_json or [],
        "negative_signals": p.negative_signals_json or [],
        "verification_questions": p.verification_questions_json or [],
        "ai_summary": p.ai_summary,
        "status": p.status,
        "confirmed_at": p.confirmed_at,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }
    if run:
        value["_ai"] = _ai_meta(run)
    return value


def assessment_view(a: ResumeAssessment, run: AgentRun | None = None) -> dict:
    value = {
        "id": a.id,
        "application_id": a.application_id,
        "candidate_id": a.candidate_id,
        "job_id": a.job_id,
        "requirement_profile_id": a.requirement_profile_id,
        "resume_id": a.resume_id,
        "recommendation": a.recommendation,
        "overall_score": a.overall_score,
        "strengths": a.strengths_json or [],
        "gaps": a.gaps_json or [],
        "risks": a.risks_json or [],
        "missing_information": a.missing_information_json or [],
        "verification_questions": a.verification_questions_json or [],
        "summary": a.summary,
        "model_name": a.model_name,
        "prompt_version": a.prompt_version,
        "created_at": a.created_at,
    }
    if run:
        value["_ai"] = _ai_meta(run)
    return value


def memory_view(m: Memory) -> dict:
    return {
        "id": m.id,
        "entity_type": m.entity_type,
        "entity_id": m.entity_id,
        "memory_type": m.memory_type,
        "content": m.content,
        "source_type": m.source_type,
        "source_id": m.source_id,
        "importance": m.importance,
        "confidence": m.confidence,
        "created_at": m.created_at,
        "updated_at": m.updated_at,
    }


def _validate_strings(values: list[str], label: str) -> None:
    if len(values) > 20:
        raise ValueError(f"{label} 超过 20 项。")
    if any(not value.strip() or len(value) > 500 for value in values):
        raise ValueError(f"{label} 含有空文本或超长文本。")


def validate_requirement(result: RequirementProfileAIResult) -> None:
    for label, values in (
        ("must_have", result.must_have),
        ("preferred", result.preferred),
    ):
        if len(values) > 20:
            raise ValueError(f"{label} 超过 20 项。")
    for label, values in (
        ("skills", result.skills),
        ("soft_skills", result.soft_skills),
        ("negative_signals", result.negative_signals),
        ("verification_questions", result.verification_questions),
    ):
        _validate_strings(values, label)
    if not result.summary.strip() or len(result.summary) > 2000:
        raise ValueError("summary 为空或超长。")
    if not any(
        (
            result.must_have,
            result.preferred,
            result.skills,
            result.soft_skills,
            result.negative_signals,
            result.verification_questions,
        )
    ):
        raise ValueError("招聘画像不能全部为空。")


def validate_assessment(result: AssessmentResult) -> None:
    if result.recommendation not in {"recommend", "review", "reject"}:
        raise ValueError("recommendation 不是允许的枚举值。")
    if len(result.strengths) > 20 or len(result.gaps) > 20:
        raise ValueError("优势或差距超过 20 项。")
    if any(
        item.status not in {"met", "partial"}
        or not item.requirement.strip()
        or not item.evidence.strip()
        or len(item.requirement) > 500
        or len(item.evidence) > 500
        for item in result.strengths
    ):
        raise ValueError("strengths 含有无效状态或文本。")
    if any(
        item.status not in {"missing", "partial", "unknown"}
        or not item.requirement.strip()
        or not item.reason.strip()
        or len(item.requirement) > 500
        or len(item.reason) > 500
        for item in result.gaps
    ):
        raise ValueError("gaps 含有无效状态或文本。")
    for label, values in (
        ("risks", result.risks),
        ("missing_information", result.missing_information),
        ("verification_questions", result.verification_questions),
    ):
        _validate_strings(values, label)
    if not result.summary.strip() or len(result.summary) > 2000:
        raise ValueError("summary 为空或超长。")


def validate_copilot(result: CopilotAIResult) -> None:
    if len(result.strengths) > 20:
        raise ValueError("优势超过 20 项。")
    if any(
        item.status not in {"met", "partial"}
        or not item.requirement.strip()
        or not item.evidence.strip()
        or len(item.requirement) > 500
        or len(item.evidence) > 500
        for item in result.strengths
    ):
        raise ValueError("strengths 含有无效状态或文本。")
    for label, values in (
        ("risks", result.risks),
        ("missing_information", result.missing_information),
        ("verification_questions", result.verification_questions),
    ):
        _validate_strings(values, label)
    if not result.summary.strip() or len(result.summary) > 2000:
        raise ValueError("summary 为空或超长。")


def _start_run(
    db: Session,
    *,
    task_type: str,
    job_id: int | None = None,
    application: Application | None = None,
    input_summary: dict[str, Any],
    ai: Any,
) -> AgentRun:
    filters = [AgentRun.agent_type == task_type, AgentRun.status == "running"]
    if application:
        filters.append(AgentRun.application_id == application.id)
    else:
        filters.append(AgentRun.job_id == job_id)
    existing = db.scalar(select(AgentRun).where(*filters).order_by(AgentRun.id.desc()))
    if existing and existing.started_at and existing.started_at < datetime.now() - timedelta(seconds=AI_TIMEOUT_SECONDS + 30):
        existing.status = "failed"
        existing.error_stage = "run"
        existing.error_type = "AI_STALE_RUN"
        existing.error_message = "AI 运行异常中断，已自动标记为失败。"
        existing.finished_at = datetime.now()
        existing.latency_ms = int((existing.finished_at - existing.started_at).total_seconds() * 1000)
        db.commit()
        existing = None
    if existing:
        conflict = AIServiceError(
            "AI_ALREADY_RUNNING", "AI 正在处理中。", stage="run", retryable=False
        )
        raise AIOperationError(conflict, existing.id, 409)
    run = AgentRun(
        agent_type=task_type,
        candidate_id=application.candidate_id if application else None,
        job_id=application.job_id if application else job_id,
        application_id=application.id if application else None,
        model_name=ai.model_name,
        provider=AI_PROVIDER,
        prompt_version=PROMPT_VERSION,
        status="running",
        started_at=datetime.now(),
        input_json=input_summary,
        repair_attempted=False,
        fallback_used=False,
    )
    # Persist before invoking the provider so a concurrent request can see the running guard.
    db.add(run)
    try:
        db.commit()
        db.refresh(run)
        return run
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(AgentRun).where(*filters).order_by(AgentRun.id.desc())
        )
        conflict = AIServiceError(
            "AI_ALREADY_RUNNING", "AI 正在处理中。", stage="run", retryable=False
        )
        raise AIOperationError(conflict, existing.id if existing else 0, 409)


def _finish_failure(db: Session, run: AgentRun, exc: AIServiceError) -> None:
    run.status, run.error_stage, run.error_type = "failed", exc.stage, exc.code
    run.error_message, run.finished_at = str(exc), datetime.now()
    run.latency_ms = (
        int((run.finished_at - run.started_at).total_seconds() * 1000)
        if run.started_at
        else None
    )
    db.commit()
    logger.error(
        json.dumps(
            {
                "event": "ai_run_failed",
                "run_id": run.id,
                "task": run.agent_type,
                "model": run.model_name,
                "prompt_version": run.prompt_version,
                "stage": exc.stage,
                "error_type": exc.code,
                "latency_ms": run.latency_ms,
                "repair_attempted": run.repair_attempted,
            },
            ensure_ascii=False,
        )
    )


def _finish_unexpected_failure(db: Session, run_id: int, exc: Exception) -> AIServiceError:
    """Persist non-AI failures too, so a crashed write cannot strand a running run."""
    db.rollback()
    run = db.get(AgentRun, run_id)
    error = AIServiceError("AI_INTERNAL_ERROR", "AI 结果保存失败。", stage="persistence", retryable=True)
    if run:
        _finish_failure(db, run, error)
    logger.exception("Unexpected AI persistence error for run %s", run_id, exc_info=exc)
    return error


def _finish_success(
    db: Session, run: AgentRun, output: dict[str, Any], degraded: bool
) -> None:
    run.status = "degraded" if degraded else "success"
    # View payloads contain datetimes, while SQLite JSON accepts JSON-native values only.
    run.output_json = json.loads(
        json.dumps(
            output,
            ensure_ascii=False,
            default=lambda value: value.isoformat()
            if isinstance(value, datetime)
            else str(value),
        )
    )
    run.finished_at = datetime.now()
    run.latency_ms = int((run.finished_at - run.started_at).total_seconds() * 1000)
    db.commit()
    logger.info(
        json.dumps(
            {
                "event": "ai_run_completed",
                "run_id": run.id,
                "task": run.agent_type,
                "model": run.model_name,
                "prompt_version": run.prompt_version,
                "status": run.status,
                "latency_ms": run.latency_ms,
                "repair_attempted": run.repair_attempted,
            },
            ensure_ascii=False,
        )
    )


def _messages(system: str, user: str, schema: type[BaseModel]) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": system
            + "\n"
            + JSON_ONLY
            + "\n目标 JSON Schema：\n"
            + json.dumps(schema.model_json_schema(), ensure_ascii=False),
        },
        {"role": "user", "content": user},
    ]


def generate_profile(db: Session, job, notes: str | None, ai=None):
    ai = ai or AIService()
    jd = job.jd_text or job.description or ""
    if not jd.strip() and not (notes or "").strip():
        raise HTTPException(422, detail="请先填写岗位 JD 或业务补充，再生成招聘画像。")
    run = _start_run(
        db,
        task_type="requirement_generation",
        job_id=job.id,
        ai=ai,
        input_summary={
            "job_id": job.id,
            "has_extra_notes": bool(notes),
            "jd_length": len(jd),
            "extra_notes_length": len(notes or ""),
        },
    )
    try:
        structured: StructuredResult = ai.generate_structured(
            db=db,
            run=run,
            task_type="requirement_generation",
            messages=_messages(
                "你是招聘需求分析助手。不得补充用户未提供的硬性要求。",
                f"岗位：{job.title}\n部门：{job.department}\n地点：{job.location}\nJD：{jd}\n补充：{notes or ''}",
                RequirementProfileAIResult,
            ),
            response_model=RequirementProfileAIResult,
            semantic_validator=validate_requirement,
        )
        result = structured.value
        previous = db.scalar(
            select(RequirementProfile)
            .where(RequirementProfile.job_id == job.id)
            .order_by(RequirementProfile.revision.desc())
        )
        revision = previous.revision + 1 if previous else 1
        if previous:
            previous.status = "archived"
        p = RequirementProfile(
            job_id=job.id,
            revision=revision,
            raw_jd=jd,
            raw_notes=notes,
            must_have_json=[x.model_dump() for x in result.must_have],
            preferred_json=[x.model_dump() for x in result.preferred],
            skills_json=result.skills,
            soft_skills_json=result.soft_skills,
            negative_signals_json=result.negative_signals,
            verification_questions_json=result.verification_questions,
            ai_summary=result.summary,
        )
        db.add(p)
        db.flush()
        _finish_success(db, run, profile_view(p), structured.degraded)
        return p, run
    except AIServiceError as exc:
        _finish_failure(db, run, exc)
        raise AIOperationError(exc, run.id)
    except Exception as exc:
        error = _finish_unexpected_failure(db, run.id, exc)
        raise AIOperationError(error, run.id) from exc


def generate_profile_stream(db: Session, job, notes: str | None, ai=None) -> Iterator[dict[str, Any]]:
    """Yield safe UI progress events and persist only the validated final profile."""
    ai = ai or AIService()
    jd = job.jd_text or job.description or ""
    if not jd.strip() and not (notes or "").strip():
        raise HTTPException(422, detail="请先填写岗位 JD 或业务补充，再生成招聘画像。")
    run = _start_run(
        db, task_type="requirement_generation", job_id=job.id, ai=ai,
        input_summary={"job_id": job.id, "has_extra_notes": bool(notes), "jd_length": len(jd), "extra_notes_length": len(notes or "")},
    )

    def events() -> Iterator[dict[str, Any]]:
        yield {"event": "run", "run_id": run.id, "message": "已创建生成任务"}
        try:
            for event in ai.stream_structured(
                db=db, run=run,
                messages=_messages("你是招聘需求分析助手。不得补充用户未提供的硬性要求。", f"岗位：{job.title}\n部门：{job.department}\n地点：{job.location}\nJD：{jd}\n补充：{notes or ''}", RequirementProfileAIResult),
                response_model=RequirementProfileAIResult, semantic_validator=validate_requirement,
            ):
                if event["event"] != "result":
                    yield event
                    continue
                structured: StructuredResult = event["result"]
                result = structured.value
                previous = db.scalar(select(RequirementProfile).where(RequirementProfile.job_id == job.id).order_by(RequirementProfile.revision.desc()))
                revision = previous.revision + 1 if previous else 1
                if previous: previous.status = "archived"
                profile = RequirementProfile(job_id=job.id, revision=revision, raw_jd=jd, raw_notes=notes, must_have_json=[item.model_dump() for item in result.must_have], preferred_json=[item.model_dump() for item in result.preferred], skills_json=result.skills, soft_skills_json=result.soft_skills, negative_signals_json=result.negative_signals, verification_questions_json=result.verification_questions, ai_summary=result.summary)
                db.add(profile); db.flush()
                _finish_success(db, run, profile_view(profile), structured.degraded)
                yield {"event": "result", "profile": profile_view(profile, run)}
                yield {"event": "done", "status": run.status}
        except AIServiceError as exc:
            _finish_failure(db, run, exc)
            yield {"event": "error", **AIOperationError(exc, run.id).body()}
        except Exception as exc:
            error = _finish_unexpected_failure(db, run.id, exc)
            yield {"event": "error", **AIOperationError(error, run.id).body()}

    return events()


def create_assessment(db: Session, app: Application, ai=None):
    ai = ai or AIService()
    profile = db.scalar(
        select(RequirementProfile)
        .where(
            RequirementProfile.job_id == app.job_id,
            RequirementProfile.status == "confirmed",
        )
        .order_by(RequirementProfile.revision.desc())
    )
    if not profile:
        raise HTTPException(422, detail="请先确认岗位招聘画像。")
    resume = db.scalar(
        select(Resume)
        .where(Resume.application_id == app.id, Resume.parse_status == "confirmed")
        .order_by(Resume.created_at.desc())
    )
    if not resume or not resume.extracted_text:
        raise HTTPException(422, detail="候选人没有已确认的可分析简历。")
    run = _start_run(
        db,
        task_type="resume_assessment",
        application=app,
        ai=ai,
        input_summary={
            "application_id": app.id,
            "candidate_id": app.candidate_id,
            "job_id": app.job_id,
            "profile_id": profile.id,
            "resume_id": resume.id,
            "resume_length": len(resume.extracted_text),
        },
    )
    try:
        structured: StructuredResult = ai.generate_structured(
            db=db,
            run=run,
            task_type="resume_assessment",
            messages=_messages(
                "你是简历评估助手。只能根据简历证据判断；未提及必须是 unknown，不得自动淘汰。recommendation 必须且只能为 recommend、review 或 reject，绝不能填中文解释句。strengths.status 必须为 met 或 partial；gaps.status 必须为 missing、partial 或 unknown。",
                f"招聘画像：{profile_view(profile)}\n候选人：{app.candidate.name}\n简历：{resume.extracted_text}",
                AssessmentResult,
            ),
            response_model=AssessmentResult,
            semantic_validator=validate_assessment,
        )
        result = structured.value
        a = ResumeAssessment(
            application_id=app.id,
            candidate_id=app.candidate_id,
            job_id=app.job_id,
            requirement_profile_id=profile.id,
            resume_id=resume.id,
            recommendation=result.recommendation,
            overall_score=result.overall_score,
            strengths_json=[x.model_dump() for x in result.strengths],
            gaps_json=[x.model_dump() for x in result.gaps],
            risks_json=result.risks,
            missing_information_json=result.missing_information,
            verification_questions_json=result.verification_questions,
            summary=result.summary,
            model_name=ai.model_name,
            prompt_version=PROMPT_VERSION,
        )
        db.add(a)
        db.flush()
        _finish_success(db, run, assessment_view(a), structured.degraded)
        return a, run
    except AIServiceError as exc:
        _finish_failure(db, run, exc)
        raise AIOperationError(exc, run.id)
    except Exception as exc:
        error = _finish_unexpected_failure(db, run.id, exc)
        raise AIOperationError(error, run.id) from exc


def create_todo_tool(db: Session, call: AgentToolCall, data: ToolApproval):
    if call.approval_status != "pending_approval" or call.status != "proposed":
        raise HTTPException(409, detail="该 Tool Call 已处理或不可审批。")
    run = db.get(AgentRun, call.agent_run_id)
    app = db.get(Application, run.application_id if run else None)
    if not app:
        raise HTTPException(404, detail="关联招聘申请不存在。")
    args = {**(call.arguments_json or {}), **data.model_dump(exclude_none=True)}
    task = Task(
        application_id=app.id,
        title=args.get("title", "跟进候选人"),
        description=args.get("description"),
        due_at=args.get("due_at"),
        priority=args.get("priority", Priority.NORMAL),
    )
    db.add(task)
    db.flush()
    call.approval_status = "approved"
    call.status = "executed"
    call.approved_at = datetime.now()
    call.result_json = {"task_id": task.id}
    db.commit()
    return task


def copilot(db: Session, app: Application, ai=None):
    ai = ai or AIService()
    resume = db.scalar(
        select(Resume)
        .where(Resume.application_id == app.id, Resume.parse_status == "confirmed")
        .order_by(Resume.created_at.desc())
    )
    if not resume or not resume.extracted_text:
        raise HTTPException(422, detail="候选人没有已确认的可分析简历。")
    memories = db.scalars(
        select(Memory)
        .where(
            Memory.entity_type == "candidate",
            Memory.entity_id == app.candidate_id,
            Memory.deleted_at.is_(None),
        )
        .order_by(Memory.importance.desc())
    ).all()
    assessment = db.scalars(
        select(ResumeAssessment)
        .where(ResumeAssessment.application_id == app.id)
        .order_by(ResumeAssessment.created_at.desc())
    ).first()
    context = {
        "candidate": {
            "name": app.candidate.name,
            "school": app.candidate.school,
            "major": app.candidate.major,
        },
        "job": {"title": app.job.title},
        "stage": app.stage.value,
        "assessment": assessment_view(assessment) if assessment else None,
        "memories": [memory_view(m) for m in memories],
        "todos": [task_view(t) for t in app.tasks if t.status == TaskStatus.TODO],
    }
    run = _start_run(
        db,
        task_type="candidate_copilot",
        application=app,
        ai=ai,
        input_summary={
            "application_id": app.id,
            "candidate_id": app.candidate_id,
            "job_id": app.job_id,
            "resume_length": len(resume.extracted_text),
            "has_assessment": bool(assessment),
            "memory_count": len(memories),
        },
    )
    try:
        structured: StructuredResult = ai.generate_structured(
            db=db,
            run=run,
            task_type="candidate_copilot",
            messages=_messages(
                "你是招聘 Copilot。基于已有上下文总结候选人；未知信息不得推断为不符合。strengths.status 必须为 met 或 partial。",
                str(context),
                CopilotAIResult,
            ),
            response_model=CopilotAIResult,
            semantic_validator=validate_copilot,
        )
        result = structured.value
        output = {
            "summary": result.summary,
            "current_status": app.stage.value,
            "strengths": [x.model_dump() for x in result.strengths],
            "risks": result.risks,
            "missing_information": result.missing_information,
            "memory_highlights": [memory_view(m) for m in memories],
            "next_actions": [],
        }
        call = AgentToolCall(
            agent_run_id=run.id,
            tool_name="create_todo",
            arguments_json={
                "title": "跟进候选人",
                "description": (
                    result.verification_questions[0]
                    if result.verification_questions
                    else "根据 Copilot 建议跟进候选人"
                ),
            },
            risk_level="medium",
            requires_approval=True,
            approval_status="pending_approval",
            status="proposed",
        )
        db.add(call)
        db.flush()
        output["next_actions"] = [
            {
                "action_type": "create_todo",
                "reason": "需要人工确认下一步跟进",
                "suggested_payload": call.arguments_json,
                "tool_call_id": call.id,
            }
        ]
        _finish_success(db, run, output, structured.degraded)
        output["_ai"] = _ai_meta(run)
        return run, output
    except AIServiceError as exc:
        _finish_failure(db, run, exc)
        # Copilot is advisory: preserve normal UI flow with a visibly degraded empty result.
        return run, {
            "summary": None,
            "current_status": app.stage.value,
            "strengths": [],
            "risks": [],
            "missing_information": [],
            "memory_highlights": [memory_view(m) for m in memories],
            "next_actions": [],
            "_ai": _ai_meta(run),
        }
    except Exception as exc:
        _finish_unexpected_failure(db, run.id, exc)
        run = db.get(AgentRun, run.id)
        return run, {
            "summary": None, "current_status": app.stage.value, "strengths": [], "risks": [],
            "missing_information": [], "memory_highlights": [memory_view(m) for m in memories],
            "next_actions": [], "_ai": _ai_meta(run),
        }
