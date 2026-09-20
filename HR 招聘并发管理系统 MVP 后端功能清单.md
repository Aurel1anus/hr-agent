# HR 招聘并发管理系统 MVP 后端功能清单

## 1. 后端目标

当前后端只负责：

> 招聘岗位、候选人、招聘流程、待办、面试和操作记录的数据管理与业务规则控制。

当前不负责：

```text
LLM
RAG
AI筛选
自动聊天
Boss接入
北森接入
钉钉接入
自动约面
自动发Offer
```

所有业务动作均由人类在 React 前端触发。

后端技术栈：

```text
Python
FastAPI
SQLAlchemy 2
Pydantic
Alembic
PostgreSQL
```

本地开发阶段可以暂时使用：

```text
SQLite
```

---

# 2. 后端核心职责

后端需要稳定回答六个问题：

```text
这个候选人是谁？

他属于哪个岗位？

当前处于哪个招聘阶段？

现在卡在谁？

下一步需要做什么？

过去发生过什么？
```

因此后端核心围绕：

```text
Job
Candidate
Application
Task
Interview
Activity
```

六个领域对象展开。

---

# 3. 推荐后端目录结构

```text
backend/

app/
├── main.py
│
├── api/
│   ├── dashboard.py
│   ├── jobs.py
│   ├── candidates.py
│   ├── applications.py
│   ├── tasks.py
│   ├── interviews.py
│   └── activities.py
│
├── models/
│   ├── job.py
│   ├── candidate.py
│   ├── application.py
│   ├── task.py
│   ├── interview.py
│   └── activity.py
│
├── schemas/
│   ├── dashboard.py
│   ├── job.py
│   ├── candidate.py
│   ├── application.py
│   ├── task.py
│   ├── interview.py
│   └── activity.py
│
├── services/
│   ├── dashboard_service.py
│   ├── job_service.py
│   ├── candidate_service.py
│   ├── application_service.py
│   ├── task_service.py
│   ├── interview_service.py
│   └── activity_service.py
│
├── repositories/
│   ├── job_repository.py
│   ├── candidate_repository.py
│   ├── application_repository.py
│   ├── task_repository.py
│   └── interview_repository.py
│
├── core/
│   ├── database.py
│   ├── config.py
│   ├── enums.py
│   ├── exceptions.py
│   └── pagination.py
│
└── migrations/
```

---

# 4. 核心数据模型

## Job

表示岗位。

```python
class Job:
    id

    title
    department
    location

    salary_min
    salary_max

    description

    status

    owner_id

    created_at
    updated_at
```

岗位状态：

```python
DRAFT
ACTIVE
PAUSED
CLOSED
```

---

# 5. Candidate

表示候选人本人。

```python
class Candidate:
    id

    name

    phone
    email

    school
    major

    graduation_year

    current_city

    source

    resume_url

    created_at
    updated_at
```

Candidate 不保存招聘流程状态。

---

# 6. Application

表示：

> 某个候选人在某个岗位中的一次招聘流程。

这是系统最重要的数据对象。

```python
class Application:
    id

    job_id
    candidate_id

    stage
    stage_changed_at

    blocked_by

    owner_id
    priority

    earliest_start_date
    internship_months
    days_per_week

    salary_accepted

    relocation_required
    relocation_accepted

    commute_minutes

    rejection_reason

    created_at
    updated_at

    archived_at
```

---

# 7. PipelineStage

```python
class PipelineStage(str, Enum):
    SCREENING = "screening"

    CONTACTING = "contacting"

    READY_TO_SUBMIT = "ready_to_submit"

    INTERVIEWER_REVIEW = "interviewer_review"

    SCHEDULING = "scheduling"

    INTERVIEW_SCHEDULED = "interview_scheduled"

    FEEDBACK_PENDING = "feedback_pending"

    DECISION_PENDING = "decision_pending"

    OFFER = "offer"

    REJECTED = "rejected"

    WITHDRAWN = "withdrawn"

    ON_HOLD = "on_hold"
```

---

# 8. BlockedBy

```python
class BlockedBy(str, Enum):
    NONE = "none"

    HR = "hr"

    CANDIDATE = "candidate"

    INTERVIEWER = "interviewer"

    SYSTEM = "system"
```

当前 MVP 主要使用：

```text
NONE
HR
CANDIDATE
INTERVIEWER
```

---

# 9. Task

