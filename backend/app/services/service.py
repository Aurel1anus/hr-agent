from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from app.core.enums import (
    BlockedBy,
    InterviewMode,
    InterviewResult,
    InterviewStatus,
    PipelineStage,
    Priority,
    TaskStatus,
)
from app.models import Activity, Application, Candidate, Interview, Job, Task

SHANGHAI = ZoneInfo("Asia/Shanghai")
INTERVIEW_STAGES = {
    PipelineStage.SCHEDULING,
    PipelineStage.INTERVIEW_SCHEDULED,
    PipelineStage.FEEDBACK_PENDING,
}
NORMAL_STAGES = [
    PipelineStage.SCREENING,
    PipelineStage.CONTACTING,
    PipelineStage.READY_TO_SUBMIT,
    PipelineStage.INTERVIEWER_REVIEW,
    PipelineStage.SCHEDULING,
    PipelineStage.INTERVIEW_SCHEDULED,
    PipelineStage.FEEDBACK_PENDING,
    PipelineStage.DECISION_PENDING,
    PipelineStage.OFFER,
]


def get_or_404(db: Session, model: Any, id: int):
    obj = db.get(model, id)
    if not obj:
        raise HTTPException(404, detail="资源不存在")
    return obj


def conflict(detail: str):
    raise HTTPException(409, detail=detail)


def activity(
    db: Session,
    application_id: int,
    type: str,
    content: str,
    metadata: dict | None = None,
):
    db.add(
        Activity(
            application_id=application_id,
            type=type,
            content=content,
            metadata_=metadata,
        )
    )


def as_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise HTTPException(422, detail="面试时间必须包含时区偏移量。")
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def as_shanghai(value: datetime | None) -> datetime | None:
    return value.replace(tzinfo=timezone.utc).astimezone(SHANGHAI) if value else None


def normalized_name(value: str) -> str:
    return " ".join(value.strip().split())


def default_round_name(n: int) -> str:
    return {1: "一面", 2: "二面", 3: "三面"}.get(n, f"第{n}轮面试")


def stage_label(stage: PipelineStage):
    return stage.value


def change_stage(
    db: Session, app: Application, target: PipelineStage, force: bool = False
):
    if target == app.stage:
        return app
    if target in INTERVIEW_STAGES or app.stage in INTERVIEW_STAGES:
        raise HTTPException(422, detail="面试阶段只能通过面试操作流转。")
    if not force and (
        app.stage not in NORMAL_STAGES
        or target not in NORMAL_STAGES
        or NORMAL_STAGES.index(target) != NORMAL_STAGES.index(app.stage) + 1
    ):
        raise HTTPException(422, detail="非正常流转请传 force=true")
    before = app.stage
    app.stage = target
    app.stage_changed_at = datetime.now()
    activity(
        db,
        app.id,
        "STAGE_CHANGED",
        f"招聘阶段：{before.value} → {target.value}",
        {"from": before.value, "to": target.value, "force": force},
    )
    return app


def task_view(t: Task):
    return {
        "id": t.id,
        "title": t.title,
        "description": t.description,
        "due_at": as_shanghai(t.due_at),
        "status": t.status,
        "priority": t.priority,
        "completed_at": as_shanghai(t.completed_at),
        "is_overdue": bool(
            t.status == TaskStatus.TODO and t.due_at and t.due_at < datetime.utcnow()
        ),
    }


def job_view(j: Job):
    return {
        "id": j.id,
        "title": j.title,
        "department": j.department,
        "location": j.location,
        "salary_min": j.salary_min,
        "salary_max": j.salary_max,
        "description": j.description,
        "status": j.status,
        "owner_name": j.owner_name,
        "created_at": as_shanghai(j.created_at),
        "updated_at": as_shanghai(j.updated_at),
    }


def candidate_view(c: Candidate):
    return {
        "id": c.id,
        "name": c.name,
        "phone": c.phone,
        "email": c.email,
        "school": c.school,
        "major": c.major,
        "highest_degree": c.highest_degree,
        "graduation_year": c.graduation_year,
        "current_city": c.current_city,
        "source": c.source,
        "resume_url": c.resume_url,
        "created_at": as_shanghai(c.created_at),
        "updated_at": as_shanghai(c.updated_at),
    }


