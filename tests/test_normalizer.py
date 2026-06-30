from normalizer import DataNormalizer


def test_normalizes_required_types() -> None:
    normalizer = DataNormalizer("US")

    assert normalizer.email(" ADA@Example.COM ") == "ada@example.com"
    assert normalizer.email("not-an-email") is None
    assert normalizer.phone("(415) 555-2671") == "+14155552671"
    assert normalizer.date("February 2024") == "2024-02"
    assert normalizer.date("present") is None
    assert normalizer.country("United States") == "US"
    assert normalizer.country("IND") == "IN"
    assert normalizer.country("UK") == "GB"
    assert normalizer.skill("CPP") == "C++"
    assert normalizer.skill("ReactJS") == "React"


def test_deduplicates_after_normalization() -> None:
    normalizer = DataNormalizer()
    assert normalizer.unique_normalized(
        ["CPP", "c++", "ReactJS", "react"], normalizer.skill
    ) == ["C++", "React"]
