# test_models.py
"""Models are frozen."""

from __future__ import annotations

import dataclasses

import pytest

from surf.models import ExtractedSection, HeadingLevel


def test_extracted_section_frozen() -> None:
    section = ExtractedSection(level=HeadingLevel(2), lines=("# A",))
    with pytest.raises(dataclasses.FrozenInstanceError):
        section.level = HeadingLevel(1)  # type: ignore[misc]
