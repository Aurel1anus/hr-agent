# HR Recruitment Agent  
# 结构化 AI 调用与错误可观测性技术设计 v1.0

## 1. 文档目标

当前系统已经能够正常调用 LLM，但出现：

```text
AI_INVALID_JSON:
模型返回内容不是有效的结构化 JSON
```

这说明：

```text
网络调用成功
↓
模型正常返回
↓
返回内容无法被业务 Schema 接受
↓
后端返回错误
```

本设计目标不是简单修复一次 JSON 解析错误，而是建立一套可以长期支撑以下模块的统一 AI 基础设施：

```text
Requirement Profile
Resume Assessment
Intent Classification
Memory Extraction
Candidate Copilot
Planner
Tool Calling
Interview Summary
```

核心目标：

> AI 输出允许不稳定，但系统行为必须稳定、可诊断、可降级、可追踪。

---

# 2. 核心设计原则

整个 AI 调用链遵循以下原则：

```text
强约束输入
+
分层解析输出
+
Schema校验
+
业务语义校验
+
一次自动修复
+
安全降级
+
全链路可观测
```

不要依赖：

```text
“Prompt写得好，所以模型一定返回正确JSON”
```

正确思路是：

```text
假设模型迟早会返回错误格式
↓
系统仍然能够正确处理
```

---

# 3. 总体调用链

推荐统一流程：

```text
Business Service
      │
      ▼
AIService.generate_structured()
      │
      ├── Build Prompt
      │
      ├── Call Provider
      │
      ▼
Raw AI Response
      │
      ├── Record Raw Response
      │
      ▼
Output Parser
      │
      ├── Direct JSON
      │
      ├── Markdown JSON
      │
      ├── JSON extraction fallback
      │
      ▼
Pydantic Validation
      │
      ▼
Semantic Validation
      │
      ├── success
      │
      └── failure
              │
              ▼
         Repair Once
              │
              ▼
        Validate Again
              │
        ┌─────┴─────┐
        ▼           ▼
      Success      Failure
        │           │
        ▼           ▼
     Return      Safe Fallback
```

---

# 4. 请求前约束

## 4.1 Prompt

所有结构化任务统一要求：

```text
你必须只返回合法 JSON。

禁止：
- Markdown代码块
- ```json
- 前言
- 后记
- 解释文本
- 注释

必须严格符合给定字段结构。
没有信息时使用 null、[] 或指定枚举值。
不得自行创建Schema中不存在的字段。
```

---

# 5. JSON Schema 模板

不要只描述：

```text
返回岗位画像
```

必须给模型明确模板。

例如 Requirement Profile：

```json
{
  "must_have": [
    {
      "name": "string",
      "description": "string"
    }
  ],
  "preferred": [],
  "skills": [],
  "soft_skills": [],
  "negative_signals": [],
  "verification_questions": [],
  "summary": "string"
}
```

---

# 6. Few-shot

Few-shot 主要用于：

```text
判断边界
```

而不是简单教模型：

```text
怎么写JSON
```

例如：

```text
业务：
最好有SHEIN经验，没有也可以。

正确：
preferred

错误：
must_have
```

再例如：

```text
简历没有写英语六级。

正确：
unknown

错误：
not_match
```

推荐：

```text
2～5个高质量示例
```

不要在每个 Prompt 塞大量重复示例。

---

# 7. Temperature

抽取、分类、结构化转换：

```text
temperature = 0 / 较低
```

例如：

```text
Requirement Extraction
Intent Classification
Memory Extraction
Resume Structured Analysis
```

目标是：

```text
降低随机性
```

而不是增加创造性。

---

# 8. Provider 原生结构化能力

如果模型 Provider 支持：

```text
JSON Mode
Structured Output
JSON Schema
Tool Calling
```

优先使用。

优先级：

```text
原生Structured Output
        >
JSON Mode
        >
Prompt要求JSON
```

Prompt 仍然保留，作为第二层约束。

---

# 9. Pydantic Schema

模型输出的最终真相来源不是 Prompt，而应该是：

```text
Pydantic Model
```

例如：

```python
class RequirementItem(BaseModel):
    name: str
    description: str


class RequirementProfileResult(BaseModel):
    must_have: list[RequirementItem]
    preferred: list[RequirementItem]
    skills: list[str]
    soft_skills: list[str]
    negative_signals: list[str]
    verification_questions: list[str]
    summary: str
