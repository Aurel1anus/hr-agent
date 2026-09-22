from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.router import job_summary
from app.core.database import Base
from app.core.enums import PipelineStage
from app.models import Application, Candidate, Job, Task


def test_job_summary_handles_undated_todos():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        job = Job(title="后端工程师")
        candidate = Candidate(name="测试候选人")
        db.add_all([job, candidate]); db.flush()
        application = Application(job_id=job.id, candidate_id=candidate.id, stage=PipelineStage.SCREENING)
        db.add(application); db.flush()
        db.add(Task(application_id=application.id, title="没有截止时间"))
        db.commit()
        summary = job_summary(db, job)
    assert summary["today_task_count"] == 0
    assert summary["overdue_count"] == 0
