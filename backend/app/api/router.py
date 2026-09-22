from __future__ import annotations
from datetime import date, datetime, time, timedelta
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload
from app.core.database import get_db
from app.core.enums import (
    BlockedBy,
    InterviewResult,
    InterviewStatus,
    JobStatus,
    PipelineStage,
    TaskStatus,
)
from app.models import Activity, AgentRun, AgentToolCall, Application, Candidate, Interview, Job, Memory, RequirementProfile, Resume, ResumeAssessment, Task
from app.schemas import (
    ApplicationCreate,
    BlockedChange,
    CandidateIn,
    CandidatePatch,
    InterviewAvailabilityPatch,
    InterviewCancel,
    InterviewCreate,
    InterviewFeedback,
    InterviewSchedule,
    JobIn,
    JobPatch,
    NoteIn,
    ReasonIn,
    RecruitmentInfo,
    ResumeConfirm,
    StageChange,
    TaskIn,
    TaskPatch,
    MemoryIn, RequirementGenerate, RequirementProfilePatch, ToolApproval,
)
from app.services.service import *
from app.services.resume_import_service import ResumeImportService
from app.services.agent_service import assessment_view, copilot, create_assessment, create_todo_tool, generate_profile, memory_view, profile_view

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    now = datetime.now()
    start = datetime.combine(now.date(), time.min)
    end = start + timedelta(days=1)
    active = list(
        db.scalars(
            select(Application).where(Application.stage.in_(NORMAL_STAGES))
        ).all()
    )
    return {
        "active_job_count": db.scalar(
            select(func.count()).select_from(Job).where(Job.status == JobStatus.ACTIVE)
        )
        or 0,
        "active_application_count": len(active),
        "today_task_count": db.scalar(
            select(func.count())
            .select_from(Task)
            .where(
                Task.status == TaskStatus.TODO, Task.due_at >= start, Task.due_at < end
            )
        )
        or 0,
        "overdue_task_count": db.scalar(
            select(func.count())
            .select_from(Task)
            .where(Task.status == TaskStatus.TODO, Task.due_at < now)
        )
        or 0,
        "today_interview_count": db.scalar(
            select(func.count())
            .select_from(Interview)
            .where(
                Interview.status == InterviewStatus.SCHEDULED,
                Interview.scheduled_start_at >= start,
                Interview.scheduled_start_at < end,
            )
        )
        or 0,
    }


@router.get("/dashboard/tasks")
def dashboard_tasks(limit: int = 10, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Task)
        .join(Task.application)
        .options(
            selectinload(Task.application).selectinload(Application.candidate),
            selectinload(Task.application).selectinload(Application.job),
        )
        .where(Task.status == TaskStatus.TODO)
        .order_by(Task.due_at.is_(None), Task.due_at)
        .limit(limit)
    ).all()
    return [
        {
            **task_view(t),
            "candidate_id": t.application.candidate_id,
            "candidate_name": t.application.candidate.name,
            "job_id": t.application.job_id,
            "job_title": t.application.job.title,
            "application_id": t.application_id,
            "stage": t.application.stage,
            "blocked_by": t.application.blocked_by,
        }
        for t in rows
    ]


@router.get("/dashboard/interviews/today")
def today_interviews(db: Session = Depends(get_db)):
    start = datetime.combine(date.today(), time.min)
    end = start + timedelta(days=1)
    rows = db.scalars(
        select(Interview)
        .options(
            selectinload(Interview.application).selectinload(Application.candidate),
            selectinload(Interview.application).selectinload(Application.job),
        )
        .where(
            Interview.scheduled_start_at >= start,
            Interview.scheduled_start_at < end,
            Interview.status == InterviewStatus.SCHEDULED,
        )
        .order_by(Interview.scheduled_start_at)
    ).all()
    return [
        {
            "id": i.id,
            "application_id": i.application_id,
            "candidate_name": i.application.candidate.name,
            "job_title": i.application.job.title,
            "scheduled_start_at": as_shanghai(i.scheduled_start_at),
            "start_at": as_shanghai(i.scheduled_start_at),
            "mode": i.mode,
            "interviewer_name": i.interviewer_name,
        }
        for i in rows
    ]


