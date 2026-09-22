# HR Recruitment Agent MVP v1 技术设计文档

## 1. 项目目标

当前项目已经具备完整的招聘管理系统 MVP，包括岗位管理、候选人管理、招聘 Pipeline、待办、面试、简历导入、数据库迁移和部署能力。

下一阶段目标是在现有系统上增加 AI 能力，使系统从：

**Recruitment Management System**

升级为：

**HR Recruitment Agent MVP**

本阶段不追求完全自动招聘，也暂不实现复杂多 Agent 架构。

MVP 的核心目标是：

> HR 输入岗位需求并导入简历后，AI 能理解岗位要求、分析候选人与岗位的匹配情况、保存招聘过程中的重要记忆、给出下一步建议，并在 HR 确认后调用系统已有能力执行部分招聘操作。

---

# 2. MVP 功能范围

本阶段实现以下六个模块：

1. Requirement Profile
   - AI 解析 JD 和业务补充要求
   - 生成结构化招聘画像
   - HR 人工修改、确认
   - 支持版本管理

2. Resume Assessment
   - 基于岗位 Requirement Profile 分析候选人简历
   - 输出匹配项、缺失项、风险项、待确认项和总结

3. Memory
   - 保存候选人相关事实
   - 保存岗位相关事实
   - 保存 HR 偏好
   - 支持人工新增、编辑、删除和查看来源

4. Agent Tool Layer
   - 将现有业务能力包装为 Agent Tools
   - Agent 不直接操作数据库

5. Candidate Copilot
   - 在候选人详情中提供 AI 总结
   - 展示风险、记忆、下一步建议
   - 支持 HR 确认后执行 Tool

6. Agent Audit
   - 记录 Agent Run
   - 记录 Tool Call
   - 记录输入、输出、审批及执行结果

---

# 3. 本阶段不做的功能

为了控制 MVP 范围，本阶段暂不实现：

- 多 Agent
- Supervisor Agent
- Agent Router
- 自动发送微信
- 自动发送短信
- 邮箱自动发信
- 招聘网站自动操作
- 企业微信接入
- 飞书接入
- Google Calendar / Outlook Calendar
- 自动约面
- 向量数据库
- 大规模 RAG
- 自动淘汰候选人
- 自动发 Offer
- AI 自动修改招聘标准
- AI 无确认直接执行高风险操作

这些功能放入后续版本。

---

# 4. 总体架构

现有架构：

```text
React
  │
  │ HTTP API
  ↓
FastAPI
  │
  ↓
Service
  │
  ↓
SQLAlchemy
  │
  ↓
SQLite
```

加入 Agent 后：

```text
                    React Frontend
                           │
                           ↓
                       FastAPI
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ↓                ↓                ↓
   Business Service    AI Service      Agent Service
          │                │                │
          │                │                ↓
          │                │              Tools
          │                │                │
          └────────────────┴────────────────┘
                           │
                           ↓
                       SQLAlchemy
                           │
                           ↓
                         SQLite
```

进一步细分：

```text
Frontend
│
├── Job Requirement UI
├── Resume Assessment UI
├── Candidate Memory UI
└── Candidate Copilot UI

Backend
│
├── API Layer
│
├── Business Services
│
├── AI Services
│
├── Memory Service
│
├── Agent Service
│
├── Tool Layer
│
└── Persistence Layer
```

---

# 5. 推荐目录结构

建议在现有 backend/app 下扩展：

```text
backend/
└── app/
    ├── api/
    │   ├── router.py
    │   ├── requirement_router.py
    │   ├── assessment_router.py
    │   ├── memory_router.py
    │   └── agent_router.py
    │
    ├── models/
    │   ├── job.py
    │   ├── candidate.py
    │   ├── requirement_profile.py
    │   ├── resume_assessment.py
    │   ├── memory.py
    │   └── agent_run.py
    │
    ├── schemas/
    │   ├── requirement.py
    │   ├── assessment.py
    │   ├── memory.py
    │   └── agent.py
    │
    ├── services/
    │   ├── service.py
    │   ├── resume_import_service.py
    │   ├── requirement_service.py
    │   ├── assessment_service.py
    │   ├── memory_service.py
    │   ├── agent_service.py
    │   └── ai_service.py
    │
    ├── agent/
    │   ├── tools/
    │   │   ├── candidate_tools.py
    │   │   ├── job_tools.py
    │   │   ├── todo_tools.py
    │   │   └── pipeline_tools.py
    │   │
    │   ├── prompts/
    │   │   ├── requirement_prompt.py
    │   │   ├── assessment_prompt.py
    │   │   └── copilot_prompt.py
    │   │
    │   └── recruitment_agent.py
    │
    └── db/
```

