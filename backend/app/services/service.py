from __future__ import annotations
from datetime import datetime
from typing import Any
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.enums import BlockedBy, PipelineStage, Priority, TaskStatus
from app.models import Application, Candidate, Interview, Job, Task, Activity

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