@router.get("/dashboard/interviews/pending-confirmation")
def pending_interviews(db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Interview)
        .options(selectinload(Interview.application).selectinload(Application.candidate), selectinload(Interview.application).selectinload(Application.job))
        .where(Interview.status == InterviewStatus.SCHEDULED, Interview.scheduled_end_at < datetime.utcnow())
        .order_by(Interview.scheduled_end_at)
    ).all()
    return [{"id": i.id, "application_id": i.application_id, "candidate_name": i.application.candidate.name, "job_title": i.application.job.title, "round_name": i.round_name, "scheduled_end_at": as_shanghai(i.scheduled_end_at)} for i in rows]


@router.get("/dashboard/jobs")
def dashboard_jobs(db: Session = Depends(get_db)):
    return [
        job_summary(db, j)
        for j in db.scalars(select(Job).where(Job.status == JobStatus.ACTIVE)).all()
    ]


def job_summary(db: Session, job: Job):
    apps = db.scalars(
        select(Application)
        .options(selectinload(Application.tasks))
        .where(Application.job_id == job.id)
    ).all()
    now = datetime.now()
    stages = {s.value: sum(a.stage == s for a in apps) for s in NORMAL_STAGES}
    todos = [t for a in apps for t in a.tasks if t.status == TaskStatus.TODO]
    return {
        "id": job.id,
        "title": job.title,
        "department": job.department,
        "location": job.location,
        "owner_name": job.owner_name,
        "status": job.status,
        "candidate_count": len(apps),
        "active_count": sum(a.stage in NORMAL_STAGES for a in apps),
        "stage_counts": stages,
        "today_task_count": sum(
            t.due_at and t.due_at.date() == date.today() for t in todos
        ),
        "overdue_count": sum(t.due_at and t.due_at < now for t in todos),
    }


