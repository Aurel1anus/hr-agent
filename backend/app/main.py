from __future__ import annotations

from datetime import date, datetime, time, timedelta
from enum import Enum
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import JSON, Boolean, Date, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, create_engine, func, or_, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker, selectinload

DATABASE_URL = "sqlite:///./hr_recruiting.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase): pass
class JobStatus(str, Enum): DRAFT="draft"; ACTIVE="active"; PAUSED="paused"; CLOSED="closed"
class PipelineStage(str, Enum):
    SCREENING="screening"; CONTACTING="contacting"; READY_TO_SUBMIT="ready_to_submit"; INTERVIEWER_REVIEW="interviewer_review"; SCHEDULING="scheduling"; INTERVIEW_SCHEDULED="interview_scheduled"; FEEDBACK_PENDING="feedback_pending"; DECISION_PENDING="decision_pending"; OFFER="offer"; REJECTED="rejected"; WITHDRAWN="withdrawn"; ON_HOLD="on_hold"
class BlockedBy(str, Enum): NONE="none"; HR="hr"; CANDIDATE="candidate"; INTERVIEWER="interviewer"; SYSTEM="system"
class TaskStatus(str, Enum): TODO="todo"; DONE="done"; CANCELLED="cancelled"
class Priority(str, Enum): LOW="low"; NORMAL="normal"; HIGH="high"
class InterviewMode(str, Enum): ONLINE="online"; OFFLINE="offline"
class InterviewStatus(str, Enum): SCHEDULED="scheduled"; COMPLETED="completed"; CANCELLED="cancelled"

class Job(Base):
    __tablename__="jobs"; id: Mapped[int]=mapped_column(primary_key=True); title: Mapped[str]=mapped_column(String(120)); department: Mapped[str|None]=mapped_column(String(120)); location: Mapped[str|None]=mapped_column(String(120)); salary_min: Mapped[int|None]=mapped_column(Integer); salary_max: Mapped[int|None]=mapped_column(Integer); description: Mapped[str|None]=mapped_column(Text); status: Mapped[JobStatus]=mapped_column(SAEnum(JobStatus), default=JobStatus.ACTIVE); owner_name: Mapped[str|None]=mapped_column(String(80)); created_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.now); updated_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.now, onupdate=datetime.now); applications: Mapped[list["Application"]]=relationship(back_populates="job")
class Candidate(Base):
    __tablename__="candidates"; id: Mapped[int]=mapped_column(primary_key=True); name: Mapped[str]=mapped_column(String(80)); phone: Mapped[str|None]=mapped_column(String(30)); email: Mapped[str|None]=mapped_column(String(120)); school: Mapped[str|None]=mapped_column(String(120)); major: Mapped[str|None]=mapped_column(String(120)); graduation_year: Mapped[int|None]=mapped_column(Integer); current_city: Mapped[str|None]=mapped_column(String(80)); source: Mapped[str|None]=mapped_column(String(80)); resume_url: Mapped[str|None]=mapped_column(String(500)); created_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.now); updated_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.now, onupdate=datetime.now); applications: Mapped[list["Application"]]=relationship(back_populates="candidate")
class Application(Base):
    __tablename__="applications"; id: Mapped[int]=mapped_column(primary_key=True); job_id: Mapped[int]=mapped_column(ForeignKey("jobs.id")); candidate_id: Mapped[int]=mapped_column(ForeignKey("candidates.id")); stage: Mapped[PipelineStage]=mapped_column(SAEnum(PipelineStage), default=PipelineStage.SCREENING); stage_before_hold: Mapped[PipelineStage|None]=mapped_column(SAEnum(PipelineStage)); stage_changed_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.now); blocked_by: Mapped[BlockedBy]=mapped_column(SAEnum(BlockedBy), default=BlockedBy.HR); priority: Mapped[Priority]=mapped_column(SAEnum(Priority), default=Priority.NORMAL); earliest_start_date: Mapped[date|None]=mapped_column(Date); internship_months: Mapped[int|None]=mapped_column(Integer); days_per_week: Mapped[int|None]=mapped_column(Integer); salary_accepted: Mapped[bool|None]=mapped_column(Boolean); relocation_required: Mapped[bool|None]=mapped_column(Boolean); relocation_accepted: Mapped[bool|None]=mapped_column(Boolean); commute_minutes: Mapped[int|None]=mapped_column(Integer); rejection_reason: Mapped[str|None]=mapped_column(Text); created_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.now); updated_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.now, onupdate=datetime.now); job: Mapped[Job]=relationship(back_populates="applications"); candidate: Mapped[Candidate]=relationship(back_populates="applications"); tasks: Mapped[list["Task"]]=relationship(back_populates="application", cascade="all, delete-orphan"); interviews: Mapped[list["Interview"]]=relationship(back_populates="application", cascade="all, delete-orphan"); activities: Mapped[list["Activity"]]=relationship(back_populates="application", cascade="all, delete-orphan")
