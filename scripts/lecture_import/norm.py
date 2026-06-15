"""Gemeinsame Textnormalisierung für Dedup und Sperrlisten."""
from __future__ import annotations

import re


def norm_key(text: str) -> str:
    t = re.sub(r"<[^>]+>", "", text.lower())
    t = re.sub(r"[^a-zäöüß0-9]+", " ", t)
    return " ".join(t.split())[:100]