@router.get("/jobs")
def list_jobs(
    status: JobStatus | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    q = select(Job)
    q = q.where(Job.status == status) if status else q
    q = (
        q.where(or_(Job.title.contains(search), Job.department.contains(search)))
        if search
        else q
    )
    return {
        "items": [
            job_summary(db, j)
            for j in db.scalars(
                q.order_by(Job.updated_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        ],
        "page": page,
        "page_size": page_size,
    }


@router.post("/jobs", status_code=201)
def create_job(data: JobIn, db: Session = Depends(get_db)):
    job = Job(**data.model_dump())
    db.add(job)
    db.commit()
    db.refresh(job)
    return job_summary(db, job)


@router.get("/jobs/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)):
    return job_view(get_or_404(db, Job, job_id))


@router.patch("/jobs/{job_id}")
def patch_job(job_id: int, data: JobPatch, db: Session = Depends(get_db)):
    job = get_or_404(db, Job, job_id)
    [setattr(job, k, v) for k, v in data.model_dump(exclude_unset=True).items()]
    db.commit()
    return job_summary(db, job)


@router.post("/jobs/{job_id}/actions/{action}")
def job_action(job_id: int, action: str, db: Session = Depends(get_db)):
    mapping = {
        "pause": JobStatus.PAUSED,
        "resume": JobStatus.ACTIVE,
        "close": JobStatus.CLOSED,
    }
    if action not in mapping:
        raise HTTPException(404, detail="操作不存在")
    job = get_or_404(db, Job, job_id)
    job.status = mapping[action]
    db.commit()
    return job_summary(db, job)


@router.post("/jobs/{job_id}/pause")
def pause_job(job_id: int, db: Session = Depends(get_db)):
    return job_action(job_id, "pause", db)


@router.post("/jobs/{job_id}/resume")
def resume_job(job_id: int, db: Session = Depends(get_db)):
    return job_action(job_id, "resume", db)


@router.post("/jobs/{job_id}/close")
def close_job(job_id: int, db: Session = Depends(get_db)):
    return job_action(job_id, "close", db)


@router.get("/jobs/{job_id}/stats")
def job_stats(job_id: int, db: Session = Depends(get_db)):
    job = get_or_404(db, Job, job_id)
    item = job_summary(db, job)
    return {
        "total_candidates": item["candidate_count"],
        "active_candidates": item["active_count"],
        "today_tasks": item["today_task_count"],
        "overdue_tasks": item["overdue_count"],
        "today_interviews": db.scalar(
            select(func.count())
            .select_from(Interview)
            .join(Application, Interview.application_id == Application.id)
            .where(
                Application.job_id == job_id,
                Interview.scheduled_start_at >= datetime.combine(date.today(), time.min),
                Interview.scheduled_start_at
                < datetime.combine(date.today() + timedelta(days=1), time.min),
            )
        )
        or 0,
        "offer_count": item["stage_counts"]["offer"],
        "stage_counts": item["stage_counts"],
    }


@router.post("/jobs/{job_id}/candidates", status_code=201)
def add_candidate(job_id: int, data: ApplicationCreate, db: Session = Depends(get_db)):
    job = get_or_404(db, Job, job_id)
    if job.status != JobStatus.ACTIVE:
        raise HTTPException(422, detail="暂停或已关闭的岗位不能新增候选人。")
    values = data.model_dump()
    values["source"] = values.get("source") or "manual"
    c = Candidate(**values)
    db.add(c)
    db.flush()
    a = Application(job_id=job_id, candidate_id=c.id)
    db.add(a)
    db.flush()
    activity(db, a.id, "APPLICATION_CREATED", "候选人加入岗位")
    db.commit()
    db.refresh(a)
    return app_card(a)


@router.post("/jobs/{job_id}/resume-imports/preview")
async def preview_resume(
    job_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    content = await file.read()
    return ResumeImportService(db).preview(job_id, file.filename or "", file.content_type, content)


@router.post("/resume-imports/{resume_id}/confirm")
def confirm_resume(resume_id: int, data: ResumeConfirm, db: Session = Depends(get_db)):
    return ResumeImportService(db).confirm(resume_id, data)


@router.delete("/resume-imports/{resume_id}", status_code=204)
def cancel_resume(resume_id: int, db: Session = Depends(get_db)):
    ResumeImportService(db).cancel(resume_id)


@router.get("/resumes/{resume_id}/file")
def resume_file(resume_id: int, db: Session = Depends(get_db)):
    service = ResumeImportService(db)
    path = service.file_path(resume_id)
    return FileResponse(path, media_type="application/pdf", filename=path.name)


@router.get("/jobs/{job_id}/applications")
def job_applications(
    job_id: int,
    stage: PipelineStage | None = None,
    blocked_by: BlockedBy | None = None,
    search: str | None = None,
    risk: str | None = None,
    db: Session = Depends(get_db),
):
    get_or_404(db, Job, job_id)
    q = (
        select(Application)
        .options(selectinload(Application.candidate), selectinload(Application.tasks))
        .where(Application.job_id == job_id)
    )
    q = q.where(Application.stage == stage) if stage else q
    q = q.where(Application.blocked_by == blocked_by) if blocked_by else q
    q = (
        q.join(Application.candidate).where(Candidate.name.contains(search))
        if search
        else q
    )
    cards = [app_card(a) for a in db.scalars(q).all()]
    return [
        x
        for x in cards
        if not risk
        or (risk == "overdue" and x["is_overdue"])
        or (risk == "no_task" and not x["primary_task"])
    ]


@router.get("/jobs/{job_id}/kanban")
def kanban(job_id: int, db: Session = Depends(get_db)):
    cards = job_applications(job_id, db=db)
    return {
        stage.value: [c for c in cards if c["stage"] == stage]
        for stage in NORMAL_STAGES
    }


@router.post("/candidates", status_code=201)
def create_candidate(data: CandidateIn, db: Session = Depends(get_db)):
    values = data.model_dump()
    values["source"] = values.get("source") or "manual"
    c = Candidate(**values)
    db.add(c)
    db.commit()
    db.refresh(c)
    return candidate_view(c)


@router.get("/candidates")
def list_candidates(
    search: str | None = None,
    school: str | None = None,
    job_id: int | None = None,
    stage: PipelineStage | None = None,
    archived: bool = False,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
):
    q = select(Candidate).options(
        selectinload(Candidate.applications).selectinload(Application.job)
    )
    q = (
        q.where(or_(Candidate.name.contains(search), Candidate.school.contains(search)))
        if search
        else q
    )
    q = q.where(Candidate.school.contains(school)) if school else q
    q = q.join(Candidate.applications).where(
        Application.archived_at.is_not(None) if archived else Application.archived_at.is_(None)
    )
    if job_id or stage:
        q = q.join(Candidate.applications).where(
            Application.job_id == job_id if job_id else True,
            Application.stage == stage if stage else True,
        )
    rows = db.scalars(q.offset((page - 1) * page_size).limit(page_size)).unique().all()
    return {
        "items": [
            {
                "id": c.id,
                "name": c.name,
                "school": c.school,
                "graduation_year": c.graduation_year,
                "current_city": c.current_city,
                "applications": [
                    {
                        "id": a.id,
                        "job_id": a.job_id,
                        "job_title": a.job.title,
                        "stage": a.stage,
                        "blocked_by": a.blocked_by,
                        "updated_at": a.updated_at,
                    }
                    for a in c.applications
                    if (a.archived_at is not None) == archived
                ],
            }
            for c in rows
        ],
        "page": page,
        "page_size": page_size,
    }


@router.get("/candidates/{candidate_id}")
def get_candidate(candidate_id: int, db: Session = Depends(get_db)):
    return candidate_view(get_or_404(db, Candidate, candidate_id))


@router.patch("/candidates/{candidate_id}")
def patch_candidate(
    candidate_id: int, data: CandidatePatch, db: Session = Depends(get_db)
):
    c = get_or_404(db, Candidate, candidate_id)
    [setattr(c, k, v) for k, v in data.model_dump(exclude_unset=True).items()]
    db.commit()
    return candidate_view(c)


@router.get("/candidates/{candidate_id}/applications")
def candidate_apps(candidate_id: int, db: Session = Depends(get_db)):
    c = get_or_404(db, Candidate, candidate_id)
    return [
        {
            "application_id": a.id,
            "job_id": a.job_id,
            "job_title": a.job.title,
            "stage": a.stage,
            "blocked_by": a.blocked_by,
            "updated_at": a.updated_at,
        }
        for a in db.scalars(
            select(Application)
            .options(selectinload(Application.job))
            .where(Application.candidate_id == c.id)
        ).all()
    ]


@router.get("/applications/{application_id}")
def application_detail(application_id: int, db: Session = Depends(get_db)):
    a = db.scalar(
        select(Application)
        .options(
            selectinload(Application.candidate),
            selectinload(Application.job),
            selectinload(Application.tasks),
            selectinload(Application.interviews),
            selectinload(Application.activities),
            selectinload(Application.resumes),
        )
        .where(Application.id == application_id)
    )
    if not a:
        raise HTTPException(404, detail="资源不存在")
    return {
        "id": a.id,
        "stage": a.stage,
        "current_interview_id": a.current_interview_id,
        "current_interview": interview_view(next((i for i in a.interviews if i.id == a.current_interview_id), None)),
        "blocked_by": a.blocked_by,
        "waiting_note": a.waiting_note,
        "priority": a.priority,
        "candidate": candidate_view(a.candidate),
        "job": job_view(a.job),
        "recruitment_info": {
            "earliest_start_date": a.earliest_start_date,
            "internship_months": a.internship_months,
            "days_per_week": a.days_per_week,
            "salary_accepted": a.salary_accepted,
            "relocation_required": a.relocation_required,
            "relocation_accepted": a.relocation_accepted,
            "commute_minutes": a.commute_minutes,
        },
        "tasks": [
            task_view(t)
            for t in sorted(a.tasks, key=lambda x: x.created_at, reverse=True)
        ],
        "interviews": [interview_view(i) for i in sorted(a.interviews, key=lambda item: (item.round_number, item.created_at))],
        "activities": [
            {
                "id": x.id,
                "type": x.type,
                "content": x.content,
                "metadata": x.metadata_,
                "created_at": x.created_at,
            }
            for x in sorted(a.activities, key=lambda x: x.created_at, reverse=True)
        ],
        "resumes": [
            {
                "id": resume.id,
                "filename": resume.original_filename,
                "created_at": resume.created_at,
                "file_url": f"/resumes/{resume.id}/file",
            }
            for resume in sorted(a.resumes, key=lambda item: item.created_at, reverse=True)
            if resume.parse_status == "confirmed"
        ],
    }


@router.post("/applications/{application_id}/change-stage")
def api_change_stage(
    application_id: int, data: StageChange, db: Session = Depends(get_db)
):
    a = get_or_404(db, Application, application_id)
    change_stage(db, a, data.target_stage, data.force)
    db.commit()
    return app_card(a)


@router.post("/applications/{application_id}/set-blocked-by")
def set_blocked(
    application_id: int, data: BlockedChange, db: Session = Depends(get_db)
):
    a = get_or_404(db, Application, application_id)
    if data.blocked_by == BlockedBy.SYSTEM and not data.waiting_note:
        raise HTTPException(422, detail="请输入自定义等待说明。")
    before = a.blocked_by
    a.blocked_by = data.blocked_by
    a.waiting_note = data.waiting_note if data.blocked_by == BlockedBy.SYSTEM else None
    activity(
        db,
        a.id,
        "BLOCKED_BY_CHANGED",
        f"等待对象：{before.value} → {data.waiting_note or data.blocked_by.value}",
        {"waiting_note": a.waiting_note},
    )
    db.commit()
    return {"id": a.id, "blocked_by": a.blocked_by, "waiting_note": a.waiting_note}


@router.post("/applications/{application_id}/archive")
def archive_application(application_id: int, db: Session = Depends(get_db)):
    a = get_or_404(db, Application, application_id)
    if not a.archived_at:
        a.archived_at = datetime.now()
        activity(db, a.id, "APPLICATION_ARCHIVED", "归档候选人流程")
        db.commit()
    return {"id": a.id, "archived": True, "archived_at": a.archived_at}


@router.post("/applications/{application_id}/unarchive")
def unarchive_application(application_id: int, db: Session = Depends(get_db)):
    a = get_or_404(db, Application, application_id)
    if a.archived_at:
        a.archived_at = None
        activity(db, a.id, "APPLICATION_UNARCHIVED", "恢复候选人流程")
        db.commit()
    return {"id": a.id, "archived": False}


@router.patch("/applications/{application_id}/recruitment-info")
def recruitment(
    application_id: int, data: RecruitmentInfo, db: Session = Depends(get_db)
):
    a = get_or_404(db, Application, application_id)
    changed = data.model_dump(exclude_unset=True)
    [setattr(a, k, v) for k, v in changed.items()]
    activity(db, a.id, "RECRUITMENT_INFO_UPDATED", "更新招聘确认信息", changed)
    db.commit()
    return changed


@router.post("/applications/{application_id}/reject")
def reject(application_id: int, data: ReasonIn, db: Session = Depends(get_db)):
    a = get_or_404(db, Application, application_id)
    a.stage = PipelineStage.REJECTED
    a.blocked_by = BlockedBy.NONE
    a.rejection_reason = data.reason
    [
        setattr(t, "status", TaskStatus.CANCELLED)
        for t in a.tasks
        if t.status == TaskStatus.TODO
    ]
    activity(db, a.id, "APPLICATION_REJECTED", f"淘汰候选人：{data.reason}")
    db.commit()
    return {"id": a.id, "stage": a.stage}


@router.post("/applications/{application_id}/withdraw")
def withdraw(application_id: int, data: ReasonIn, db: Session = Depends(get_db)):
    a = get_or_404(db, Application, application_id)
    a.stage = PipelineStage.WITHDRAWN
    a.blocked_by = BlockedBy.NONE
    a.rejection_reason = data.reason
    activity(db, a.id, "APPLICATION_WITHDRAWN", f"候选人退出：{data.reason}")
    db.commit()
    return {"id": a.id, "stage": a.stage}


@router.post("/applications/{application_id}/hold")
def hold(application_id: int, data: ReasonIn, db: Session = Depends(get_db)):
    a = get_or_404(db, Application, application_id)
    a.stage_before_hold = a.stage
    a.stage = PipelineStage.ON_HOLD
    activity(db, a.id, "APPLICATION_HELD", f"暂缓候选人：{data.reason}")
    db.commit()
    return {"id": a.id, "stage": a.stage}


@router.post("/applications/{application_id}/resume")
def resume(application_id: int, db: Session = Depends(get_db)):
    a = get_or_404(db, Application, application_id)
    a.stage = a.stage_before_hold or PipelineStage.CONTACTING
    a.stage_before_hold = None
    activity(db, a.id, "APPLICATION_RESUMED", "恢复候选人流程")
    db.commit()
    return {"id": a.id, "stage": a.stage}


@router.post("/applications/{application_id}/tasks", status_code=201)
def create_task(application_id: int, data: TaskIn, db: Session = Depends(get_db)):
    get_or_404(db, Application, application_id)
    t = Task(application_id=application_id, **data.model_dump())
    db.add(t)
    db.flush()
    activity(db, application_id, "TASK_CREATED", f"创建待办：{t.title}")
    db.commit()
    return task_view(t)


@router.get("/applications/{application_id}/tasks")
def application_tasks(
    application_id: int, status: TaskStatus | None = None, db: Session = Depends(get_db)
):
    get_or_404(db, Application, application_id)
    q = select(Task).where(Task.application_id == application_id)
    q = q.where(Task.status == status) if status else q
    return [task_view(t) for t in db.scalars(q.order_by(Task.created_at.desc())).all()]


@router.patch("/tasks/{task_id}")
def patch_task(task_id: int, data: TaskPatch, db: Session = Depends(get_db)):
    t = get_or_404(db, Task, task_id)
    [setattr(t, k, v) for k, v in data.model_dump(exclude_unset=True).items()]
    activity(db, t.application_id, "TASK_UPDATED", f"修改待办：{t.title}")
    db.commit()
    return task_view(t)


@router.post("/tasks/{task_id}/{action}")
def task_action(task_id: int, action: str, db: Session = Depends(get_db)):
    t = get_or_404(db, Task, task_id)
    if action == "complete":
        t.status = TaskStatus.DONE
        t.completed_at = datetime.now()
        typ = "TASK_COMPLETED"
        msg = f"完成待办：{t.title}"
    elif action == "cancel":
        t.status = TaskStatus.CANCELLED
        typ = "TASK_CANCELLED"
        msg = f"取消待办：{t.title}"
    else:
        raise HTTPException(404, detail="操作不存在")
    activity(db, t.application_id, typ, msg)
    db.commit()
    return task_view(t)


@router.get("/tasks")
def all_tasks(
    status: TaskStatus | None = None,
    due: str | None = None,
    overdue: bool = False,
    job_id: int | None = None,
    candidate_id: int | None = None,
    db: Session = Depends(get_db),
):
    q = (
        select(Task)
        .join(Task.application)
        .options(
            selectinload(Task.application).selectinload(Application.candidate),
            selectinload(Task.application).selectinload(Application.job),
        )
    )
    q = q.where(Task.status == status) if status else q
    q = q.where(Application.job_id == job_id) if job_id else q
    q = q.where(Application.candidate_id == candidate_id) if candidate_id else q
    now = datetime.now()
    start = datetime.combine(now.date(), time.min)
    end = start + timedelta(days=1)
    q = q.where(Task.due_at >= start, Task.due_at < end) if due == "today" else q
    q = q.where(Task.due_at < now, Task.status == TaskStatus.TODO) if overdue else q
    return [
        {
            **task_view(t),
            "application_id": t.application_id,
            "candidate_name": t.application.candidate.name,
            "job_title": t.application.job.title,
            "stage": t.application.stage,
        }
        for t in db.scalars(q.order_by(Task.due_at)).all()
    ]


@router.post("/applications/{application_id}/interviews", status_code=201)
def create_interview(
    application_id: int, data: InterviewCreate, db: Session = Depends(get_db)
):
    i = InterviewService(db).create_round(application_id, **data.model_dump())
    db.commit()
    return interview_view(i)


@router.get("/applications/{application_id}/interviews")
def application_interviews(application_id: int, db: Session = Depends(get_db)):
    get_or_404(db, Application, application_id)
    return [
        interview_view(i)
        for i in db.scalars(
            select(Interview)
            .where(Interview.application_id == application_id)
            .order_by(Interview.round_number, Interview.created_at)
        ).all()
    ]


@router.patch("/interviews/{interview_id}")
def patch_interview(
    interview_id: int, data: InterviewAvailabilityPatch, db: Session = Depends(get_db)
):
    i = InterviewService(db).update_availability(interview_id, data.model_dump(exclude_unset=True))
    db.commit()
    return interview_view(i)


@router.get("/interviews/{interview_id}")
def get_interview(interview_id: int, db: Session = Depends(get_db)):
    return interview_view(get_or_404(db, Interview, interview_id))

@router.post("/interviews/{interview_id}/schedule")
def schedule_interview(interview_id: int, data: InterviewSchedule, db: Session = Depends(get_db)):
    i = InterviewService(db).schedule(interview_id, data.model_dump())
    db.commit()
    return interview_view(i)

@router.post("/interviews/{interview_id}/reschedule")
def reschedule_interview(interview_id: int, data: InterviewSchedule, db: Session = Depends(get_db)):
    i = InterviewService(db).schedule(interview_id, data.model_dump(), reschedule=True)
    db.commit()
    return interview_view(i)

@router.post("/interviews/{interview_id}/complete")
def complete_interview(interview_id: int, db: Session = Depends(get_db)):
    i = InterviewService(db).complete(interview_id)
    db.commit()
    return interview_view(i)

@router.post("/interviews/{interview_id}/feedback")
def feedback_interview(interview_id: int, data: InterviewFeedback, db: Session = Depends(get_db)):
    i = InterviewService(db).submit_feedback(interview_id, data.feedback, data.result, data.next_round_name)
    db.commit()
    return interview_view(i)

@router.post("/interviews/{interview_id}/cancel")
def cancel_interview(interview_id: int, data: InterviewCancel, db: Session = Depends(get_db)):
    i = InterviewService(db).cancel(interview_id, data.reason, data.disposition)
    db.commit()
    return interview_view(i)


@router.post("/applications/{application_id}/notes", status_code=201)
def note(application_id: int, data: NoteIn, db: Session = Depends(get_db)):
    get_or_404(db, Application, application_id)
    activity(db, application_id, "NOTE_ADDED", data.content)
    db.commit()
    return {"ok": True}


@router.get("/applications/{application_id}/activities")
def activities(application_id: int, db: Session = Depends(get_db)):
    get_or_404(db, Application, application_id)
    return [
        {
            "id": x.id,
            "type": x.type,
            "content": x.content,
            "metadata": x.metadata_,
            "created_at": x.created_at,
        }
        for x in db.scalars(
            select(Activity)
            .where(Activity.application_id == application_id)
            .order_by(Activity.created_at.desc())
        ).all()
    ]


@router.get("/search")
def search(q: str = Query(min_length=1), db: Session = Depends(get_db)):
    return {
        "candidates": [
            {"id": c.id, "name": c.name, "school": c.school}
            for c in db.scalars(
                select(Candidate).where(Candidate.name.contains(q)).limit(10)
            ).all()
        ],
        "jobs": [
            {"id": j.id, "title": j.title, "location": j.location}
            for j in db.scalars(
                select(Job).where(Job.title.contains(q)).limit(10)
            ).all()
        ],
    }


@router.post("/jobs/{job_id}/requirement-profile/generate")
def generate_requirement_profile(job_id: int, data: RequirementGenerate, db: Session = Depends(get_db)):
    return profile_view(generate_profile(db, get_or_404(db, Job, job_id), data.extra_notes))


@router.get("/jobs/{job_id}/requirement-profile")
def get_requirement_profile(job_id: int, db: Session = Depends(get_db)):
    get_or_404(db, Job, job_id)
    profile = db.scalar(select(RequirementProfile).where(RequirementProfile.job_id == job_id).order_by(RequirementProfile.revision.desc()))
    return profile_view(profile) if profile else None


@router.put("/requirement-profiles/{profile_id}")
def update_requirement_profile(profile_id: int, data: RequirementProfilePatch, db: Session = Depends(get_db)):
    profile = get_or_404(db, RequirementProfile, profile_id)
    values = data.model_dump()
    mapping = {"must_have": "must_have_json", "preferred": "preferred_json", "skills": "skills_json", "soft_skills": "soft_skills_json", "negative_signals": "negative_signals_json", "verification_questions": "verification_questions_json"}
    new_values = {"job_id": profile.job_id, "revision": profile.revision + 1, "raw_jd": profile.raw_jd, "raw_notes": profile.raw_notes, "must_have_json": profile.must_have_json, "preferred_json": profile.preferred_json, "skills_json": profile.skills_json, "soft_skills_json": profile.soft_skills_json, "negative_signals_json": profile.negative_signals_json, "verification_questions_json": profile.verification_questions_json, "ai_summary": profile.ai_summary, "status": "draft"}
    for key, value in values.items():
        if value is not None: new_values[mapping.get(key, key)] = [x.model_dump() if hasattr(x, "model_dump") else x for x in value] if key in mapping else value
    profile.status = "archived"
    current = RequirementProfile(**new_values); db.add(current); db.commit(); db.refresh(current)
    return profile_view(current)


@router.post("/requirement-profiles/{profile_id}/confirm")
def confirm_requirement_profile(profile_id: int, db: Session = Depends(get_db)):
    profile = get_or_404(db, RequirementProfile, profile_id)
    profile.status = "confirmed"; profile.confirmed_at = datetime.now()
    db.commit(); return profile_view(profile)


@router.post("/applications/{application_id}/assessment")
def application_assessment(application_id: int, db: Session = Depends(get_db)):
    app = db.scalar(select(Application).options(selectinload(Application.candidate), selectinload(Application.job)).where(Application.id == application_id))
    if not app: raise HTTPException(404, detail="资源不存在")
    return assessment_view(create_assessment(db, app))


@router.get("/applications/{application_id}/assessment")
def get_application_assessment(application_id: int, db: Session = Depends(get_db)):
    rows = db.scalars(select(ResumeAssessment).where(ResumeAssessment.application_id == application_id).order_by(ResumeAssessment.created_at.desc())).all()
    return {"latest": assessment_view(rows[0]) if rows else None, "history": [assessment_view(x) for x in rows]}


@router.post("/applications/{application_id}/assessment/regenerate")
def regenerate_application_assessment(application_id: int, db: Session = Depends(get_db)):
    return application_assessment(application_id, db)


@router.get("/candidates/{candidate_id}/memories")
def candidate_memories(candidate_id: int, db: Session = Depends(get_db)):
    get_or_404(db, Candidate, candidate_id)
    return [memory_view(x) for x in db.scalars(select(Memory).where(Memory.entity_type == "candidate", Memory.entity_id == candidate_id, Memory.deleted_at.is_(None)).order_by(Memory.created_at.desc())).all()]


@router.post("/candidates/{candidate_id}/memories", status_code=201)
def add_candidate_memory(candidate_id: int, data: MemoryIn, db: Session = Depends(get_db)):
    get_or_404(db, Candidate, candidate_id)
    memory = Memory(entity_type="candidate", entity_id=candidate_id, **data.model_dump())
    db.add(memory); db.commit(); db.refresh(memory); return memory_view(memory)


@router.put("/memories/{memory_id}")
def update_memory(memory_id: int, data: MemoryIn, db: Session = Depends(get_db)):
    memory = get_or_404(db, Memory, memory_id)
    for key, value in data.model_dump().items(): setattr(memory, key, value)
    db.commit(); return memory_view(memory)


@router.delete("/memories/{memory_id}", status_code=204)
def delete_memory(memory_id: int, db: Session = Depends(get_db)):
    memory = get_or_404(db, Memory, memory_id); memory.deleted_at = datetime.now(); db.commit()


@router.post("/applications/{application_id}/copilot")
def application_copilot(application_id: int, db: Session = Depends(get_db)):
    app = db.scalar(select(Application).options(selectinload(Application.candidate), selectinload(Application.job), selectinload(Application.tasks)).where(Application.id == application_id))
    if not app: raise HTTPException(404, detail="资源不存在")
    _, output = copilot(db, app)
    return output


@router.post("/agent/tool-calls/{tool_call_id}/approve")
def approve_tool_call(tool_call_id: int, data: ToolApproval, db: Session = Depends(get_db)):
    call = get_or_404(db, AgentToolCall, tool_call_id)
    if call.tool_name != "create_todo": raise HTTPException(422, detail="当前 Tool 不允许执行。")
    return task_view(create_todo_tool(db, call, data))