```python
class Task:
    id

    application_id

    title
    description

    due_at

    status

    priority

    owner_id

    created_by_type
    created_by_id

    created_at
    completed_at
```

状态：

```python
TODO
DONE
CANCELLED
```

---

# 10. Interview

```python
class Interview:
    id

    application_id

    round

    interviewer_name
    interviewer_id

    start_at
    end_at

    mode

    location
    meeting_url

    status

    created_at
    updated_at
```

InterviewMode：

```python
ONLINE
OFFLINE
```

InterviewStatus：

```python
SCHEDULED
COMPLETED
CANCELLED
```

---

# 11. Activity

所有重要业务动作都形成 Activity。

```python
class Activity:
    id

    application_id

    type

    content

    actor_type
    actor_id

    metadata

    created_at
```

---

# 12. ActorType

虽然当前所有动作都是人工触发，但建议现在就定义：

```python
class ActorType(str, Enum):
    HUMAN = "human"
    AGENT = "agent"
    SYSTEM = "system"
```

当前默认：

```text
HUMAN
```

以后 Agent 可以直接复用。

---

# 13. Dashboard 后端功能

前端 Dashboard 需要一个聚合接口。

推荐：

```text
GET /dashboard
```

返回：

```json
{
  "active_job_count": 5,
  "active_application_count": 46,
  "today_task_count": 8,
  "overdue_task_count": 3,
  "today_interview_count": 4
}
```

---

# 14. Dashboard 待办

```text
GET /dashboard/tasks
```

支持：

```text
?limit=10
```

返回跨岗位待处理 Task。

每一条至少包含：

```text
task_id

task_title

due_at

is_overdue

candidate_id
candidate_name

job_id
job_title

application_id

stage

blocked_by
```

---

# 15. Dashboard 今日面试

```text
GET /dashboard/interviews/today
```

返回：

```text
候选人

岗位

开始时间

面试形式

面试官

Application ID
Interview ID
```

---

# 16. Dashboard 岗位概览

```text
GET /dashboard/jobs
```

每个岗位返回：

```text
岗位基本信息

候选人总数

进行中数量

各阶段数量

今日待办数量

逾期数量

今日面试数量
```

这样前端不用自己连续发十几个请求。

---

# 17. Job 后端功能

## 查询岗位列表

```text
GET /jobs
```

支持：

```text
?status=active

?search=HRBP

?page=1

?page_size=20
```

---

# 18. 创建岗位

```text
POST /jobs
```

Body：

```json
{
  "title": "HRBP实习生",
  "department": "人力资源部",
  "location": "杭州",
  "salary_min": 150,
  "salary_max": 200,
  "description": "...",
  "owner_id": null
}
```

默认：

```text
status = ACTIVE
```

或者也可以默认：

```text
DRAFT
```

第一版推荐直接 ACTIVE，减少一步操作。

---

# 19. 查询单个岗位

```text
GET /jobs/{job_id}
```

返回：

```text
岗位基础信息

岗位状态

负责人

创建时间

更新时间
```

---

# 20. 修改岗位

```text
PATCH /jobs/{job_id}
```

允许修改：

```text
title

department

location

salary_min

salary_max

description

owner_id
```

---

# 21. 暂停岗位

```text
POST /jobs/{job_id}/pause
```

更新：

```text
status = PAUSED
```

---

# 22. 恢复岗位

```text
POST /jobs/{job_id}/resume
```

更新：

```text
status = ACTIVE
```

---

# 23. 关闭岗位

```text
POST /jobs/{job_id}/close
```

更新：

```text
status = CLOSED
```

不真正删除岗位。

---

# 24. 岗位统计

```text
GET /jobs/{job_id}/stats
```

返回：

```text
total_candidates

active_candidates

today_tasks

overdue_tasks

today_interviews

offer_count
```

以及：

```text
stage_counts
```

例如：

```json
{
  "screening": 4,
  "contacting": 5,
  "ready_to_submit": 2,
  "interviewer_review": 3,
  "scheduling": 2,
  "interview_scheduled": 2,
  "feedback_pending": 1,
  "decision_pending": 1,
  "offer": 1
}
```

---

# 25. Candidate 后端功能

## 创建候选人

```text
POST /candidates
```

Body：

```json
{
  "name": "张三",
  "phone": null,
  "email": null,
  "school": "浙江大学",
  "major": null,
  "graduation_year": 2027,
  "current_city": "南京",
  "source": "Boss",
  "resume_url": null
}
```