def interview_view(i: Interview | None):
    if not i:
        return None
    return {
        "id": i.id,
        "application_id": i.application_id,
        "round_number": i.round_number,
        "round_name": i.round_name,
        "status": i.status,
        "candidate_availability": i.candidate_availability,
        "interviewer_availability": i.interviewer_availability,
        "scheduled_start_at": as_shanghai(i.scheduled_start_at),
        "scheduled_end_at": as_shanghai(i.scheduled_end_at),
        "interviewer_name": i.interviewer_name,
        "mode": i.mode,
        "location": i.location,
        "meeting_url": i.meeting_url,
        "feedback": i.feedback,
        "result": i.result,
        "cancel_reason": i.cancel_reason,
        "created_at": as_shanghai(i.created_at),
        "updated_at": as_shanghai(i.updated_at),
    }


def app_card(app: Application):
    todos = [t for t in app.tasks if t.status == TaskStatus.TODO]
    todos.sort(
        key=lambda t: (
            {Priority.HIGH: 0, Priority.NORMAL: 1, Priority.LOW: 2}[t.priority],
            t.due_at or datetime.max,
        )
    )
    primary = todos[0] if todos else None
    current = next(
        (i for i in app.interviews if i.id == app.current_interview_id), None
    )
    return {
        "application_id": app.id,
        "candidate_id": app.candidate_id,
        "candidate_name": app.candidate.name,
        "school": app.candidate.school,
        "graduation_year": app.candidate.graduation_year,
        "stage": app.stage,
        "blocked_by": app.blocked_by,
        "primary_task": primary.title if primary else None,
        "task_due_at": as_shanghai(primary.due_at) if primary else None,
        "is_overdue": bool(
            primary and primary.due_at and primary.due_at < datetime.utcnow()
        ),
        "stage_changed_at": as_shanghai(app.stage_changed_at),
        "current_interview": interview_view(current),
    }


