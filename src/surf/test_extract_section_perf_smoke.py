# test_extract_section_perf_smoke.py
"""Smoke: extract_section stays sub-millisecond on a small fixture."""

from __future__ import annotations

import time

from surf.logic import (
    extract_section,
    parse_heading_path,
    parse_headings,
    parse_tex_headings,
)
from surf.models import HeadingPathRemainder

FIXTURE = """# Title

## Alpha

alpha body line

## Beta

beta body line
"""


def test_extract_section_returns_section_and_is_sub_millisecond() -> None:
    lines = FIXTURE.splitlines()
    heading = parse_heading_path(HeadingPathRemainder("Alpha"))
    assert heading is not None
    t0 = time.perf_counter_ns()
    result = extract_section(lines, heading)
    dt_ns = time.perf_counter_ns() - t0
    assert result is not None
    assert int(result.level) == 2
    text = "\n".join(result.lines)
    assert "alpha body line" in text
    assert "Beta" not in text
    assert dt_ns < 1_000_000, f"extract_section took {dt_ns} ns"


def test_parse_headings_finds_both() -> None:
    titles = [str(record.text) for record in parse_headings(FIXTURE.splitlines())]
    assert "Alpha" in titles and "Beta" in titles


TEX_FIXTURE = r"""\section{Title}

\subsection{Alpha}

alpha body line

\subsection{Beta}

beta body line
"""


def test_tex_extract_section_is_sub_millisecond() -> None:
    lines = TEX_FIXTURE.splitlines()
    heading = parse_heading_path(HeadingPathRemainder("Alpha"))
    assert heading is not None
    t0 = time.perf_counter_ns()
    headings = parse_tex_headings(lines)
    result = extract_section(lines, heading, headings=headings)
    dt_ns = time.perf_counter_ns() - t0
    assert result is not None
    assert int(result.level) == 4
    text = "\n".join(result.lines)
    assert "alpha body line" in text
    assert "Beta" not in text
    assert dt_ns < 1_000_000, f"tex extract_section took {dt_ns} ns"
