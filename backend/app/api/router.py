from __future__ import annotations
from datetime import date, datetime, time, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload
from app.core.database import get_db
from app.core.enums import BlockedBy, InterviewStatus, JobStatus, PipelineStage, TaskStatus
from app.models import Activity, Application, Candidate, Interview, Job, Task
from app.schemas import ApplicationCreate, BlockedChange, CandidateIn, CandidatePatch, InterviewIn, InterviewPatch, JobIn, JobPatch, NoteIn, ReasonIn, RecruitmentInfo, StageChange, TaskIn, TaskPatch
from app.services.service import *

router = APIRouter()

@router.get("/health")
def health(): return {"status":"ok"}
@router.get("/dashboard")
def dashboard(db:Session=Depends(get_db)):
    now=datetime.now(); start=datetime.combine(now.date(),time.min); end=start+timedelta(days=1); active=list(db.scalars(select(Application).where(Application.stage.in_(NORMAL_STAGES))).all())
    return {"active_job_count":db.scalar(select(func.count()).select_from(Job).where(Job.status==JobStatus.ACTIVE)) or 0,"active_application_count":len(active),"today_task_count":db.scalar(select(func.count()).select_from(Task).where(Task.status==TaskStatus.TODO,Task.due_at>=start,Task.due_at<end)) or 0,"overdue_task_count":db.scalar(select(func.count()).select_from(Task).where(Task.status==TaskStatus.TODO,Task.due_at<now)) or 0,"today_interview_count":db.scalar(select(func.count()).select_from(Interview).where(Interview.status==InterviewStatus.SCHEDULED,Interview.start_at>=start,Interview.start_at<end)) or 0}
@router.get("/dashboard/tasks")
def dashboard_tasks(limit:int=10,db:Session=Depends(get_db)):
    rows=db.scalars(select(Task).join(Task.application).options(selectinload(Task.application).selectinload(Application.candidate),selectinload(Task.application).selectinload(Application.job)).where(Task.status==TaskStatus.TODO).order_by(Task.due_at.is_(None),Task.due_at).limit(limit)).all(); return [{**task_view(t),"candidate_id":t.application.candidate_id,"candidate_name":t.application.candidate.name,"job_id":t.application.job_id,"job_title":t.application.job.title,"application_id":t.application_id,"stage":t.application.stage,"blocked_by":t.application.blocked_by} for t in rows]
@router.get("/dashboard/interviews/today")
def today_interviews(db:Session=Depends(get_db)):
    start=datetime.combine(date.today(),time.min); end=start+timedelta(days=1); rows=db.scalars(select(Interview).options(selectinload(Interview.application).selectinload(Application.candidate),selectinload(Interview.application).selectinload(Application.job)).where(Interview.start_at>=start,Interview.start_at<end,Interview.status==InterviewStatus.SCHEDULED).order_by(Interview.start_at)).all(); return [{"id":i.id,"application_id":i.application_id,"candidate_name":i.application.candidate.name,"job_title":i.application.job.title,"start_at":i.start_at,"mode":i.mode,"interviewer_name":i.interviewer_name} for i in rows]
@router.get("/dashboard/jobs")
def dashboard_jobs(db:Session=Depends(get_db)): return [job_summary(db,j) for j in db.scalars(select(Job).where(Job.status==JobStatus.ACTIVE)).all()]

def job_summary(db:Session, job:Job):
    apps=db.scalars(select(Application).options(selectinload(Application.tasks)).where(Application.job_id==job.id)).all(); now=datetime.now(); stages={s.value:sum(a.stage==s for a in apps) for s in NORMAL_STAGES}; todos=[t for a in apps for t in a.tasks if t.status==TaskStatus.TODO]; return {"id":job.id,"title":job.title,"department":job.department,"location":job.location,"owner_name":job.owner_name,"status":job.status,"candidate_count":len(apps),"active_count":sum(a.stage in NORMAL_STAGES for a in apps),"stage_counts":stages,"today_task_count":sum(t.due_at and t.due_at.date()==date.today() for t in todos),"overdue_count":sum(t.due_at and t.due_at<now for t in todos)}
