# HR Agent 简历上传与候选人自动录入——本地实现方案

## 1. 本阶段目标

在现有 HR 招聘并发管理系统基础上增加：

```text
岗位看板
   ↓
上传 PDF 简历
   ↓
本地保存 PDF
   ↓
提取 PDF 文本
   ↓
自动识别候选人基础信息
   ↓
生成候选人草稿
   ↓
HR 人工确认 / 修改
   ↓
创建 Candidate
   ↓
创建 Application
   ↓
候选人进入“待筛选”
```

当前版本：

```text
不接 AWS S3
不接 PostgreSQL
不接 LLM
不做 OCR
不做登录鉴权
```

继续使用当前已有：

```text
React
FastAPI
SQLAlchemy
SQLite
```

新增：

```text
PyMuPDF
本地文件存储
Resume 数据模型
ResumeImportService
ResumeParser
```

---

# 2. 本地整体架构

```text
React
  │
  │ 上传 PDF
  ▼
FastAPI
  │
  ├── 保存 PDF 到本地
  │
  ├── PyMuPDF 提取文字
  │
  ├── ResumeParser 提取字段
  │
  └── 返回候选人草稿
  │
  ▼
React 确认页面
  │
  │ HR 修改 / 确认
  ▼
FastAPI
  │
  ├── 创建 Candidate
  ├── 创建 Application
  ├── Resume 关联 Candidate
  └── 创建 Activity
  │
  ▼
SQLite
```

文件与数据库分开：

```text
SQLite

Job
Candidate
Application
Task
Interview
Activity
Resume Metadata
```

```text
本地磁盘

PDF Resume
```

---

# 3. 为什么本地 PDF 也不要存在 SQLite

不要：

```text
PDF
↓
二进制
↓
SQLite BLOB
```

而是：

```text
PDF
↓
backend/data/resumes/xxx.pdf
```

SQLite 只保存：

```text
文件路径
原始文件名
文件大小
解析状态
解析结果
```

这样后面迁移 S3 时非常简单。

---

# 4. 推荐目录结构

在你现在的后端增加：

```text
backend/
│
├── app/
│   ├── main.py
│   │
│   ├── api/
│   │   ├── jobs.py
│   │   ├── candidates.py
│   │   ├── applications.py
│   │   ├── tasks.py
│   │   ├── interviews.py
│   │   ├── activities.py
│   │   └── resumes.py
│   │
│   ├── models/
│   │   ├── resume.py
│   │   └── ...
│   │
│   ├── schemas/
│   │   ├── resume.py
│   │   └── ...
│   │
│   ├── services/
│   │   ├── resume_import_service.py
│   │   └── ...
│   │
│   ├── parsers/
│   │   ├── base.py
│   │   └── resume_parser.py
│   │
│   ├── storage/
│   │   ├── base.py
│   │   └── local.py
│   │
│   └── core/
│
└── data/
    └── resumes/
```

注意：

```text
backend/data/resumes/
```

加入 `.gitignore`。

不要把真实简历提交到 GitHub。

---

# 5. Resume 数据模型

新增 `Resume` 表。

建议：

```python
class Resume(Base):
    __tablename__ = "resumes"

    id: UUID

    job_id: UUID

    candidate_id: UUID | None

    original_filename: str

    storage_path: str

    mime_type: str

    file_size: int

    sha256: str | None

    parse_status: str

    extracted_text: str | None

    parsed_data: JSON | None

    parser_version: str | None

    created_at: datetime
    updated_at: datetime
```

其中：

```text
candidate_id
```

上传并解析时：

```text
null
```

HR 确认创建 Candidate 后再关联。

---

# 6. Resume 状态

建议定义：

```python
class ResumeParseStatus(str, Enum):
    UPLOADED = "uploaded"
    PARSED = "parsed"
    FAILED = "failed"
    CONFIRMED = "confirmed"
```

当前流程：

```text
上传
↓
UPLOADED

解析成功
↓
PARSED

HR确认
↓
CONFIRMED
```

解析失败：

```text
FAILED
```

---

# 7. LocalStorage 抽象

虽然现在只存本地，也不要直接在 API 里：

```python
open("xxx.pdf", "wb")
```

建议定义：

```python
class FileStorage:

    def save(self, file, filename):
        pass

    def delete(self, path):
        pass

    def get_path(self, path):
        pass
```

本地实现：

```python
class LocalFileStorage(FileStorage):
    ...
```

例如：

```text
storage/
├── base.py
└── local.py
```

