import pymupdf
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models import Job, Resume
from app.schemas.schemas import ResumeConfirm
from app.services.resume_import_service import ResumeImportService
from app.storage.local import LocalFileStorage
from app.parsers.resume_parser import ResumeParser


def resume_pdf() -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "姓名：张三\n手机：13812345678\n邮箱：zhangsan@example.com\n浙江大学\n专业：人力资源管理\n2027届毕业\n现居：杭州")
    content = document.tobytes()
    document.close()
    return content


def service(tmp_path):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)
    job = Job(title="HRBP 实习生")
    session.add(job)
    session.commit()
    return session, job, ResumeImportService(session, LocalFileStorage(tmp_path))


def test_preview_confirm_and_deduplicate_same_resume(tmp_path):
    session, job, importer = service(tmp_path)
    content = resume_pdf()
    preview = importer.preview(job.id, "zhangsan.pdf", "application/pdf", content)
    assert preview["status"] == "parsed"
    assert preview["candidate"]["phone"] == "13812345678"
    result = importer.confirm(preview["resume_id"], ResumeConfirm(name="张三", phone="13812345678"))
    assert result["status"] == "confirmed"
    assert result["application_id"]
    assert session.get(Resume, preview["resume_id"]).parse_status == "confirmed"
    duplicate = importer.preview(job.id, "zhangsan.pdf", "application/pdf", content)
    assert duplicate["status"] == "already_exists"


def test_cancel_removes_unconfirmed_file_and_record(tmp_path):
    session, job, importer = service(tmp_path)
    preview = importer.preview(job.id, "zhangsan.pdf", "application/pdf", resume_pdf())
    resume = session.get(Resume, preview["resume_id"])
    path = importer.storage.get_path(resume.storage_path)
    assert path.exists()
    importer.cancel(resume.id)
    assert not path.exists()
    assert session.get(Resume, resume.id) is None


def test_name_and_graduation_year_need_high_confidence_evidence():
    parser = ResumeParser()
    first_page_lines = [
        {"text": "张三", "size": 22, "y": 45, "page_height": 842},
        {"text": "求职简历", "size": 14, "y": 80, "page_height": 842},
    ]
    text = """张三
教育经历
浙江大学 本科 人力资源管理 2023.09 - 2027.06
浙江大学 硕士 管理学 2027.09 - 2030.06
工作经历
某公司 2031.01 - 至今
"""
    result = parser.parse(text, first_page_lines)
    assert result["candidate"]["name"] == "张三"
    assert result["candidate"]["graduation_year"] == 2030
    assert result["candidate"]["highest_degree"] == "硕士"
    assert result["candidate"]["school"] == "浙江大学"
    assert result["candidate"]["major"] == "管理学"

    no_evidence = parser.parse("工作经历\n2022 - 2024", [])
    assert no_evidence["candidate"]["name"] is None
    assert no_evidence["candidate"]["graduation_year"] is None


def test_structured_filename_has_priority_over_pdf_guesses():
    result = ResumeParser().parse(
        "教育经历\n某大学 本科 2022.09 - 2026.06",
        [{"text": "李四", "size": 22, "y": 40, "page_height": 842}],
        "【AI应用实习生（深圳）_深圳 200-210元_天】张三 27年应届生.pdf",
    )
    assert result["candidate"]["name"] == "张三"
    assert result["candidate"]["graduation_year"] == 2027
    assert result["confidence"]["name"] == 1.0
    assert result["confidence"]["graduation_year"] == 1.0
