import json

from cli.app import main


def test_cli_writes_atomic_json(tmp_path) -> None:
    source = tmp_path / "candidates.csv"
    source.write_text("name,email\nAda Lovelace,ada@example.com\n", encoding="utf-8")
    output = tmp_path / "nested" / "output.json"

    exit_code = main(["--csv", str(source), "--output", str(output), "--log-level", "ERROR"])

    assert exit_code == 0
    assert json.loads(output.read_text(encoding="utf-8"))[0]["emails"] == ["ada@example.com"]
    assert not list(output.parent.glob("*.tmp"))


def test_cli_requires_an_input(tmp_path) -> None:
    assert main(["--output", str(tmp_path / "output.json")]) == 2