未来迁移 AWS：

```text
storage/
├── base.py
├── local.py
└── s3.py
```

然后业务代码完全不用改。

---

# 8. 本地文件命名

不要直接使用：

```text
张三的简历.pdf
```

作为实际文件名。

使用 UUID：

```text
data/resumes/
    {job_id}/
        {uuid}.pdf
```

例如：

```text
data/resumes/
    17/
        82cd8f90-a891-46c2.pdf
```

数据库：

```text
original_filename =
张三-浙江大学.pdf

storage_path =
17/82cd8f90-a891-46c2.pdf
```

---

# 9. 上传接口

新增：

```text
POST /jobs/{job_id}/resume-imports/preview
```

请求：

```text
multipart/form-data
```

字段：

```text
file
```

FastAPI：

```python
from fastapi import UploadFile, File

@router.post(
    "/jobs/{job_id}/resume-imports/preview"
)
async def preview_resume(
    job_id: int,
    file: UploadFile = File(...)
):
    ...
```

---

# 10. 上传时需要做的校验

首先检查：

```text
文件是否为空
```

然后：

```text
文件类型是否 PDF
```

建议同时检查：

```text
filename 后缀
+
Content-Type
```

第一版限制：

```text
application/pdf
```

以及文件大小，例如：

```text
最大 10MB
```

超过：

```text
简历文件过大，请上传 10MB 以下 PDF。
```

---

# 11. 保存 PDF

收到文件后：

```text
读取文件
↓
生成 UUID
↓
计算 SHA256
↓
保存到 data/resumes/{job_id}/
```

SHA256 后面可以用于：

```text
重复文件检测
```

例如：

```text
同一份 PDF 被重复上传
```

可以直接提示。

---

# 12. PDF 文本提取

安装：

```bash
pip install pymupdf python-multipart
```

代码单独放：

```text
services/
或者
parsers/
```

例如：

```python
import fitz


def extract_pdf_text(path: str) -> str:
    doc = fitz.open(path)

    pages = []

    for page in doc:
        pages.append(page.get_text())

    return "\n".join(pages)
```

不要把 PyMuPDF 调用直接写在 FastAPI Route 中。

---

# 13. 扫描版 PDF 判断

当前版本不做 OCR。

如果：

```text
len(extracted_text.strip()) < 50
```

可以认为：

```text
可能是扫描版PDF
```

返回：

```json
{
  "status": "failed",
  "error_code": "PDF_TEXT_NOT_FOUND",
  "message": "未能从该 PDF 中识别出有效文本，请手动添加候选人。"
}
```

以后再做：

```text
PyMuPDF
↓
失败
↓
OCR
```

---

# 14. ResumeParser

新增：

```text
app/parsers/resume_parser.py
```

职责只有：

> 把文本转换成候选人结构化数据。

例如：

```python
class ResumeParser:

    def parse(self, text: str):
        return {
            "name": self.extract_name(text),
            "phone": self.extract_phone(text),
            "email": self.extract_email(text),
            "school": self.extract_school(text),
            "major": self.extract_major(text),
            "graduation_year": self.extract_graduation_year(text),
            "current_city": self.extract_current_city(text),
        }
```

---

# 15. 第一版优先自动识别字段

只识别：

```text
姓名

手机

邮箱

学校

专业

毕业年份

当前城市
```

不要一开始解析：

```text
所有工作经历

所有项目

技能

证书

求职意向

复杂教育经历
```

这些以后 Agent 阶段再做。

---

# 16. 手机号识别

中国大陆手机号可以先使用正则：

```python
r'(?<!\d)1[3-9]\d{9}(?!\d)'
```

例如：

```text
13812345678
```

---

# 17. Email 识别

可以用：

```python
r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
```

这种字段规则解析成功率很高。

---

# 18. 毕业年份

可以先查：

```text
2025
2026
2027
2028
2029
```

再结合：

```text
毕业
届
教育经历
本科
硕士
```

判断。

第一版不用追求完美。

---

# 19. 学校和专业

这是规则解析里相对困难的一部分。

第一版可以：

```text
按行解析
+
关键词判断
```

例如包含：

```text
大学
学院
University
College
```

的行优先作为学校候选。

然后保留：

```text
confidence
```

概念。

例如：

```json
{
  "value": "浙江大学",
  "confidence": 0.85
}
```

---

# 20. 解析结果 Schema

推荐不要直接返回：

```json
{
  "school": "浙江大学"
}
```

内部可以：