@router.get("/jobs")
def list_jobs(status:JobStatus|None=None,search:str|None=None,page:int=1,page_size:int=20,db:Session=Depends(get_db)):
    q=select(Job); q=q.where(Job.status==status) if status else q; q=q.where(or_(Job.title.contains(search),Job.department.contains(search))) if search else q; return {"items":[job_summary(db,j) for j in db.scalars(q.order_by(Job.updated_at.desc()).offset((page-1)*page_size).limit(page_size)).all()],"page":page,"page_size":page_size}
@router.post("/jobs",status_code=201)
def create_job(data:JobIn,db:Session=Depends(get_db)):
    job=Job(**data.model_dump()); db.add(job); db.commit(); db.refresh(job); return job_summary(db,job)
@router.get("/jobs/{job_id}")
def get_job(job_id:int,db:Session=Depends(get_db)): return job_view(get_or_404(db,Job,job_id))
@router.patch("/jobs/{job_id}")
def patch_job(job_id:int,data:JobPatch,db:Session=Depends(get_db)):
    job=get_or_404(db,Job,job_id); [setattr(job,k,v) for k,v in data.model_dump(exclude_unset=True).items()]; db.commit(); return job_summary(db,job)
@router.post("/jobs/{job_id}/actions/{action}")
def job_action(job_id:int,action:str,db:Session=Depends(get_db)):
    mapping={"pause":JobStatus.PAUSED,"resume":JobStatus.ACTIVE,"close":JobStatus.CLOSED};
    if action not in mapping: raise HTTPException(404,detail="操作不存在")
    job=get_or_404(db,Job,job_id); job.status=mapping[action]; db.commit(); return job_summary(db,job)
@router.post("/jobs/{job_id}/pause")
def pause_job(job_id:int,db:Session=Depends(get_db)): return job_action(job_id,"pause",db)
@router.post("/jobs/{job_id}/resume")
def resume_job(job_id:int,db:Session=Depends(get_db)): return job_action(job_id,"resume",db)
@router.post("/jobs/{job_id}/close")
def close_job(job_id:int,db:Session=Depends(get_db)): return job_action(job_id,"close",db)
@router.get("/jobs/{job_id}/stats")
def job_stats(job_id:int,db:Session=Depends(get_db)):
    job=get_or_404(db,Job,job_id); item=job_summary(db,job); return {"total_candidates":item["candidate_count"],"active_candidates":item["active_count"],"today_tasks":item["today_task_count"],"overdue_tasks":item["overdue_count"],"today_interviews":db.scalar(select(func.count()).select_from(Interview).join(Application).where(Application.job_id==job_id,Interview.start_at>=datetime.combine(date.today(),time.min),Interview.start_at<datetime.combine(date.today()+timedelta(days=1),time.min))) or 0,"offer_count":item["stage_counts"]["offer"],"stage_counts":item["stage_counts"]}
@router.post("/jobs/{job_id}/candidates",status_code=201)
def add_candidate(job_id:int,data:ApplicationCreate,db:Session=Depends(get_db)):
    get_or_404(db,Job,job_id); c=Candidate(**data.model_dump()); db.add(c); db.flush(); a=Application(job_id=job_id,candidate_id=c.id); db.add(a); db.flush(); activity(db,a.id,"APPLICATION_CREATED","候选人加入岗位"); db.commit(); db.refresh(a); return app_card(a)
@router.get("/jobs/{job_id}/applications")
def job_applications(job_id:int,stage:PipelineStage|None=None,blocked_by:BlockedBy|None=None,search:str|None=None,risk:str|None=None,db:Session=Depends(get_db)):
    get_or_404(db,Job,job_id); q=select(Application).options(selectinload(Application.candidate),selectinload(Application.tasks)).where(Application.job_id==job_id); q=q.where(Application.stage==stage) if stage else q; q=q.where(Application.blocked_by==blocked_by) if blocked_by else q; q=q.join(Application.candidate).where(Candidate.name.contains(search)) if search else q; cards=[app_card(a) for a in db.scalars(q).all()]; return [x for x in cards if not risk or (risk=="overdue" and x["is_overdue"]) or (risk=="no_task" and not x["primary_task"])]
@router.get("/jobs/{job_id}/kanban")
def kanban(job_id:int,db:Session=Depends(get_db)):
    cards=job_applications(job_id,db=db); return {stage.value:[c for c in cards if c["stage"]==stage] for stage in NORMAL_STAGES}