---

# 26. 创建 Candidate + Application

前端在岗位页面点击：

```text
添加候选人
```

更推荐直接调用一个组合接口：

```text
POST /jobs/{job_id}/candidates
```

后端自动完成：

```text
创建 Candidate
+
创建 Application
```

默认：

```text
stage = SCREENING

blocked_by = HR
```

这样前端不需要：

```text
先 POST Candidate
再 POST Application
```

更符合实际业务。

---

# 27. 查询候选人

```text
GET /candidates/{candidate_id}
```

返回候选人本身基本信息。

---

# 28. 修改候选人

```text
PATCH /candidates/{candidate_id}
```

允许修改：

```text
name

phone

email

school

major

graduation_year

current_city

source

resume_url
```

---

# 29. 全部候选人搜索

```text
GET /candidates
```

支持：

```text
?search=张三

?school=浙江大学

?job_id=

?stage=

?page=

?page_size=
```

---

# 30. 查询候选人的全部 Application

```text
GET /candidates/{candidate_id}/applications
```

解决：

> 同一个人同时投多个岗位。

返回：

```text
job

stage

blocked_by

updated_at

application_id
```

---

# 31. Application 后端功能

Application 是业务逻辑中心。

需要：

```text
创建

查询

修改招聘信息

改变阶段

修改blocked_by

淘汰

退出

暂缓

恢复

获取时间线
```

---

# 32. 查询岗位下所有 Application

```text
GET /jobs/{job_id}/applications
```

支持：

```text
?stage=

?blocked_by=

?search=

?risk=

?owner_id=
```

---

# 33. Kanban 数据接口

为了降低 React 复杂度，可以专门提供：

```text
GET /jobs/{job_id}/kanban
```

返回结构：

```json
{
  "screening": [],
  "contacting": [],
  "ready_to_submit": [],
  "interviewer_review": [],
  "scheduling": [],
  "interview_scheduled": [],
  "feedback_pending": [],
  "decision_pending": [],
  "offer": []
}
```

每个卡片只返回 Kanban 真正需要的数据：

```text
application_id

candidate_id

candidate_name

school

graduation_year

stage

blocked_by

primary_task

task_due_at

is_overdue

stage_changed_at
```

这样前端不需要自己分组。

---

# 34. Application 详情

```text
GET /applications/{application_id}
```

返回 Candidate Drawer 所需完整数据。

推荐一次返回：

```text
Candidate基本信息

Job信息

Application信息

当前Task

全部Task

Interview

Notes / Activities

招聘信息
```

或者拆接口。

第一版为了简单，推荐：

> Drawer 首次打开走一个详情聚合接口。

---

# 35. 更新招聘确认信息

例如：

```text
最快到岗日期

每周到岗天数

最长实习周期

是否接受薪资

异地搬迁

通勤时间
```

使用：

```text
PATCH /applications/{id}/recruitment-info
```

Body：

```json
{
  "earliest_start_date": "2026-09-30",
  "days_per_week": 5,
  "internship_months": 6,
  "salary_accepted": true,
  "relocation_required": true,
  "relocation_accepted": true,
  "commute_minutes": null
}
```

每一个有变化的字段需要记录 Activity。

---

# 36. 改变招聘阶段

```text
POST /applications/{id}/change-stage
```

Body：

```json
{
  "target_stage": "ready_to_submit"
}
```

Service 需要：

```text
校验 Application 是否存在

校验状态转换是否合法

更新 stage

更新 stage_changed_at

记录 Activity
```

---

# 37. 正常状态流转

默认正常路径：

```text
SCREENING
→ CONTACTING
→ READY_TO_SUBMIT
→ INTERVIEWER_REVIEW
→ SCHEDULING
→ INTERVIEW_SCHEDULED
→ FEEDBACK_PENDING
→ DECISION_PENDING
→ OFFER
```

---

# 38. 非正常跨阶段

允许管理员手动跨阶段，但请求需要明确：

```json
{
  "target_stage": "interview_scheduled",
  "force": true
}
```

后端记录：

```text
原阶段

目标阶段

操作人

是否强制跳转
```

---

# 39. 修改 blocked_by

```text
POST /applications/{id}/set-blocked-by
```

Body：

```json
{
  "blocked_by": "candidate"
}
```

