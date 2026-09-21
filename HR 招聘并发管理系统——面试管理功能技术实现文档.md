# HR 招聘并发管理系统——面试管理功能技术实现文档

## 1. 功能目标

在现有招聘流程管理系统中补全面试管理能力，解决：

```text
一面 / 二面 / 三面 / 终面

约面时间协调

面试时间确认

面试改期

面试取消

面试完成

面评记录

面试结果

进入下一轮面试
```

核心目标：

> Application 负责记录“招聘流程现在进行到哪里”，Interview 负责记录“这一轮面试具体是什么、什么时候、谁来面、结果如何”。

不能把：

```text
一面
二面
三面
```

设计成 Pipeline Stage。

---

# 2. 核心设计原则

系统中必须区分两个概念：

## Application Stage

回答：

> 当前招聘流程正在做什么？

例如：

```text
约面中
待面试
待面评
待结果
```

---

## Interview Round

回答：

> 当前是第几轮面试？

例如：

```text
一面
二面
业务面
HR面
终面
```

最终页面可能显示：

```text
二面 · 约面中
```

或者：

```text
一面 · 待面评
```

而数据库实际是：

```text
Application.stage = SCHEDULING

Interview.round_name = 二面
```

---

# 3. Application Pipeline

现有 Pipeline 保持：

```text
待筛选
↓
沟通确认
↓
待送面
↓
面试官评估
↓
约面中
↓
待面试
↓
待面评
↓
待结果
↓
Offer
```

对应：

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

# 4. Application 增加 current_interview_id

建议 Application 增加：

```python
current_interview_id: UUID | None
```

作用：

> 快速知道当前正在处理哪一轮 Interview。

例如：

```text
Application

stage = INTERVIEW_SCHEDULED

current_interview_id = Interview #32
```

Interview #32：

```text
round_number = 2

round_name = 二面

scheduled_start_at =
2026-09-23 15:00
```

前端即可直接展示：

```text
二面 · 待面试

9月23日 15:00
```

---

# 5. Interview 数据模型

推荐最终结构：

```python
class Interview(Base):
    __tablename__ = "interviews"

    id: UUID

    application_id: UUID

    round_number: int

    round_name: str

    status: InterviewStatus

    candidate_availability: str | None

    interviewer_availability: str | None

    scheduled_start_at: datetime | None

    scheduled_end_at: datetime | None

    interviewer_name: str | None

    interviewer_id: UUID | None

    mode: InterviewMode | None

    location: str | None

    meeting_url: str | None

    feedback: str | None

    result: InterviewResult | None

    cancel_reason: str | None

    created_at: datetime

    updated_at: datetime
```

---

# 6. InterviewStatus

```python
class InterviewStatus(str, Enum):
    SCHEDULING = "scheduling"

    SCHEDULED = "scheduled"

    COMPLETED = "completed"

    CANCELLED = "cancelled"
```

含义：

```text
SCHEDULING

双方正在协调时间
```

```text
SCHEDULED

具体面试时间已经确定
```

```text
COMPLETED

这一轮已经面试结束
```

```text
CANCELLED

这一轮面试取消
```

---

# 7. InterviewResult

建议：

```python
class InterviewResult(str, Enum):
    PENDING = "pending"

    PASS = "pass"

    NEXT_ROUND = "next_round"

    REJECT = "reject"
```

含义：

```text
PENDING
尚未给结果

PASS
面试通过，招聘流程可以继续进入Offer/最终决策

NEXT_ROUND
这一轮通过，需要下一轮面试

REJECT
这一轮淘汰
```

---

# 8. InterviewMode

```python
class InterviewMode(str, Enum):
    ONLINE = "online"

    OFFLINE = "offline"
```

---

# 9. 为什么 round_number 和 round_name 都要保存

只保存：

```text
round = 1
```

不够。

因为现实业务可能不是：

```text
一面
二面
三面
```

而是：

```text
HR初面
业务一面
主管面
终面
```

因此：

```python
round_number = 2
round_name = "业务一面"
```

比较合理。

例如：

```text
Round 1
HR初面

Round 2
业务面

Round 3
终面
```

