#!/usr/bin/env python3
"""
Erstellt: 2026-06-11
Kurzbeschreibung: Sichert collection.anki2 nach backups/ – Profil kommt aus
.env / ANKI_PROFILE (via anki_paths), kein manuelles Pfad-Raten mehr.

Nutzung:
  python scripts/backup_collection.py            # Backup anlegen
  python scripts/backup_collection.py --check    # Exit 0, wenn Backup ≤1h alt existiert
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from anki_paths import ANKI_PROFILE, collection_db

BACKUP_DIR = SCRIPT_DIR.parent / "backups"
MAX_AGE_S = 3600


def latest_backup_age() -> float | None:
    backups = sorted(BACKUP_DIR.glob("collection_*.anki2"), reverse=True)
    if not backups:
        return None
    return time.time() - backups[0].stat().st_mtime


def main() -> int:
    parser = argparse.ArgumentParser(description="Anki-Collection nach backups/ sichern")
    parser.add_argument("--check", action="store_true", help="Nur prüfen, ob ein Backup ≤1h alt existiert")
    args = parser.parse_args()

    if args.check:
        age = latest_backup_age()
        if age is not None and age <= MAX_AGE_S:
            print(f"OK – Backup ist {age / 60:.0f} min alt.")
            return 0
        print("Kein aktuelles Backup (≤1h). Bitte: python scripts/backup_collection.py")
        return 1

    src = collection_db()
    if not src.is_file():
        print(f"collection.anki2 nicht gefunden: {src}\n(Profil '{ANKI_PROFILE}' – ANKI_PROFILE in .env prüfen)", file=sys.stderr)
        return 1

    BACKUP_DIR.mkdir(exist_ok=True)
    dest = BACKUP_DIR / f"collection_{datetime.now():%Y%m%d_%H%M%S}.anki2"
    shutil.copy2(src, dest)
    print(f"Backup: {dest.name} (Profil {ANKI_PROFILE}, {dest.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
