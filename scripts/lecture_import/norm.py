"""Gemeinsame Textnormalisierung für Dedup und Sperrlisten."""
from __future__ import annotations

import re
import unicodedata


def norm_key(text: str) -> str:
    t = re.sub(r"<[^>]+>", "", text.lower())
    t = re.sub(r"[^a-zäöüß0-9]+", " ", t)
    return " ".join(t.split())[:100]


def norm_match(text: str) -> str:
    """Like norm_key but without length cap — for slide/page matching only."""
    t = re.sub(r"<[^>]+>", "", text.lower())
    t = re.sub(r"[^a-zäöüß0-9]+", " ", t)
    return " ".join(t.split())


def norm_filename(name: str) -> str:
    """Lowercase filename with stable umlaut folding for classification."""
    s = unicodedata.normalize("NFC", name).lower()
    return s.replace("ü", "u").replace("ö", "o").replace("ä", "a").replace("ß", "ss")