---

# 10. 创建第一轮面试

当：

```text
Application.stage =
INTERVIEWER_REVIEW
```

面试官确认愿意见候选人。

点击：

```text
进入约面
```

后端执行：

```text
创建 Interview

round_number = 1

round_name = 一面

status = SCHEDULING
```

同时：

```text
Application.stage = SCHEDULING

Application.current_interview_id =
new_interview.id
```

---

# 11. 创建接口

推荐：

```text
POST /applications/{application_id}/interviews
```

Body：

```json
{
  "round_name": "一面"
}
```

如果不传 `round_number`：

后端自动：

```text
当前最大round_number + 1
```

例如当前没有 Interview：

```text
round_number = 1
```

已有一面：

```text
round_number = 2
```

---

# 12. 约面阶段

进入：

```text
Application.stage = SCHEDULING

Interview.status = SCHEDULING
```

这个阶段 HR 需要协调：

```text
候选人什么时候有空

面试官什么时候有空

最终安排什么时候
```

---

# 13. 候选人可用时间

MVP 不需要复杂 Calendar Slot 模型。

直接：

```python
candidate_availability: str | None
```

例如：

```text
周三下午2点以后，周四全天
```

这是非常适合人工招聘的形式。

---

# 14. 面试官可用时间

同样：

```python
interviewer_availability: str | None
```

例如：

```text
周三15:00-17:00
周五上午
```

---

# 15. 为什么先用文本而不是时间段数组

以后可以设计：

```json
[
  {
    "start": "...",
    "end": "..."
  }
]
```

但 MVP 没必要。

因为现实中很多 HR 得到的信息本身就是：

```text
下午都可以

周三两点之后

上午除了十点都行
```

文本更容易记录。

以后接 Calendar 时再结构化。

---

# 16. 更新约面信息

接口：

```text
PATCH /interviews/{interview_id}
```

Body 可以：

```json
{
  "candidate_availability": "周三14点以后",
  "interviewer_availability": "周三15点到17点"
}
```

---

# 17. 确认具体面试时间

当双方时间一致后：

前端：

```text
确认面试时间
```

填写：

```text
日期

开始时间

预计结束时间

线上 / 线下

面试官

会议链接 / 地点
```

推荐专门接口：

```text
POST /interviews/{interview_id}/schedule
```

Body：

```json
{
  "scheduled_start_at": "2026-09-23T15:00:00",
  "scheduled_end_at": "2026-09-23T16:00:00",
  "interviewer_name": "李XX",
  "mode": "online",
  "meeting_url": "https://..."
}
```

---

# 18. schedule 后端行为

`InterviewService.schedule()`：

```text
验证 Interview 存在

验证 Interview.status = SCHEDULING

验证结束时间 > 开始时间

更新具体时间

status = SCHEDULED
```

然后：

```text
Application.stage =
INTERVIEW_SCHEDULED

Application.blocked_by =
NONE
```

记录 Activity：

```text
二面已安排：
9月23日 15:00
面试官：李XX
```

整个操作放 Transaction。

---

# 19. Candidate Card 展示

约面中：

```text
张三

浙江大学 · 27届

二面 · 约面中

等待面试官

确认周三下午时间
```

待面试：

```text
张三

浙江大学 · 27届

二面 · 待面试

9月23日 15:00

李XX
```

---

# 20. Candidate Drawer 面试区域

建议增加独立：

```text
面试
```

模块。

当前面试：

```text
二面

状态：
待面试

时间：
9月23日 15:00 - 16:00

面试官：
李XX

形式：
线上

会议：
查看会议链接
```

操作：

```text
重新约面

取消面试

标记面试完成
```

---

# 21. 面试历史

Drawer 同时显示：

```text
面试记录
```

例如：

```text
✓ 一面
  9月20日 14:00
  王XX
  结果：进入下一轮

● 二面
  9月23日 15:00
  李XX
  待面试
```

如果三轮：

```text
✓ HR初面
✓ 业务面
● 终面
```

---

# 22. 面试完成

按钮：

```text
面试完成
```

接口：

