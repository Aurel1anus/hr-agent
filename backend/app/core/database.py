from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass

def ensure_local_schema():
    with engine.begin() as connection:
        tables = inspect(connection).get_table_names()
        if "interviews" in tables and "round_number" not in {column["name"] for column in inspect(connection).get_columns("interviews")}:
            connection.execute(text("ALTER TABLE interviews RENAME TO interviews_legacy"))
            connection.execute(text("""CREATE TABLE interviews (
                id INTEGER NOT NULL PRIMARY KEY, application_id INTEGER NOT NULL,
                round_number INTEGER NOT NULL, round_name VARCHAR(120) NOT NULL,
                candidate_availability TEXT, interviewer_availability TEXT,
                interviewer_name VARCHAR(120), interviewer_id INTEGER,
                scheduled_start_at DATETIME, scheduled_end_at DATETIME,
                mode VARCHAR(20), location VARCHAR(300), meeting_url VARCHAR(500),
                status VARCHAR(20) NOT NULL, feedback TEXT, result VARCHAR(20) NOT NULL DEFAULT 'pending',
                cancel_reason TEXT, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL,
                FOREIGN KEY(application_id) REFERENCES applications (id))"""))
            legacy = connection.execute(text("SELECT * FROM interviews_legacy")).mappings().all()
            for row in legacy:
                number = row.get("round") or 1
                names = {1: "一面", 2: "二面", 3: "三面"}
                connection.execute(text("""INSERT INTO interviews
                    (id, application_id, round_number, round_name, interviewer_name, scheduled_start_at, scheduled_end_at, mode, location, meeting_url, status, result, created_at, updated_at)
                    VALUES (:id,:application_id,:round_number,:round_name,:interviewer_name,:start,:end,:mode,:location,:meeting_url,:status,'pending',:created_at,:updated_at)"""), {
                    "id": row["id"], "application_id": row["application_id"], "round_number": number, "round_name": names.get(number, f"第{number}轮面试"), "interviewer_name": row.get("interviewer_name"), "start": row.get("start_at"), "end": row.get("end_at"), "mode": row.get("mode"), "location": row.get("location"), "meeting_url": row.get("meeting_url"), "status": row.get("status") or "scheduled", "created_at": row.get("created_at"), "updated_at": row.get("updated_at")})
            connection.execute(text("DROP TABLE interviews_legacy"))
        if "applications" in inspect(connection).get_table_names():
            columns = {column["name"] for column in inspect(connection).get_columns("applications")}
            additions = {
                "waiting_note": "ALTER TABLE applications ADD COLUMN waiting_note VARCHAR(120)",
                "archived_at": "ALTER TABLE applications ADD COLUMN archived_at DATETIME",
                "current_interview_id": "ALTER TABLE applications ADD COLUMN current_interview_id INTEGER",
                "highest_degree": "ALTER TABLE candidates ADD COLUMN highest_degree VARCHAR(30)",
            }
            candidate_columns = {column["name"] for column in inspect(connection).get_columns("candidates")} if "candidates" in inspect(connection).get_table_names() else set()
            for column, statement in additions.items():
                existing_columns = candidate_columns if column == "highest_degree" else columns
                if column not in existing_columns:
                    connection.execute(text(statement))
            if "interviews" in inspect(connection).get_table_names():
                connection.execute(text("UPDATE interviews SET status = UPPER(status), result = UPPER(result)"))
                connection.execute(text("""UPDATE applications SET current_interview_id = (
                    SELECT id FROM interviews WHERE interviews.application_id = applications.id
                    AND interviews.status IN ('scheduling', 'scheduled', 'completed')
                    ORDER BY interviews.created_at DESC LIMIT 1
                ) WHERE current_interview_id IS NULL AND stage IN ('scheduling', 'interview_scheduled', 'feedback_pending')"""))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
