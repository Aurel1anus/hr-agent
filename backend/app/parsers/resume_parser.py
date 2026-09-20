from __future__ import annotations
import re
from typing import Any


class ResumeParser:
    version = "2.0"
    phone_pattern = re.compile(
        r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d[- ]?\d{4}[- ]?\d{4}(?!\d)"
    )
    email_pattern = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    education_heading = re.compile(
        r"教育经历|教育背景|教育信息|Education(?: Background| Experience)?", re.I
    )
    section_heading = re.compile(
        r"工作经历|实习经历|项目经历|校园经历|技能|专业技能|证书|自我评价|求职意向|Work Experience|Projects?|Skills?|Certificates?",
        re.I,
    )
    degree_rank = {
        "博士": 4,
        "phd": 4,
        "doctor": 4,
        "硕士": 3,
        "master": 3,
        "研究生": 3,
        "mba": 3,
        "本科": 2,
        "学士": 2,
        "bachelor": 2,
        "大专": 1,
        "专科": 1,
        "associate": 1,
        "高中": 0,
    }
    degree_label = {
        "博士": "博士",
        "phd": "博士",
        "doctor": "博士",
        "硕士": "硕士",
        "master": "硕士",
        "研究生": "硕士",
        "mba": "硕士",
        "本科": "本科",
        "学士": "本科",
        "bachelor": "本科",
        "大专": "大专",
        "专科": "大专",
        "associate": "大专",
        "高中": "高中",
    }
    date_range = re.compile(
        r"(20\d{2})\s*(?:[./年-]\s*\d{1,2}\s*月?)?\s*(?:-|—|–|至|to)\s*(20\d{2})\s*(?:[./年]\s*\d{1,2}\s*月?)?",
        re.I,
    )
    school_pattern = re.compile(
        r"([\u4e00-\u9fffA-Za-z·（）() ]+?(?:大学|学院|University|College))", re.I
    )
    filename_candidate = re.compile(
        r"(?:】|\])\s*(?P<name>[\u4e00-\u9fff]{2,4}|[A-Za-z][A-Za-z.' -]{1,40}?)\s+(?P<year>\d{2}|20\d{2})年(?:应届生|应届|毕业)",
        re.I,
    )

    def parse(
        self,
        text: str,
        first_page_lines: list[dict[str, Any]] | None = None,
        filename: str | None = None,
    ) -> dict:
        lines = [self._clean(line) for line in text.splitlines()]
        lines = [line for line in lines if line]
        phone = self._first(self.phone_pattern, text)
        email = self._first(self.email_pattern, text)
        education = self._highest_education(lines)
        school = education["school"]
        name, name_confidence = self._name_from_first_page(
            first_page_lines or [], phone, email
        )
        graduation_year, graduation_confidence = (
            education["graduation_year"],
            education["confidence"],
        )
        filename_values = self._filename_values(filename)
        if filename_values["name"]:
            name, name_confidence = filename_values["name"], 1.0
        if filename_values["graduation_year"]:
            graduation_year, graduation_confidence = (
                filename_values["graduation_year"],
                1.0,
            )
        major = education["major"]
        city = self._city(lines)
        candidate = {
            "name": name,
            "phone": phone,
            "email": email,
            "school": school,
            "major": major,
            "highest_degree": education["degree"],
            "graduation_year": graduation_year,
            "current_city": city,
        }
        confidence = {
            "name": name_confidence,
            "phone": 1.0 if phone else 0,
            "email": 1.0 if email else 0,
            "school": 0.9 if school else 0,
            "major": 0.8 if major else 0,
            "highest_degree": education["confidence"],
            "graduation_year": graduation_confidence,
            "current_city": 0.4 if city else 0,
        }
        warnings = [
            f"未识别{label}" if not candidate[key] else f"{label}识别结果建议人工确认"
            for key, label in (
                ("name", "姓名"),
                ("major", "专业"),
                ("highest_degree", "最高学历"),
                ("current_city", "当前城市"),
            )
        ]
        if graduation_year is None:
            warnings.append("未能从教育经历中确认毕业年份")
        return {"candidate": candidate, "confidence": confidence, "warnings": warnings}

    @staticmethod
    def _clean(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip(" -|：:")

    @staticmethod
    def _first(pattern: re.Pattern[str], text: str) -> str | None:
        match = pattern.search(text)
        return match.group(0) if match else None

    def _name_from_first_page(
        self, lines: list[dict[str, Any]], phone: str | None, email: str | None
    ) -> tuple[str | None, float]:
        if not lines:
            return None, 0
        max_size = max((float(line.get("size", 0)) for line in lines), default=0)
        page_height = max(
            (float(line.get("page_height", 0)) for line in lines), default=0
        )
        banned = re.compile(
            r"简历|求职|教育|经历|联系方式|电话|手机|邮箱|意向|个人信息|resume|curriculum|vitae",
            re.I,
        )
        candidates = []
        for line in lines:
            value = self._clean(str(line.get("text", "")))
            if (
                not value
                or len(value) > 30
                or banned.search(value)
                or re.search(r"\d", value)
            ):
                continue
            if (phone and phone in value) or (email and email in value):
                continue
            chinese = bool(re.fullmatch(r"[\u4e00-\u9fff]{2,4}", value))
            english = bool(
                re.fullmatch(
                    r"[A-Za-z][A-Za-z.'-]*(?:\s+[A-Za-z][A-Za-z.'-]*){1,3}", value
                )
            )
            if not (chinese or english):
                continue
            score = 2.0 if chinese else 1.5
            y, size = float(line.get("y", 0)), float(line.get("size", 0))
            if page_height and y <= page_height * 0.35:
                score += 2
            if max_size and size >= max_size * 0.85:
                score += 2
            elif max_size and size >= max_size * 0.65:
                score += 1
            candidates.append((score, value))
        if not candidates:
            return None, 0
        score, value = max(candidates, key=lambda item: item[0])
        return (value, min(round(score / 6, 2), 0.95)) if score >= 4 else (None, 0)

    def _graduation_year_from_education(
        self, lines: list[str]
    ) -> tuple[int | None, float]:
        start = next(
            (i for i, line in enumerate(lines) if self.education_heading.search(line)),
            None,
        )
        if start is None:
            return None, 0
        end = next(
            (
                i
                for i in range(start + 1, len(lines))
                if self.section_heading.search(lines[i])
            ),
            len(lines),
        )
        education = lines[start + 1 : end]
        entries = []
        for i, line in enumerate(education):
            lowered = line.lower()
            rank = max(
                (
                    value
                    for degree, value in self.degree_rank.items()
                    if degree in lowered
                ),
                default=-1,
            )
            if rank < 0:
                continue
            ranges = self.date_range.findall(
                " ".join(education[max(0, i - 2) : min(len(education), i + 3)])
            )
            if ranges:
                entries.append((rank, int(ranges[-1][1])))
        if not entries:
            return None, 0
        highest = max(rank for rank, _ in entries)
        return max(year for rank, year in entries if rank == highest), 0.9

    def _highest_education(self, lines: list[str]) -> dict:
        empty = {
            "degree": None,
            "school": None,
            "major": None,
            "graduation_year": None,
            "confidence": 0,
        }
        start = next(
            (i for i, line in enumerate(lines) if self.education_heading.search(line)),
            None,
        )
        if start is None:
            return empty
        end = next(
            (
                i
                for i in range(start + 1, len(lines))
                if self.section_heading.search(lines[i])
            ),
            len(lines),
        )
        education = lines[start + 1 : end]
        entries = []
        for i, line in enumerate(education):
            lowered = line.lower()
            matches = [
                (rank, self.degree_label[degree])
                for degree, rank in self.degree_rank.items()
                if degree in lowered
            ]
            if not matches:
                continue
            rank, degree = max(matches, key=lambda item: item[0])
            context = " ".join(education[max(0, i - 2) : min(len(education), i + 3)])
            ranges = self.date_range.findall(context)
            year = int(ranges[-1][1]) if ranges else None
            school_match = self.school_pattern.search(context)
            school = school_match.group(1).strip() if school_match else None
            major = self._major_from_education_line(line, school)
            entries.append(
                {
                    "rank": rank,
                    "degree": degree,
                    "school": school,
                    "major": major,
                    "graduation_year": year,
                }
            )
        if not entries:
            return empty
        highest = max(entry["rank"] for entry in entries)
        choices = [entry for entry in entries if entry["rank"] == highest]
        chosen = max(choices, key=lambda entry: entry["graduation_year"] or 0)
        return {**chosen, "confidence": 0.9}

    def _major_from_education_line(self, line: str, school: str | None) -> str | None:
        explicit = re.search(
            r"(?:专业|Major)\s*[:：]?\s*([^,，;；\d]{2,50})", line, re.I
        )
        if explicit:
            return self._clean(explicit.group(1))
        value = line
        if school:
            value = value.replace(school, " ")
        value = self.date_range.sub(" ", value)
        for token in self.degree_rank:
            value = re.sub(re.escape(token), " ", value, flags=re.I)
        value = re.sub(r"20\d{2}|\d{1,2}[./年\-月]", " ", value)
        value = self._clean(value)
        return (
            value[:50]
            if 2 <= len(value) <= 50
            and not re.search(r"大学|学院|研究生|本科|硕士|博士", value)
            else None
        )

    def _filename_values(self, filename: str | None) -> dict:
        if not filename:
            return {"name": None, "graduation_year": None}
        stem = re.sub(r"\.[^.]+$", "", filename).strip()
        match = self.filename_candidate.search(stem)
        if not match:
            return {"name": None, "graduation_year": None}
        year = match.group("year")
        return {
            "name": match.group("name").strip(),
            "graduation_year": int(year) if len(year) == 4 else 2000 + int(year),
        }

    @staticmethod
    def _major(lines: list[str], school: str | None) -> str | None:
        for line in lines:
            if re.search(r"专业|Major|本科|硕士|学士|Bachelor|Master", line, re.I):
                value = re.sub(r"^(专业|Major)\s*[:：]?\s*", "", line, flags=re.I)
                if value != school:
                    return value[:120]
        return None

    @staticmethod
    def _city(lines: list[str]) -> str | None:
        for line in lines[:12]:
            match = re.search(
                r"(?:现居|所在地|城市|Location)\s*[:：]?\s*([\u4e00-\u9fff]{2,8})",
                line,
                re.I,
            )
            if match:
                return match.group(1)
        return None
