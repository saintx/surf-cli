"""Smoke: real extract_section path is fast in-process on a small fixture.

Not a host SLO — asserts the shipped function returns content and completes
well under CLI-process timescales (millisecond scale).
"""
from __future__ import annotations

import time
from pathlib import Path

import surf


FIXTURE = """# Title

## Alpha

alpha body line

## Beta

beta body line
"""


def test_extract_section_returns_section_and_is_sub_millisecond():
    lines = FIXTURE.splitlines(keepends=True)
    t0 = time.perf_counter_ns()
    result = surf.extract_section(lines, "Alpha")
    dt_ns = time.perf_counter_ns() - t0
    assert result is not None
    level, section = result
    assert level == 2
    text = "".join(section)
    assert "alpha body line" in text
    assert "Beta" not in text  # stopped at next same-level heading
    # Generous bound: pure extract should be far below 1 ms on any modern host
    assert dt_ns < 1_000_000, f"extract_section took {dt_ns} ns"


def test_parse_headings_finds_both():
    lines = FIXTURE.splitlines(keepends=True)
    heads = surf.parse_headings(lines)
    titles = [t for _, _, t in heads]
    assert "Alpha" in titles and "Beta" in titles
