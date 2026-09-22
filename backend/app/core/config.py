import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./hr_recruiting.db")
LOCAL_STORAGE_ROOT = Path(os.getenv("LOCAL_STORAGE_ROOT", BASE_DIR / "data"))
MAX_RESUME_SIZE_MB = int(os.getenv("MAX_RESUME_SIZE_MB", "10"))
MAX_RESUME_PAGES = int(os.getenv("MAX_RESUME_PAGES", "30"))
AI_PROVIDER = os.getenv("AI_PROVIDER", "deepseek")
AI_PROTOCOL = os.getenv("AI_PROTOCOL", "openai")
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.deepseek.com")
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "deepseek-flash")
AI_TIMEOUT_SECONDS = float(os.getenv("AI_TIMEOUT_SECONDS", "60"))
# DeepSeek V4 起 thinking 默认开启；默认关闭以保证响应确定性与成本可控
AI_DISABLE_THINKING = os.getenv("AI_DISABLE_THINKING", "1") == "1"
AI_THINKING_EFFORT = os.getenv("AI_THINKING_EFFORT", "high")  # low/high/max