```json
{
  "school": {
    "value": "浙江大学",
    "confidence": 0.86
  }
}
```

其他字段相同。

例如：

```json
{
  "name": {
    "value": "张三",
    "confidence": 0.8
  },
  "phone": {
    "value": "13812345678",
    "confidence": 1.0
  },
  "current_city": {
    "value": null,
    "confidence": 0
  }
}
```

---

# 21. Preview API 返回

完整响应可以设计：

```json
{
  "resume_id": "abc123",

  "filename": "张三简历.pdf",

  "status": "parsed",

  "candidate": {
    "name": "张三",
    "phone": "13812345678",
    "email": "zhangsan@example.com",
    "school": "浙江大学",
    "major": "人力资源管理",
    "graduation_year": 2027,
    "current_city": null
  },

  "confidence": {
    "name": 0.8,
    "phone": 1.0,
    "email": 1.0,
    "school": 0.86,
    "major": 0.63,
    "graduation_year": 0.75,
    "current_city": 0
  },

  "warnings": [
    "未识别当前城市",
    "专业识别结果建议人工确认"
  ]
}
```

---

# 22. React 上传入口

岗位 Kanban 页面：

```text
[ + 添加候选人 ]
```

点击：

```text
添加候选人

○ 手动填写
● 上传简历
```

上传区域：

```text
┌──────────────────────────┐
│                          │
│   拖拽 PDF 到这里        │
│                          │
│   或                     │
│                          │
│   [选择 PDF 文件]        │
│                          │
└──────────────────────────┘
```

---

# 23. 上传过程状态

用户选择：

```text
张三简历.pdf
```

页面显示：

```text
正在上传简历...
```

然后：

```text
正在解析候选人信息...
```

第一版两步实际上可以是同一个 API。

UI 分开显示只是体验更好。

---

# 24. 解析确认页面

解析成功后不要立即创建 Candidate。

显示：

```text
简历识别结果
```

例如：

```text
姓名
[ 张三                 ]

手机
[ 13812345678          ]

邮箱
[ zhangsan@gmail.com   ]

学校
[ 浙江大学             ]

专业
[ 人力资源管理         ]

毕业年份
[ 2027                 ]

当前城市
[ 未识别               ]
  ⚠ 请手动确认
```

下面显示：

```text
原始简历

张三简历.pdf

[查看简历]
```

按钮：

```text
取消

确认添加
```

---

# 25. HR 可以修改全部识别字段

重要原则：

> 自动识别结果只是 Draft。

用户可以直接：

```text
改姓名
改学校
改专业
补城市
改毕业年份
```

数据库最终以：

```text
HR确认后的数据
```

为准。

---

# 26. 确认接口

新增：

```text
POST /resume-imports/{resume_id}/confirm
```

Body：

```json
{
  "name": "张三",
  "phone": "13812345678",
  "email": "zhangsan@example.com",
  "school": "浙江大学",
  "major": "人力资源管理",
  "graduation_year": 2027,
  "current_city": "杭州"
}
```

---

# 27. Confirm Service

后端：

```text
ResumeImportService.confirm()
```

执行：

```text
查询 Resume

确认 Resume 尚未 confirmed

检查 Candidate 是否重复

创建 / 复用 Candidate

创建 Application

Resume.candidate_id = Candidate.id

Resume.parse_status = CONFIRMED

创建 Activity
```

必须使用数据库 Transaction。

---

# 28. 创建 Candidate

如果没有重复：

```text
create Candidate
```

信息来自：

```text
HR最终确认值
```

不要重新使用 Parser 原始值。

---

# 29. 创建 Application

自动：

```text
job_id = 当前上传所在岗位

candidate_id = Candidate.id

stage = SCREENING

blocked_by = HR
```

然后：

```text
stage_changed_at = now()
```

---

# 30. 创建 Activity

自动产生：

```text
候选人通过简历上传加入岗位
```

例如：

```text
type =
APPLICATION_CREATED
```

metadata：

```json
{
  "source": "resume_upload",
  "resume_id": "xxx"
}
```

这样以后可以统计：

```text
手动添加
vs
简历上传
vs
Boss自动导入
```

---

# 31. 重复候选人检测

第一版可以采用三层。

强匹配：

```text
phone 相同
```

或者：

```text
email 相同
```

认为：

```text
极可能同一个 Candidate
```

弱匹配：

```text
姓名
+
学校
+
毕业年份
```

全部一致：

```text
疑似重复
```

---