class Task(Base):
    __tablename__="tasks"; id: Mapped[int]=mapped_column(primary_key=True); application_id: Mapped[int]=mapped_column(ForeignKey("applications.id")); title: Mapped[str]=mapped_column(String(200)); description: Mapped[str|None]=mapped_column(Text); due_at: Mapped[datetime|None]=mapped_column(DateTime); status: Mapped[TaskStatus]=mapped_column(SAEnum(TaskStatus), default=TaskStatus.TODO); priority: Mapped[Priority]=mapped_column(SAEnum(Priority), default=Priority.NORMAL); created_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.now); completed_at: Mapped[datetime|None]=mapped_column(DateTime); application: Mapped[Application]=relationship(back_populates="tasks")
class Interview(Base):
    __tablename__="interviews"; id: Mapped[int]=mapped_column(primary_key=True); application_id: Mapped[int]=mapped_column(ForeignKey("applications.id")); round: Mapped[int]=mapped_column(Integer, default=1); interviewer_name: Mapped[str|None]=mapped_column(String(120)); start_at: Mapped[datetime]=mapped_column(DateTime); end_at: Mapped[datetime|None]=mapped_column(DateTime); mode: Mapped[InterviewMode]=mapped_column(SAEnum(InterviewMode), default=InterviewMode.ONLINE); location: Mapped[str|None]=mapped_column(String(300)); meeting_url: Mapped[str|None]=mapped_column(String(500)); status: Mapped[InterviewStatus]=mapped_column(SAEnum(InterviewStatus), default=InterviewStatus.SCHEDULED); created_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.now); updated_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.now, onupdate=datetime.now); application: Mapped[Application]=relationship(back_populates="interviews")
class Activity(Base):
    __tablename__="activities"; id: Mapped[int]=mapped_column(primary_key=True); application_id: Mapped[int]=mapped_column(ForeignKey("applications.id")); type: Mapped[str]=mapped_column(String(60)); content: Mapped[str]=mapped_column(Text); metadata_: Mapped[dict[str,Any]|None]=mapped_column("metadata", JSON); created_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.now); application: Mapped[Application]=relationship(back_populates="activities")

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

def db_session():
    db=SessionLocal()
    try: yield db
    finally: db.close()
def get_or_404(db:Session, model:Any, id:int):
    obj=db.get(model,id)
    if not obj: raise HTTPException(404,detail="资源不存在")
    return obj
def activity(db:Session, application_id:int, type:str, content:str, metadata:dict|None=None): db.add(Activity(application_id=application_id,type=type,content=content,metadata_=metadata))
def stage_label(stage:PipelineStage): return {s:s.value for s in PipelineStage}[stage]
NORMAL_STAGES=[PipelineStage.SCREENING,PipelineStage.CONTACTING,PipelineStage.READY_TO_SUBMIT,PipelineStage.INTERVIEWER_REVIEW,PipelineStage.SCHEDULING,PipelineStage.INTERVIEW_SCHEDULED,PipelineStage.FEEDBACK_PENDING,PipelineStage.DECISION_PENDING,PipelineStage.OFFER]
def change_stage(db:Session, app:Application, target:PipelineStage, force:bool=False):
    if target==app.stage:return app
    if not force and (app.stage not in NORMAL_STAGES or target not in NORMAL_STAGES or NORMAL_STAGES.index(target)!=NORMAL_STAGES.index(app.stage)+1): raise HTTPException(422,detail="非正常流转请传 force=true")
    before=app.stage; app.stage=target; app.stage_changed_at=datetime.now(); activity(db,app.id,"STAGE_CHANGED",f"招聘阶段：{before.value} → {target.value}",{"from":before.value,"to":target.value,"force":force}); return app
