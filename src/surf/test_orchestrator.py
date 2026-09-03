# test_orchestrator.py
"""Orchestrator composition tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from surf import __version__, __version_tag__
from surf.models import CliFailure
from surf.orchestrator import build_parser, main, run_argv

SAMPLE = """---
title: Test Document
---
# Introduction

intro

## Details

Detail content here.
"""

NESTED = """## Foo

### Baz

Foo Baz body.

## Bar

### Baz

Bar Baz body.
"""


@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
    path = tmp_path / "sample.md"
    path.write_text(SAMPLE)
    return path


@pytest.fixture
def nested_file(tmp_path: Path) -> Path:
    path = tmp_path / "nested.md"
    path.write_text(NESTED)
    return path


def rendered(argv: list[str]) -> str:
    result = run_argv(argv)
    if isinstance(result, CliFailure):
        return f"Error: {result.message}"
    return result.body


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--version"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == __version_tag__
    assert __version_tag__ == f"surf-v{__version__}"


def test_extract_details(sample_file: Path) -> None:
    output = rendered([str(sample_file), "Details"])
    assert "title: Test Document" not in output
    assert "## Details" in output
    assert "Detail content" in output


def test_no_heading_does_not_dump(sample_file: Path) -> None:
    result = run_argv([str(sample_file)])
    assert isinstance(result, CliFailure)
    assert "no heading specified" in result.message
    assert "Introduction" not in result.message


def test_list_headings(sample_file: Path) -> None:
    output = rendered(["--list", str(sample_file)])
    assert "- Introduction" in output
    assert "  - Details" in output


def test_nested_path(nested_file: Path) -> None:
    output = rendered([f"[[{nested_file}#Foo#Baz]]"])
    assert "Foo Baz body" in output
    assert "Bar Baz body" not in output


def test_missing_file() -> None:
    output = rendered(["/nonexistent/file.md"])
    assert "Error" in output
    assert "not found" in output.lower()


def test_output_to_file(sample_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    outfile = tmp_path / "out.md"
    monkeypatch.setattr(
        "sys.argv",
        ["surf", "-o", str(outfile), "--list", str(sample_file)],
    )
    main()
    assert outfile.exists()
    assert "- Introduction" in outfile.read_text()


def test_parser_positional() -> None:
    args = build_parser().parse_args(["file.md", "My Heading"])
    assert args.target == "file.md"
    assert args.heading == "My Heading"