# 32. 如果 Candidate 已存在

例如：

```text
张三
浙江大学
2027
```

已经存在。

现在又在：

```text
HRBP实习生
```

上传他的简历。

正确行为不是：

```text
再创建一个张三
```

而是：

```text
已有 Candidate
+
新的 Application
```

数据库：

```text
Candidate 张三
    │
    ├── 招聘实习生 Application
    │
    └── HRBP实习生 Application
```

---

# 33. 如果 Candidate 在这个 Job 也已经存在

例如：

```text
Candidate 张三
+
HRBP 实习生
```

已经有 Application。

则返回：

```text
该候选人已经存在于当前岗位。
```

前端：

```text
[查看已有候选人]
```

不要重复创建 Application。

---

# 34. PDF 查看

本地版本提供：

```text
GET /resumes/{resume_id}/file
```

FastAPI：

```text
查询 Resume.storage_path
↓
FileResponse
```

React：

```text
[查看简历]
```

点击：

```text
新标签页打开 PDF
```

以后迁 S3 时这个接口可以改成：

```text
返回 presigned URL
```

前端甚至无需明显变化。

---

# 35. PDF 删除

MVP 暂时不要提供：

```text
删除 Resume
```

尤其 Resume 已经和 Candidate 关联后。

后续可以考虑：

```text
软删除
```

避免破坏 Activity 和历史数据。

---

# 36. ResumeImportService

建议：

```python
class ResumeImportService:

    def preview_resume(
        self,
        job_id,
        upload_file
    ):
        pass

    def confirm_resume(
        self,
        resume_id,
        candidate_data
    ):
        pass

    def get_resume_file(
        self,
        resume_id
    ):
        pass
```

这是整个功能的业务入口。

---

# 37. 依赖关系

推荐：

```text
Resume API
   │
   ▼
ResumeImportService
   │
   ├── LocalFileStorage
   │
   ├── PDFTextExtractor
   │
   ├── ResumeParser
   │
   ├── CandidateService
   │
   ├── ApplicationService
   │
   └── ActivityService
```

这很重要。

不要：

```text
ResumeImportService
↓
直接各种数据库 update
```

尽量复用你已经写好的 Service。

---

# 38. 前端 TypeScript 类型

新增：

```typescript
type ParsedField<T> = {
  value: T | null
  confidence: number
}

type ResumePreview = {
  resumeId: string
  filename: string

  candidate: {
    name: string | null
    phone: string | null
    email: string | null
    school: string | null
    major: string | null
    graduationYear: number | null
    currentCity: string | null
  }

  confidence: Record<string, number>

  warnings: string[]
}
```

---

# 39. React 组件建议

增加：

```text
components/
└── resume/
    ├── ResumeUpload.tsx
    ├── ResumeDropzone.tsx
    ├── ResumeParsing.tsx
    ├── ResumePreview.tsx
    └── ResumeField.tsx
```

现有：

```text
AddCandidateModal
```

可以改成：

```text
AddCandidateModal
├── ManualCandidateForm
└── ResumeImport
```

---

# 40. API Service

前端：

```text
services/
└── resumes.ts
```

例如：

```typescript
previewResume(jobId, file)

confirmResume(resumeId, data)

getResumeFileUrl(resumeId)
```

---

# 41. Docker 本地运行需要注意

你已经有 Docker Compose。

如果 FastAPI 在 Docker 中运行，本地简历必须使用 Docker Volume。

否则：

```text
docker compose down
↓
重新创建 container
↓
PDF可能没了
```

因此：

```yaml
services:
  backend:
    volumes:
      - ./backend/data:/app/data
```

这样：

```text
Container
/app/data/resumes
```

实际对应：

```text
你的电脑
backend/data/resumes
```

即使重新构建容器：

```text
PDF还在。
```

---

# 42. SQLite 也要挂 Volume

如果 SQLite 当前在：

```text
backend/data/hr.db
```

同一个：

```yaml
- ./backend/data:/app/data
```

就可以同时持久化：

```text
SQLite
+
PDF
```

所以本地开发结构变成：

```text
backend/data/

├── hr.db
└── resumes/
```

非常简单。

---

# 43. .gitignore

增加：

```gitignore
backend/data/
```

或者：

```gitignore
backend/data/*.db
backend/data/resumes/
```

如果需要保留：

```text
data/
```

目录本身，可以：

```text
backend/data/resumes/.gitkeep
```

但真实 PDF 永远不要提交。

---

# 44. 本地配置

