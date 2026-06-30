import pytest

from confidence import ConfidenceScorer
from config import MissingValuePolicy, ProjectionConfig
from mapper import CanonicalMapper
from merge import CandidateMerger
from models import SourceRecord, SourceType
from projection import ProjectionError, Projector
from validator import OutputValidator


def candidate():
    mapped = CanonicalMapper().map(SourceRecord(
        source=SourceType.ATS,
        source_id="1",
        fields={"name": "Ada Lovelace", "email": "ada@example.com"},
        extraction_methods={"name": "structured_json", "email": "structured_json"},
    ))
    return ConfidenceScorer().score(CandidateMerger().merge([mapped]))


def test_projection_selects_renames_and_disables_metadata() -> None:
    config = ProjectionConfig(
        fields=["candidate_id", "full_name", "emails"],
        rename={"candidate_id": "id", "full_name": "name"},
        include_confidence=False,
        include_provenance=False,
        missing_value_policy=MissingValuePolicy.OMIT,
    )
    result = Projector().project(candidate(), config)
    assert set(result) == {"id", "name", "emails"}
    OutputValidator().validate_projected([result], config)


def test_missing_value_policies() -> None:
    null_config = ProjectionConfig(
        fields=["full_name", "headline"], include_confidence=False,
        include_provenance=False, missing_value_policy="null",
    )
    assert Projector().project(candidate(), null_config)["headline"] is None

    error_config = null_config.model_copy(update={"missing_value_policy": MissingValuePolicy.ERROR})
    with pytest.raises(ProjectionError):
        Projector().project(candidate(), error_config)