def task_view(t:Task):
    return {"id":t.id,"title":t.title,"description":t.description,"due_at":t.due_at,"status":t.status,"priority":t.priority,"completed_at":t.completed_at,"is_overdue":bool(t.status==TaskStatus.TODO and t.due_at and t.due_at<datetime.now())}
def job_view(j:Job): return {"id":j.id,"title":j.title,"department":j.department,"location":j.location,"salary_min":j.salary_min,"salary_max":j.salary_max,"description":j.description,"status":j.status,"owner_name":j.owner_name,"created_at":j.created_at,"updated_at":j.updated_at}
def candidate_view(c:Candidate): return {"id":c.id,"name":c.name,"phone":c.phone,"email":c.email,"school":c.school,"major":c.major,"graduation_year":c.graduation_year,"current_city":c.current_city,"source":c.source,"resume_url":c.resume_url,"created_at":c.created_at,"updated_at":c.updated_at}
def interview_view(i:Interview): return {"id":i.id,"application_id":i.application_id,"round":i.round,"interviewer_name":i.interviewer_name,"start_at":i.start_at,"end_at":i.end_at,"mode":i.mode,"location":i.location,"meeting_url":i.meeting_url,"status":i.status,"created_at":i.created_at,"updated_at":i.updated_at}
def app_card(app:Application):
    todos=[t for t in app.tasks if t.status==TaskStatus.TODO]; todos.sort(key=lambda t: ({Priority.HIGH:0,Priority.NORMAL:1,Priority.LOW:2}[t.priority],t.due_at or datetime.max)); primary=todos[0] if todos else None
    return {"application_id":app.id,"candidate_id":app.candidate_id,"candidate_name":app.candidate.name,"school":app.candidate.school,"graduation_year":app.candidate.graduation_year,"stage":app.stage,"blocked_by":app.blocked_by,"primary_task":primary.title if primary else None,"task_due_at":primary.due_at if primary else None,"is_overdue":bool(primary and primary.due_at and primary.due_at<datetime.now()),"stage_changed_at":app.stage_changed_at}

