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
    InterviewResult,
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
    jd_text: Mapped[str | None] = mapped_column(Text)
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
    current_interview_id: Mapped[int | None] = mapped_column(ForeignKey("interviews.id"), nullable=True)
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
        back_populates="application", cascade="all, delete-orphan", foreign_keys="Interview.application_id"
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
    round_number: Mapped[int] = mapped_column(Integer)
    round_name: Mapped[str] = mapped_column(String(120))
    candidate_availability: Mapped[str | None] = mapped_column(Text)
    interviewer_availability: Mapped[str | None] = mapped_column(Text)
    interviewer_name: Mapped[str | None] = mapped_column(String(120))
    interviewer_id: Mapped[int | None] = mapped_column(Integer)
    scheduled_start_at: Mapped[datetime | None] = mapped_column(DateTime)
    scheduled_end_at: Mapped[datetime | None] = mapped_column(DateTime)
    mode: Mapped[InterviewMode | None] = mapped_column(SAEnum(InterviewMode))
    location: Mapped[str | None] = mapped_column(String(300))
    meeting_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[InterviewStatus] = mapped_column(
        SAEnum(InterviewStatus), default=InterviewStatus.SCHEDULING
    )
    feedback: Mapped[str | None] = mapped_column(Text)
    result: Mapped[InterviewResult] = mapped_column(SAEnum(InterviewResult), default=InterviewResult.PENDING)
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )
    application: Mapped[Application] = relationship(back_populates="interviews", foreign_keys=[application_id])


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
    extracted_text: Mapped[str | None] = mapped_column(Text)
    parser_version: Mapped[str] = mapped_column(String(40), default="1.0")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
    candidate: Mapped[Candidate | None] = relationship(back_populates="resumes")
    application: Mapped[Application | None] = relationship(back_populates="resumes")


class RequirementProfile(Base):
    __tablename__ = "job_requirement_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    raw_jd: Mapped[str | None] = mapped_column(Text)
    raw_notes: Mapped[str | None] = mapped_column(Text)
    must_have_json: Mapped[list[Any]] = mapped_column(JSON, default=list)
    preferred_json: Mapped[list[Any]] = mapped_column(JSON, default=list)
    skills_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    soft_skills_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    negative_signals_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    verification_questions_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    ai_summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class ResumeAssessment(Base):
    __tablename__ = "resume_assessments"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    requirement_profile_id: Mapped[int] = mapped_column(ForeignKey("job_requirement_profiles.id"))
    resume_id: Mapped[int | None] = mapped_column(ForeignKey("resumes.id"))
    recommendation: Mapped[str] = mapped_column(String(30))
    overall_score: Mapped[int] = mapped_column(Integer)
    strengths_json: Mapped[list[Any]] = mapped_column(JSON, default=list)
    gaps_json: Mapped[list[Any]] = mapped_column(JSON, default=list)
    risks_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    missing_information_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    verification_questions_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    summary: Mapped[str] = mapped_column(Text)
    model_name: Mapped[str] = mapped_column(String(80))
    prompt_version: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class Memory(Base):
    __tablename__ = "memories"
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(30), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    memory_type: Mapped[str] = mapped_column(String(50))
    content: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(40), default="hr_manual")
    source_id: Mapped[int | None] = mapped_column(Integer)
    importance: Mapped[int] = mapped_column(Integer, default=3)
    confidence: Mapped[float] = mapped_column(default=1.0)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)


class AgentRun(Base):
    __tablename__ = "agent_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    agent_type: Mapped[str] = mapped_column(String(40), index=True)
    candidate_id: Mapped[int | None] = mapped_column(ForeignKey("candidates.id"))
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"))
    application_id: Mapped[int | None] = mapped_column(ForeignKey("applications.id"))
    input_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    output_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    model_name: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class AgentToolCall(Base):
    __tablename__ = "agent_tool_calls"
    id: Mapped[int] = mapped_column(primary_key=True)
    agent_run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    tool_name: Mapped[str] = mapped_column(String(80))
    arguments_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    risk_level: Mapped[str] = mapped_column(String(20), default="medium")
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    approval_status: Mapped[str] = mapped_column(String(30), default="pending_approval")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="proposed")
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