前端建议：

```text
frontend/src/
│
├── components/
│   ├── RequirementProfilePanel.tsx
│   ├── ResumeAssessmentPanel.tsx
│   ├── CandidateMemoryPanel.tsx
│   └── CandidateCopilotPanel.tsx
│
├── api/
│   ├── requirement.ts
│   ├── assessment.ts
│   ├── memory.ts
│   └── agent.ts
```

---

# 6. Requirement Profile 模块

## 6.1 目标

把以下输入：

```text
岗位 JD
+
HR 和业务沟通得到的补充信息
```

转成结构化招聘标准。

---

## 6.2 数据模型

新增：

```text
job_requirement_profiles
```

字段建议：

```text
id

job_id
version

raw_jd
raw_notes

must_have_json
preferred_json
skills_json
soft_skills_json
negative_signals_json
verification_questions_json

ai_summary

status
created_at
updated_at
confirmed_at
```

status：

```text
draft
confirmed
archived
```

---

## 6.3 JSON 数据示例

```json
{
  "must_have": [
    {
      "name": "学历",
      "description": "本科及以上"
    }
  ],
  "preferred": [
    {
      "name": "SHEIN经验",
      "description": "有SHEIN平台运营经验优先"
    }
  ],
  "skills": [
    "数据分析",
    "库存管理"
  ],
  "soft_skills": [
    "沟通能力",
    "执行力"
  ],
  "negative_signals": [
    "经历描述过于模糊"
  ],
  "verification_questions": [
    "是否可以在两周内到岗？"
  ]
}
```

---

# 7. Requirement Profile API

## AI 生成岗位要求

```http
POST /api/jobs/{job_id}/requirement-profile/generate
```

Request：

```json
{
  "extra_notes": "业务更看重SHEIN经验，学校不是重点"
}
```

Response：

```json
{
  "profile_id": 12,
  "version": 1,
  "status": "draft",
  "must_have": [],
  "preferred": [],
  "skills": [],
  "soft_skills": [],
  "negative_signals": [],
  "verification_questions": []
}
```

---

## 修改草稿

```http
PUT /api/requirement-profiles/{profile_id}
```

---

## 确认 Profile

```http
POST /api/requirement-profiles/{profile_id}/confirm
```

规则：

确认后不得直接覆盖。

修改要求时：

```text
v1 confirmed
↓
clone
↓
v2 draft
↓
HR修改
↓
v2 confirmed
```

---

# 8. Requirement AI Service

建议：

```python
generate_requirement_profile(
    jd_text: str,
    extra_notes: str
) -> RequirementProfileResult
```

LLM 必须输出结构化 JSON。

不要直接保存自然语言结果。

建议使用 Pydantic Model 校验：

```python
class RequirementItem(BaseModel):
    name: str
    description: str

class RequirementProfileAIResult(BaseModel):
    must_have: list[RequirementItem]
    preferred: list[RequirementItem]
    skills: list[str]
    soft_skills: list[str]
    negative_signals: list[str]
    verification_questions: list[str]
    summary: str
```

---

# 9. Resume Assessment 模块

## 9.1 目标

根据：

```text
Resume Text
+
Requirement Profile
```

生成：

```text
候选人与岗位匹配分析
```

---

# 10. Resume Assessment 数据模型

新增：

```text
resume_assessments
```

建议字段：

```text
id

candidate_id
job_id
requirement_profile_id

recommendation
overall_score

strengths_json
gaps_json
risks_json
missing_information_json
verification_questions_json

summary

model_name
prompt_version

created_at
updated_at
```

recommendation：

```text
strong_match
match
review
weak_match
```

注意：

推荐状态只是 AI 辅助结果。