Service：

```text
更新 blocked_by

记录 Activity
```

---

# 40. 淘汰候选人

```text
POST /applications/{id}/reject
```

Body：

```json
{
  "reason": "无法满足每周5天实习要求"
}
```

后端：

```text
stage = REJECTED

保存 rejection_reason

blocked_by = NONE

记录 Activity

可选：
取消未完成 Task
```

建议第一版自动取消该 Application 的未完成 Task。

---

# 41. 候选人主动退出

```text
POST /applications/{id}/withdraw
```

Body：

```json
{
  "reason": "已接受其他Offer"
}
```

更新：

```text
stage = WITHDRAWN
blocked_by = NONE
```

---

# 42. 暂缓候选人

```text
POST /applications/{id}/hold
```

Body：

```json
{
  "reason": "等待HC确认"
}
```

更新：

```text
stage = ON_HOLD
```

建议同时保存：

```text
previous_stage
```

便于后面恢复。

---

# 43. 恢复暂缓候选人

```text
POST /applications/{id}/resume
```

恢复到：

```text
previous_stage
```

如果没有 previous_stage：

```text
CONTACTING
```

或要求前端指定恢复阶段。

更推荐保存：

```text
stage_before_hold
```

---

# 44. Task 后端功能

Task 是并发管理的核心。

需要：

```text
创建

查询

修改

完成

取消

逾期判断

跨岗位查询
```

---

# 45. 创建 Task

```text
POST /applications/{id}/tasks
```

Body：

```json
{
  "title": "确认最长实习周期",
  "description": null,
  "due_at": "2026-09-21T18:00:00",
  "priority": "normal"
}
```

---

# 46. 查询某 Application 的 Task

```text
GET /applications/{id}/tasks
```

支持：

```text
?status=todo
```

---

# 47. 修改 Task

```text
PATCH /tasks/{task_id}
```

支持修改：

```text
title

description

due_at

priority

owner_id
```

---

# 48. 完成 Task

```text
POST /tasks/{task_id}/complete
```

后端：

```text
status = DONE

completed_at = now()
```

同时生成 Activity。

---

# 49. 取消 Task

```text
POST /tasks/{task_id}/cancel
```

更新：

```text
status = CANCELLED
```

不删除。

---

# 50. 全部 Task 查询

```text
GET /tasks
```

支持：

```text
?status=

?due=today

?overdue=true

?job_id=

?candidate_id=

?owner_id=

?page=

?page_size=
```

---

# 51. 今日 Task

逻辑：

```text
status = TODO

due_at >= today_start

due_at <= today_end
```

---

# 52. 逾期 Task

逻辑：

```text
status = TODO

due_at < now()
```

---

# 53. Primary Task

Kanban 卡片只展示一个 Task。

推荐后端计算：

```text
priority最高
+
截止时间最近
```

返回：

```text
primary_task
```

不要让前端自己决定。

---

# 54. Interview 后端功能

需要支持：

```text
创建面试

查询面试

修改面试

重新安排

完成面试

取消面试

多轮面试
```

---

# 55. 创建面试

```text
POST /applications/{id}/interviews
```

Body：

```json
{
  "round": 1,
  "interviewer_name": "李XX",
  "start_at": "2026-09-22T14:30:00",
  "end_at": "2026-09-22T15:30:00",
  "mode": "online",
  "meeting_url": "...",
  "location": null
}
```

创建成功后建议自动：

```text
Application.stage
→ INTERVIEW_SCHEDULED

blocked_by
→ NONE
```

并记录 Activity。

---

# 56. 查询 Application 面试

```text
GET /applications/{id}/interviews
```

返回全部轮次。

---

# 57. 修改面试

```text
PATCH /interviews/{interview_id}
```

支持：

```text
start_at

end_at

interviewer

mode

location

meeting_url
```

任何重要变更都记录 Activity。

---

# 58. 重新约面

可以直接使用 PATCH。

也可以提供语义接口：

```text
POST /interviews/{id}/reschedule
```

第一版推荐直接 PATCH，少写接口。

---

# 59. 面试完成

```text
POST /interviews/{id}/complete
```

后端自动：

```text
Interview.status = COMPLETED
```

同时：

```text
Application.stage
→ FEEDBACK_PENDING
```

通常：

```text
blocked_by
→ INTERVIEWER
```

生成 Activity。

---

# 60. 取消面试

