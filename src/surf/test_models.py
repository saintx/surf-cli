# test_models.py
"""Models are frozen."""

from __future__ import annotations

import dataclasses

import pytest

from surf.models import (
    ExtractedOutline,
    ExtractedSection,
    HeadingLevel,
    HeadingLineCount,
    OutlineLevel,
)


def test_extracted_section_frozen() -> None:
    section = ExtractedSection(
        level=HeadingLevel(2), lines=("# A",), heading_line_count=HeadingLineCount(1)
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        section.level = HeadingLevel(1)  # type: ignore[misc]


def test_extracted_outline_frozen() -> None:
    extracted = ExtractedOutline(level=OutlineLevel(1), pages=("page",))
    with pytest.raises(dataclasses.FrozenInstanceError):
        extracted.level = OutlineLevel(2)  # type: ignore[misc]
