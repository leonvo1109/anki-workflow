"""Anki-Pfade – Profil über Umgebungsvariable ANKI_PROFILE (Standard: User)."""
from __future__ import annotations

import os
from pathlib import Path

ANKI_PROFILE = os.environ.get("ANKI_PROFILE", "User")
ANKI_BASE = Path.home() / "Library/Application Support/Anki2" / ANKI_PROFILE


def collection_db() -> Path:
    return ANKI_BASE / "collection.anki2"


def collection_media() -> Path:
    return ANKI_BASE / "collection.media"
