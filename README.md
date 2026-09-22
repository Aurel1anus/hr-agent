# HR 招聘并发管理系统｜运行手册

本手册用于开发、演示和日常运维。项目由 React/Vite 前端和 FastAPI/SQLite 后端组成；后端首次启动会执行数据库迁移并写入演示数据。

## 运行前检查

| 项目 | 要求 | 验证命令 |
| --- | --- | --- |
| 操作系统 | Windows（内置脚本为 PowerShell） | `$PSVersionTable.PSVersion` |
| Python | 3.12 或 3.13 | `python --version` |
| Node.js | 22 或兼容的现代 LTS 版本 | `node --version` |
| Docker（可选） | Docker Desktop + Compose | `docker compose version` |

后端 Python 依赖唯一由 `backend/pyproject.toml` 管理。请使用 `pip install .`，不要使用已移除的 `requirements.txt`。

## 首次启动：Windows 快捷方式

1. 可选：从示例文件创建本地配置并填写 AI 密钥。

   ```powershell
   Copy-Item backend/.env.example backend/.env
   Copy-Item frontend/.env.example frontend/.env
   ```

2. 在项目根目录打开两个 PowerShell 窗口，分别运行：

   ```powershell
   .\启动后端.ps1
   ```

   ```powershell
   .\启动前端.ps1
   ```

3. 打开下列地址确认服务可用：

   - 前端：<http://localhost:5173>
   - 后端健康检查：<http://localhost:8000/health>
   - OpenAPI 文档：<http://localhost:8000/docs>

脚本会安装依赖；后端脚本会在启动前执行迁移。首次启动时间通常比后续启动更长。

## 手动开发启动

### 后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install .
python -m uvicorn app.main:app --reload --reload-exclude data --host 127.0.0.1 --port 8000
```

`--reload-exclude data` 必须保留：简历文件写入 `backend/data`，如果监视此目录会导致后端反复重启。

### 前端

```powershell
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

默认后端地址为 `http://localhost:8000`；需要修改时在 `frontend/.env` 设置 `VITE_API_BASE_URL`，重启前端后生效。

## Docker 启动

在项目根目录执行：

```powershell
docker compose up --build -d
docker compose ps
```

访问 <http://localhost:8080>；后端文档仍在 <http://localhost:8000/docs>。

查看日志与停止服务：

```powershell
docker compose logs -f backend
docker compose logs -f frontend
docker compose down
```

容器数据映射到 `backend/data/`，执行 `docker compose down` 不会删除数据。

## 配置清单

将 `backend/.env.example` 复制为 `backend/.env` 后按需修改：

| 变量 | 用途 | 默认值 |
| --- | --- | --- |
| `DATABASE_URL` | SQLite 数据库连接地址 | `sqlite:///./hr_recruiting.db` |
| `LOCAL_STORAGE_ROOT` | 简历等本地文件存储目录 | `./data` |
| `AI_API_KEY` | AI 服务密钥 | 空 |
| `AI_BASE_URL` / `AI_MODEL` | AI 服务地址与模型 | DeepSeek 默认值 |
| `AI_TIMEOUT_SECONDS` | AI 请求超时秒数 | `60` |
| `CORS_ORIGINS` | 允许访问 API 的前端来源，逗号分隔 | 本地开发地址 |

`.env` 文件和 `backend/data/` 都被 Git 忽略，不应提交密钥或业务数据。

## 更新流程

拉取代码后，在项目根目录执行：

```powershell
.\更新.ps1
```

该脚本会安装后端依赖、执行待处理迁移、安装前端依赖并构建前端。随后重启本地进程或 Docker 服务。

## 健康检查与验证

后端启动后可执行：

```powershell
Invoke-WebRequest http://localhost:8000/health | Select-Object -ExpandProperty Content
```

开发验证命令：

```powershell
cd backend; python -m pytest
cd ../frontend; npm run build
```

当前测试覆盖简历导入、面试流程、岗位汇总和 AI 输出解析。

## 常见问题

| 现象 | 排查方式 |
| --- | --- |
| 前端提示请求失败 | 确认后端 `http://localhost:8000/health` 可访问，并检查 `VITE_API_BASE_URL`。 |
| 浏览器出现 CORS 错误 | 将前端实际来源加入 `CORS_ORIGINS`，然后重启后端。 |
| AI 功能不可用 | 检查 `backend/.env` 的 `AI_API_KEY`、`AI_BASE_URL`、模型名及网络连通性。 |
| 数据库迁移失败 | 关闭后端后保留 `backend/data/` 以便备份；查看终端错误和 `backend/backups/`。 |
| 需要重置演示数据 | 先停止后端或执行 `docker compose down`，再手动删除 `backend/data/`；此操作会永久删除本地业务数据。 |

## 项目入口

| 位置 | 用途 |
| --- | --- |
| `frontend/` | React/Vite 前端 |
| `backend/app/` | FastAPI 应用与业务逻辑 |
| `backend/migrations/` | Alembic 数据库迁移 |
| `backend/pyproject.toml` | 后端依赖与打包配置 |
| `docker-compose.yml` | 双容器部署编排 |
| `backend/README.md` | 后端侧的简要开发说明 |
