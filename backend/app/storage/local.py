from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from app.core.config import LOCAL_STORAGE_ROOT


class LocalFileStorage:
    """Stores resumes below the configured local data directory."""

    def __init__(self, root: Path = LOCAL_STORAGE_ROOT):
        self.root = root.resolve()

    def save_resume(self, job_id: int, content: bytes) -> str:
        relative_path = Path("resumes") / str(job_id) / f"{uuid4()}.pdf"
        destination = self.root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return relative_path.as_posix()

    def get_path(self, storage_path: str) -> Path:
        path = (self.root / storage_path).resolve()
        if self.root not in path.parents:
            raise ValueError("非法文件路径")
        return path

    def delete(self, storage_path: str) -> None:
        path = self.get_path(storage_path)
        if path.exists():
            path.unlink()