```

整个系统围绕：

```text
Pydantic Schema
```

定义结构。

---

# 10. 统一 AIService

新增：

```text
services/
    ai_service.py
```

建议接口：

```python
async def generate_structured(
    *,
    task_type: str,
    messages: list,
    response_model: type[BaseModel],
    prompt_version: str,
    allow_repair: bool = True,
):
    ...
```

业务层不关心：

```text
Markdown
JSON解析
Pydantic
Retry
Provider异常
```

业务层只关心：

```python
result = await ai_service.generate_structured(...)
```

---

# 11. Parser 分层设计

推荐新增：

```text
services/
    ai_output_parser.py
```

解析优先级：

```text
① 原始JSON直接解析

② Markdown fence去除

③ JSON code block提取

④ JSON对象安全提取

⑤ repair
```

---

# 12. 第一层：直接解析

首先：

```python
json.loads(raw_content)
```

如果成功，不做额外处理。

原因：

> 模型已经正确返回时，不应该修改模型输出。

---

# 13. 第二层：Markdown去壳

兼容：

````text
```json
{
  "intent": "CREATE_TODO"
}
```
````

清理之后：

```json
{
  "intent": "CREATE_TODO"
}
```

然后再次：

```python
json.loads()
```

---

# 14. find/rfind JSON提取

可以保留：

```python
start = text.find("{")
end = text.rfind("}")
```

但只能作为：

```text
fallback
```

不能成为主解析方式。

原因：

```text
模型可能输出多个JSON
模型可能包含Example JSON
字符串内部可能包含 {}
模型可能输出说明 + JSON + 第二个JSON
```

因此：

```text
direct JSON
↓
markdown cleanup
↓
structured extraction
↓
find/rfind fallback
```

---

# 15. JSON Parse 和 Schema Validation 必须分离

禁止统一转换成：

```text
AI_INVALID_JSON
```

应该明确区分：

```text
AI_EMPTY_RESPONSE

AI_JSON_PARSE_ERROR

AI_SCHEMA_VALIDATION_ERROR

AI_SEMANTIC_VALIDATION_ERROR

AI_OUTPUT_TRUNCATED

AI_PROVIDER_ERROR

AI_TIMEOUT

AI_RATE_LIMIT
```

这对于排查问题非常重要。

---

# 16. JSON Parse Error

代表：

```text
字符串本身不是合法JSON
```

例如：

```text
下面是结果：

{
  "intent": "CREATE_TODO"
}
```

错误记录：

```text
stage:
json_parse

error_type:
AI_JSON_PARSE_ERROR
```

---

# 17. Schema Validation Error

例如模型返回：

```json
{
  "requirements": [],
  "advantages": []
}
```

它是完全合法的 JSON。

但是你的 Schema 要：

```text
must_have
preferred
skills
...
```

因此应该记录：

```text
AI_SCHEMA_VALIDATION_ERROR
```

而不是：

```text
AI_INVALID_JSON
```

这是两个完全不同的问题。

---

# 18. Semantic Validation

即使 Schema 正确，也可能：

```json
{
  "intent": "MOVE_TO_MARS"
}
```

JSON合法。

Schema可能也允许 string。

但业务不允许。

因此必须做：

```text
Semantic Validation
```

---

# 19. Enum Fallback

分类型任务可以：

```python
try:
    intent = IntentCategory(value)
except ValueError:
    intent = IntentCategory.OTHER
```

适合：

```text
Intent
Memory Type
Recommendation Type
```

核心原则：

> 未知分类降级成 OTHER，而不是让整个系统崩溃。

---

# 20. 业务校验

例如：

```text
move_candidate_stage
```

即使参数：

```json
{
  "candidate_id": 12,
  "stage": "offer"
}
```

Schema 完全正确。

仍然必须验证：

```text
Candidate 是否存在

Candidate 是否属于该岗位

当前 Pipeline 是否允许进入 Offer

是否缺少必要前置步骤

当前用户是否有权限
```

因此：

```text
Schema正确
≠
可以执行
```

---

# 21. Repair Retry

结构化输出第一次失败后：

```text
不要立即502
```

允许：

```text
Repair Once
```

---

# 22. Repair Prompt

输入：

```text
模型原始输出
+
Validation Error
+
Target Schema
```

例如：

```text
你的上一条输出没有通过结构校验。

错误：

must_have
Field required

preferred
Field required

