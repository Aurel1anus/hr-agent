from __future__ import annotations
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.core.enums import BlockedBy, InterviewMode, PipelineStage, Priority

class Schema(BaseModel): model_config=ConfigDict(from_attributes=True)
class JobIn(Schema):
    title:str=Field(min_length=1,max_length=120); department:str|None=None; location:str|None=None; salary_min:int|None=None; salary_max:int|None=None; description:str|None=None; owner_name:str|None=None
    @model_validator(mode="after")
    def salary_range(self):
        if self.salary_min is not None and self.salary_max is not None and self.salary_min>self.salary_max: raise ValueError("最低薪资不能高于最高薪资")
        return self
class JobPatch(JobIn): title:str|None=None
class CandidateIn(Schema): name:str=Field(min_length=1,max_length=80); phone:str|None=None; email:str|None=None; school:str|None=None; major:str|None=None; graduation_year:int|None=None; current_city:str|None=None; source:str|None=None; resume_url:str|None=None
class CandidatePatch(CandidateIn): name:str|None=None
class ApplicationCreate(CandidateIn): pass
class StageChange(Schema): target_stage:PipelineStage; force:bool=False
class BlockedChange(Schema): blocked_by:BlockedBy
class ReasonIn(Schema): reason:str=Field(min_length=1,max_length=500)
class RecruitmentInfo(Schema):
    earliest_start_date:date|None=None; internship_months:int|None=Field(default=None,ge=0); days_per_week:int|None=Field(default=None,ge=1,le=7); salary_accepted:bool|None=None; relocation_required:bool|None=None; relocation_accepted:bool|None=None; commute_minutes:int|None=Field(default=None,ge=0)
class TaskIn(Schema): title:str=Field(min_length=1,max_length=200); description:str|None=None; due_at:datetime|None=None; priority:Priority=Priority.NORMAL
class TaskPatch(Schema): title:str|None=None; description:str|None=None; due_at:datetime|None=None; priority:Priority|None=None
class InterviewIn(Schema):
    round:int=Field(default=1,ge=1); interviewer_name:str|None=None; start_at:datetime; end_at:datetime|None=None; mode:InterviewMode=InterviewMode.ONLINE; location:str|None=None; meeting_url:str|None=None
    @model_validator(mode="after")
    def period(self):
        if self.end_at and self.end_at<=self.start_at: raise ValueError("结束时间必须晚于开始时间")
        return self
class InterviewPatch(InterviewIn): start_at:datetime|None=None
class NoteIn(Schema): content:str=Field(min_length=1,max_length=5000)