不能自动淘汰候选人。

---

# 11. Assessment JSON 示例

```json
{
  "recommendation": "match",
  "overall_score": 82,

  "strengths": [
    {
      "requirement": "SHEIN运营经验",
      "evidence": "2025年6月至12月负责SHEIN店铺运营"
    }
  ],

  "gaps": [
    {
      "requirement": "女装经验",
      "reason": "简历没有明确说明"
    }
  ],

  "risks": [
    "到岗时间未知"
  ],

  "missing_information": [
    "期望薪资"
  ],

  "verification_questions": [
    "之前主要负责哪些类目？",
    "最快什么时候可以到岗？"
  ],

  "summary": "候选人具备较完整的SHEIN运营经历..."
}
```

---

# 12. Resume Assessment API

```http
POST /api/jobs/{job_id}/candidates/{candidate_id}/assessment
```

执行流程：

```text
获取Job
↓
获取Confirmed RequirementProfile
↓
获取Resume Text
↓
调用LLM
↓
校验JSON
↓
保存ResumeAssessment
↓
返回前端
```

---

## 获取最新分析

```http
GET /api/jobs/{job_id}/candidates/{candidate_id}/assessment
```

---

## 重新分析

```http
POST /api/jobs/{job_id}/candidates/{candidate_id}/assessment/regenerate
```

重新分析时必须记录新的 assessment。

不建议直接覆盖旧数据。

---

# 13. Memory 模块

MVP 第一版只实现结构化 Memory。

暂不使用向量数据库。

Memory 类型：

```text
candidate
job
user_preference
```

---

# 14. Memory 数据模型

```text
memories
```

字段建议：

```text
id

user_id

entity_type
entity_id

memory_type
content

source_type
source_id

importance
confidence

valid_from
valid_until

created_at
updated_at
deleted_at
```

entity_type：

```text
candidate
job
user
```

memory_type 示例：

```text
availability
salary_expectation
location_preference
candidate_status
screening_preference
interview_preference
business_requirement
other
```

---

# 15. Memory 示例

```json
{
  "entity_type": "candidate",
  "entity_id": 123,
  "memory_type": "availability",
  "content": "最快可以于2026-10-08到岗",
  "source_type": "hr_manual",
  "confidence": 1
}
```

---

# 16. Memory API

获取候选人记忆：

```http
GET /api/candidates/{candidate_id}/memories
```

新增：

```http
POST /api/candidates/{candidate_id}/memories
```

更新：

```http
PUT /api/memories/{memory_id}
```

删除：

```http
DELETE /api/memories/{memory_id}
```

---

# 17. Memory Service

```python
class MemoryService:

    create_memory()

    update_memory()

    delete_memory()

    get_candidate_memories()

    get_job_memories()

    get_user_preferences()

    search_memories()
```

第一版：

```text
不要embedding
不要vector database
不要自动总结全部聊天记录
```

---

# 18. 自动 Memory Extraction

可以作为 MVP 后半段能力。

例如 HR 输入：

```text
候选人最快10月8日到岗，期望薪资15-18K。
```

AI 提取：

```json
[
  {
    "type": "availability",
    "content": "最快2026-10-08到岗"
  },
  {
    "type": "salary_expectation",
    "content": "期望薪资15-18K"
  }
]
```

界面展示：

```text
AI识别出2条记忆：

✓ 最快10月8日到岗
✓ 期望薪资15-18K

[全部保存]
```

第一版必须由 HR 确认。

---

# 19. Agent Tool Layer

Agent 不得：

```text
直接访问db.session
直接调用SQLAlchemy model
```

Agent 必须：

```text
Agent
 ↓
Tool
 ↓
Service
 ↓
DB
```

---

# 20. MVP Tool 列表

读取类：

```python
get_job(job_id)

get_candidate(candidate_id)

get_candidate_resume(candidate_id)

get_candidate_memories(candidate_id)

get_candidate_timeline(candidate_id)

get_candidate_todos(candidate_id)

get_latest_assessment(candidate_id, job_id)
```

执行类：

```python
create_todo()

move_candidate_stage()
```

第一版只开放两个写操作即可。

---

# 21. Tool Schema 示例