```text
POST /interviews/{id}/cancel
```

Body：

```json
{
  "reason": "候选人临时无法参加"
}
```

更新：

```text
Interview.status = CANCELLED
```

Application 默认回：

```text
SCHEDULING
```

便于重新约面。

---

# 61. 进入下一轮面试

```text
POST /applications/{id}/next-interview-round
```

后端：

```text
stage = SCHEDULING
```

然后前端重新创建下一轮 Interview。

也可以不做这个专门接口，而使用：

```text
change-stage → SCHEDULING
```

第一版推荐复用 `change-stage`。

---

# 62. Activity 后端功能

Activity 是只增不改的数据。

主要负责：

```text
保存历史动作

提供时间线
```

---

# 63. Activity 类型

建议先定义：

```text
APPLICATION_CREATED

STAGE_CHANGED

BLOCKED_BY_CHANGED

CANDIDATE_UPDATED

RECRUITMENT_INFO_UPDATED

TASK_CREATED

TASK_UPDATED

TASK_COMPLETED

TASK_CANCELLED

INTERVIEW_CREATED

INTERVIEW_UPDATED

INTERVIEW_COMPLETED

INTERVIEW_CANCELLED

NOTE_ADDED

APPLICATION_REJECTED

APPLICATION_WITHDRAWN

APPLICATION_HELD

APPLICATION_RESUMED
```

---

# 64. Candidate Notes

备注可以直接建 Activity：

```text
type = NOTE_ADDED
```

不一定需要单独 Note 表。

接口：

```text
POST /applications/{id}/notes
```

Body：

```json
{
  "content": "候选人目前人在南京，愿意去杭州租房。"
}
```

后端写 Activity。

---

# 65. 查询时间线

```text
GET /applications/{id}/activities
```

支持：

```text
?page=

?page_size=
```

默认：

```text
created_at DESC
```

---

# 66. 全局搜索

前端顶部搜索需要：

```text
GET /search?q=张三
```

第一版搜索：

```text
Candidate name

Job title
```

返回：

```json
{
  "candidates": [],
  "jobs": []
}
```

---

# 67. 数据校验

后端必须校验基本业务规则。

例如：

```text
salary_min <= salary_max
```

```text
days_per_week
只能是 1-7
```

```text
internship_months >= 0
```

```text
graduation_year
必须合理
```

```text
Interview.end_at > Interview.start_at
```

---

# 68. 删除策略

第一版尽量：

```text
不真正 DELETE
```

岗位：

```text
CLOSED
```

Application：

```text
REJECTED
WITHDRAWN
ON_HOLD
```

Task：

```text
CANCELLED
```

Interview：

```text
CANCELLED
```

这样历史记录完整。

---

# 69. 事务 Transaction

以下操作必须放事务里。

例如：

```text
创建 Candidate
+
创建 Application
```

必须：

```text
一起成功
或者一起失败
```

---

创建 Interview 时：

```text
创建 Interview
+
Application进入待面试
+
创建 Activity
```

也是一个事务。

---

完成 Interview：

```text
Interview → COMPLETED
+
Application → FEEDBACK_PENDING
+
Activity
```

同样一个事务。

---

# 70. ApplicationService

推荐至少有：

```python
class ApplicationService:

    def create_application():
        pass

    def get_application_detail():
        pass

    def change_stage():
        pass

    def set_blocked_by():
        pass

    def update_recruitment_info():
        pass

    def reject():
        pass

    def withdraw():
        pass

    def hold():
        pass

    def resume():
        pass
```

---

# 71. JobService

```python
class JobService:

    def create_job():
        pass

    def update_job():
        pass

    def get_job():
        pass

    def list_jobs():
        pass

    def pause_job():
        pass

    def resume_job():
        pass

    def close_job():
        pass

    def get_job_stats():
        pass
```

---

# 72. CandidateService

```python
class CandidateService:

    def create_candidate():
        pass

    def update_candidate():
        pass

    def get_candidate():
        pass

    def list_candidates():
        pass

    def get_candidate_applications():
        pass
```

---

# 73. TaskService

```python
class TaskService:

    def create_task():
        pass

    def update_task():
        pass

    def complete_task():
        pass

    def cancel_task():
        pass

    def list_tasks():
        pass

    def get_primary_task():
        pass
```

---

# 74. InterviewService

