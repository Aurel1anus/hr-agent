import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models import Job
from app.services.agent_service import generate_profile


def test_requirement_generation_requires_jd_or_notes():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        job = Job(title="商务助理实习生")
        db.add(job); db.commit()
        with pytest.raises(HTTPException) as error:
            generate_profile(db, job, None)
    assert error.value.status_code == 422
    assert error.value.detail == "请先填写岗位 JD 或业务补充，再生成招聘画像。"