```python
class CreateTodoInput(BaseModel):
    candidate_id: int
    title: str
    due_at: datetime | None
    description: str | None
```

Tool：

```python
def create_todo_tool(data: CreateTodoInput):
    return todo_service.create_todo(...)
```

---

# 22. Tool 风险分级

建议从第一版就设计：

## LOW

只读：

```text
get_job
get_candidate
get_memory
get_timeline
```

可以直接执行。

---

## MEDIUM

```text
create_todo
```

需要 HR 点击确认。

---

## HIGH

未来：

```text
reject_candidate
send_email
send_offer
delete_candidate
close_job
```

必须人工确认。

MVP 暂不开放。

---

# 23. Candidate Copilot

Candidate Copilot 放在：

```text
Candidate Detail Drawer
```

不单独做完整 Chat。

---

# 24. Candidate Copilot 输入上下文

调用 Copilot 时获取：

```text
Candidate
+
Job
+
RequirementProfile
+
ResumeAssessment
+
Candidate Memories
+
Candidate Todos
+
Timeline
+
Interview
```

---

# 25. Copilot 输出结构

```json
{
  "summary": "",

  "current_status": "",

  "strengths": [],

  "risks": [],

  "missing_information": [],

  "memories": [],

  "next_actions": [
    {
      "action_type": "create_todo",
      "reason": "",
      "suggested_payload": {}
    }
  ]
}
```

---

# 26. Candidate Copilot UI

候选人详情增加：

```text
AI Assistant
────────────────

候选人总结

当前状态

岗位匹配

关键记忆

风险

待确认问题

下一步建议
```

例如：

```text
下一步建议

候选人目前处于“沟通确认”。

已24小时未回复。

建议：
今日再次进行跟进。

[生成话术]

[创建跟进待办]
```

点击：

```text
创建跟进待办
```

弹确认：

```text
Agent准备执行：

创建待办

候选人：王小明
内容：再次联系候选人确认岗位意向
截止：今天18:00

[取消]
[确认]
```

确认后调用 Tool。

---

# 27. Agent Run

新增：

```text
agent_runs
```

字段：

```text
id

user_id

agent_type

candidate_id
job_id

input_json
output_json

model_name

status
error_message

started_at
finished_at
```

agent_type：

```text
requirement_generation
resume_assessment
candidate_copilot
memory_extraction
```

---

# 28. Agent Tool Call

```text
agent_tool_calls
```

字段：

```text
id

agent_run_id

tool_name

arguments_json
result_json

risk_level

requires_approval
approval_status
approved_at

status
error_message

created_at
```

approval_status：

```text
not_required
pending
approved
rejected
```

---

# 29. Agent 调用流程

Candidate Copilot：

```text
POST /agent/candidate/{candidate_id}/copilot
            │
            ↓
      Create AgentRun
            │
            ↓
       Fetch Context
            │
   ┌────────┼────────┐
   ↓        ↓        ↓
Candidate Resume   Memory
Job       Assessment
            │
            ↓
            LLM
            │
            ↓
     Structured Output
            │
            ↓
        Save AgentRun
            │
            ↓
          Response
```

---

# 30. Tool 执行流程

```text
AI建议创建待办
        │
        ↓
前端展示建议
        │
        ↓
HR点击确认
        │
        ↓
POST /agent/actions/execute
        │
        ↓
检查Tool权限
        │
        ↓
执行create_todo_tool
        │
        ↓
TodoService
        │
        ↓
Database
        │
        ↓
记录AgentToolCall
```

---

# 31. AI Service

建议统一封装：

```python
class AIService:

    generate_structured(
        prompt: str,
        response_model: type[BaseModel]
    ):
        ...
```

业务层不要到处直接写：

```python
client.chat.completions...
```

统一：

```text
AIService
```

这样未来换：

```text
OpenAI
Gemini
Claude
DeepSeek
Qwen
```

时不用改业务代码。

---

# 32. Prompt 管理

Prompt 不建议直接散落在 service.py。

目录：

```text
agent/prompts/
```

例如：

```text
requirement_prompt.py
assessment_prompt.py
copilot_prompt.py
```

每个 Prompt 增加：

```text
PROMPT_VERSION = "v1"
```

数据库保存：

```text
prompt_version
```