原始输出：

{
  "requirements": [...]
}

请只修复JSON结构。

不得重新分析原始业务问题。
不得增加新的事实。
只返回合法JSON。

目标Schema：
...
```

---

# 23. 为什么只 Retry 一次

避免：

```text
模型错误
↓
retry
↓
错误
↓
retry
↓
错误
↓
无限循环
```

推荐：

```text
max_repair_attempts = 1
```

如果仍然失败：

```text
进入Fallback
```

---

# 24. Fail-open 与 Fail-closed

这是整个系统非常重要的设计。

不是所有失败都：

```text
return default
```

---

# 25. Fail-open

AI失败后可以安全继续业务。

例如：

```text
Intent Classification
Memory Extraction
Summary
风险标签
AI建议
```

可以：

```text
Intent → OTHER

Memory Extraction → []

Summary → null
```

系统继续运行。

---

# 26. Fail-closed

涉及真实业务写操作：

```text
推进候选人阶段

取消面试

创建面试

发送消息

淘汰候选人

发Offer

删除数据
```

模型输出不可靠时：

```text
必须停止Action
```

不能：

```text
猜一个默认值继续执行
```

---

# 27. 核心原则

应该定义为：

> AI失败绝不能让整个应用崩溃，但可以让当前AI操作安全失败。

例如：

```text
Resume Assessment失败
```

系统：

```text
继续可以使用
```

候选人页面：

```text
AI分析失败
[重新分析]
```

而不是整个 HTTP 请求链失控。

---

# 28. Tool Calling 架构

Tool 调用建议：

```text
LLM
↓
Provider Tool Schema
↓
Local Pydantic Schema
↓
Business Validation
↓
Permission Validation
↓
Human Approval
↓
Service
↓
Database
```

---

# 29. Tool不能直接访问数据库

禁止：

```text
Agent
↓
SQLAlchemy
```

必须：

```text
Agent
↓
Tool
↓
Service
↓
SQLAlchemy
```

---

# 30. Tool参数校验

例如：

```python
class CreateTodoArgs(BaseModel):
    candidate_id: int
    title: str
    due_at: datetime | None
```

Provider 返回：

```json
{
  "candidate_id": "王小明",
  "due_at": "以后"
}
```

必须被：

```text
Pydantic
```

拦截。

---

# 31. Tool Error

定义：

```text
TOOL_ARGUMENT_VALIDATION_ERROR

TOOL_BUSINESS_RULE_ERROR

TOOL_PERMISSION_DENIED

TOOL_APPROVAL_REQUIRED

TOOL_EXECUTION_ERROR
```

---

# 32. Human Approval

推荐 Tool Risk：

```text
READ
LOW
MEDIUM
HIGH
```

READ：

```text
get_candidate
get_job
get_todos
```

直接执行。

LOW：

```text
create_todo
add_memory
```

可以根据产品策略确认。

MEDIUM：

```text
move_candidate_stage
schedule_interview
```

建议确认。

HIGH：

```text
reject_candidate
delete_candidate
send_offer
close_job
```

必须确认。

---

# 33. 错误可观测性总体目标

错误可观测性解决的问题是：

> AI失败以后，我怎么知道究竟是哪一层出问题？

必须做到：

```text
一个失败
↓
可以定位到具体Stage
↓
看到原始模型响应
↓
看到解析结果
↓
看到Validation Error
↓
看到Repair过程
↓
看到最终Fallback
```

---

# 34. Agent Run

建议：

```text
agent_runs
```

新增/完善：

```text
id

run_id

task_type

provider
model

prompt_version

status

started_at
finished_at

latency_ms

repair_attempted

fallback_used

error_stage
error_type
error_message
```

status：

```text
running
success
degraded
failed
```

---

# 35. AI Raw Response

建议开发阶段至少记录：

```text
ai_model_calls
```

字段：

```text
id

agent_run_id

provider

model

request_id

prompt_version

raw_response

finish_reason

latency_ms

input_tokens
output_tokens

created_at
```

生产环境再考虑：

```text
脱敏
截断
加密
Retention
```

---

# 36. Validation Error

建议记录：

```text
ai_validation_errors
```

字段：

```text
id

agent_run_id

stage

error_type

error_message

raw_output

parsed_output

schema_name

repair_attempted

created_at
```

---

# 37. 一个失败到底怎么分析

假设发生：

```text
AI_SCHEMA_VALIDATION_ERROR
```

你应该能够看到：

```text
Run #827