```text
POST /interviews/{interview_id}/complete
```

后端：

```text
Interview.status =
COMPLETED
```

同时：

```text
Application.stage =
FEEDBACK_PENDING
```

通常：

```text
Application.blocked_by =
INTERVIEWER
```

因为接下来：

```text
等待面试官面评
```

Activity：

```text
二面已完成，等待面评
```

---

# 23. 待面评页面

Candidate Drawer：

```text
二面 · 待面评

面试时间：
9月23日 15:00

面试官：
李XX

面评：
[                            ]

结果：
○ 通过
○ 进入下一轮
○ 淘汰
```

---

# 24. 保存面评

推荐：

```text
POST /interviews/{interview_id}/feedback
```

Body：

```json
{
  "feedback": "候选人沟通能力较好，业务理解较快。",
  "result": "next_round"
}
```

---

# 25. 面评完成后的流程

根据 Result：

## NEXT_ROUND

执行：

```text
当前 Interview.result =
NEXT_ROUND
```

创建下一轮：

```text
round_number + 1
```

例如：

```text
一面
↓
二面
```

新 Interview：

```text
status = SCHEDULING
```

Application：

```text
stage = SCHEDULING

current_interview_id =
new_interview.id
```

---

## REJECT

执行：

```text
Interview.result = REJECT
```

Application：

```text
stage = REJECTED

blocked_by = NONE
```

可以同步填写：

```text
rejection_reason
```

---

## PASS

执行：

```text
Interview.result = PASS
```

Application：

```text
stage = DECISION_PENDING
```

而不是直接自动 Offer。

因为业务上可能还需要：

```text
HC确认

薪资确认

领导确认
```

然后 HR 再：

```text
待结果
→ Offer
```

---

# 26. 为什么 PASS 不直接 Offer

建议：

```text
面试通过
↓
待结果
↓
Offer
```

而不是：

```text
面试通过
↓
Offer
```

这样系统可以覆盖：

```text
面试官通过
但是HC暂停

业务需要再讨论

薪资需要确认
```

---

# 27. 进入下一轮接口

可以使用：

```text
POST /interviews/{id}/feedback
```

由：

```text
result = NEXT_ROUND
```

自动创建。

不建议前端先：

```text
提交面评
```

再单独：

```text
创建下一轮
```

否则中间可能出现：

```text
上一轮显示进入下一轮
但是下一轮没创建
```

应由后端 Transaction 一次完成。

---

# 28. 面试取消

接口：

```text
POST /interviews/{id}/cancel
```

Body：

```json
{
  "reason": "候选人临时退出流程"
}
```

后端：

```text
Interview.status =
CANCELLED
```

记录：

```text
cancel_reason
```

不能删除 Interview。

---

# 29. 取消后 Application 怎么处理

不能固定一个结果。

前端取消时让 HR 选择：

```text
取消本场但继续约面

候选人退出

招聘方淘汰
```

---

## 继续约面

```text
Interview.status = CANCELLED
```

创建新的同轮 Interview：

```text
round_number 保持相同
round_name 保持相同
status = SCHEDULING
```

Application：

```text
stage = SCHEDULING
```

---

## 候选人退出

```text
Application.stage =
WITHDRAWN
```

---

## 招聘方淘汰

```text
Application.stage =
REJECTED
```

---

# 30. 重新约面

如果只是：

```text
9月23日15:00
↓
改成
9月24日14:00
```

不需要取消。

直接：

```text
PATCH /interviews/{id}
```

更新：

```text
scheduled_start_at
scheduled_end_at
```

并记录 Activity：

```text
二面时间由
9月23日15:00

调整为
9月24日14:00
```

---

# 31. 面试时间校验

后端至少校验：

```text
scheduled_start_at
不能为空
```

```text
scheduled_end_at
必须晚于 scheduled_start_at
```

不能：

```text
结束时间早于开始时间
```

---

# 32. 面试冲突检测

MVP 可以做一个简单版本。

如果：

```text
同一个 interviewer_name
```

在：

```text
15:00 - 16:00
```

已有面试。

又安排：