@router.post("/candidates",status_code=201)
def create_candidate(data:CandidateIn,db:Session=Depends(get_db)): c=Candidate(**data.model_dump()); db.add(c); db.commit(); db.refresh(c); return candidate_view(c)
@router.get("/candidates")
def list_candidates(search:str|None=None,school:str|None=None,job_id:int|None=None,stage:PipelineStage|None=None,page:int=1,page_size:int=50,db:Session=Depends(get_db)):
    q=select(Candidate).options(selectinload(Candidate.applications).selectinload(Application.job)); q=q.where(or_(Candidate.name.contains(search),Candidate.school.contains(search))) if search else q; q=q.where(Candidate.school.contains(school)) if school else q
    if job_id or stage: q=q.join(Candidate.applications).where(Application.job_id==job_id if job_id else True,Application.stage==stage if stage else True)
    rows=db.scalars(q.offset((page-1)*page_size).limit(page_size)).unique().all(); return {"items":[{"id":c.id,"name":c.name,"school":c.school,"graduation_year":c.graduation_year,"current_city":c.current_city,"applications":[{"id":a.id,"job_id":a.job_id,"job_title":a.job.title,"stage":a.stage,"blocked_by":a.blocked_by,"updated_at":a.updated_at} for a in c.applications]} for c in rows],"page":page,"page_size":page_size}
@router.get("/candidates/{candidate_id}")
def get_candidate(candidate_id:int,db:Session=Depends(get_db)): return candidate_view(get_or_404(db,Candidate,candidate_id))
@router.patch("/candidates/{candidate_id}")
def patch_candidate(candidate_id:int,data:CandidatePatch,db:Session=Depends(get_db)):
    c=get_or_404(db,Candidate,candidate_id); [setattr(c,k,v) for k,v in data.model_dump(exclude_unset=True).items()]; db.commit(); return candidate_view(c)
@router.get("/candidates/{candidate_id}/applications")
def candidate_apps(candidate_id:int,db:Session=Depends(get_db)):
    c=get_or_404(db,Candidate,candidate_id); return [{"application_id":a.id,"job_id":a.job_id,"job_title":a.job.title,"stage":a.stage,"blocked_by":a.blocked_by,"updated_at":a.updated_at} for a in db.scalars(select(Application).options(selectinload(Application.job)).where(Application.candidate_id==c.id)).all()]

@router.get("/applications/{application_id}")
def application_detail(application_id:int,db:Session=Depends(get_db)):
    a=db.scalar(select(Application).options(selectinload(Application.candidate),selectinload(Application.job),selectinload(Application.tasks),selectinload(Application.interviews),selectinload(Application.activities)).where(Application.id==application_id));
    if not a: raise HTTPException(404,detail="资源不存在")
    return {"id":a.id,"stage":a.stage,"blocked_by":a.blocked_by,"priority":a.priority,"candidate":candidate_view(a.candidate),"job":job_view(a.job),"recruitment_info":{"earliest_start_date":a.earliest_start_date,"internship_months":a.internship_months,"days_per_week":a.days_per_week,"salary_accepted":a.salary_accepted,"relocation_required":a.relocation_required,"relocation_accepted":a.relocation_accepted,"commute_minutes":a.commute_minutes},"tasks":[task_view(t) for t in sorted(a.tasks,key=lambda x:x.created_at,reverse=True)],"interviews":[interview_view(i) for i in a.interviews],"activities":[{"id":x.id,"type":x.type,"content":x.content,"metadata":x.metadata_,"created_at":x.created_at} for x in sorted(a.activities,key=lambda x:x.created_at,reverse=True)]}
@router.post("/applications/{application_id}/change-stage")
def api_change_stage(application_id:int,data:StageChange,db:Session=Depends(get_db)): a=get_or_404(db,Application,application_id); change_stage(db,a,data.target_stage,data.force); db.commit(); return app_card(a)
@router.post("/applications/{application_id}/set-blocked-by")
def set_blocked(application_id:int,data:BlockedChange,db:Session=Depends(get_db)):
    a=get_or_404(db,Application,application_id); before=a.blocked_by; a.blocked_by=data.blocked_by; activity(db,a.id,"BLOCKED_BY_CHANGED",f"等待对象：{before.value} → {data.blocked_by.value}"); db.commit(); return {"id":a.id,"blocked_by":a.blocked_by}
