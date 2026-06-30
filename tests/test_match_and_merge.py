from confidence import ConfidenceScorer
from mapper import CanonicalMapper
from merge import CandidateMatcher, CandidateMerger
from models import SourceRecord, SourceType


def profile(source: SourceType, source_id: str, **fields):
    return CanonicalMapper().map(SourceRecord(
        source=source,
        source_id=source_id,
        fields=fields,
        extraction_methods={key: "structured_json" for key in fields},
    ))


def test_match_priority_and_conflict_guard() -> None:
    matcher = CandidateMatcher(85)
    left = profile(SourceType.ATS, "1", name="Alex Smith", email="one@example.com", phone="+14155552671")
    same_phone = profile(SourceType.CSV, "2", name="A. Smith", email="other@example.com", phone="+14155552671")
    conflicting = profile(SourceType.CSV, "3", name="Alex Smith", email="different@example.com")

    assert matcher.is_match(left, same_phone)
    assert not matcher.is_match(left, conflicting)


def test_merger_applies_rules_and_scores_fields() -> None:
    resume = profile(
        SourceType.RESUME, "resume.txt", full_name="Ada Byron Lovelace",
        emails=["ADA@example.com"], skills=["CPP", "Python"], headline="Engineer",
    )
    ats = profile(
        SourceType.ATS, "ats-1", full_name="Ada Lovelace", email="ada@example.com",
        skills=["ReactJS", "Python"], years_experience=8,
    )
    merged = ConfidenceScorer().score(CandidateMerger().merge([ats, resume]))

    assert merged.full_name == "Ada Byron Lovelace"
    assert merged.emails == ["ada@example.com"]
    assert merged.skills == ["C++", "Python", "React"]
    assert merged.years_experience == 8
    assert merged.candidate_id.startswith("cand_")
    assert 0 < merged.confidence["skills"] <= 1
    assert 0 < merged.overall_confidence <= 1
    assert {item.source for item in merged.provenance["skills"]} == {SourceType.RESUME, SourceType.ATS}


def test_grouping_is_deterministic() -> None:
    profiles = [
        profile(SourceType.CSV, "2", name="Grace Hopper", email="grace@example.com"),
        profile(SourceType.ATS, "1", name="Rear Admiral Grace Hopper", email="GRACE@example.com"),
    ]
    groups = CandidateMatcher().group(profiles)
    first = CandidateMerger().merge(groups[0]).candidate_id
    second = CandidateMerger().merge(list(reversed(groups[0]))).candidate_id
    assert len(groups) == 1
    assert first == second

