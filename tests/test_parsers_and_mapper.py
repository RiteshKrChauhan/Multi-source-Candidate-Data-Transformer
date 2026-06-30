import json

from mapper import CanonicalMapper
from parsers import AtsJsonParser, CsvParser, ResumeParser


def test_csv_parser_and_mapper(tmp_path) -> None:
    path = tmp_path / "people.csv"
    path.write_text(
        "name,email,phone,country,skills\nAda Lovelace,ADA@example.com,(415) 555-2671,USA,CPP;ReactJS\n",
        encoding="utf-8",
    )
    record = CsvParser().parse(path)[0]
    profile = CanonicalMapper().map(record)

    assert profile.full_name == "Ada Lovelace"
    assert profile.emails == ["ada@example.com"]
    assert profile.phones == ["+14155552671"]
    assert profile.skills == ["C++", "React"]
    assert profile.location and profile.location.country == "US"
    assert profile.provenance["emails"][0].extraction_method == "structured_column"


def test_ats_parser_maps_nested_fields(tmp_path) -> None:
    path = tmp_path / "ats.json"
    path.write_text(json.dumps({"candidates": [{
        "id": 42, "name": "Ada Lovelace", "contact": {"email": "ada@example.com"},
        "experience": [{"company": "Engine Co", "start": "2020-04", "end": "2023-09"}],
    }]}), encoding="utf-8")
    profile = CanonicalMapper().map(AtsJsonParser().parse(path)[0])

    assert profile.emails == ["ada@example.com"]
    assert profile.experience[0].start_date == "2020-04"


def test_resume_parser_extracts_unstructured_text(tmp_path) -> None:
    path = tmp_path / "resume.txt"
    path.write_text(
        "Ada Byron Lovelace\nada@example.com | +1 415 555 2671\n"
        "SKILLS\nPython, CPP, ReactJS\n"
        "EXPERIENCE\nEngine Co — Senior Engineer — 2020 to Present\n"
        "EDUCATION\nUniversity of London — BSc Mathematics — 2019\n",
        encoding="utf-8",
    )
    profile = CanonicalMapper().map(ResumeParser().parse(path)[0])

    assert profile.full_name == "Ada Byron Lovelace"
    assert profile.emails == ["ada@example.com"]
    assert profile.skills == ["Python", "C++", "React"]
    assert profile.experience[0].company == "Engine Co"
    assert profile.experience[0].start_date == "2020-01"
    assert profile.education[0].institution == "University of London"
    assert profile.education[0].degree == "BSc"
    assert profile.education[0].field_of_study == "Mathematics"
