import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./hr_recruiting.db")
LOCAL_STORAGE_ROOT = Path(os.getenv("LOCAL_STORAGE_ROOT", BASE_DIR / "data"))
MAX_RESUME_SIZE_MB = int(os.getenv("MAX_RESUME_SIZE_MB", "10"))
MAX_RESUME_PAGES = int(os.getenv("MAX_RESUME_PAGES", "30"))
