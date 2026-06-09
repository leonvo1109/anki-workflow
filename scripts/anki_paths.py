"""Anki-Pfade – Profil über .env / Umgebungsvariable ANKI_PROFILE (Standard: User)."""
from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Lädt Projekt-.env (KEY=VALUE). Shell-Variablen haben Vorrang."""
    env_file = PROJECT_ROOT / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        if key:
            os.environ.setdefault(key, value)


_load_dotenv()
ANKI_PROFILE = os.environ.get("ANKI_PROFILE", "User")
ANKI_BASE = Path.home() / "Library/Application Support/Anki2" / ANKI_PROFILE


def collection_db() -> Path:
    return ANKI_BASE / "collection.anki2"


def collection_media() -> Path:
    return ANKI_BASE / "collection.media"
