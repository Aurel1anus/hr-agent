from __future__ import annotations
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.core.enums import BlockedBy, InterviewMode, InterviewResult, PipelineStage, Priority

class Schema(BaseModel): model_config=ConfigDict(from_attributes=True)
class JobIn(Schema):
    title:str=Field(min_length=1,max_length=120); department:str|None=None; location:str|None=None; salary_min:int|None=None; salary_max:int|None=None; description:str|None=None; jd_text:str|None=None; owner_name:str|None=None
    @model_validator(mode="after")
    def salary_range(self):
        if self.salary_min is not None and self.salary_max is not None and self.salary_min>self.salary_max: raise ValueError("最低薪资不能高于最高薪资")
        return self
class JobPatch(JobIn): title:str|None=None
class CandidateIn(Schema): name:str=Field(min_length=1,max_length=80); phone:str|None=None; email:str|None=None; school:str|None=None; major:str|None=None; highest_degree:str|None=None; graduation_year:int|None=None; current_city:str|None=None; source:str|None=None; resume_url:str|None=None
class CandidatePatch(CandidateIn): name:str|None=None
class ApplicationCreate(CandidateIn): pass
class ResumeConfirm(CandidateIn):
    candidate_id: int | None = None
    create_new: bool = False
class StageChange(Schema): target_stage:PipelineStage; force:bool=False
class BlockedChange(Schema): blocked_by:BlockedBy; waiting_note:str|None=Field(default=None,max_length=120)
class ReasonIn(Schema): reason:str=Field(min_length=1,max_length=500)
class RecruitmentInfo(Schema):
    earliest_start_date:date|None=None; internship_months:int|None=Field(default=None,ge=0); days_per_week:int|None=Field(default=None,ge=1,le=7); salary_accepted:bool|None=None; relocation_required:bool|None=None; relocation_accepted:bool|None=None; commute_minutes:int|None=Field(default=None,ge=0)
class TaskIn(Schema): title:str=Field(min_length=1,max_length=200); description:str|None=None; due_at:datetime|None=None; priority:Priority=Priority.NORMAL
class TaskPatch(Schema): title:str|None=None; description:str|None=None; due_at:datetime|None=None; priority:Priority|None=None
class InterviewCreate(Schema):
    round_name: str = Field(min_length=1, max_length=120)
    candidate_availability: str | None = Field(default=None, max_length=2000)
    interviewer_availability: str | None = Field(default=None, max_length=2000)

class InterviewAvailabilityPatch(Schema):
    candidate_availability: str | None = Field(default=None, max_length=2000)
    interviewer_availability: str | None = Field(default=None, max_length=2000)

class InterviewSchedule(Schema):
    scheduled_start_at: datetime
    scheduled_end_at: datetime
    interviewer_name: str = Field(min_length=1, max_length=120)
    mode: InterviewMode
    location: str | None = Field(default=None, max_length=300)
    meeting_url: str | None = Field(default=None, max_length=500)

class InterviewFeedback(Schema):
    feedback: str | None = Field(default=None, max_length=5000)
    result: InterviewResult
    next_round_name: str | None = Field(default=None, max_length=120)

class InterviewCancel(Schema):
    reason: str | None = Field(default=None, max_length=500)
    disposition: str = Field(pattern="^(reschedule|withdraw|reject)$")
class NoteIn(Schema): content:str=Field(min_length=1,max_length=5000)

class RequirementItem(Schema):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=500)
    evidence_required: bool = True

class RequirementProfilePatch(Schema):
    raw_jd: str | None = None
    raw_notes: str | None = None
    must_have: list[RequirementItem] = []
    preferred: list[RequirementItem] = []
    skills: list[str] = []
    soft_skills: list[str] = []
    negative_signals: list[str] = []
    verification_questions: list[str] = []
    ai_summary: str | None = None

class RequirementGenerate(Schema):
    extra_notes: str | None = None

class AssessmentStrength(Schema):
    requirement: str
    evidence: str
    status: str = "met"

class AssessmentGap(Schema):
    requirement: str
    reason: str
    status: str = "unknown"

class AssessmentResult(Schema):
    recommendation: str
    overall_score: int = Field(ge=0, le=100)
    strengths: list[AssessmentStrength] = []
    gaps: list[AssessmentGap] = []
    risks: list[str] = []
    missing_information: list[str] = []
    verification_questions: list[str] = []
    summary: str

class MemoryIn(Schema):
    memory_type: str = Field(min_length=1, max_length=50)
    content: str = Field(min_length=1, max_length=2000)
    source_type: str = "hr_manual"
    source_id: int | None = None
    importance: int = Field(default=3, ge=1, le=5)
    confidence: float = Field(default=1.0, ge=0, le=1)

class ToolApproval(Schema):
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    due_at: datetime | None = None
    priority: Priority | None = None
