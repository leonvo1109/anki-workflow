#!/usr/bin/env python3
"""
Erstellt: 2026-06-09
Kurzbeschreibung: Stellt eine Anki-Sicherung aus ./backups/ wieder her.
Benötigte Abhängigkeiten: keine (nur Python-Standardbibliothek)
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from anki_paths import collection_db

ANKI_COLLECTION = collection_db()
BACKUP_DIR = Path(__file__).resolve().parent.parent / "backups"


def list_backups() -> list[Path]:
    return sorted(BACKUP_DIR.glob("collection_*.anki2"), reverse=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Anki-Backup wiederherstellen")
    parser.add_argument(
        "backup",
        nargs="?",
        help="Backup-Dateiname in ./backups/ (Standard: neuestes Backup)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nur anzeigen, was kopiert würde",
    )
    args = parser.parse_args()

    if args.backup:
        source = BACKUP_DIR / args.backup
    else:
        backups = list_backups()
        if not backups:
            print("Kein Backup in ./backups/ gefunden.", file=sys.stderr)
            return 1
        source = backups[0]

    if not source.exists():
        print(f"Backup nicht gefunden: {source}", file=sys.stderr)
        return 1

    print(f"Quelle:      {source}")
    print(f"Ziel:        {ANKI_COLLECTION}")

    if args.dry_run:
        print("Dry-run – keine Änderung vorgenommen.")
        return 0

    if ANKI_COLLECTION.exists():
        safety = ANKI_COLLECTION.with_suffix(".anki2.pre_restore")
        shutil.copy2(ANKI_COLLECTION, safety)
        print(f"Sicherheitskopie: {safety}")

    shutil.copy2(source, ANKI_COLLECTION)
    print("Wiederherstellung abgeschlossen. Anki neu starten.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