Task:
requirement_generation

Model:
deepseek-flash

Prompt:
requirement-v3

Latency:
18.9s

Stage:
schema_validation

Raw:
{
  "requirements": [...]
}

Parsed:
{
  "requirements": [...]
}

Validation:
must_have → Field required
preferred → Field required

Repair:
yes

Repair result:
success
```

那么你马上知道：

> 网络没问题，JSON没问题，是模型用了错误字段名。

解决：

```text
加强Prompt Schema / Few-shot
```

---

# 38. JSON Parse Error 怎么看

例如：

```text
Stage:
json_parse

Raw:

下面是结果：

```json
{
   ...
}
```
```

说明：

```text
模型输出Markdown
```

解决：

```text
Parser兼容
+
Prompt限制
```

---

# 39. AI_OUTPUT_TRUNCATED

例如：

```text
finish_reason = length
```

Raw：

```text
{
  "must_have": [
    ...
```

没有闭合。

说明：

> 不是JSON逻辑问题，而是输出被截断。

解决方向：

```text
增加max_tokens

减少Prompt

减少输出字段冗余

减少few-shot
```

---

# 40. Schema Error 怎么分析

例如：

```text
ValidationError:

preferred.0
Input should be a valid dictionary
```

Raw：

```json
{
  "preferred": [
    "有SHEIN经验"
  ]
}
```

Schema：

```json
{
  "name": "",
  "description": ""
}
```

这说明：

> 模型理解了字段，但元素结构错误。

解决：

```text
加强JSON模板
+
增加few-shot
```

---

# 41. Semantic Error 怎么分析

Raw：

```json
{
  "intent": "DELETE_ALL_CANDIDATES"
}
```

JSON正确。

Schema正确。

但是 enum 不允许。

记录：

```text
Stage:
semantic_validation

Fallback:
OTHER
```

这说明：

> 模型产生了不存在的业务分类。

---

# 42. Tool Error 怎么分析

例如：

```text
HR:
把王小明推进下一轮
```

Tool：

```text
move_candidate_stage

candidate_id = 123

target_stage = interview_2
```

Tool报：

```text
INVALID_STAGE_TRANSITION
```

这不是：

```text
AI JSON问题
```

这是：

```text
Business Validation问题
```

你应该看到：

```text
AI:
正常

Tool Schema:
正常

Business Validation:
失败

Current Stage:
waiting_feedback

Required:
feedback completed

Target:
interview_2
```

于是问题非常清楚。

---

# 43. 最重要的一个字段：error_stage

建议统一：

```text
provider

response

parse

schema_validation

semantic_validation

planning

tool_argument_validation

business_validation

permission

approval

tool_execution
```

以后看到：

```text
error_stage = schema_validation
```

就知道：

> 不用查数据库。

看到：

```text
error_stage = business_validation
```

就知道：

> 不用改 Prompt。

这个字段价值非常高。

---

# 44. error_type

例如：

```text
PROVIDER_TIMEOUT

PROVIDER_RATE_LIMIT

EMPTY_RESPONSE

JSON_PARSE_ERROR

SCHEMA_VALIDATION_ERROR

UNKNOWN_ENUM

INVALID_TOOL_ARGUMENTS

INVALID_STAGE_TRANSITION

PERMISSION_DENIED

TOOL_EXECUTION_ERROR
```

---

# 45. 开发环境日志格式

推荐 Structured Logging：

```json
{
  "event": "ai_validation_failed",
  "run_id": "run_827",
  "task": "requirement_generation",
  "model": "deepseek-flash",
  "prompt_version": "v3",
  "stage": "schema_validation",
  "error_type": "SCHEMA_VALIDATION_ERROR",
  "latency_ms": 18942,
  "repair_attempted": false
}
```

不要只：

```text
ERROR something failed
```

---

# 46. 不要吞异常

禁止：

```python
try:
    ...
except Exception:
    return {}
```

因为你以后完全不知道发生过错误。

正确：

```python
try:
    ...
except Exception as exc:
    record_error(...)
    return fallback
```

也就是说：

```text
用户无感
≠
系统无记录
```

---

# 47. Degraded 状态

这是非常推荐增加的状态。

例如：

```text
第一次输出失败

Repair成功
```

最终请求是成功的。

但是应该：

```text
status = degraded
```

而不是完全：

```text
success
```

因为这说明：

> 当前Prompt / Model稳定性存在问题。

---

# 48. 错误分析 Dashboard

以后可以在开发后台增加：

```text
AI Observability
```

展示：

```text
最近24小时

AI Calls              132

Success                118
Degraded                11
Failed                   3

JSON Parse Error         4
Schema Error             7
Provider Error           2
Tool Error               1
```

再展示：

```text
RequirementProfile

成功率 94%

ResumeAssessment

成功率 98%

MemoryExtraction

成功率 87%
```

---

# 49. Prompt Version 分析

这一点特别重要。

必须记录：

```text
prompt_version
```

例如：

```text
requirement-v1
requirement-v2
requirement-v3
```

以后可能发现：

```text
v2 Schema Failure:
12%

v3:
2%
```

你才能知道：

> Prompt修改到底有没有提升系统质量。

---

# 50. Model Version 分析

同理：

```text
DeepSeek A
JSON Failure 5%

DeepSeek B
JSON Failure 1%
```

未来换模型才有依据。

而不是：

> “感觉B更聪明。”

---

# 51. Latency Observability

记录：

```text
total_latency_ms

provider_latency_ms

repair_latency_ms

tool_latency_ms
```

例如你之前：

```text
19秒
```

以后可以知道：

```text
Provider：
17.8s

Parsing：
2ms

Validation：
3ms

Repair：
0

Total：
17.9s
```

于是你知道瓶颈：

> 是模型，不是 FastAPI。

---

# 52. Debug API

开发阶段可以增加：

```http
GET /api/debug/agent-runs/{run_id}
```

返回：

```json
{
  "run": {},
  "model_calls": [],
  "validation_errors": [],
  "tool_calls": []
}
```

方便自己查看。

生产环境必须：

```text
admin only
```

---

# 53. 前端错误展示

普通 HR 不需要看到：

```text
Pydantic ValidationError...
```

用户只需要：

```text
AI分析失败，请重试。
```

或者：

```text
AI分析结果格式异常，系统已自动重试但仍未成功。
```

开发信息放：

```text
Logs
Agent Run
Debug Dashboard
```

---

# 54. Resume Assessment 失败

不要：

```text
return 默认评分50
```

否则这是伪造AI结果。

正确：

```text
assessment_status = failed
```

前端：

```text
AI分析失败

[重新分析]
```

---

# 55. Requirement Profile 失败

同理：

```text
不要生成一个空招聘画像然后假装成功
```

应该：

```text
generation_status = failed
```

JD仍然正常保存。

HR可以：

```text
重新生成
```

---

# 56. Memory Extraction 失败

可以：

```text
return []
```

因为 Memory Extraction 属于：

```text
辅助型功能
```

但后台：

```text
status = degraded
```

记录失败原因。

---

# 57. Intent Classification 失败

可以：

```text
intent = OTHER
```

然后：

```text
走普通Chat
```

这是非常适合 fallback 的地方。

---

# 58. Tool Calling 失败

必须：

```text
Stop
```

然后告诉 HR：

```text
我没有执行这个操作，因为候选人或目标阶段无法确认。
```

而不是猜。

---

# 59. 推荐代码结构

```text
backend/app/

services/
├── ai_service.py
├── ai_output_parser.py
├── ai_repair_service.py
├── ai_observability_service.py
└── memory_service.py

agent/
├── schemas/
│   ├── requirement.py
│   ├── assessment.py
│   ├── memory.py
│   ├── intent.py
│   └── planner.py
│
├── prompts/
│   ├── requirement.py
│   ├── assessment.py
│   ├── memory.py
│   └── intent.py
│
└── tools/
    ├── candidate.py
    ├── todo.py
    ├── pipeline.py
    └── interview.py
```

---

# 60. AIService 伪代码

```python
async def generate_structured(
    task_type,
    messages,
    response_model,
    prompt_version,
):

    run = observability.start_run(...)

    try:

        response = await provider.generate(...)

        observability.record_raw_response(
            run=run,
            response=response,
        )

        raw = response.content

        parsed = parser.parse(raw)

        try:
            result = response_model.model_validate(parsed)

        except ValidationError as exc:

            observability.record_validation_error(
                run=run,
                stage="schema_validation",
                error=exc,
                raw=raw,
                parsed=parsed,
            )

            repaired = await repair_once(
                raw=raw,
                error=exc,
                schema=response_model.model_json_schema(),
            )

            result = response_model.model_validate(repaired)

            observability.mark_degraded(run)

        observability.mark_success(run)

        return result

    except AIParseError as exc:

        observability.mark_failure(
            run,
            stage="parse",
            error=exc,
        )

        raise

    except Exception as exc:

        observability.mark_failure(
            run,
            stage="unknown",
            error=exc,
        )

        raise
```

具体业务是否：

```text
raise
```

还是：

```text
fallback
```

由任务策略决定。

---

# 61. Task Policy

建议建立：

```python
AI_TASK_POLICIES = {
    "intent_classification": {
        "fallback": "OTHER",
        "fail_mode": "open",
    },

    "memory_extraction": {
        "fallback": [],
        "fail_mode": "open",
    },

    "resume_assessment": {
        "fallback": None,
        "fail_mode": "closed",
    },

    "requirement_generation": {
        "fallback": None,
        "fail_mode": "closed",
    },

    "tool_planning": {
        "fallback": None,
        "fail_mode": "closed",
    },
}
```

这样系统行为统一。

---

# 62. MVP 第一阶段实施顺序

第一步：

```text
记录 raw response
```

马上解决：

> 到底DeepSeek返回了什么？

---

第二步：

拆分错误：

```text
JSON_PARSE_ERROR

SCHEMA_VALIDATION_ERROR
```

---

第三步：

建立统一：

```text
Pydantic Schema
```

---

第四步：

增加：

```text
Markdown cleanup
```

---

第五步：

增加：

```text
Repair Once
```

---

第六步：

增加：

```text
agent_runs
```

以及：

```text
error_stage
error_type
prompt_version
model
latency
```

---

第七步：

Tool：

```text
Pydantic
+
Business Validation
+
Approval
```

---

# 63. MVP 验收测试

准备至少以下测试。

## Case 1 正常JSON

输入：

```json
{"intent":"CREATE_TODO"}
```

结果：

```text
success
```

---

## Case 2 Markdown JSON

输入：

````text
```json
{"intent":"CREATE_TODO"}
```
````

结果：

```text
parser自动修复
status = degraded 或 success-with-normalization
```

---

## Case 3 错误字段

输入：

```json
{
  "intent_type": "CREATE_TODO"
}
```

结果：

```text
Schema validation失败
↓
Repair
↓
成功
```

---

## Case 4 非法枚举

```json
{
  "intent": "MAKE_ME_COFFEE"
}
```

Intent：

```text
OTHER
```

---

## Case 5 非法 Tool 参数

```json
{
  "candidate_id": "小王"
}
```

结果：

```text
Tool不执行
```

---

## Case 6 JSON截断

```text
{
  "must_have": [
```

结果：

```text
OUTPUT_TRUNCATED / JSON_PARSE_ERROR
```

不得写入数据库。

---

## Case 7 Provider Timeout

结果：

```text
应用正常
AgentRun = failed
error_stage = provider
```

---

# 64. 最终设计思想

整个系统不要追求：

> 模型永远正确。

真正应该追求：

> 模型犯错的时候，系统知道它错在哪，而且不会让错误扩散到业务系统。

最终架构：

```text
                 LLM

                  │

          Structured Output

                  │

          Output Normalizer

                  │

             JSON Parser

                  │

          Pydantic Schema

                  │

        Semantic Validation

                  │

             ┌────┴────┐
             │         │
          Success    Repair
                        │
                        ▼
                    Validate
                        │
                 ┌──────┴──────┐
                 ▼             ▼
              Success       Fallback

                                │

                       Fail-open / Fail-closed


                  ↓

                Planner

                  ↓

               Tools

                  ↓

       Tool Schema Validation

                  ↓

       Business Rule Validation

                  ↓

        Permission / Approval

                  ↓

               Service

                  ↓

              Database


同时全程：

                  │
                  ▼

             Observability

       Run / Raw / Error / Tool
```

最终要达到的工程标准是：

> AI 可以失败，JSON 可以失败，模型可以理解错，但系统不能“莫名其妙失败”。

任何一次错误都应该能够回答四个问题：

1. **在哪一层失败？**
2. **模型原始输出是什么？**
3. **具体哪个 Schema / 业务规则没通过？**
4. **系统最后采取了什么降级策略？**

做到这一点以后，这套 AIService 才真正适合继续承载后面的招聘 Agent。