```text
15:30 - 16:30
```

后端返回：

```text
INTERVIEW_TIME_CONFLICT
```

前端提示：

```text
李XX 在该时间段已有面试。
```

---

# 33. 冲突查询逻辑

查询：

```text
Interview.status = SCHEDULED
```

并且：

```text
existing.start < new.end

AND

existing.end > new.start
```

就是有时间重叠。

---

# 34. interviewer_id 和 interviewer_name

当前 MVP 如果还没有 User / Interviewer 表：

可以先：

```text
interviewer_name
```

作为主要字段。

```text
interviewer_id
```

留空。

以后如果做：

```text
企业用户

面试官日历

多人账号
```

再正式建立：

```text
Interviewer / User
```

---

# 35. 今日面试接口

Dashboard：

```text
GET /dashboard/interviews/today
```

返回：

```json
[
  {
    "interview_id": "...",
    "application_id": "...",
    "candidate_name": "张三",
    "job_title": "HRBP实习生",
    "round_name": "二面",
    "scheduled_start_at": "...",
    "scheduled_end_at": "...",
    "interviewer_name": "李XX",
    "mode": "online"
  }
]
```

---

# 36. 岗位页面面试筛选

岗位 Kanban 支持：

```text
今天面试

明天面试

本周面试
```

这些都从 Interview 查询。

---

# 37. 面试时间排序

`待面试` 列：

建议按：

```text
scheduled_start_at ASC
```

也就是：

> 最近要面的放最上面。

而不是按创建时间。

---

# 38. 已经过面试时间但未完成

这是非常重要的异常提醒。

如果：

```text
Interview.status = SCHEDULED

AND

scheduled_end_at < now()
```

仍然没有点击：

```text
面试完成
```

系统显示：

```text
⚠ 面试时间已结束，请确认面试状态
```

Dashboard 可以加入：

```text
待确认面试
```

避免遗漏。

---

# 39. 面评逾期

进入：

```text
FEEDBACK_PENDING
```

后可以自动创建 Task：

```text
跟进二面面评
```

例如截止：

```text
面试结束后当天18:00
```

MVP 可以：

```text
由HR手动创建
```

以后 Agent/System 自动创建。

---

# 40. Activity 类型

新增：

```text
INTERVIEW_CREATED

INTERVIEW_AVAILABILITY_UPDATED

INTERVIEW_SCHEDULED

INTERVIEW_RESCHEDULED

INTERVIEW_COMPLETED

INTERVIEW_FEEDBACK_ADDED

INTERVIEW_NEXT_ROUND_CREATED

INTERVIEW_CANCELLED
```

---

# 41. Activity 示例

```text
9月20日 11:30

创建一面
```

```text
9月20日 14:10

候选人可用时间更新：
周三下午
```

```text
9月20日 15:00

一面已安排：
9月22日 14:30
面试官：李XX
```

```text
9月22日 15:30

一面完成
```

```text
9月22日 17:00

一面结果：
进入下一轮
```

```text
9月22日 17:00

创建二面
```

---

# 42. Service 设计

新增 / 完善：

```python
class InterviewService:

    def create_round():
        pass

    def update_availability():
        pass

    def schedule():
        pass

    def reschedule():
        pass

    def complete():
        pass

    def submit_feedback():
        pass

    def cancel():
        pass

    def create_next_round():
        pass

    def list_for_application():
        pass

    def check_time_conflict():
        pass
```

---

# 43. create_round()

职责：

```text
计算round_number

创建Interview

设置current_interview_id

修改Application.stage

写Activity
```

必须 Transaction。

---

# 44. schedule()

职责：

```text
校验时间

检查冲突

写Interview时间

status = SCHEDULED

Application.stage =
INTERVIEW_SCHEDULED

写Activity
```

---

# 45. complete()

职责：

```text
Interview.status =
COMPLETED

Application.stage =
FEEDBACK_PENDING

Application.blocked_by =
INTERVIEWER

写Activity
```

---

# 46. submit_feedback()

职责：

```text
保存feedback

保存result
```

如果：

```text
NEXT_ROUND
```

则：