```python
class InterviewService:

    def create_interview():
        pass

    def update_interview():
        pass

    def complete_interview():
        pass

    def cancel_interview():
        pass

    def list_interviews():
        pass
```

---

# 75. ActivityService

```python
class ActivityService:

    def record():
        pass

    def add_note():
        pass

    def list_for_application():
        pass
```

Activity 写入尽量统一从 Service 调用。

---

# 76. DashboardService

```python
class DashboardService:

    def get_summary():
        pass

    def get_today_tasks():
        pass

    def get_overdue_tasks():
        pass

    def get_today_interviews():
        pass

    def get_job_overview():
        pass
```

---

# 77. Repository 层

Repository 只负责：

```text
SQL 查询
数据库 CRUD
```

例如：

```python
class ApplicationRepository:

    def get_by_id():
        pass

    def list_by_job():
        pass

    def create():
        pass

    def update():
        pass
```

Repository 不应该包含：

```text
招聘流程规则

状态流转判断

是否需要创建Activity
```

这些属于 Service。

---

# 78. API 层职责

FastAPI Route 只负责：

```text
接收请求

校验参数

识别当前用户

调用 Service

返回 Response
```

不要写：

```text
复杂业务逻辑
SQL
状态流转规则
```

---

# 79. 前端不能决定业务规则

例如 React 拖动：

```text
SCREENING
→ OFFER
```

前端可以发请求。

但最终能不能成功必须由后端：

```text
ApplicationService
```

决定。

否则以后 Agent、移动端或其他客户端可能绕过前端规则。

---

# 80. 错误返回

统一错误结构，例如：

```json
{
  "code": "INVALID_STAGE_TRANSITION",
  "message": "不能直接从待筛选进入Offer阶段"
}
```

常见：

```text
JOB_NOT_FOUND

CANDIDATE_NOT_FOUND

APPLICATION_NOT_FOUND

TASK_NOT_FOUND

INTERVIEW_NOT_FOUND

INVALID_STAGE_TRANSITION

INVALID_INTERVIEW_TIME

VALIDATION_ERROR
```

---

# 81. 并发更新

因为系统核心就是“并发候选人管理”，后面可能出现：

```text
两个浏览器窗口同时修改同一个候选人
```

第一版至少使用：

```text
updated_at
```

未来可增加：

```text
version
```

做乐观锁。

例如：

```text
version = 5
```

前端修改时携带：

```text
version = 5
```

如果数据库已经变成：

```text
version = 6
```

则提示：

```text
候选人信息已经被其他操作修改，请刷新后重试。
```

MVP 第一版可暂缓实现，但数据结构可以预留。

---

# 82. 数据库索引

建议至少：

```text
applications.job_id

applications.candidate_id

applications.stage

applications.blocked_by

tasks.application_id

tasks.status

tasks.due_at

interviews.application_id

interviews.start_at

activities.application_id

activities.created_at
```

否则候选人多起来后 Dashboard 查询会慢。

---

# 83. 分页

以下接口必须准备分页：

```text
GET /jobs

GET /candidates

GET /tasks

GET /applications/{id}/activities
```

统一返回：

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 134
}
```

---

# 84. 日期时间处理

数据库统一存：

```text
UTC
```

API 返回：

```text
ISO 8601
```

例如：

```text
2026-09-22T06:30:00Z
```

前端负责转换成本地时区。

不要数据库里直接存：

```text
明天下午
```

---

# 85. 未来 Agent 接入接口

当前所有操作来源：

```text
React
↓
FastAPI
↓
Service
```

未来：

```text
Agent
↓
Tool
↓
同一个 Service
```

例如未来 Agent Tool：

```python
change_candidate_stage()
```

内部仍然调用：

```python
ApplicationService.change_stage()
```

---

# 86. 未来外部平台 Adapter

以后 Boss、北森、钉钉不要直接侵入业务代码。

建议：

```text
integrations/

├── boss/
├── beisen/
├── dingtalk/
└── calendar/
```

结构：

```text
External Platform

↓

Adapter

↓

ApplicationService
InterviewService
TaskService

↓

Database
```

---

# 87. 第一阶段必做 API 总表

Dashboard：

```text
GET /dashboard

GET /dashboard/tasks

GET /dashboard/interviews/today

GET /dashboard/jobs
```

Job：

```text
GET    /jobs

POST   /jobs

GET    /jobs/{id}

PATCH  /jobs/{id}

