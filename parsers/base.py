from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from models.source import SourceRecord


class ParserError(RuntimeError):
    pass


class BaseParser(ABC):
    @abstractmethod
    def parse(self, path: str | Path) -> list[SourceRecord]:
        """Parse one file without applying canonical business rules."""
        raise NotImplementedError

