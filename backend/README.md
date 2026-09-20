# HR 招聘并发管理系统后端

本地开发默认使用 SQLite，首次启动会自动建表并写入演示数据。

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

接口文档：http://localhost:8000/docs