class InterviewService:
    def __init__(self, db: Session):
        self.db = db

    def _app(self, id: int):
        obj = self.db.scalar(
            select(Application)
            .options(
                selectinload(Application.job),
                selectinload(Application.interviews),
                selectinload(Application.tasks),
                selectinload(Application.candidate),
            )
            .where(Application.id == id)
            .with_for_update()
        )
        if not obj:
            raise HTTPException(404, detail="资源不存在")
        return obj

    def _interview(self, id: int):
        obj = self.db.scalar(
            select(Interview)
            .options(
                selectinload(Interview.application).selectinload(Application.job),
                selectinload(Interview.application).selectinload(
                    Application.interviews
                ),
                selectinload(Interview.application).selectinload(Application.tasks),
            )
            .where(Interview.id == id)
            .with_for_update()
        )
        if not obj:
            raise HTTPException(404, detail="资源不存在")
        return obj

    def create_round(
        self,
        application_id: int,
        round_name: str,
        candidate_availability: str | None = None,
        interviewer_availability: str | None = None,
    ):
        app = self._app(application_id)
        if app.stage != PipelineStage.INTERVIEWER_REVIEW or app.current_interview_id:
            conflict("候选人当前状态已变化，请刷新后重试。")
        n = max((i.round_number for i in app.interviews), default=0) + 1
        i = Interview(
            application_id=app.id,
            round_number=n,
            round_name=round_name.strip() or default_round_name(n),
            candidate_availability=candidate_availability,
            interviewer_availability=interviewer_availability,
            status=InterviewStatus.SCHEDULING,
        )
        self.db.add(i)
        self.db.flush()
        app.current_interview_id = i.id
        app.stage = PipelineStage.SCHEDULING
        app.blocked_by = BlockedBy.CANDIDATE
        app.waiting_note = None
        app.stage_changed_at = datetime.now()
        activity(
            self.db,
            app.id,
            "INTERVIEW_CREATED",
            f"创建{i.round_name}",
            {"interview_id": i.id, "round_number": n},
        )
        return i

    def update_availability(self, id: int, values: dict):
        i = self._interview(id)
        if (
            i.status != InterviewStatus.SCHEDULING
            or i.application.current_interview_id != i.id
        ):
            conflict("当前面试不处于约面中，无法更新可用时间。")
        for k, v in values.items():
            setattr(i, k, v)
        activity(
            self.db,
            i.application_id,
            "INTERVIEW_AVAILABILITY_UPDATED",
            f"更新{i.round_name}可用时间",
            {"interview_id": i.id, **values},
        )
        return i

    def _validate_schedule(
        self,
        mode: InterviewMode,
        location: str | None,
        url: str | None,
        start: datetime,
        end: datetime,
    ):
        if end <= start:
            raise HTTPException(422, detail="结束时间必须晚于开始时间。")
        if mode == InterviewMode.ONLINE and not (url or "").strip():
            raise HTTPException(422, detail="线上面试必须填写会议链接。")
        if mode == InterviewMode.OFFLINE and not (location or "").strip():
            raise HTTPException(422, detail="线下面试必须填写地点。")

    def _check_conflict(self, i: Interview, name: str, start: datetime, end: datetime):
        norm = normalized_name(name).lower()
        rows = self.db.scalars(
            select(Interview).where(
                Interview.status == InterviewStatus.SCHEDULED,
                Interview.id != i.id,
                Interview.scheduled_start_at < end,
                Interview.scheduled_end_at > start,
            )
        ).all()
        if any(normalized_name(x.interviewer_name or "").lower() == norm for x in rows):
            conflict(f"{name} 在该时间段已有面试。")

    def schedule(self, id: int, values: dict, reschedule: bool = False):
        i = self._interview(id)
        app = i.application
        expected = (
            InterviewStatus.SCHEDULED if reschedule else InterviewStatus.SCHEDULING
        )
        if i.status != expected or app.current_interview_id != i.id:
            conflict("候选人当前状态已变化，请刷新后重试。")
        start, end = as_utc_naive(values["scheduled_start_at"]), as_utc_naive(
            values["scheduled_end_at"]
        )
        self._validate_schedule(
            values["mode"],
            values.get("location"),
            values.get("meeting_url"),
            start,
            end,
        )
        name = normalized_name(values["interviewer_name"])
        self._check_conflict(i, name, start, end)
        before = i.scheduled_start_at
        i.scheduled_start_at, i.scheduled_end_at, i.interviewer_name = start, end, name
        i.mode, i.location, i.meeting_url, i.status = (
            values["mode"],
            values.get("location"),
            values.get("meeting_url"),
            InterviewStatus.SCHEDULED,
        )
        app.stage = PipelineStage.INTERVIEW_SCHEDULED
        app.blocked_by = BlockedBy.NONE
        app.waiting_note = None
        app.stage_changed_at = datetime.now()
        typ = "INTERVIEW_RESCHEDULED" if reschedule else "INTERVIEW_SCHEDULED"
        verb = "改期" if reschedule else "已安排"
        activity(
            self.db,
            app.id,
            typ,
            f"{i.round_name}{verb}：{as_shanghai(start).strftime('%m月%d日 %H:%M')}，面试官：{name}",
            {
                "interview_id": i.id,
                "before": as_shanghai(before).isoformat() if before else None,
                "after": as_shanghai(start).isoformat(),
            },
        )
        return i

    def complete(self, id: int):
        i = self._interview(id)
        app = i.application
        if i.status != InterviewStatus.SCHEDULED or app.current_interview_id != i.id:
            conflict("只有待面试的当前面试可以标记完成。")
        i.status = InterviewStatus.COMPLETED
        app.stage = PipelineStage.FEEDBACK_PENDING
        app.blocked_by = BlockedBy.INTERVIEWER
        app.waiting_note = None
        app.stage_changed_at = datetime.now()
        end = as_shanghai(i.scheduled_end_at)
        due = end.replace(hour=18, minute=0, second=0, microsecond=0)
        if end > due:
            due += timedelta(days=1)
            while due.weekday() >= 5:
                due += timedelta(days=1)
        self.db.add(
            Task(
                application_id=app.id,
                title=f"跟进{i.round_name}面评",
                due_at=as_utc_naive(due),
                priority=Priority.HIGH,
            )
        )
        activity(
            self.db,
            app.id,
            "INTERVIEW_COMPLETED",
            f"{i.round_name}已完成，等待面评",
            {"interview_id": i.id},
        )
        return i

    def submit_feedback(
        self,
        id: int,
        feedback: str | None,
        result: InterviewResult,
        next_round_name: str | None,
    ):
        i = self._interview(id)
        app = i.application
        if (
            i.status != InterviewStatus.COMPLETED
            or app.stage != PipelineStage.FEEDBACK_PENDING
            or app.current_interview_id != i.id
        ):
            conflict("当前面试不在待面评状态。")
        if result == InterviewResult.PENDING:
            raise HTTPException(422, detail="请提交明确的面试结果。")
        if result == InterviewResult.NEXT_ROUND and not (next_round_name or "").strip():
            raise HTTPException(422, detail="进入下一轮时必须填写下一轮名称。")
        i.feedback, i.result = feedback, result
        activity(
            self.db,
            app.id,
            "INTERVIEW_FEEDBACK_ADDED",
            f"{i.round_name}结果：{result.value}",
            {"interview_id": i.id, "result": result.value},
        )
        if result == InterviewResult.NEXT_ROUND:
            n = max(x.round_number for x in app.interviews) + 1
            next_i = Interview(
                application_id=app.id,
                round_number=n,
                round_name=(next_round_name or default_round_name(n)).strip(),
                status=InterviewStatus.SCHEDULING,
            )
            self.db.add(next_i)
            self.db.flush()
            app.current_interview_id = next_i.id
            app.stage = PipelineStage.SCHEDULING
            app.blocked_by = BlockedBy.CANDIDATE
            app.waiting_note = None
            activity(
                self.db,
                app.id,
                "INTERVIEW_NEXT_ROUND_CREATED",
                f"创建{next_i.round_name}",
                {"interview_id": next_i.id, "round_number": n},
            )
        elif result == InterviewResult.REJECT:
            app.current_interview_id = None
            app.stage = PipelineStage.REJECTED
            app.blocked_by = BlockedBy.NONE
            app.waiting_note = None
        else:
            app.current_interview_id = None
            app.stage = PipelineStage.DECISION_PENDING
            app.blocked_by = BlockedBy.HR
            app.waiting_note = None
        app.stage_changed_at = datetime.now()
        return i

    def cancel(self, id: int, reason: str | None, disposition: str):
        i = self._interview(id)
        app = i.application
        if i.status == InterviewStatus.COMPLETED:
            conflict("已完成的面试不能取消。")
        if i.status == InterviewStatus.CANCELLED:
            conflict("该面试已取消。")
        if app.current_interview_id != i.id:
            conflict("只有当前面试可以取消。")
        i.status, i.cancel_reason = InterviewStatus.CANCELLED, reason
        activity(
            self.db,
            app.id,
            "INTERVIEW_CANCELLED",
            f"取消{i.round_name}" + (f"：{reason}" if reason else ""),
            {"interview_id": i.id, "disposition": disposition},
        )
        if disposition == "reschedule":
            nxt = Interview(
                application_id=app.id,
                round_number=i.round_number,
                round_name=i.round_name,
                status=InterviewStatus.SCHEDULING,
            )
            self.db.add(nxt)
            self.db.flush()
            app.current_interview_id = nxt.id
            app.stage = PipelineStage.SCHEDULING
            app.blocked_by = BlockedBy.CANDIDATE
            app.waiting_note = None
            activity(
                self.db,
                app.id,
                "INTERVIEW_CREATED",
                f"重新创建{i.round_name}",
                {"interview_id": nxt.id, "round_number": nxt.round_number},
            )
        else:
            app.current_interview_id = None
            app.stage = (
                PipelineStage.WITHDRAWN
                if disposition == "withdraw"
                else PipelineStage.REJECTED
            )
            app.blocked_by = BlockedBy.NONE
            app.waiting_note = None
            app.rejection_reason = reason
        app.stage_changed_at = datetime.now()
        return i