方便未来排查：

```text
为什么这次AI分析和以前不同？
```

---

# 33. Requirement Prompt 原则

模型必须遵守：

```text
1. 不补充用户没有提供的硬性要求
2. JD与业务补充冲突时标记冲突
3. 硬性要求和加分项必须区分
4. 不进行候选人判断
5. 必须输出JSON
```

---

# 34. Resume Assessment Prompt 原则

必须明确：

```text
只能根据简历提供的信息判断。

没有的信息必须标记为未知。

不能把未知解释为不符合。

所有重要判断尽量给出简历证据。

不得自动决定淘汰候选人。
```

非常重要：

```text
未提及 ≠ 不满足
```

应该输出：

```text
unknown
```

而不是：

```text
false
```

---

# 35. Candidate Copilot Prompt 原则

职责：

```text
总结
发现风险
发现遗漏
推荐下一步
```

不允许：

```text
自动淘汰候选人
自动发Offer
自动删除
自动修改岗位要求
```

---

# 36. 前端开发

## Job 页面

增加：

```text
AI岗位画像
```

按钮：

```text
[AI生成招聘要求]
```

内容：

```text
硬性要求

加分项

核心技能

软技能

风险项

沟通确认问题
```

按钮：

```text
[编辑]
[确认]
[重新生成]
```

---

# 37. Candidate 页面

候选人增加：

```text
AI匹配
```

状态：

```text
未分析
分析中
已分析
失败
```

展示：

```text
AI匹配分析

总体匹配
优势
不足
风险
待确认问题
```

---

# 38. Candidate Detail Drawer

建议最终 Tab：

```text
基本信息

招聘进度

简历

AI分析

记忆

面试

时间线
```

右侧或者顶部增加：

```text
AI Copilot
```

---

# 39. 异步任务

MVP 初期可以同步调用 AI。

例如：

```text
POST assessment
↓
等待5-20秒
↓
返回
```

如果后续批量处理 50 份简历，再增加：

```text
BackgroundTask
```

或者：

```text
Celery / Redis
```

MVP 暂不引入。

---

# 40. 批量简历评估

建议在单份评估稳定后开发。

接口：

```http
POST /api/jobs/{job_id}/assessments/batch
```

Request：

```json
{
  "candidate_ids": [
    1,
    2,
    3
  ]
}
```

第一版可以串行。

以后再做并发控制。

---

# 41. 错误处理

AI 相关错误至少分：

```text
AI_TIMEOUT

AI_INVALID_JSON

AI_MODEL_ERROR

AI_RATE_LIMIT

REQUIREMENT_NOT_CONFIRMED

RESUME_NOT_FOUND
```

不要统一：

```text
500 Internal Server Error
```

---

# 42. 数据安全

简历属于敏感招聘数据。

MVP 至少做到：

```text
Agent输入只包含本任务需要的数据

日志不要输出完整手机号

日志不要输出完整邮箱

不要把resume全文写进普通日志

AgentRun可保存输入摘要而不是完整原文
```

后续企业化再增加：

```text
Encryption
RBAC
Tenant Isolation
Audit
Data Retention
```

---

# 43. Alembic Migration

新增表后必须：

```bash
alembic revision --autogenerate -m "add recruitment agent models"

alembic upgrade head
```

Migration 包含：

```text
job_requirement_profiles

resume_assessments

memories

agent_runs

agent_tool_calls
```

不要依赖：

```python
Base.metadata.create_all()
```

作为正式迁移机制。

---

# 44. 测试

至少增加：

```text
tests/

test_requirement_profile.py

test_resume_assessment.py

test_memory_service.py

test_agent_tools.py

test_candidate_copilot.py
```

---

# 45. Unit Test

重点测试：

```text
RequirementProfile创建

RequirementProfile版本升级

Confirmed Profile不可覆盖

Memory CRUD

Candidate Memory查询

Tool不能绕过Service

无Resume时Assessment报错

无Confirmed Requirement时Assessment报错
```

---

# 46. AI Mock

测试时不要真正调用 LLM。

提供：

```python
FakeAIService
```

例如：

```python
class FakeAIService:

    def generate_structured(...):
        return TEST_RESULT
```

