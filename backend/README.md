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

业务数据保存在 Docker volume `hr-v2_hr-data` 中，重启容器不会丢失。
