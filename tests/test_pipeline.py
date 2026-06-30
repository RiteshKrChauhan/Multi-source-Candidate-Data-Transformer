import json

import pytest

from config import ProjectionConfig
from pipeline import CandidatePipeline, PipelineError


def test_end_to_end_merges_sources_and_is_deterministic(tmp_path) -> None:
    csv_path = tmp_path / "input.csv"
    csv_path.write_text(
        "name,email,skills\nAda Lovelace,ADA@example.com,CPP\nGrace Hopper,grace@example.com,Python\n",
        encoding="utf-8",
    )
    ats_path = tmp_path / "ats.json"
    ats_path.write_text(json.dumps({"candidates": [{
        "name": "Ada Byron Lovelace", "email": "ada@example.com", "skills": ["ReactJS"]
    }]}), encoding="utf-8")
    config = ProjectionConfig(include_provenance=False, include_confidence=False)
    pipeline = CandidatePipeline()

    first = pipeline.run(csv_paths=[csv_path], ats_paths=[ats_path], config=config)
    second = pipeline.run(csv_paths=[csv_path], ats_paths=[ats_path], config=config)

    assert first == second
    assert len(first) == 2
    ada = next(item for item in first if item["full_name"] == "Ada Byron Lovelace")
    assert ada["skills"] == ["React", "C++"]


def test_bad_input_is_skipped_when_another_input_is_valid(tmp_path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    good = tmp_path / "good.csv"
    good.write_text("name,email\nAda Lovelace,ada@example.com\n", encoding="utf-8")

    output = CandidatePipeline().run(csv_paths=[good], ats_paths=[bad])
    assert len(output) == 1


def test_no_valid_inputs_fails_clearly(tmp_path) -> None:
    with pytest.raises(PipelineError, match="No candidate records"):
        CandidatePipeline().run(csv_paths=[tmp_path / "missing.csv"])