```text
创建下一轮Interview
```

如果：

```text
REJECT
```

则：

```text
Application → REJECTED
```

如果：

```text
PASS
```

则：

```text
Application → DECISION_PENDING
```

全部同一个 Transaction。

---

# 47. 推荐 API 总表

```text
GET
/applications/{id}/interviews
```

查询所有面试轮次。

```text
POST
/applications/{id}/interviews
```

创建面试轮次。

```text
GET
/interviews/{id}
```

查询某场面试。

```text
PATCH
/interviews/{id}
```

修改普通字段。

```text
POST
/interviews/{id}/schedule
```

确认时间。

```text
POST
/interviews/{id}/complete
```

标记完成。

```text
POST
/interviews/{id}/feedback
```

提交面评和结果。

```text
POST
/interviews/{id}/cancel
```

取消。

---

# 48. React 组件

建议新增：

```text
components/
└── interview/
    ├── InterviewCard.tsx
    ├── InterviewHistory.tsx
    ├── InterviewSchedulingForm.tsx
    ├── InterviewDetail.tsx
    ├── InterviewFeedbackForm.tsx
    ├── InterviewCancelModal.tsx
    └── InterviewStatusBadge.tsx
```

---

# 49. CandidateDrawer 调整

结构建议：

```text
CandidateDrawer

├── 当前招聘状态

├── 招聘关键信息

├── 当前面试
│   ├── 轮次
│   ├── 时间
│   ├── 面试官
│   └── 快捷操作

├── 面试记录

├── Task

├── Notes

└── Activity Timeline
```

---

# 50. 创建面试 UI

约面中显示：

```text
二面约面
```

字段：

```text
轮次名称

候选人可用时间

面试官可用时间
```

当时间确定：

```text
日期 *

开始时间 *

预计时长

面试官

形式

会议链接 / 地址
```

按钮：

```text
确认面试时间
```

---

# 51. 面试完成 UI

待面试时：

```text
二面

9月23日 15:00

李XX

线上

[重新约面]

[取消面试]

[面试完成]
```

---

# 52. 面评 UI

点击：

```text
面试完成
```

进入：

```text
二面 · 待面评
```

显示：

```text
面评

[                            ]
[                            ]

面试结果

○ 通过
○ 进入下一轮
○ 淘汰
```

---

# 53. NEXT_ROUND UI

用户选择：

```text
进入下一轮
```

额外输入：

```text
下一轮名称

[ 二面 ]
```

或者：

```text
[ 终面 ]
```

确认后：

```text
创建下一轮
```

---

# 54. 前端 TypeScript 类型

```typescript
type InterviewStatus =
  | "scheduling"
  | "scheduled"
  | "completed"
  | "cancelled"

type InterviewResult =
  | "pending"
  | "pass"
  | "next_round"
  | "reject"

type InterviewMode =
  | "online"
  | "offline"

type Interview = {
  id: string

  applicationId: string

  roundNumber: number
  roundName: string

  status: InterviewStatus

  candidateAvailability?: string
  interviewerAvailability?: string

  scheduledStartAt?: string
  scheduledEndAt?: string

  interviewerName?: string

  mode?: InterviewMode

  location?: string
  meetingUrl?: string

  feedback?: string

  result?: InterviewResult

  cancelReason?: string
}
```

---

# 55. 后端数据库迁移

你已经准备使用 Alembic。

本次 Migration 主要：

```text
Application
新增 current_interview_id
```

Interview：

```text
新增 / 调整：

round_number

round_name

candidate_availability

interviewer_availability

scheduled_start_at

scheduled_end_at

feedback

result

cancel_reason
```

---

# 56. 旧数据迁移

如果旧 Interview 已经有：

```text
round
```

可以迁：

```text
round → round_number
```

并生成：

```text
round_number = 1
→
round_name = 一面

round_number = 2
→
round_name = 二面

round_number = 3
→
round_name = 三面
```

已有：

```text
start_at
end_at
```

迁到：

```text
scheduled_start_at
scheduled_end_at
```

不要删除旧数据后重建。

---

# 57. 核心事务

以下必须 Transaction。

