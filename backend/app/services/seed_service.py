from datetime import datetime, timedelta
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.enums import BlockedBy, InterviewMode, PipelineStage, Priority
from app.models import Application, Candidate, Interview, Job, Task
from app.services.service import activity

def seed(db:Session):
    if db.scalar(select(func.count()).select_from(Job)): return
    j1=Job(title="HRBP 实习生",department="人力资源部",location="杭州",salary_min=150,salary_max=200,owner_name="王晓");j2=Job(title="产品实习生",department="产品部",location="杭州",salary_min=180,salary_max=220,owner_name="陈默");db.add_all([j1,j2]);db.flush()
    specs=[("张子航","浙江大学",2027,"沟通确认",PipelineStage.CONTACTING,BlockedBy.CANDIDATE,"确认最长实习周期",-19), ("李思雨","南京大学",2027,"待筛选",PipelineStage.SCREENING,BlockedBy.HR,"查看并筛选简历",-3), ("王予安","复旦大学",2026,"待送面",PipelineStage.READY_TO_SUBMIT,BlockedBy.HR,"发送简历给面试官",18), ("周逸凡","中国人民大学",2027,"面试官评估",PipelineStage.INTERVIEWER_REVIEW,BlockedBy.INTERVIEWER,"跟进面试官评估",-1), ("林嘉乐","浙江大学",2027,"约面中",PipelineStage.SCHEDULING,BlockedBy.CANDIDATE,"确认面试时间",26), ("陈知行","同济大学",2026,"待面试",PipelineStage.INTERVIEW_SCHEDULED,BlockedBy.NONE,"参加一面",-5)]
    for idx,(name,school,year,_,stage,blocked,title,hours) in enumerate(specs):
        c=Candidate(name=name,school=school,graduation_year=year,current_city="杭州",phone=f"1380000{2200+idx}",email=f"candidate{idx+1}@example.com",source="Boss 直聘");db.add(c);db.flush();a=Application(job_id=j1.id,candidate_id=c.id,stage=stage,blocked_by=blocked);db.add(a);db.flush();t=Task(application_id=a.id,title=title,due_at=datetime.now()+timedelta(hours=hours),priority=Priority.HIGH if hours<0 else Priority.NORMAL);db.add(t);activity(db,a.id,"APPLICATION_CREATED","候选人加入岗位")
    db.flush(); first=db.scalar(select(Application).where(Application.stage==PipelineStage.INTERVIEW_SCHEDULED)); db.add(Interview(application_id=first.id,round=1,interviewer_name="李然",start_at=datetime.now().replace(hour=14,minute=0,second=0,microsecond=0),end_at=datetime.now().replace(hour=15,minute=0,second=0,microsecond=0)));db.commit()
