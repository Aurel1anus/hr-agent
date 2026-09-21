from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.core.enums import InterviewMode, InterviewResult, InterviewStatus, PipelineStage
from app.models import Application, Candidate, Job
from app.services.service import InterviewService


TZ = ZoneInfo("Asia/Shanghai")


def setup_application(session: Session, name: str = "张三"):
    job = Job(title="HRBP", owner_name="李XX")
    candidate = Candidate(name=name)
    session.add_all([job, candidate]); session.flush()
    application = Application(job_id=job.id, candidate_id=candidate.id, stage=PipelineStage.INTERVIEWER_REVIEW)
    session.add(application); session.commit()
    return application


def test_full_next_round_flow_creates_feedback_task():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)
    application = setup_application(session)
    service = InterviewService(session)
    first = service.create_round(application.id, "一面", "周三下午")
    session.commit()
    assert first.status == InterviewStatus.SCHEDULING
    assert session.get(Application, application.id).stage == PipelineStage.SCHEDULING
    first = service.schedule(first.id, {"scheduled_start_at": datetime(2026, 9, 23, 15, tzinfo=TZ), "scheduled_end_at": datetime(2026, 9, 23, 16, tzinfo=TZ), "interviewer_name": " 李XX ", "mode": InterviewMode.ONLINE, "meeting_url": "https://meeting.example.com", "location": None})
    session.commit()
    assert first.status == InterviewStatus.SCHEDULED
    assert first.interviewer_name == "李XX"
    service.complete(first.id); session.commit()
    application = session.get(Application, application.id)
    assert application.stage == PipelineStage.FEEDBACK_PENDING
    assert application.tasks[0].title == "跟进一面面评"
    service.submit_feedback(first.id, None, InterviewResult.NEXT_ROUND, "业务二面")
    session.commit()
    application = session.get(Application, application.id)
    assert application.stage == PipelineStage.SCHEDULING
    assert len(application.interviews) == 2
    assert next(i for i in application.interviews if i.id == application.current_interview_id).round_name == "业务二面"


def test_conflict_and_cancel_are_guarded():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)
    one, two = setup_application(session, "甲"), setup_application(session, "乙")
    service = InterviewService(session)
    first = service.create_round(one.id, "一面"); session.commit()
    values = {"scheduled_start_at": datetime(2026, 9, 23, 15, tzinfo=TZ), "scheduled_end_at": datetime(2026, 9, 23, 16, tzinfo=TZ), "interviewer_name": "李XX", "mode": InterviewMode.ONLINE, "meeting_url": "https://meeting.example.com", "location": None}
    service.schedule(first.id, values); session.commit()
    second = service.create_round(two.id, "一面"); session.commit()
    with pytest.raises(HTTPException) as error:
        service.schedule(second.id, values)
    assert error.value.status_code == 409
    service.cancel(second.id, None, "reschedule"); session.commit()
    current = session.get(Application, two.id).current_interview_id
    assert current != second.id
    with pytest.raises(HTTPException) as cancelled:
        service.cancel(second.id, None, "reschedule")
    assert cancelled.value.status_code == 409