### 确认面试

```text
Interview → SCHEDULED

Application →
INTERVIEW_SCHEDULED

Activity
```

---

### 面试完成

```text
Interview → COMPLETED

Application →
FEEDBACK_PENDING

Activity
```

---

### 进入下一轮

```text
当前Interview →
NEXT_ROUND

创建Next Interview

Application.current_interview_id →
新Interview

Application.stage →
SCHEDULING

Activity
```

---

### 淘汰

```text
Interview.result →
REJECT

Application.stage →
REJECTED

Activity
```

---

# 58. 一面到二面的标准流程

```text
面试官评估通过
↓
创建一面
↓
一面 · 约面中
↓
确认时间
↓
一面 · 待面试
↓
面试完成
↓
一面 · 待面评
↓
提交面评
↓
选择“进入下一轮”
↓
自动创建二面
↓
二面 · 约面中
↓
确认时间
↓
二面 · 待面试
↓
面试完成
↓
二面 · 待面评
↓
通过
↓
待结果
↓
Offer
```

---

# 59. 异常流程

## 候选人临时改期

```text
待面试
↓
修改Interview时间
↓
仍然待面试
```

---

## 面试取消但之后还面

```text
当前Interview
→ CANCELLED

创建新的同轮Interview

Application
→ SCHEDULING
```

---

## 候选人退出

```text
Interview
→ CANCELLED

Application
→ WITHDRAWN
```

---

## 面试官淘汰

```text
Interview.result
→ REJECT

Application
→ REJECTED
```

---

# 60. MVP 第一阶段暂时不做

当前不要做：

```text
Google Calendar同步

Outlook Calendar同步

自动查面试官空闲时间

自动约面

会议室预订

自动创建腾讯会议

多面试官复杂排期

日历拖拽

邮件邀请

北森同步
```

先把：

```text
人工记录
+
时间管理
+
多轮面试
```

做稳定。

---

# 61. 后续扩展接口

未来可以增加：

```text
CalendarProvider

get_availability()

create_event()

update_event()

cancel_event()
```

例如：

```text
GoogleCalendarProvider
OutlookCalendarProvider
```

InterviewService 仍然不需要重写。

---

# 62. 当前版本验收标准

能够完成：

```text
创建候选人
↓
进入约面中
↓
创建一面
↓
记录双方可用时间
↓
确认一面时间
↓
Dashboard显示今日面试
↓
标记一面完成
↓
填写一面面评
↓
选择进入下一轮
↓
自动创建二面
↓
安排二面时间
↓
完成二面
↓
填写面评
↓
进入待结果
↓
Offer / 淘汰
```

同时：

```text
每一轮面试都有独立记录

每次改期都有Activity

取消面试不会删除历史

Candidate Drawer可以查看全部面试历史

Kanban始终只显示当前轮次
```

做到这些，面试模块第一版就算完成。

---

# 63. 最终数据关系

```text
Job
 │
 │
Application ───────── Candidate
 │
 │ current_interview_id
 │
 ├──────── Interview #1
 │           一面
 │           COMPLETED
 │
 ├──────── Interview #2
 │           二面
 │           SCHEDULED
 │
 ├──────── Task
 │
 └──────── Activity
```

Application：

```text
告诉系统：
候选人现在处于“待面试”
```

当前 Interview：

```text
告诉系统：
这是二面
9月23日15:00
李XX来面试
```

历史 Interview：

```text
告诉系统：
一面什么时候进行
谁面试
结果是什么
```

这是面试管理模块最核心的结构。

---

# 64. 最核心设计结论

整个面试系统只需要坚持三条规则：

```text
Stage
=
现在招聘流程正在做什么
```

```text
Interview
=
某一轮具体发生了什么
```

```text
current_interview_id
=
现在正在处理哪一轮
```

不要把：

```text
一面
二面
三面
```

塞进 Pipeline。

也不要把：

```text
所有面试时间
```

塞进 Application。

这样系统以后无论增加：

```text
三面
HR面
主管面
终面
Calendar
Agent自动约面
北森
```

都不需要重构核心招聘流程。