from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pymupdf
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import MAX_RESUME_PAGES, MAX_RESUME_SIZE_MB
from app.core.enums import JobStatus
from app.models import Application, Candidate, Job, Resume
from app.parsers import ResumeParser
from app.services.service import activity
from app.storage import LocalFileStorage


class ResumeImportService:
    def __init__(self, db: Session, storage: LocalFileStorage | None = None):
        self.db = db
        self.storage = storage or LocalFileStorage()
        self.parser = ResumeParser()

    def preview(self, job_id: int, filename: str, content_type: str | None, content: bytes) -> dict:
        job = self._job(job_id)
        if job.status == JobStatus.CLOSED:
            raise HTTPException(422, detail="已关闭的岗位不能导入简历。")
        self._validate_upload(filename, content_type, content)
        sha256 = hashlib.sha256(content).hexdigest()
        try:
            document = pymupdf.open(stream=content, filetype="pdf")
            if document.needs_pass:
                raise ValueError("加密 PDF")
            if document.page_count > MAX_RESUME_PAGES:
                raise ValueError(f"页数超过 {MAX_RESUME_PAGES} 页")
            text = "\n".join(page.get_text() for page in document)
            first_page_lines = self._first_page_lines(document[0])
            document.close()
        except ValueError as error:
            raise HTTPException(422, detail=f"无法解析 PDF：{error}。请上传未加密、可复制文字的 PDF，或改为手动录入。")
        except Exception:
            raise HTTPException(422, detail="PDF 文件损坏或无法读取，请上传有效 PDF，或改为手动录入。")
        if len(text.strip()) < 50:
            raise HTTPException(422, detail="未能从该 PDF 中识别出有效文本，请上传可复制文字的 PDF，或改为手动录入。")

        parsed = self.parser.parse(text, first_page_lines, filename)
        match = self._match_candidates(parsed["candidate"])
        application = self._existing_application(job_id, match["strong_candidate_id"])
        if application and self.db.scalar(
            select(Resume).where(Resume.application_id == application.id, Resume.sha256 == sha256)
        ):
            return {
                "status": "already_exists",
                "application_id": application.id,
                "message": "该候选人的同一份简历已存在于当前岗位。",
            }

        storage_path = self.storage.save_resume(job_id, content)
        resume = Resume(
            job_id=job_id,
            original_filename=Path(filename).name[:255],
            storage_path=storage_path,
            mime_type="application/pdf",
            file_size=len(content),
            sha256=sha256,
            parse_status="parsed",
            parsed_data={**parsed, "match": match},
            extracted_text=text,
            parser_version=self.parser.version,
        )
        self.db.add(resume)
        self.db.commit()
        self.db.refresh(resume)
        return {**self._preview_view(resume), "text_preview": text[:20000]}

    def confirm(self, resume_id: int, data) -> dict:
        resume = self.db.get(Resume, resume_id)
        if not resume:
            raise HTTPException(404, detail="简历草稿不存在或已被删除。")
        if resume.parse_status == "confirmed":
            return {"status": "confirmed", "application_id": resume.application_id, "resume_id": resume.id, "already_confirmed": True}
        job = self._job(resume.job_id)
        parsed = resume.parsed_data or {}
        match = parsed.get("match", {})
        candidate = self._resolve_candidate(data, match)
        application = self._existing_application(job.id, candidate.id) if candidate else None
        if job.status == JobStatus.CLOSED:
            raise HTTPException(422, detail="已关闭的岗位不能确认导入简历。")
        if job.status == JobStatus.PAUSED and not application:
            raise HTTPException(422, detail="已暂停岗位只允许为已有候选人补充简历。")

        if candidate is None:
            candidate = Candidate(**self._candidate_values(data), source="resume_upload")
            self.db.add(candidate)
            self.db.flush()
        else:
            for key, value in self._candidate_values(data).items():
                if value is not None and value != "":
                    setattr(candidate, key, value)

        if application is None:
            application = Application(job_id=job.id, candidate_id=candidate.id)
            self.db.add(application)
            self.db.flush()
            activity(self.db, application.id, "APPLICATION_CREATED", "候选人通过 PDF 简历加入岗位", {"source": "resume_upload", "resume_id": resume.id})
        else:
            activity(self.db, application.id, "RESUME_UPDATED", "候选人更新了 PDF 简历", {"source": "resume_upload", "resume_id": resume.id})
        resume.candidate_id = candidate.id
        resume.application_id = application.id
        resume.parse_status = "confirmed"
        self.db.commit()
        return {"status": "confirmed", "application_id": application.id, "resume_id": resume.id, "already_confirmed": False}

    def cancel(self, resume_id: int) -> None:
        resume = self.db.get(Resume, resume_id)
        if not resume or resume.parse_status == "confirmed":
            return
        self.storage.delete(resume.storage_path)
        self.db.delete(resume)
        self.db.commit()

    def file_path(self, resume_id: int) -> Path:
        resume = self.db.get(Resume, resume_id)
        if not resume or resume.parse_status != "confirmed":
            raise HTTPException(404, detail="简历文件不存在。")
        path = self.storage.get_path(resume.storage_path)
        if not path.exists():
            raise HTTPException(404, detail="简历文件不存在。")
        return path

    @classmethod
    def cleanup_drafts(cls, db: Session) -> None:
        storage = LocalFileStorage()
        drafts = db.scalars(select(Resume).where(Resume.parse_status != "confirmed")).all()
        for resume in drafts:
            storage.delete(resume.storage_path)
            db.delete(resume)
        db.commit()

    def _job(self, job_id: int) -> Job:
        job = self.db.get(Job, job_id)
        if not job:
            raise HTTPException(404, detail="岗位不存在。")
        return job

    @staticmethod
    def _validate_upload(filename: str, content_type: str | None, content: bytes) -> None:
        if not filename or not filename.lower().endswith(".pdf"):
            raise HTTPException(422, detail="请上传 PDF 格式的简历。")
        if content_type not in (None, "", "application/pdf"):
            raise HTTPException(422, detail="请上传 PDF 格式的简历。")
        if not content:
            raise HTTPException(422, detail="简历文件不能为空。")
        if len(content) > MAX_RESUME_SIZE_MB * 1024 * 1024:
            raise HTTPException(422, detail=f"简历文件过大，请上传 {MAX_RESUME_SIZE_MB}MB 以下 PDF。")
        if not content.startswith(b"%PDF-"):
            raise HTTPException(422, detail="文件不是有效 PDF。")

    @staticmethod
    def _normal_phone(value: str | None) -> str | None:
        if not value:
            return None
        value = re.sub(r"[\s-]", "", value)
        return value[3:] if value.startswith("+86") else value

    @staticmethod
    def _normal_email(value: str | None) -> str | None:
        return value.strip().lower() if value else None

    def _match_candidates(self, data: dict) -> dict:
        phone, email = self._normal_phone(data.get("phone")), self._normal_email(data.get("email"))
        candidates = self.db.scalars(select(Candidate).options(selectinload(Candidate.applications).selectinload(Application.job))).all()
        phone_ids = {candidate.id for candidate in candidates if phone and self._normal_phone(candidate.phone) == phone}
        email_ids = {candidate.id for candidate in candidates if email and self._normal_email(candidate.email) == email}
        strong_ids = phone_ids | email_ids
        conflict = bool(phone_ids and email_ids and phone_ids != email_ids)
        weak = []
        if data.get("name") and data.get("school") and data.get("graduation_year"):
            weak = [candidate for candidate in candidates if candidate.name == data["name"] and candidate.school == data["school"] and candidate.graduation_year == data["graduation_year"] and candidate.id not in strong_ids]
        by_id = {candidate.id: candidate for candidate in candidates}
        return {
            "strong_candidate_id": next(iter(strong_ids)) if len(strong_ids) == 1 and not conflict else None,
            "identity_conflict": conflict or len(strong_ids) > 1,
            "strong_candidates": [self._candidate_option(by_id[x]) for x in strong_ids],
            "weak_candidates": [self._candidate_option(candidate) for candidate in weak],
        }

    @staticmethod
    def _candidate_option(candidate: Candidate) -> dict:
        return {"id": candidate.id, "name": candidate.name, "phone": candidate.phone, "email": candidate.email, "school": candidate.school, "graduation_year": candidate.graduation_year, "current_city": candidate.current_city, "applications": [{"id": app.id, "job_title": app.job.title} for app in candidate.applications]}

    def _resolve_candidate(self, data, match: dict) -> Candidate | None:
        allowed_ids = {item["id"] for item in match.get("strong_candidates", []) + match.get("weak_candidates", [])}
        if data.candidate_id is not None:
            if data.candidate_id not in allowed_ids:
                raise HTTPException(422, detail="只能选择本次识别出的重复候选人。")
            candidate = self.db.get(Candidate, data.candidate_id)
            if not candidate:
                raise HTTPException(422, detail="所选候选人不存在。")
            return candidate
        if match.get("identity_conflict") and not data.create_new:
            raise HTTPException(422, detail="身份信息冲突，请选择已有候选人或新建候选人。")
        if match.get("strong_candidate_id") and not data.create_new:
            return self.db.get(Candidate, match["strong_candidate_id"])
        return None

    def _existing_application(self, job_id: int, candidate_id: int | None) -> Application | None:
        return self.db.scalar(select(Application).where(Application.job_id == job_id, Application.candidate_id == candidate_id)) if candidate_id else None

    @staticmethod
    def _candidate_values(data) -> dict:
        return {key: getattr(data, key) for key in ("name", "phone", "email", "school", "major", "highest_degree", "graduation_year", "current_city")}

    @staticmethod
    def _first_page_lines(page) -> list[dict]:
        page_height = float(page.rect.height)
        lines = []
        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                text = "".join(span.get("text", "") for span in spans).strip()
                if text:
                    lines.append({"text": text, "size": max((span.get("size", 0) for span in spans), default=0), "y": line.get("bbox", [0, 0])[1], "page_height": page_height})
        return lines

    def _preview_view(self, resume: Resume) -> dict:
        data = resume.parsed_data or {}
        return {"resume_id": resume.id, "filename": resume.original_filename, "status": resume.parse_status, "candidate": data.get("candidate", {}), "confidence": data.get("confidence", {}), "warnings": data.get("warnings", []), "match": data.get("match", {})}
