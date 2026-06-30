from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path

from confidence import ConfidenceScorer
from config import ProjectionConfig
from mapper import CanonicalMapper
from merge import CandidateMatcher, CandidateMerger
from models import CandidateProfile, SourceRecord
from normalizer import DataNormalizer
from parsers import AtsJsonParser, CsvParser, ResumeParser
from parsers.base import BaseParser, ParserError
from projection import Projector
from validator import OutputValidator


LOGGER = logging.getLogger(__name__)


class PipelineError(RuntimeError):
    pass


class CandidatePipeline:
    """Orchestrates decoupled parser, business, projection, and validation stages."""

    def __init__(
        self,
        default_phone_region: str = "US",
        name_similarity_threshold: float = 90.0,
    ) -> None:
        normalizer = DataNormalizer(default_phone_region)
        self.mapper = CanonicalMapper(normalizer)
        self.matcher = CandidateMatcher(name_similarity_threshold)
        self.merger = CandidateMerger()
        self.scorer = ConfidenceScorer()
        self.projector = Projector(normalizer)
        self.validator = OutputValidator()

    def run(
        self,
        *,
        csv_paths: Iterable[str | Path] = (),
        resume_paths: Iterable[str | Path] = (),
        ats_paths: Iterable[str | Path] = (),
        config: ProjectionConfig | None = None,
    ) -> list[dict[str, object]]:
        projection = config or ProjectionConfig()
        records: list[SourceRecord] = []
        records.extend(self._load(CsvParser(), csv_paths))
        records.extend(self._load(ResumeParser(), resume_paths))
        records.extend(self._load(AtsJsonParser(), ats_paths))
        if not records:
            raise PipelineError("No candidate records could be loaded from the supplied inputs")

        mapped: list[CandidateProfile] = []
        for record in records:
            try:
                mapped.append(self.mapper.map(record))
            except Exception as exc:  # isolate one malformed candidate from the rest of a batch
                LOGGER.warning("Skipping invalid %s record %s: %s", record.source, record.source_id, exc)
        if not mapped:
            raise PipelineError("All loaded candidate records failed canonical mapping")

        groups = self.matcher.group(mapped)
        profiles = [self.scorer.score(self.merger.merge(group)) for group in groups]
        profiles.sort(key=lambda profile: profile.candidate_id)

        canonical = [profile.model_dump(mode="json") for profile in profiles]
        self.validator.validate_canonical(canonical)
        output = [self.projector.project(profile, projection) for profile in profiles]
        self.validator.validate_projected(output, projection)
        LOGGER.info(
            "Processed %d source records into %d canonical candidates", len(records), len(output)
        )
        return output

    @staticmethod
    def _load(parser: BaseParser, paths: Iterable[str | Path]) -> list[SourceRecord]:
        result: list[SourceRecord] = []
        for path in paths:
            try:
                parsed = parser.parse(path)
                result.extend(parsed)
                LOGGER.info("Loaded %d records from %s", len(parsed), path)
            except ParserError as exc:
                LOGGER.warning("Skipping input: %s", exc)
        return result

