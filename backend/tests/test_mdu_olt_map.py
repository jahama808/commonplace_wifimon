"""SAG name extraction is the only piece of mdu_olt_map worth unit-testing
without a Postgres — the upload + lookup paths run through SQLAlchemy and
are covered by the admin integration tests."""
from __future__ import annotations

import pytest

from app.services.mdu_olt_map import extract_mdu_name


@pytest.mark.parametrize(
    "sag,expected",
    [
        # Clean, common case
        ("MDU - 1506 PIIKOI", "1506 PIIKOI"),
        # Asterisks-as-decoration on either side
        ("*MDU - HERITAGE HOUSE*", "HERITAGE HOUSE"),
        ("*MDU - SEASIDE TOWERS*", "SEASIDE TOWERS"),
        # Prefix junk before the MDU - marker
        (
            "FTTPB; CAF2A;MDU - TERRACES AT MANELE BAY PHASE I-III",
            "TERRACES AT MANELE BAY PHASE I-III",
        ),
        # Lowercase / mixed case — match should be case-insensitive
        ("mdu - lowercase", "lowercase"),
        ("Mdu  -  weird spacing", "weird spacing"),
        # Trailing garbage trimmed
        ("MDU - X**", "X"),
    ],
)
def test_extract_extracts(sag: str, expected: str) -> None:
    assert extract_mdu_name(sag) == expected


@pytest.mark.parametrize(
    "sag",
    [
        None,
        "",
        "no MDU here",
        "MDU",  # no dash
        "MDU - ",  # marker but no name
        "MDU - **",  # marker, only stripped chars
    ],
)
def test_extract_rejects(sag) -> None:
    assert extract_mdu_name(sag) is None