`.env`：

```text
DATABASE_URL=sqlite:///./data/hr.db

STORAGE_BACKEND=local

LOCAL_STORAGE_ROOT=./data

RESUME_STORAGE_DIR=resumes

MAX_RESUME_SIZE_MB=10
```

未来线上：

```text
STORAGE_BACKEND=s3
```

然后切换实现。

---

# 45. 未来迁移 S3 时怎么改

现在：

```text
ResumeImportService
        │
        ▼
LocalFileStorage
```

以后：

```text
ResumeImportService
        │
        ▼
S3FileStorage
```

其他：

```text
React
API
Resume
Candidate
Application
Parser
```

全部不用改。

例如：

```python
if settings.STORAGE_BACKEND == "local":
    storage = LocalFileStorage()

elif settings.STORAGE_BACKEND == "s3":
    storage = S3FileStorage()
```

---

# 46. 第一版不要实现的功能

当前不要同时做：

```text
OCR

LLM解析

AI筛选

Word简历

图片简历

批量上传

拖入50份文件

自动创建候选人无需确认

复杂重复匹配

S3

异步消息队列
```

把单份 PDF 先跑稳定。

---

# 47. 第二版再做批量上传

第一版：

```text
1 PDF
↓
1 Preview
↓
1 Confirm
```

第二版：

```text
20 PDF
↓
20 Resume
↓
解析
↓
表格
```

例如：

```text
姓名   学校       毕业   状态

张三   浙江大学   27届   ✓
李四   南京大学   27届   ✓
王五   未识别     27届   ⚠
```

然后：

```text
批量确认添加
```

---

# 48. 推荐开发顺序

第一步先新增：

```text
Resume model
```

和数据库迁移。

第二步做：

```text
LocalFileStorage
```

保证 PDF 能保存。

第三步：

```text
PyMuPDF TextExtractor
```

确认可以抽出简历文本。

第四步：

```text
ResumeParser
```

先实现：

```text
phone
email
graduation_year
```

再逐渐加：

```text
name
school
major
city
```

第五步：

```text
POST /resume-imports/preview
```

第六步 React：

```text
上传
+
Preview
```

第七步：

```text
confirm
```

创建：

```text
Candidate
Application
```

第八步：

```text
重复检测
```

第九步：

```text
PDF查看
```

---

# 49. 第一阶段验收场景

进入：

```text
HRBP实习生
```

点击：

```text
添加候选人
```

选择：

```text
上传简历
```

上传：

```text
张三.pdf
```

系统显示：

```text
姓名       张三

手机号     138xxxxxxxx

邮箱       xxx@gmail.com

学校       浙江大学

专业       人力资源管理

毕业年份   2027

当前城市   未识别
```

HR填写：

```text
当前城市：
杭州
```

点击：

```text
确认添加
```

然后岗位 Kanban：

```text
待筛选  5

张三
浙江大学 · 27届
等待HR处理
```

打开张三 Drawer：

```text
基础信息
✓

招聘流程
待筛选

原始简历
[查看PDF]

招聘记录
刚刚
通过PDF简历导入候选人
```

关闭浏览器。

重新打开：

```text
张三还存在。
```

关闭 Docker。

重新：

```text
docker compose up
```

张三和 PDF：

```text
仍然存在。
```

达到这一点，本地版本就算完成。

---

# 50. 当前建议最终架构

```text
                     React
                       │
                       ▼
                    FastAPI
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
Application       ResumeImport     Existing
 Service            Service         Services
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
       ResumeParser       LocalFileStorage
             │                   │
             ▼                   ▼
           SQLite          data/resumes/
```

未来线上只需要变成：

```text
SQLite
↓
PostgreSQL
```

以及：

```text
LocalFileStorage
↓
S3FileStorage
```

你的：

```text
React
FastAPI API
ResumeImportService
ResumeParser
CandidateService
ApplicationService
```

都可以继续保留。

---

# 51. 本阶段最重要的设计原则

这个功能不要理解成：

```text
上传 PDF
→ 自动创建候选人
```

而应该理解成：

```text
上传 PDF
→ 自动生成候选人草稿
→ 人工确认
→ 正式加入招聘流程
```

这样第一版即使规则解析准确率还没有做到非常高，也已经可以投入使用。

它减少的是：

> HR 打开 PDF 后，把姓名、学校、手机、邮箱、毕业年份等信息重新手工抄进系统的过程。

而不是要求第一版就做到：

> 机器 100% 理解一份复杂简历。