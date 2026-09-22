from __future__ import annotations

from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from fastapi import HTTPException

from app.core.enums import Priority, TaskStatus
from app.models import AgentRun, AgentToolCall, Application, Memory, RequirementProfile, Resume, ResumeAssessment, Task
from app.schemas import AssessmentResult, RequirementGenerate, RequirementProfilePatch, ToolApproval
from app.services.ai_service import AIService, AIServiceError
from app.services.service import task_view

PROMPT_VERSION = "v1"

from pydantic import BaseModel

class RequirementProfileAIResult(BaseModel):
    must_have: list[dict] = []
    preferred: list[dict] = []
    skills: list[str] = []
    soft_skills: list[str] = []
    negative_signals: list[str] = []
    verification_questions: list[str] = []
    summary: str


def profile_view(p: RequirementProfile) -> dict:
    return {"id": p.id, "job_id": p.job_id, "revision": p.revision, "raw_jd": p.raw_jd, "raw_notes": p.raw_notes, "must_have": p.must_have_json or [], "preferred": p.preferred_json or [], "skills": p.skills_json or [], "soft_skills": p.soft_skills_json or [], "negative_signals": p.negative_signals_json or [], "verification_questions": p.verification_questions_json or [], "ai_summary": p.ai_summary, "status": p.status, "confirmed_at": p.confirmed_at, "created_at": p.created_at, "updated_at": p.updated_at}

def assessment_view(a: ResumeAssessment) -> dict:
    return {"id": a.id, "application_id": a.application_id, "candidate_id": a.candidate_id, "job_id": a.job_id, "requirement_profile_id": a.requirement_profile_id, "resume_id": a.resume_id, "recommendation": a.recommendation, "overall_score": a.overall_score, "strengths": a.strengths_json or [], "gaps": a.gaps_json or [], "risks": a.risks_json or [], "missing_information": a.missing_information_json or [], "verification_questions": a.verification_questions_json or [], "summary": a.summary, "model_name": a.model_name, "prompt_version": a.prompt_version, "created_at": a.created_at}

def memory_view(m: Memory) -> dict:
    return {"id": m.id, "entity_type": m.entity_type, "entity_id": m.entity_id, "memory_type": m.memory_type, "content": m.content, "source_type": m.source_type, "source_id": m.source_id, "importance": m.importance, "confidence": m.confidence, "created_at": m.created_at, "updated_at": m.updated_at}

def generate_profile(db: Session, job, notes: str | None, ai=None):
    ai = ai or AIService()
    run = AgentRun(agent_type="requirement_generation", job_id=job.id, model_name=ai.model_name, status="running", started_at=datetime.now(), input_json={"job_id": job.id, "extra_notes": notes})
    db.add(run); db.flush()
    try:
        result = ai.generate_structured("你是招聘需求分析助手，只输出 JSON。不得补充用户未提供的硬性要求。", f"岗位：{job.title}\n部门：{job.department}\n地点：{job.location}\nJD：{job.jd_text or job.description or ''}\n补充：{notes or ''}", RequirementProfileAIResult)
        previous = db.scalar(select(RequirementProfile).where(RequirementProfile.job_id == job.id).order_by(RequirementProfile.revision.desc()))
        revision = (previous.revision + 1) if previous else 1
        if previous: previous.status = "archived"
        p = RequirementProfile(job_id=job.id, revision=revision, raw_jd=job.jd_text or job.description, raw_notes=notes, must_have_json=result.must_have, preferred_json=result.preferred, skills_json=result.skills, soft_skills_json=result.soft_skills, negative_signals_json=result.negative_signals, verification_questions_json=result.verification_questions, ai_summary=result.summary)
        db.add(p); db.flush()
        run.status="succeeded"; run.output_json=profile_view(p); run.finished_at=datetime.now(); db.commit(); return p
    except AIServiceError as exc:
        run.status="failed"; run.error_message=f"{exc.code}: {exc}"; run.finished_at=datetime.now(); db.commit(); raise HTTPException(502, detail=run.error_message)

