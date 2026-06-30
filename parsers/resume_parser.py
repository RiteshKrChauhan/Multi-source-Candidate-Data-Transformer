from __future__ import annotations

import re
from pathlib import Path

from models.source import SourceRecord, SourceType
from parsers.base import BaseParser, ParserError


EMAIL_RE = re.compile(r"[\w.!#$%&'*+/=?^`{|}~-]+@[\w-]+(?:\.[\w-]+)+", re.I)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d().\-\s]{7,}\d)")
URL_RE = re.compile(r"(?:https?://)?(?:www\.)?(?:linkedin\.com/in|github\.com)/[\w.%-]+/?", re.I)


class ResumeParser(BaseParser):
    SECTION_NAMES = {"skills", "technical skills", "experience", "work experience", "education", "summary", "profile"}

    def parse(self, path: str | Path) -> list[SourceRecord]:
        source_path = Path(path)
        try:
            text = self._read(source_path)
        except Exception as exc:
            raise ParserError(f"Could not parse resume {source_path}: {exc}") from exc
        fields, methods = self._extract(text)
        return [SourceRecord(
            source=SourceType.RESUME,
            source_id=source_path.name,
            fields=fields,
            extraction_methods=methods,
        )]

    @staticmethod
    def _read(path: Path) -> str:
        if path.suffix.lower() == ".txt":
            return path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(path)
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        raise ValueError("resume must be a .txt or .pdf file")

    def _extract(self, text: str) -> tuple[dict[str, object], dict[str, str]]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            raise ValueError("resume contains no extractable text")
        fields: dict[str, object] = {}
        methods: dict[str, str] = {}

        header = lines[:8]
        name = next((line for line in header if self._looks_like_name(line)), None)
        if name:
            fields["full_name"] = name
            methods["full_name"] = "header_heuristic"
        emails = EMAIL_RE.findall(text)
        phones = PHONE_RE.findall(text)
        urls = URL_RE.findall(text)
        if emails:
            fields["emails"] = emails
            methods["emails"] = "regex"
        if phones:
            fields["phones"] = phones
            methods["phones"] = "regex"
        for url in urls:
            key = "linkedin" if "linkedin.com" in url.lower() else "github"
            fields[key] = url
            methods[key] = "regex"

        sections = self._sections(lines)
        skill_lines = sections.get("skills", []) + sections.get("technical skills", [])
        if skill_lines:
            skills = [item.strip() for line in skill_lines for item in re.split(r"[,|;•]", line) if item.strip()]
            fields["skills"] = skills
            methods["skills"] = "section_heuristic"
        summary = sections.get("summary", sections.get("profile", []))
        if summary:
            fields["headline"] = " ".join(summary[:2])
            methods["headline"] = "section_heuristic"
        experience_lines = sections.get("experience", []) + sections.get("work experience", [])
        experience = [item for line in experience_lines if (item := self._experience_line(line))]
        if experience:
            fields["experience"] = experience
            methods["experience"] = "section_heuristic"
        education = [item for line in sections.get("education", []) if (item := self._education_line(line))]
        if education:
            fields["education"] = education
            methods["education"] = "section_heuristic"
        return fields, methods

    @classmethod
    def _sections(cls, lines: list[str]) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        current: str | None = None
        for line in lines:
            normalized = line.rstrip(":").strip().casefold()
            if normalized in cls.SECTION_NAMES:
                current = normalized
                result.setdefault(current, [])
            elif current:
                result[current].append(line)
        return result

    @staticmethod
    def _looks_like_name(line: str) -> bool:
        if any(token in line for token in ("@", "http", "+", "|")) or any(char.isdigit() for char in line):
            return False
        words = line.split()
        return 2 <= len(words) <= 5 and len(line) <= 80

    @staticmethod
    def _experience_line(line: str) -> dict[str, str] | None:
        parts = [part.strip() for part in re.split(r"\s+(?:—|–|-|\|)\s+", line) if part.strip()]
        if len(parts) < 2:
            return None
        result = {"company": parts[0], "title": parts[1]}
        dates = re.search(
            r"(?P<start>(?:[A-Za-z]{3,9}\s+)?\d{4})\s*(?:-|—|–|to)\s*"
            r"(?P<end>present|current|(?:[A-Za-z]{3,9}\s+)?\d{4})",
            " ".join(parts[2:]), re.I,
        )
        if dates:
            result["start_date"] = dates.group("start")
            result["end_date"] = dates.group("end")
        return result

    @staticmethod
    def _education_line(line: str) -> dict[str, str] | None:
        parts = [part.strip() for part in re.split(r"\s+(?:—|–|-|\|)\s+", line) if part.strip()]
        if not parts or len(parts[0]) < 2:
            return None
        result = {"institution": parts[0]}
        if len(parts) > 1:
            degree = re.match(
                r"^(?P<degree>(?:B|M)(?:Sc|A|S|E|Tech)|PhD|MBA|"
                r"Bachelor(?:'s)?(?: of [A-Za-z]+)?|Master(?:'s)?(?: of [A-Za-z]+)?)"
                r"(?:\s+(?:in\s+)?(?P<field>.*?))?(?:\s+—\s+\d{4})?$",
                parts[1], re.I,
            )
            if degree:
                result["degree"] = degree.group("degree")
                if degree.group("field"):
                    result["field_of_study"] = degree.group("field")
            else:
                result["degree"] = parts[1]
        year = re.search(r"\b(?:19|20)\d{2}\b", " ".join(parts[1:]))
        if year:
            result["end_date"] = year.group()
        return result
