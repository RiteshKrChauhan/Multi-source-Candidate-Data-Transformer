from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from models.source import SourceRecord, SourceType
from parsers.base import BaseParser, ParserError


class CsvParser(BaseParser):
    def parse(self, path: str | Path) -> list[SourceRecord]:
        source_path = Path(path)
        try:
            frame = pd.read_csv(source_path, dtype=str, keep_default_na=False)
        except (OSError, UnicodeError, pd.errors.ParserError) as exc:
            raise ParserError(f"Could not parse CSV {source_path}: {exc}") from exc
        records: list[SourceRecord] = []
        for index, row in frame.iterrows():
            fields: dict[str, Any] = {
                str(key).strip(): value.strip() if isinstance(value, str) else value
                for key, value in row.to_dict().items()
                if value is not None and str(value).strip()
            }
            records.append(SourceRecord(
                source=SourceType.CSV,
                source_id=f"{source_path.name}:{index + 2}",
                fields=fields,
                extraction_methods={key: "structured_column" for key in fields},
            ))
        return records