app=FastAPI(title="HR Recruiting MVP API",version="0.1.0")
app.add_middleware(CORSMiddleware,allow_origins=["http://localhost:5173","http://127.0.0.1:5173"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
@app.get("/health")
def health(): return {"status":"ok"}
@app.get("/dashboard")
def dashboard(db:Session=Depends(db_session)):
    now=datetime.now(); start=datetime.combine(now.date(),time.min); end=start+timedelta(days=1); active=list(db.scalars(select(Application).where(Application.stage.in_(NORMAL_STAGES))).all())
    return {"active_job_count":db.scalar(select(func.count()).select_from(Job).where(Job.status==JobStatus.ACTIVE)) or 0,"active_application_count":len(active),"today_task_count":db.scalar(select(func.count()).select_from(Task).where(Task.status==TaskStatus.TODO,Task.due_at>=start,Task.due_at<end)) or 0,"overdue_task_count":db.scalar(select(func.count()).select_from(Task).where(Task.status==TaskStatus.TODO,Task.due_at<now)) or 0,"today_interview_count":db.scalar(select(func.count()).select_from(Interview).where(Interview.status==InterviewStatus.SCHEDULED,Interview.start_at>=start,Interview.start_at<end)) or 0}
@app.get("/dashboard/tasks")
def dashboard_tasks(limit:int=10,db:Session=Depends(db_session)):
    rows=db.scalars(select(Task).join(Task.application).options(selectinload(Task.application).selectinload(Application.candidate),selectinload(Task.application).selectinload(Application.job)).where(Task.status==TaskStatus.TODO).order_by(Task.due_at.is_(None),Task.due_at).limit(limit)).all(); return [{**task_view(t),"candidate_id":t.application.candidate_id,"candidate_name":t.application.candidate.name,"job_id":t.application.job_id,"job_title":t.application.job.title,"application_id":t.application_id,"stage":t.application.stage,"blocked_by":t.application.blocked_by} for t in rows]
@app.get("/dashboard/interviews/today")
def today_interviews(db:Session=Depends(db_session)):
    start=datetime.combine(date.today(),time.min); end=start+timedelta(days=1); rows=db.scalars(select(Interview).options(selectinload(Interview.application).selectinload(Application.candidate),selectinload(Interview.application).selectinload(Application.job)).where(Interview.start_at>=start,Interview.start_at<end,Interview.status==InterviewStatus.SCHEDULED).order_by(Interview.start_at)).all(); return [{"id":i.id,"application_id":i.application_id,"candidate_name":i.application.candidate.name,"job_title":i.application.job.title,"start_at":i.start_at,"mode":i.mode,"interviewer_name":i.interviewer_name} for i in rows]
@app.get("/dashboard/jobs")
def dashboard_jobs(db:Session=Depends(db_session)): return [job_summary(db,j) for j in db.scalars(select(Job).where(Job.status==JobStatus.ACTIVE)).all()]

def job_summary(db:Session, job:Job):
    apps=db.scalars(select(Application).options(selectinload(Application.tasks)).where(Application.job_id==job.id)).all(); now=datetime.now(); stages={s.value:sum(a.stage==s for a in apps) for s in NORMAL_STAGES}; todos=[t for a in apps for t in a.tasks if t.status==TaskStatus.TODO]; return {"id":job.id,"title":job.title,"department":job.department,"location":job.location,"owner_name":job.owner_name,"status":job.status,"candidate_count":len(apps),"active_count":sum(a.stage in NORMAL_STAGES for a in apps),"stage_counts":stages,"today_task_count":sum(t.due_at and t.due_at.date()==date.today() for t in todos),"overdue_count":sum(t.due_at and t.due_at<now for t in todos)}
@app.get("/jobs")
def list_jobs(status:JobStatus|None=None,search:str|None=None,page:int=1,page_size:int=20,db:Session=Depends(db_session)):
    q=select(Job); q=q.where(Job.status==status) if status else q; q=q.where(or_(Job.title.contains(search),Job.department.contains(search))) if search else q; return {"items":[job_summary(db,j) for j in db.scalars(q.order_by(Job.updated_at.desc()).offset((page-1)*page_size).limit(page_size)).all()],"page":page,"page_size":page_size}
@app.post("/jobs",status_code=201)
def create_job(data:JobIn,db:Session=Depends(db_session)):
    job=Job(**data.model_dump()); db.add(job); db.commit(); db.refresh(job); return job_summary(db,job)
@app.get("/jobs/{job_id}")
def get_job(job_id:int,db:Session=Depends(db_session)): return job_view(get_or_404(db,Job,job_id))
@app.patch("/jobs/{job_id}")
def patch_job(job_id:int,data:JobPatch,db:Session=Depends(db_session)):
    job=get_or_404(db,Job,job_id); [setattr(job,k,v) for k,v in data.model_dump(exclude_unset=True).items()]; db.commit(); return job_summary(db,job)
@app.post("/jobs/{job_id}/actions/{action}")
def job_action(job_id:int,action:str,db:Session=Depends(db_session)):
    mapping={"pause":JobStatus.PAUSED,"resume":JobStatus.ACTIVE,"close":JobStatus.CLOSED};
    if action not in mapping: raise HTTPException(404,detail="操作不存在")
    job=get_or_404(db,Job,job_id); job.status=mapping[action]; db.commit(); return job_summary(db,job)
@app.post("/jobs/{job_id}/pause")
def pause_job(job_id:int,db:Session=Depends(db_session)): return job_action(job_id,"pause",db)
@app.post("/jobs/{job_id}/resume")
def resume_job(job_id:int,db:Session=Depends(db_session)): return job_action(job_id,"resume",db)
@app.post("/jobs/{job_id}/close")
def close_job(job_id:int,db:Session=Depends(db_session)): return job_action(job_id,"close",db)
@app.get("/jobs/{job_id}/stats")
def job_stats(job_id:int,db:Session=Depends(db_session)):
    job=get_or_404(db,Job,job_id); item=job_summary(db,job); return {"total_candidates":item["candidate_count"],"active_candidates":item["active_count"],"today_tasks":item["today_task_count"],"overdue_tasks":item["overdue_count"],"today_interviews":db.scalar(select(func.count()).select_from(Interview).join(Application).where(Application.job_id==job_id,Interview.start_at>=datetime.combine(date.today(),time.min),Interview.start_at<datetime.combine(date.today()+timedelta(days=1),time.min))) or 0,"offer_count":item["stage_counts"]["offer"],"stage_counts":item["stage_counts"]}
@app.post("/jobs/{job_id}/candidates",status_code=201)
def add_candidate(job_id:int,data:ApplicationCreate,db:Session=Depends(db_session)):
    get_or_404(db,Job,job_id); c=Candidate(**data.model_dump()); db.add(c); db.flush(); a=Application(job_id=job_id,candidate_id=c.id); db.add(a); db.flush(); activity(db,a.id,"APPLICATION_CREATED","候选人加入岗位"); db.commit(); db.refresh(a); return app_card(a)
@app.get("/jobs/{job_id}/applications")
def job_applications(job_id:int,stage:PipelineStage|None=None,blocked_by:BlockedBy|None=None,search:str|None=None,risk:str|None=None,db:Session=Depends(db_session)):
    get_or_404(db,Job,job_id); q=select(Application).options(selectinload(Application.candidate),selectinload(Application.tasks)).where(Application.job_id==job_id); q=q.where(Application.stage==stage) if stage else q; q=q.where(Application.blocked_by==blocked_by) if blocked_by else q; q=q.join(Application.candidate).where(Candidate.name.contains(search)) if search else q; cards=[app_card(a) for a in db.scalars(q).all()]; return [x for x in cards if not risk or (risk=="overdue" and x["is_overdue"]) or (risk=="no_task" and not x["primary_task"])]
@app.get("/jobs/{job_id}/kanban")
def kanban(job_id:int,db:Session=Depends(db_session)):
    cards=job_applications(job_id,db=db); return {stage.value:[c for c in cards if c["stage"]==stage] for stage in NORMAL_STAGES}

@app.post("/candidates",status_code=201)
def create_candidate(data:CandidateIn,db:Session=Depends(db_session)): c=Candidate(**data.model_dump()); db.add(c); db.commit(); db.refresh(c); return candidate_view(c)
@app.get("/candidates")
def list_candidates(search:str|None=None,school:str|None=None,job_id:int|None=None,stage:PipelineStage|None=None,page:int=1,page_size:int=50,db:Session=Depends(db_session)):
    q=select(Candidate).options(selectinload(Candidate.applications).selectinload(Application.job)); q=q.where(or_(Candidate.name.contains(search),Candidate.school.contains(search))) if search else q; q=q.where(Candidate.school.contains(school)) if school else q
    if job_id or stage: q=q.join(Candidate.applications).where(Application.job_id==job_id if job_id else True,Application.stage==stage if stage else True)
    rows=db.scalars(q.offset((page-1)*page_size).limit(page_size)).unique().all(); return {"items":[{"id":c.id,"name":c.name,"school":c.school,"graduation_year":c.graduation_year,"current_city":c.current_city,"applications":[{"id":a.id,"job_id":a.job_id,"job_title":a.job.title,"stage":a.stage,"blocked_by":a.blocked_by,"updated_at":a.updated_at} for a in c.applications]} for c in rows],"page":page,"page_size":page_size}
@app.get("/candidates/{candidate_id}")
def get_candidate(candidate_id:int,db:Session=Depends(db_session)): return candidate_view(get_or_404(db,Candidate,candidate_id))
@app.patch("/candidates/{candidate_id}")
def patch_candidate(candidate_id:int,data:CandidatePatch,db:Session=Depends(db_session)):
    c=get_or_404(db,Candidate,candidate_id); [setattr(c,k,v) for k,v in data.model_dump(exclude_unset=True).items()]; db.commit(); return candidate_view(c)
@app.get("/candidates/{candidate_id}/applications")
def candidate_apps(candidate_id:int,db:Session=Depends(db_session)):
    c=get_or_404(db,Candidate,candidate_id); return [{"application_id":a.id,"job_id":a.job_id,"job_title":a.job.title,"stage":a.stage,"blocked_by":a.blocked_by,"updated_at":a.updated_at} for a in db.scalars(select(Application).options(selectinload(Application.job)).where(Application.candidate_id==c.id)).all()]

@app.get("/applications/{application_id}")
def application_detail(application_id:int,db:Session=Depends(db_session)):
    a=db.scalar(select(Application).options(selectinload(Application.candidate),selectinload(Application.job),selectinload(Application.tasks),selectinload(Application.interviews),selectinload(Application.activities)).where(Application.id==application_id));
    if not a: raise HTTPException(404,detail="资源不存在")
    return {"id":a.id,"stage":a.stage,"blocked_by":a.blocked_by,"priority":a.priority,"candidate":candidate_view(a.candidate),"job":job_view(a.job),"recruitment_info":{"earliest_start_date":a.earliest_start_date,"internship_months":a.internship_months,"days_per_week":a.days_per_week,"salary_accepted":a.salary_accepted,"relocation_required":a.relocation_required,"relocation_accepted":a.relocation_accepted,"commute_minutes":a.commute_minutes},"tasks":[task_view(t) for t in sorted(a.tasks,key=lambda x:x.created_at,reverse=True)],"interviews":[interview_view(i) for i in a.interviews],"activities":[{"id":x.id,"type":x.type,"content":x.content,"metadata":x.metadata_,"created_at":x.created_at} for x in sorted(a.activities,key=lambda x:x.created_at,reverse=True)]}
@app.post("/applications/{application_id}/change-stage")
def api_change_stage(application_id:int,data:StageChange,db:Session=Depends(db_session)): a=get_or_404(db,Application,application_id); change_stage(db,a,data.target_stage,data.force); db.commit(); return app_card(a)
@app.post("/applications/{application_id}/set-blocked-by")
def set_blocked(application_id:int,data:BlockedChange,db:Session=Depends(db_session)):
    a=get_or_404(db,Application,application_id); before=a.blocked_by; a.blocked_by=data.blocked_by; activity(db,a.id,"BLOCKED_BY_CHANGED",f"等待对象：{before.value} → {data.blocked_by.value}"); db.commit(); return {"id":a.id,"blocked_by":a.blocked_by}
@app.patch("/applications/{application_id}/recruitment-info")
def recruitment(application_id:int,data:RecruitmentInfo,db:Session=Depends(db_session)):
    a=get_or_404(db,Application,application_id); changed=data.model_dump(exclude_unset=True); [setattr(a,k,v) for k,v in changed.items()]; activity(db,a.id,"RECRUITMENT_INFO_UPDATED","更新招聘确认信息",changed); db.commit(); return changed
@app.post("/applications/{application_id}/reject")
def reject(application_id:int,data:ReasonIn,db:Session=Depends(db_session)):
    a=get_or_404(db,Application,application_id); a.stage=PipelineStage.REJECTED; a.blocked_by=BlockedBy.NONE; a.rejection_reason=data.reason; [setattr(t,"status",TaskStatus.CANCELLED) for t in a.tasks if t.status==TaskStatus.TODO]; activity(db,a.id,"APPLICATION_REJECTED",f"淘汰候选人：{data.reason}"); db.commit(); return {"id":a.id,"stage":a.stage}
@app.post("/applications/{application_id}/withdraw")
def withdraw(application_id:int,data:ReasonIn,db:Session=Depends(db_session)):
    a=get_or_404(db,Application,application_id); a.stage=PipelineStage.WITHDRAWN; a.blocked_by=BlockedBy.NONE; a.rejection_reason=data.reason; activity(db,a.id,"APPLICATION_WITHDRAWN",f"候选人退出：{data.reason}"); db.commit(); return {"id":a.id,"stage":a.stage}
@app.post("/applications/{application_id}/hold")
def hold(application_id:int,data:ReasonIn,db:Session=Depends(db_session)):
    a=get_or_404(db,Application,application_id); a.stage_before_hold=a.stage; a.stage=PipelineStage.ON_HOLD; activity(db,a.id,"APPLICATION_HELD",f"暂缓候选人：{data.reason}"); db.commit(); return {"id":a.id,"stage":a.stage}
@app.post("/applications/{application_id}/resume")
def resume(application_id:int,db:Session=Depends(db_session)):
    a=get_or_404(db,Application,application_id); a.stage=a.stage_before_hold or PipelineStage.CONTACTING; a.stage_before_hold=None; activity(db,a.id,"APPLICATION_RESUMED","恢复候选人流程"); db.commit(); return {"id":a.id,"stage":a.stage}

@app.post("/applications/{application_id}/tasks",status_code=201)
def create_task(application_id:int,data:TaskIn,db:Session=Depends(db_session)):
    get_or_404(db,Application,application_id); t=Task(application_id=application_id,**data.model_dump()); db.add(t); db.flush(); activity(db,application_id,"TASK_CREATED",f"创建待办：{t.title}"); db.commit(); return task_view(t)
@app.get("/applications/{application_id}/tasks")
def application_tasks(application_id:int,status:TaskStatus|None=None,db:Session=Depends(db_session)):
    get_or_404(db,Application,application_id); q=select(Task).where(Task.application_id==application_id); q=q.where(Task.status==status) if status else q; return [task_view(t) for t in db.scalars(q.order_by(Task.created_at.desc())).all()]
@app.patch("/tasks/{task_id}")
def patch_task(task_id:int,data:TaskPatch,db:Session=Depends(db_session)):
    t=get_or_404(db,Task,task_id); [setattr(t,k,v) for k,v in data.model_dump(exclude_unset=True).items()]; activity(db,t.application_id,"TASK_UPDATED",f"修改待办：{t.title}"); db.commit(); return task_view(t)
@app.post("/tasks/{task_id}/{action}")
def task_action(task_id:int,action:str,db:Session=Depends(db_session)):
    t=get_or_404(db,Task,task_id)
    if action=="complete": t.status=TaskStatus.DONE; t.completed_at=datetime.now(); typ="TASK_COMPLETED"; msg=f"完成待办：{t.title}"
    elif action=="cancel": t.status=TaskStatus.CANCELLED; typ="TASK_CANCELLED"; msg=f"取消待办：{t.title}"
    else: raise HTTPException(404,detail="操作不存在")
    activity(db,t.application_id,typ,msg); db.commit(); return task_view(t)
@app.get("/tasks")
def all_tasks(status:TaskStatus|None=None,due:str|None=None,overdue:bool=False,job_id:int|None=None,candidate_id:int|None=None,db:Session=Depends(db_session)):
    q=select(Task).join(Task.application).options(selectinload(Task.application).selectinload(Application.candidate),selectinload(Task.application).selectinload(Application.job)); q=q.where(Task.status==status) if status else q; q=q.where(Application.job_id==job_id) if job_id else q; q=q.where(Application.candidate_id==candidate_id) if candidate_id else q; now=datetime.now(); start=datetime.combine(now.date(),time.min); end=start+timedelta(days=1); q=q.where(Task.due_at>=start,Task.due_at<end) if due=="today" else q; q=q.where(Task.due_at<now,Task.status==TaskStatus.TODO) if overdue else q; return [{**task_view(t),"application_id":t.application_id,"candidate_name":t.application.candidate.name,"job_title":t.application.job.title,"stage":t.application.stage} for t in db.scalars(q.order_by(Task.due_at)).all()]

@app.post("/applications/{application_id}/interviews",status_code=201)
def create_interview(application_id:int,data:InterviewIn,db:Session=Depends(db_session)):
    a=get_or_404(db,Application,application_id); i=Interview(application_id=application_id,**data.model_dump()); db.add(i); a.stage=PipelineStage.INTERVIEW_SCHEDULED; a.blocked_by=BlockedBy.NONE; db.flush(); activity(db,a.id,"INTERVIEW_CREATED",f"创建第 {i.round} 轮面试"); db.commit(); return interview_view(i)
@app.get("/applications/{application_id}/interviews")
def application_interviews(application_id:int,db:Session=Depends(db_session)): get_or_404(db,Application,application_id); return [interview_view(i) for i in db.scalars(select(Interview).where(Interview.application_id==application_id).order_by(Interview.round)).all()]
@app.patch("/interviews/{interview_id}")
def patch_interview(interview_id:int,data:InterviewPatch,db:Session=Depends(db_session)):
    i=get_or_404(db,Interview,interview_id); [setattr(i,k,v) for k,v in data.model_dump(exclude_unset=True).items()]; activity(db,i.application_id,"INTERVIEW_UPDATED",f"修改第 {i.round} 轮面试"); db.commit(); return interview_view(i)
@app.post("/interviews/{interview_id}/{action}")
def interview_action(interview_id:int,action:str,data:ReasonIn|None=None,db:Session=Depends(db_session)):
    i=get_or_404(db,Interview,interview_id); a=i.application
    if action=="complete": i.status=InterviewStatus.COMPLETED; a.stage=PipelineStage.FEEDBACK_PENDING; a.blocked_by=BlockedBy.INTERVIEWER; typ="INTERVIEW_COMPLETED"; msg=f"完成第 {i.round} 轮面试"
    elif action=="cancel": i.status=InterviewStatus.CANCELLED; a.stage=PipelineStage.SCHEDULING; typ="INTERVIEW_CANCELLED"; msg=f"取消面试：{data.reason if data else ''}"
    else: raise HTTPException(404,detail="操作不存在")
    activity(db,a.id,typ,msg); db.commit(); return interview_view(i)
@app.post("/applications/{application_id}/notes",status_code=201)
def note(application_id:int,data:NoteIn,db:Session=Depends(db_session)): get_or_404(db,Application,application_id); activity(db,application_id,"NOTE_ADDED",data.content); db.commit(); return {"ok":True}
@app.get("/applications/{application_id}/activities")
def activities(application_id:int,db:Session=Depends(db_session)): get_or_404(db,Application,application_id); return [{"id":x.id,"type":x.type,"content":x.content,"metadata":x.metadata_,"created_at":x.created_at} for x in db.scalars(select(Activity).where(Activity.application_id==application_id).order_by(Activity.created_at.desc())).all()]
@app.get("/search")
def search(q:str=Query(min_length=1),db:Session=Depends(db_session)):
    return {"candidates":[{"id":c.id,"name":c.name,"school":c.school} for c in db.scalars(select(Candidate).where(Candidate.name.contains(q)).limit(10)).all()],"jobs":[{"id":j.id,"title":j.title,"location":j.location} for j in db.scalars(select(Job).where(Job.title.contains(q)).limit(10)).all()]}

def seed(db:Session):
    if db.scalar(select(func.count()).select_from(Job)): return
    j1=Job(title="HRBP 实习生",department="人力资源部",location="杭州",salary_min=150,salary_max=200,owner_name="王晓");j2=Job(title="产品实习生",department="产品部",location="杭州",salary_min=180,salary_max=220,owner_name="陈默");db.add_all([j1,j2]);db.flush()
    specs=[("张子航","浙江大学",2027,"沟通确认",PipelineStage.CONTACTING,BlockedBy.CANDIDATE,"确认最长实习周期",-19), ("李思雨","南京大学",2027,"待筛选",PipelineStage.SCREENING,BlockedBy.HR,"查看并筛选简历",-3), ("王予安","复旦大学",2026,"待送面",PipelineStage.READY_TO_SUBMIT,BlockedBy.HR,"发送简历给面试官",18), ("周逸凡","中国人民大学",2027,"面试官评估",PipelineStage.INTERVIEWER_REVIEW,BlockedBy.INTERVIEWER,"跟进面试官评估",-1), ("林嘉乐","浙江大学",2027,"约面中",PipelineStage.SCHEDULING,BlockedBy.CANDIDATE,"确认面试时间",26), ("陈知行","同济大学",2026,"待面试",PipelineStage.INTERVIEW_SCHEDULED,BlockedBy.NONE,"参加一面",-5)]
    for idx,(name,school,year,_,stage,blocked,title,hours) in enumerate(specs):
        c=Candidate(name=name,school=school,graduation_year=year,current_city="杭州",phone=f"1380000{2200+idx}",email=f"candidate{idx+1}@example.com",source="Boss 直聘");db.add(c);db.flush();a=Application(job_id=j1.id,candidate_id=c.id,stage=stage,blocked_by=blocked);db.add(a);db.flush();t=Task(application_id=a.id,title=title,due_at=datetime.now()+timedelta(hours=hours),priority=Priority.HIGH if hours<0 else Priority.NORMAL);db.add(t);activity(db,a.id,"APPLICATION_CREATED","候选人加入岗位")
    db.flush(); first=db.scalar(select(Application).where(Application.stage==PipelineStage.INTERVIEW_SCHEDULED)); db.add(Interview(application_id=first.id,round=1,interviewer_name="李然",start_at=datetime.now().replace(hour=14,minute=0,second=0,microsecond=0),end_at=datetime.now().replace(hour=15,minute=0,second=0,microsecond=0)));db.commit()
@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine)
    with SessionLocal() as db: seed(db)
