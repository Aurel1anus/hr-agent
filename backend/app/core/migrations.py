from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

from app.core.config import DATABASE_URL

BACKUP_LIMIT = 30
BACKUP_DIR = Path(__file__).resolve().parents[2] / "backups"
ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def sqlite_database_path(url: str) -> Path | None:
    if not url.startswith("sqlite:///") or url in {"sqlite://", "sqlite:///:memory:"}:
        return None
    database = Path(url.removeprefix("sqlite:///"))
    return database.resolve()


def alembic_config() -> Config:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", DATABASE_URL)
    return config


def migration_required(config: Config) -> bool:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    try:
        with engine.connect() as connection:
            current = MigrationContext.configure(connection).get_current_revision()
        return current != ScriptDirectory.from_config(config).get_current_head()
    finally:
        engine.dispose()


def backup_sqlite_database(path: Path) -> Path | None:
    if not path.exists() or not path.stat().st_size:
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup = BACKUP_DIR / f"{path.stem}-{datetime.now():%Y%m%d-%H%M%S}{path.suffix}"
    shutil.copy2(path, backup)
    backups = sorted(BACKUP_DIR.glob(f"{path.stem}-*{path.suffix}"), key=lambda item: item.stat().st_mtime, reverse=True)
    for stale in backups[BACKUP_LIMIT:]:
        stale.unlink()
    return backup


def upgrade_database() -> Path | None:
    """Back up file-backed SQLite data before applying pending migrations."""
    config = alembic_config()
    if not migration_required(config):
        return None
    path = sqlite_database_path(DATABASE_URL)
    backup = backup_sqlite_database(path) if path else None
    command.upgrade(config, "head")
    return backup
