from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass

def ensure_local_schema():
    with engine.begin() as connection:
        if "applications" in inspect(connection).get_table_names():
            columns = {column["name"] for column in inspect(connection).get_columns("applications")}
            additions = {
                "waiting_note": "ALTER TABLE applications ADD COLUMN waiting_note VARCHAR(120)",
                "archived_at": "ALTER TABLE applications ADD COLUMN archived_at DATETIME",
                "highest_degree": "ALTER TABLE candidates ADD COLUMN highest_degree VARCHAR(30)",
            }
            candidate_columns = {column["name"] for column in inspect(connection).get_columns("candidates")} if "candidates" in inspect(connection).get_table_names() else set()
            for column, statement in additions.items():
                existing_columns = candidate_columns if column == "highest_degree" else columns
                if column not in existing_columns:
                    connection.execute(text(statement))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
