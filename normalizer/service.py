from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from urllib.parse import urlparse, urlunparse

import phonenumbers
import pycountry
from dateutil import parser as date_parser
from pydantic import TypeAdapter, ValidationError


EMAIL_ADAPTER = TypeAdapter(str)
EMAIL_RE = re.compile(r"^[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?(?:\.[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?)+$", re.I)


class DataNormalizer:
    COUNTRY_ALIASES = {
        "uk": "GB", "u.k.": "GB", "great britain": "GB",
        "us": "US", "u.s.": "US", "u.s.a.": "US", "united states of america": "US",
    }
    SKILL_ALIASES = {
        "cpp": "C++", "c plus plus": "C++", "c++": "C++",
        "reactjs": "React", "react.js": "React", "react": "React",
        "nodejs": "Node.js", "node.js": "Node.js",
        "js": "JavaScript", "javascript": "JavaScript",
        "ts": "TypeScript", "typescript": "TypeScript",
        "py": "Python", "python": "Python",
        "postgres": "PostgreSQL", "postgresql": "PostgreSQL",
        "aws": "AWS", "amazon web services": "AWS",
        "ml": "Machine Learning", "machine learning": "Machine Learning",
    }

    def __init__(self, default_phone_region: str = "US") -> None:
        self.default_phone_region = default_phone_region.upper()

    def email(self, value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        email = value.strip().lower()
        try:
            EMAIL_ADAPTER.validate_python(email)
        except ValidationError:
            return None
        return email if EMAIL_RE.fullmatch(email) else None

    def phone(self, value: Any) -> str | None:
        if value is None:
            return None
        raw = str(value).strip()
        if not raw:
            return None
        try:
            parsed = phonenumbers.parse(raw, None if raw.startswith("+") else self.default_phone_region)
        except phonenumbers.NumberParseException:
            return None
        if not phonenumbers.is_valid_number(parsed):
            return None
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)

    def date(self, value: Any) -> str | None:
        if value is None or str(value).strip().lower() in {"", "present", "current", "now"}:
            return None
        if isinstance(value, datetime):
            parsed = value
        else:
            try:
                parsed = date_parser.parse(str(value), default=datetime(1900, 1, 1), fuzzy=False)
            except (ValueError, TypeError, OverflowError):
                return None
        return parsed.strftime("%Y-%m")

    def country(self, value: Any) -> str | None:
        if not isinstance(value, str) or not value.strip():
            return None
        raw = value.strip()
        if raw.casefold() in self.COUNTRY_ALIASES:
            return self.COUNTRY_ALIASES[raw.casefold()]
        if len(raw) == 2:
            result = pycountry.countries.get(alpha_2=raw.upper())
        elif len(raw) == 3:
            result = pycountry.countries.get(alpha_3=raw.upper())
        else:
            result = pycountry.countries.get(name=raw)
            if result is None:
                try:
                    result = pycountry.countries.search_fuzzy(raw)[0]
                except LookupError:
                    return None
        return result.alpha_2 if result else None

    def skill(self, value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        cleaned = re.sub(r"\s+", " ", value.strip())
        if not cleaned:
            return None
        key = cleaned.casefold()
        return self.SKILL_ALIASES.get(key, cleaned if any(c.isupper() for c in cleaned) else cleaned.title())

    def url(self, value: Any) -> str | None:
        if not isinstance(value, str) or not value.strip():
            return None
        raw = value.strip()
        if not re.match(r"^https?://", raw, re.I):
            raw = "https://" + raw
        parsed = urlparse(raw)
        if not parsed.netloc or "." not in parsed.netloc:
            return None
        return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), "", "", ""))

    @staticmethod
    def name(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        cleaned = re.sub(r"\s+", " ", value).strip(" ,\t\r\n")
        return cleaned or None

    def unique_normalized(self, values: list[Any], normalizer: Any) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = normalizer(value)
            if normalized is not None and normalized.casefold() not in seen:
                seen.add(normalized.casefold())
                result.append(normalized)
        return result
