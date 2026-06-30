from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from models.source import SourceRecord, SourceType
from parsers.base import BaseParser, ParserError


class AtsJsonParser(BaseParser):
    def parse(self, path: str | Path) -> list[SourceRecord]:
        source_path = Path(path)
        try:
            with source_path.open(encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ParserError(f"Could not parse ATS JSON {source_path}: {exc}") from exc

        if isinstance(payload, dict):
            candidates = payload.get("candidates", payload.get("results", payload))
            candidates = [candidates] if isinstance(candidates, dict) else candidates
        else:
            candidates = payload
        if not isinstance(candidates, list) or not all(isinstance(item, dict) for item in candidates):
            raise ParserError(f"ATS JSON {source_path} must contain an object or a list of objects")

        records: list[SourceRecord] = []
        for index, item in enumerate(candidates):
            source_id = str(item.get("id") or item.get("candidate_id") or f"{source_path.name}:{index + 1}")
            records.append(SourceRecord(
                source=SourceType.ATS,
                source_id=source_id,
                fields=item,
                extraction_methods={key: "structured_json" for key in item},
            ))
        return records

