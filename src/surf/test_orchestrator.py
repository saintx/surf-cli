# test_orchestrator.py
"""Orchestrator composition tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from surf import __version__
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

SAMPLE_TEX = r"""\section{What this corpus is}

corpus body

\subsection{A subsection}

sub body

\section{Sibling}

sibling body
"""

MD_WITH_TEX_COMMAND = r"""\section{Not a heading}

# Real
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


@pytest.fixture
def tex_file(tmp_path: Path) -> Path:
    path = tmp_path / "sample.tex"
    path.write_text(SAMPLE_TEX)
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
    assert captured.out.strip() == f"surf {__version__}"


def test_extract_details(sample_file: Path) -> None:
    output = rendered([str(sample_file), "Details"])
    assert "title: Test Document" not in output
    assert "## Details" in output
    assert "Detail content" in output


def test_no_heading_does_not_dump(sample_file: Path) -> None:
    output = rendered([str(sample_file)])
    assert "title: Test Document" in output
    assert "- Introduction" in output
    assert "Detail content" not in output
    assert "intro" not in output.splitlines()


def test_list_headings(sample_file: Path) -> None:
    output = rendered(["--list", str(sample_file)])
    assert "- Introduction" in output
    assert "  - Details" in output
    assert "title:" not in output


def test_frontmatter_only(sample_file: Path) -> None:
    output = rendered(["-f", str(sample_file)])
    assert "title: Test Document" in output
    assert "- Introduction" not in output
    assert "Detail content" not in output


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


def test_tex_list_headings(tex_file: Path) -> None:
    output = rendered(["--list", str(tex_file)])
    lines = output.splitlines()
    assert "    - What this corpus is" in lines
    assert "      - A subsection" in lines
    assert "    - Sibling" in lines
    assert "corpus body" not in output


def test_tex_extract_named_section(tex_file: Path) -> None:
    output = rendered([str(tex_file), "What this corpus is"])
    assert r"\section{What this corpus is}" in output
    assert "corpus body" in output
    assert r"\section{Sibling}" not in output
    assert "sibling body" not in output


def test_tex_missing_heading(tex_file: Path) -> None:
    result = run_argv([str(tex_file), "No such heading"])
    assert isinstance(result, CliFailure)
    assert result.exit_code == 1
    assert "not found" in result.message


def test_tex_no_heading_returns_index(tex_file: Path) -> None:
    output = rendered([str(tex_file)])
    assert output != ""
    assert "    - What this corpus is" in output.splitlines()
    assert "      - A subsection" in output.splitlines()
    assert "corpus body" not in output
    assert "sibling body" not in output


def test_md_suffix_keeps_atx_not_tex_commands(tmp_path: Path) -> None:
    path = tmp_path / "sample.md"
    path.write_text(MD_WITH_TEX_COMMAND)
    output = rendered(["--list", str(path)])
    assert "- Real" in output.splitlines()
    assert "Not a heading" not in output