def create_assessment(db: Session, app: Application, ai=None):
    ai = ai or AIService()
    profile = db.scalar(select(RequirementProfile).where(RequirementProfile.job_id == app.job_id, RequirementProfile.status == "confirmed").order_by(RequirementProfile.revision.desc()))
    if not profile: raise HTTPException(422, detail="请先确认岗位招聘画像。")
    resume = db.scalar(select(Resume).where(Resume.application_id == app.id, Resume.parse_status == "confirmed").order_by(Resume.created_at.desc()))
    if not resume or not resume.extracted_text: raise HTTPException(422, detail="候选人没有已确认的可分析简历。")
    run = AgentRun(agent_type="resume_assessment", candidate_id=app.candidate_id, job_id=app.job_id, application_id=app.id, model_name=ai.model_name, status="running", started_at=datetime.now(), input_json={"application_id": app.id, "profile_id": profile.id, "resume_id": resume.id})
    db.add(run); db.flush()
    try:
        result = ai.generate_structured("你是简历评估助手。只能根据简历证据判断；未提及必须是 unknown，不得自动淘汰。只输出 JSON。", f"招聘画像：{profile_view(profile)}\n候选人：{app.candidate.name}\n简历：{resume.extracted_text}", AssessmentResult)
        a = ResumeAssessment(application_id=app.id, candidate_id=app.candidate_id, job_id=app.job_id, requirement_profile_id=profile.id, resume_id=resume.id, recommendation=result.recommendation, overall_score=result.overall_score, strengths_json=[x.model_dump() for x in result.strengths], gaps_json=[x.model_dump() for x in result.gaps], risks_json=result.risks, missing_information_json=result.missing_information, verification_questions_json=result.verification_questions, summary=result.summary, model_name=ai.model_name, prompt_version=PROMPT_VERSION)
        db.add(a); db.flush(); run.status="succeeded"; run.output_json=assessment_view(a); run.finished_at=datetime.now(); db.commit(); return a
    except AIServiceError as exc:
        run.status="failed"; run.error_message=f"{exc.code}: {exc}"; run.finished_at=datetime.now(); db.commit(); raise HTTPException(502, detail=run.error_message)

def create_todo_tool(db: Session, call: AgentToolCall, data: ToolApproval):
    if call.approval_status != "pending_approval" or call.status != "proposed": raise HTTPException(409, detail="该 Tool Call 已处理或不可审批。")
    run = db.get(AgentRun, call.agent_run_id); app = db.get(Application, run.application_id if run else None)
    if not app: raise HTTPException(404, detail="关联招聘申请不存在。")
    args = {**(call.arguments_json or {}), **data.model_dump(exclude_none=True)}
    task = Task(application_id=app.id, title=args.get("title", "跟进候选人"), description=args.get("description"), due_at=args.get("due_at"), priority=args.get("priority", Priority.NORMAL))
    db.add(task); db.flush(); call.approval_status="approved"; call.status="executed"; call.approved_at=datetime.now(); call.result_json={"task_id": task.id}; db.commit(); return task

def copilot(db: Session, app: Application, ai=None):
    ai = ai or AIService()
    resume = db.scalar(select(Resume).where(Resume.application_id == app.id, Resume.parse_status == "confirmed").order_by(Resume.created_at.desc()))
    if not resume or not resume.extracted_text:
        raise HTTPException(422, detail="候选人没有已确认的可分析简历。")
    memories = db.scalars(select(Memory).where(Memory.entity_type == "candidate", Memory.entity_id == app.candidate_id, Memory.deleted_at.is_(None)).order_by(Memory.importance.desc())).all()
    assessment = db.scalars(select(ResumeAssessment).where(ResumeAssessment.application_id == app.id).order_by(ResumeAssessment.created_at.desc())).first()
    context = {"candidate": {"name": app.candidate.name, "school": app.candidate.school, "major": app.candidate.major}, "job": {"title": app.job.title}, "stage": app.stage.value, "assessment": assessment_view(assessment) if assessment else None, "memories": [memory_view(m) for m in memories], "todos": [task_view(t) for t in app.tasks if t.status == TaskStatus.TODO]}
    run = AgentRun(agent_type="candidate_copilot", candidate_id=app.candidate_id, job_id=app.job_id, application_id=app.id, model_name=ai.model_name, status="running", started_at=datetime.now(), input_json={"application_id": app.id, "has_assessment": bool(assessment)})
    db.add(run); db.flush()
    try:
        # Copilot deliberately reuses the assessment schema and creates only one safe action.
        result = ai.generate_structured("你是招聘 Copilot。基于已有上下文总结候选人，只输出 JSON；未知信息不得推断为不符合。", str(context), AssessmentResult)
        output = {"summary": result.summary, "current_status": app.stage.value, "strengths": [x.model_dump() for x in result.strengths], "risks": result.risks, "missing_information": result.missing_information, "memory_highlights": [memory_view(m) for m in memories], "next_actions": []}
        call = AgentToolCall(agent_run_id=run.id, tool_name="create_todo", arguments_json={"title": "跟进候选人", "description": result.verification_questions[0] if result.verification_questions else "根据 Copilot 建议跟进候选人"}, risk_level="medium", requires_approval=True, approval_status="pending_approval", status="proposed")
        db.add(call); db.flush(); output["next_actions"] = [{"action_type": "create_todo", "reason": "需要人工确认下一步跟进", "suggested_payload": call.arguments_json, "tool_call_id": call.id}]
        run.status="succeeded"; run.output_json=output; run.finished_at=datetime.now(); db.commit(); return run, output
    except AIServiceError as exc:
        run.status="failed"; run.error_message=f"{exc.code}: {exc}"; run.finished_at=datetime.now(); db.commit(); raise HTTPException(502, detail=run.error_message)
