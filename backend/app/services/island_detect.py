"""Best-effort island detection from a free-form address.

Hawaiian addresses are ambiguous by ZIP alone (96xxx covers all six
islands), so we look for explicit island names + well-known town
keywords. Returns `None` when the address doesn't yield an unambiguous
match — the UI then falls back to letting the operator pick.
"""
from __future__ import annotations

import re

from app.models.common_area import Island

# Order matters: explicit island names checked first; ambiguous town
# names skipped (e.g. "Kailua" exists on both Oahu and Big Island —
# we'd need state context to disambiguate, so we don't).
_KEYWORDS: list[tuple[Island, list[str]]] = [
    (
        Island.OAHU,
        [
            "oahu",
            "honolulu", "waikiki", "kakaako", "kaka'ako", "ala moana",
            "hawaii kai", "pearl city", "aiea", "mililani", "kaneohe",
            "waipahu", "kapolei", "ewa beach", "ewa", "wahiawa",
            "haleiwa", "mililani", "pearlridge",
        ],
    ),
    (
        Island.MAUI,
        [
            "maui",
            "lahaina", "wailuku", "kahului", "kihei", "wailea",
            "hana", "makawao", "paia", "kaanapali", "ka'anapali",
            "napili", "kapalua",
        ],
    ),
    (
        Island.HAWAII,
        [
            "hilo", "kona", "kailua-kona", "kailua kona",
            "waikoloa", "pahoa", "naalehu", "na'alehu", "volcano",
            "captain cook", "honokaa", "honoka'a", "papaikou",
            "keaau", "kea'au", "pepeekeo", "pepe'ekeo",
            # 'big island' / 'hawaii island' explicit
            "big island", "hawaii island",
        ],
    ),
    (
        Island.KAUAI,
        [
            "kauai",
            "lihue", "lihu'e", "princeville", "hanalei", "kapaa", "kapa'a",
            "poipu", "po'ipu", "koloa", "kekaha", "wailua",
        ],
    ),
    (
        Island.MOLOKAI,
        ["molokai", "moloka'i", "kaunakakai", "hoolehua", "ho'olehua"],
    ),
    (
        Island.LANAI,
        ["lanai", "lana'i", "lanai city", "lana'i city"],
    ),
]


def detect_island(address: str | None) -> Island | None:
    """Return the inferred Island, or None if the address is empty /
    ambiguous / unrecognized."""
    if not address:
        return None
    text = address.lower()
    # Match against word boundaries so "ko olina" doesn't match "olina"
    # inside a longer street name. Use a simple non-letter delimiter.
    for island, keywords in _KEYWORDS:
        for kw in keywords:
            pattern = r"(?<![a-z])" + re.escape(kw) + r"(?![a-z])"
            if re.search(pattern, text):
                return island
    return None
