# HR 招聘并发管理系统后端

本地开发默认使用 SQLite，首次启动会自动建表并写入演示数据。

首次运行前，可复制 `backend/.env.example` 为 `backend/.env`，并填写 `AI_API_KEY`。前端可复制 `frontend/.env.example` 为 `frontend/.env` 配置后端地址。两个实际 `.env` 文件不会提交到 Git。

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install .
uvicorn app.main:app --reload --reload-exclude data --port 8000
```

接口文档：http://localhost:8000/docs

## Docker 一键运行

在项目根目录执行：

```powershell
docker compose up --build
```

浏览器访问：http://localhost:8080

后端文档：http://localhost:8000/docs

停止服务：

```powershell
docker compose down
```

业务数据保存在项目的 `backend/data/` 中，重启容器不会丢失。该目录已被 Git 忽略；需要重置演示数据时，先停止服务再删除其中的数据库和简历文件。

本地开发启用热重载时，务必使用上面的 `--reload-exclude data` 参数；否则新增或删除简历文件会触发后端重启，并清理尚未确认的简历草稿。