@router.patch("/applications/{application_id}/recruitment-info")
def recruitment(application_id:int,data:RecruitmentInfo,db:Session=Depends(get_db)):
    a=get_or_404(db,Application,application_id); changed=data.model_dump(exclude_unset=True); [setattr(a,k,v) for k,v in changed.items()]; activity(db,a.id,"RECRUITMENT_INFO_UPDATED","更新招聘确认信息",changed); db.commit(); return changed
@router.post("/applications/{application_id}/reject")
def reject(application_id:int,data:ReasonIn,db:Session=Depends(get_db)):
    a=get_or_404(db,Application,application_id); a.stage=PipelineStage.REJECTED; a.blocked_by=BlockedBy.NONE; a.rejection_reason=data.reason; [setattr(t,"status",TaskStatus.CANCELLED) for t in a.tasks if t.status==TaskStatus.TODO]; activity(db,a.id,"APPLICATION_REJECTED",f"淘汰候选人：{data.reason}"); db.commit(); return {"id":a.id,"stage":a.stage}
@router.post("/applications/{application_id}/withdraw")
def withdraw(application_id:int,data:ReasonIn,db:Session=Depends(get_db)):
    a=get_or_404(db,Application,application_id); a.stage=PipelineStage.WITHDRAWN; a.blocked_by=BlockedBy.NONE; a.rejection_reason=data.reason; activity(db,a.id,"APPLICATION_WITHDRAWN",f"候选人退出：{data.reason}"); db.commit(); return {"id":a.id,"stage":a.stage}
@router.post("/applications/{application_id}/hold")
def hold(application_id:int,data:ReasonIn,db:Session=Depends(get_db)):
    a=get_or_404(db,Application,application_id); a.stage_before_hold=a.stage; a.stage=PipelineStage.ON_HOLD; activity(db,a.id,"APPLICATION_HELD",f"暂缓候选人：{data.reason}"); db.commit(); return {"id":a.id,"stage":a.stage}
@router.post("/applications/{application_id}/resume")
def resume(application_id:int,db:Session=Depends(get_db)):
    a=get_or_404(db,Application,application_id); a.stage=a.stage_before_hold or PipelineStage.CONTACTING; a.stage_before_hold=None; activity(db,a.id,"APPLICATION_RESUMED","恢复候选人流程"); db.commit(); return {"id":a.id,"stage":a.stage}

@router.post("/applications/{application_id}/tasks",status_code=201)
def create_task(application_id:int,data:TaskIn,db:Session=Depends(get_db)):
    get_or_404(db,Application,application_id); t=Task(application_id=application_id,**data.model_dump()); db.add(t); db.flush(); activity(db,application_id,"TASK_CREATED",f"创建待办：{t.title}"); db.commit(); return task_view(t)
@router.get("/applications/{application_id}/tasks")
def application_tasks(application_id:int,status:TaskStatus|None=None,db:Session=Depends(get_db)):
    get_or_404(db,Application,application_id); q=select(Task).where(Task.application_id==application_id); q=q.where(Task.status==status) if status else q; return [task_view(t) for t in db.scalars(q.order_by(Task.created_at.desc())).all()]
@router.patch("/tasks/{task_id}")
def patch_task(task_id:int,data:TaskPatch,db:Session=Depends(get_db)):
    t=get_or_404(db,Task,task_id); [setattr(t,k,v) for k,v in data.model_dump(exclude_unset=True).items()]; activity(db,t.application_id,"TASK_UPDATED",f"修改待办：{t.title}"); db.commit(); return task_view(t)
@router.post("/tasks/{task_id}/{action}")
def task_action(task_id:int,action:str,db:Session=Depends(get_db)):
    t=get_or_404(db,Task,task_id)
    if action=="complete": t.status=TaskStatus.DONE; t.completed_at=datetime.now(); typ="TASK_COMPLETED"; msg=f"完成待办：{t.title}"
    elif action=="cancel": t.status=TaskStatus.CANCELLED; typ="TASK_CANCELLED"; msg=f"取消待办：{t.title}"
    else: raise HTTPException(404,detail="操作不存在")
    activity(db,t.application_id,typ,msg); db.commit(); return task_view(t)