POST   /jobs/{id}/pause

POST   /jobs/{id}/resume

POST   /jobs/{id}/close

GET    /jobs/{id}/stats

GET    /jobs/{id}/kanban
```

Candidate：

```text
GET    /candidates

POST   /candidates

GET    /candidates/{id}

PATCH  /candidates/{id}

GET    /candidates/{id}/applications

POST   /jobs/{job_id}/candidates
```

Application：

```text
GET   /applications/{id}

PATCH /applications/{id}/recruitment-info

POST  /applications/{id}/change-stage

POST  /applications/{id}/set-blocked-by

POST  /applications/{id}/reject

POST  /applications/{id}/withdraw

POST  /applications/{id}/hold

POST  /applications/{id}/resume
```

Task：

```text
GET   /tasks

GET   /applications/{id}/tasks

POST  /applications/{id}/tasks

PATCH /tasks/{id}

POST  /tasks/{id}/complete

POST  /tasks/{id}/cancel
```

Interview：

```text
GET   /applications/{id}/interviews

POST  /applications/{id}/interviews

PATCH /interviews/{id}

POST  /interviews/{id}/complete

POST  /interviews/{id}/cancel
```

Activity：

```text
GET  /applications/{id}/activities

POST /applications/{id}/notes
```

Search：

```text
GET /search
```

---

# 88. 第一阶段真正必须实现的后端能力

如果还要进一步缩 MVP，我建议最先实现：

```text
创建岗位

查看岗位

添加候选人

查看岗位Kanban

查看Application详情

改变阶段

设置blocked_by

编辑招聘确认信息

创建Task

完成Task

创建Interview

完成Interview

添加备注

查询Activity Timeline
```

只要这些完成：

```text
React Dashboard
+
岗位 Kanban
+
Candidate Drawer
```

就能真正跑起来。

---

# 89. 推荐开发顺序

## 第一步

搭建：

```text
FastAPI

SQLAlchemy

Alembic

Database
```

---

## 第二步

建六个模型：

```text
Job

Candidate

Application

Task

Interview

Activity
```

---

## 第三步

完成：

```text
Job CRUD

Candidate CRUD

Application创建
```

---

## 第四步

完成招聘状态逻辑：

```text
change_stage

set_blocked_by

reject

withdraw

hold
```

---

## 第五步

Task：

```text
create

complete

cancel

list
```

---

## 第六步

Interview：

```text
create

update

complete

cancel
```

---

## 第七步

Activity：

```text
状态变化记录

字段修改记录

Task记录

Interview记录

备注
```

---

## 第八步

Kanban 聚合接口：

```text
GET /jobs/{id}/kanban
```

---

## 第九步

Dashboard 聚合接口。

---

# 90. 后端最终架构

```text
React
   │
   │ HTTP / JSON
   ▼
FastAPI API
   │
   ▼
Service Layer
   │
   ├── JobService
   ├── CandidateService
   ├── ApplicationService
   ├── TaskService
   ├── InterviewService
   └── ActivityService
   │
   ▼
Repository
   │
   ▼
SQLAlchemy
   │
   ▼
PostgreSQL
```

未来变成：

```text
React ───────┐
             │
Agent ───────┼──→ Service Layer → Database
             │
Boss Adapter ┤
北森 Adapter ┤
钉钉 Adapter ┘
```

也就是说：

> 当前人工招聘流程和未来 Agent 自动化，共用同一套业务服务层。

这样以后增加 AI 时，不需要重新设计招聘流程数据库和后端业务规则。

---

# 91. 后端 MVP 验收标准

后端完成后应该能够完整支持以下流程：

```text
创建一个 HRBP 实习生岗位
↓
添加 20 个候选人
↓
候选人默认进入待筛选
↓
HR推进某人进入沟通确认
↓
设置正在等待候选人
↓
创建“确认实习周期”Task
↓
候选人回复后人工填写6个月
↓
完成Task
↓
进入待送面
↓
进入面试官评估
↓
设置等待面试官
↓
面试官通过
↓
进入约面中
↓
创建Interview
↓
进入待面试
↓
面试完成
↓
进入待面评
↓
进入待结果
↓
Offer
```

并且整个过程中：

```text
所有阶段变化

所有任务

所有面试

所有备注

所有关键字段修改
```

都可以在 Activity Timeline 中追溯。

这就是当前 React MVP 对应的完整后端能力。