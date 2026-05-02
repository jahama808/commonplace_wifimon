"""Address → island heuristic. Tests pin the unambiguous cases we know
about so future edits don't accidentally regress them."""
from __future__ import annotations

import pytest

from app.models.common_area import Island
from app.services.island_detect import detect_island


@pytest.mark.parametrize(
    "address,expected",
    [
        ("1388 Ala Moana Blvd, Honolulu, HI 96814", Island.OAHU),
        ("3445 Lower Honoapiilani Rd, Lahaina, HI 96761", Island.MAUI),
        ("75-5646 Palani Rd, Kailua Kona, HI 96740, USA", Island.HAWAII),
        ("3970 Wyllie Rd, Princeville", Island.KAUAI),
        ("Kaunakakai, HI", Island.MOLOKAI),
        ("Lanai City, HI 96763", Island.LANAI),
        # Explicit island mention beats town heuristics
        ("Some Street, Maui, HI", Island.MAUI),
    ],
)
def test_detect_known(address: str, expected: Island) -> None:
    assert detect_island(address) == expected


@pytest.mark.parametrize(
    "address",
    [
        None,
        "",
        "1234 Main St",  # generic, no island/town hint
        "Kailua, HI",  # ambiguous (Oahu vs Big Island) — leave it None
    ],
)
def test_detect_ambiguous_or_empty(address) -> None:
    assert detect_island(address) is None