@router.get("/tasks")
def all_tasks(status:TaskStatus|None=None,due:str|None=None,overdue:bool=False,job_id:int|None=None,candidate_id:int|None=None,db:Session=Depends(get_db)):
    q=select(Task).join(Task.application).options(selectinload(Task.application).selectinload(Application.candidate),selectinload(Task.application).selectinload(Application.job)); q=q.where(Task.status==status) if status else q; q=q.where(Application.job_id==job_id) if job_id else q; q=q.where(Application.candidate_id==candidate_id) if candidate_id else q; now=datetime.now(); start=datetime.combine(now.date(),time.min); end=start+timedelta(days=1); q=q.where(Task.due_at>=start,Task.due_at<end) if due=="today" else q; q=q.where(Task.due_at<now,Task.status==TaskStatus.TODO) if overdue else q; return [{**task_view(t),"application_id":t.application_id,"candidate_name":t.application.candidate.name,"job_title":t.application.job.title,"stage":t.application.stage} for t in db.scalars(q.order_by(Task.due_at)).all()]

@router.post("/applications/{application_id}/interviews",status_code=201)
def create_interview(application_id:int,data:InterviewIn,db:Session=Depends(get_db)):
    a=get_or_404(db,Application,application_id); i=Interview(application_id=application_id,**data.model_dump()); db.add(i); a.stage=PipelineStage.INTERVIEW_SCHEDULED; a.blocked_by=BlockedBy.NONE; db.flush(); activity(db,a.id,"INTERVIEW_CREATED",f"创建第 {i.round} 轮面试"); db.commit(); return interview_view(i)
@router.get("/applications/{application_id}/interviews")
def application_interviews(application_id:int,db:Session=Depends(get_db)): get_or_404(db,Application,application_id); return [interview_view(i) for i in db.scalars(select(Interview).where(Interview.application_id==application_id).order_by(Interview.round)).all()]
@router.patch("/interviews/{interview_id}")
def patch_interview(interview_id:int,data:InterviewPatch,db:Session=Depends(get_db)):
    i=get_or_404(db,Interview,interview_id); [setattr(i,k,v) for k,v in data.model_dump(exclude_unset=True).items()]; activity(db,i.application_id,"INTERVIEW_UPDATED",f"修改第 {i.round} 轮面试"); db.commit(); return interview_view(i)
@router.post("/interviews/{interview_id}/{action}")
def interview_action(interview_id:int,action:str,data:ReasonIn|None=None,db:Session=Depends(get_db)):
    i=get_or_404(db,Interview,interview_id); a=i.application
    if action=="complete": i.status=InterviewStatus.COMPLETED; a.stage=PipelineStage.FEEDBACK_PENDING; a.blocked_by=BlockedBy.INTERVIEWER; typ="INTERVIEW_COMPLETED"; msg=f"完成第 {i.round} 轮面试"
    elif action=="cancel": i.status=InterviewStatus.CANCELLED; a.stage=PipelineStage.SCHEDULING; typ="INTERVIEW_CANCELLED"; msg=f"取消面试：{data.reason if data else ''}"
    else: raise HTTPException(404,detail="操作不存在")
    activity(db,a.id,typ,msg); db.commit(); return interview_view(i)
@router.post("/applications/{application_id}/notes",status_code=201)
def note(application_id:int,data:NoteIn,db:Session=Depends(get_db)): get_or_404(db,Application,application_id); activity(db,application_id,"NOTE_ADDED",data.content); db.commit(); return {"ok":True}
@router.get("/applications/{application_id}/activities")
def activities(application_id:int,db:Session=Depends(get_db)): get_or_404(db,Application,application_id); return [{"id":x.id,"type":x.type,"content":x.content,"metadata":x.metadata_,"created_at":x.created_at} for x in db.scalars(select(Activity).where(Activity.application_id==application_id).order_by(Activity.created_at.desc())).all()]
@router.get("/search")
def search(q:str=Query(min_length=1),db:Session=Depends(get_db)):
    return {"candidates":[{"id":c.id,"name":c.name,"school":c.school} for c in db.scalars(select(Candidate).where(Candidate.name.contains(q)).limit(10)).all()],"jobs":[{"id":j.id,"title":j.title,"location":j.location} for j in db.scalars(select(Job).where(Job.title.contains(q)).limit(10)).all()]}

