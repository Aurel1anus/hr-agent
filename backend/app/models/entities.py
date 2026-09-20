from __future__ import annotations
from datetime import date, datetime
from typing import Any
from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.core.enums import (
    BlockedBy,
    InterviewMode,
    InterviewStatus,
    JobStatus,
    PipelineStage,
    Priority,
    TaskStatus,
)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    department: Mapped[str | None] = mapped_column(String(120))
    location: Mapped[str | None] = mapped_column(String(120))
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus), default=JobStatus.ACTIVE
    )
    owner_name: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )
    applications: Mapped[list["Application"]] = relationship(back_populates="job")


class Candidate(Base):
    __tablename__ = "candidates"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(120))
    school: Mapped[str | None] = mapped_column(String(120))
    major: Mapped[str | None] = mapped_column(String(120))
    highest_degree: Mapped[str | None] = mapped_column(String(30))
    graduation_year: Mapped[int | None] = mapped_column(Integer)
    current_city: Mapped[str | None] = mapped_column(String(80))
    source: Mapped[str | None] = mapped_column(String(80))
    resume_url: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )
    applications: Mapped[list["Application"]] = relationship(back_populates="candidate")
    resumes: Mapped[list["Resume"]] = relationship(back_populates="candidate")


class Application(Base):
    __tablename__ = "applications"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"))
    stage: Mapped[PipelineStage] = mapped_column(
        SAEnum(PipelineStage), default=PipelineStage.SCREENING
    )
    stage_before_hold: Mapped[PipelineStage | None] = mapped_column(
        SAEnum(PipelineStage)
    )
    stage_changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    blocked_by: Mapped[BlockedBy] = mapped_column(
        SAEnum(BlockedBy), default=BlockedBy.HR
    )
    waiting_note: Mapped[str | None] = mapped_column(String(120))
    priority: Mapped[Priority] = mapped_column(
        SAEnum(Priority), default=Priority.NORMAL
    )
    earliest_start_date: Mapped[date | None] = mapped_column(Date)
    internship_months: Mapped[int | None] = mapped_column(Integer)
    days_per_week: Mapped[int | None] = mapped_column(Integer)
    salary_accepted: Mapped[bool | None] = mapped_column(Boolean)
    relocation_required: Mapped[bool | None] = mapped_column(Boolean)
    relocation_accepted: Mapped[bool | None] = mapped_column(Boolean)
    commute_minutes: Mapped[int | None] = mapped_column(Integer)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime)
    job: Mapped[Job] = relationship(back_populates="applications")
    candidate: Mapped[Candidate] = relationship(back_populates="applications")
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    interviews: Mapped[list["Interview"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    activities: Mapped[list["Activity"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    resumes: Mapped[list["Resume"]] = relationship(back_populates="application")


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    due_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus), default=TaskStatus.TODO
    )
    priority: Mapped[Priority] = mapped_column(
        SAEnum(Priority), default=Priority.NORMAL
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    application: Mapped[Application] = relationship(back_populates="tasks")


class Interview(Base):
    __tablename__ = "interviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    round: Mapped[int] = mapped_column(Integer, default=1)
    interviewer_name: Mapped[str | None] = mapped_column(String(120))
    start_at: Mapped[datetime] = mapped_column(DateTime)
    end_at: Mapped[datetime | None] = mapped_column(DateTime)
    mode: Mapped[InterviewMode] = mapped_column(
        SAEnum(InterviewMode), default=InterviewMode.ONLINE
    )
    location: Mapped[str | None] = mapped_column(String(300))
    meeting_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[InterviewStatus] = mapped_column(
        SAEnum(InterviewStatus), default=InterviewStatus.SCHEDULED
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )
    application: Mapped[Application] = relationship(back_populates="interviews")


class Activity(Base):
    __tablename__ = "activities"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    type: Mapped[str] = mapped_column(String(60))
    content: Mapped[str] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    application: Mapped[Application] = relationship(back_populates="activities")


class Resume(Base):
    __tablename__ = "resumes"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    candidate_id: Mapped[int | None] = mapped_column(ForeignKey("candidates.id"), index=True)
    application_id: Mapped[int | None] = mapped_column(ForeignKey("applications.id"), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str] = mapped_column(String(100))
    file_size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    parse_status: Mapped[str] = mapped_column(String(20), default="parsed", index=True)
    parsed_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    parser_version: Mapped[str] = mapped_column(String(40), default="1.0")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
    candidate: Mapped[Candidate | None] = relationship(back_populates="resumes")
    application: Mapped[Application | None] = relationship(back_populates="resumes")
