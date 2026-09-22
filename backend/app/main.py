import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import router
from app.core.database import SessionLocal
from app.core.migrations import upgrade_database
from app.services.seed_service import seed
from app.services.resume_import_service import ResumeImportService
from app.services.agent_service import AIOperationError

app = FastAPI(title="HR Recruiting MVP API", version="0.1.0")
default_cors_origins = (
    "http://localhost:5173,http://127.0.0.1:5173,"
    "http://localhost:8080,http://127.0.0.1:8080,"
    "https://aurel1anus.github.io"
)
cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", default_cors_origins).split(",")
    if origin.strip()
]
github_pages_origin = "https://aurel1anus.github.io"
if github_pages_origin not in cors_origins:
    cors_origins.append(github_pages_origin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.exception_handler(AIOperationError)
async def ai_operation_error_handler(_: Request, exc: AIOperationError):
    return JSONResponse(status_code=exc.status_code, content=exc.body())


@app.on_event("startup")
def startup():
    upgrade_database()
    with SessionLocal() as db:
        ResumeImportService.cleanup_drafts(db)
        seed(db)