这样 pytest：

```text
快
稳定
不花API钱
```

---

# 47. Agent Tool Test

Tool 测试：

```text
create_todo_tool
```

验证：

```text
Tool
↓
TodoService
↓
Todo创建成功
```

不要测试：

```text
LLM是否真的会调用Tool
```

那是 Integration Test。

---

# 48. MVP 开发顺序

建议严格按这个顺序。

## Sprint 1

数据库模型：

```text
RequirementProfile
ResumeAssessment
Memory
AgentRun
AgentToolCall
```

+

Alembic Migration

---

## Sprint 2

Requirement Profile：

```text
CRUD
↓
AI Generate
↓
HR Confirm
↓
Version
```

完成后先测试：

```text
JD
↓
AI Requirement Profile
```

---

## Sprint 3

Resume Assessment：

```text
Resume Text
+
Requirement Profile
↓
AI Assessment
```

完成单候选人分析。

---

## Sprint 4

Memory：

```text
Memory CRUD
↓
Candidate Memory UI
```

暂时手动录入。

---

## Sprint 5

Agent Tool Layer：

```text
get_candidate

get_job

get_resume

get_memory

get_todo

create_todo

move_stage
```

---

## Sprint 6

Candidate Copilot：

```text
Context Aggregation
↓
LLM
↓
Next Action
↓
Human Approval
↓
Tool Execution
```

---

## Sprint 7

Agent Audit：

完善：

```text
AgentRun

ToolCall

Approval
```

---

## Sprint 8

Memory Extraction：

```text
HR Note
↓
AI Extract
↓
HR Confirm
↓
Memory
```

---

# 49. MVP 验收标准

MVP 完成必须能完成完整 Demo：

```text
创建岗位
↓
输入JD
↓
输入业务补充信息
↓
AI生成Requirement Profile
↓
HR修改
↓
HR确认
↓
上传简历
↓
解析简历
↓
AI Assessment
↓
展示匹配证据
↓
HR进入Candidate详情
↓
查看Candidate Copilot
↓
HR记录候选人记忆
↓
Copilot给出Next Action
↓
HR确认
↓
Agent执行Create Todo
↓
Timeline记录操作
```

这条链成功：

```text
Requirement
↓
Assessment
↓
Memory
↓
Reasoning
↓
Recommendation
↓
Human Approval
↓
Tool
↓
Action
```

即可认为：

**HR Recruitment Agent MVP v1 完成。**

---

# 50. MVP 成功标准

技术上不是看：

```text
用了几个Agent
用了没有RAG
用了没有向量数据库
```

而是看：

```text
HR是否明显减少手动阅读和判断成本
```

核心指标未来可以设计为：

```text
单份简历筛选耗时

一个岗位筛选20份简历耗时

AI建议被HR采纳比例

AI Assessment人工修改比例

遗漏待办数量

逾期候选人数

单候选人推进操作次数
```

---

# 51. 后续版本

MVP v2：

```text
Agent Chat

Batch Resume Assessment

Memory Automatic Extraction

HR Preference Memory

Interview Question Generation

Interview Feedback Summarization
```

MVP v3：

```text
RAG

Organization Memory

Email Integration

Calendar Integration

Auto Scheduling

Multi-Agent
```

企业版：

```text
Multi-tenant

RBAC

PostgreSQL

Object Storage

Redis

Task Queue

Enterprise SSO

Recruitment Platform Integration

Observability

Evaluation System
```

---

# 52. 最终技术定位

本项目最终不是：

> 带 AI 功能的招聘管理系统

而是：

> 以招聘业务系统作为 Tool Environment，以 LLM 作为推理核心，以 Memory 提供长期上下文，以人工审批约束高风险操作的招聘 Agent 系统。

核心架构：

```text
                 Recruitment Agent

                         │

        ┌────────────────┼────────────────┐

        ↓                ↓                ↓

     Reasoning          Memory            Tools

        │                │                │

       LLM          Candidate Memory     Job
                    Job Memory           Candidate
                    HR Preference        Todo
                                         Pipeline
                                         Interview

                         │

                         ↓

                     HR Approval

                         │

                         ↓

                     Real Action
```

这就是当前 MVP 最合理的技术落点。