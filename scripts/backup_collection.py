#!/usr/bin/env python3
"""
Erstellt: 2026-06-11
Kurzbeschreibung: 2-stufige Sicherung nach backups/:
1) collection.anki2 (+ optional collection.media)
2) optional komplettes Anki-Profil als Archiv
Profil kommt aus .env / ANKI_PROFILE (via anki_paths), kein manuelles Pfad-Raten.

Nutzung:
  python scripts/backup_collection.py            # Backup anlegen
  python scripts/backup_collection.py --with-media
  python scripts/backup_collection.py --with-profile
  python scripts/backup_collection.py --check    # Exit 0, wenn Backup ≤1h alt existiert
  python scripts/backup_collection.py --check --with-media
  python scripts/backup_collection.py --check --with-profile
  python scripts/backup_collection.py --auto     # führt faellige Backups automatisch aus
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

from anki_paths import ANKI_BASE, ANKI_PROFILE, collection_db, collection_media

BACKUP_DIR = SCRIPT_DIR.parent / "backups"
MAX_AGE_S = 3600
PROFILE_MAX_AGE_S = 24 * 3600


def latest_backup_age() -> float | None:
    backups = sorted(BACKUP_DIR.glob("collection_*.anki2"), reverse=True)
    if not backups:
        return None
    return time.time() - backups[0].stat().st_mtime


def latest_media_backup_age() -> float | None:
    backups = sorted(BACKUP_DIR.glob("collection_media_*.zip"), reverse=True)
    if not backups:
        return None
    return time.time() - backups[0].stat().st_mtime


def latest_profile_backup_age() -> float | None:
    backups = sorted(BACKUP_DIR.glob("anki_profile_*.zip"), reverse=True)
    if not backups:
        return None
    return time.time() - backups[0].stat().st_mtime


def _fmt_age(age_s: float | None) -> str:
    if age_s is None:
        return "keines"
    if age_s < 3600:
        return f"{age_s / 60:.0f} min"
    return f"{age_s / 3600:.1f} h"


def main() -> int:
    parser = argparse.ArgumentParser(description="Anki-Collection nach backups/ sichern")
    parser.add_argument("--check", action="store_true", help="Nur prüfen, ob ein Backup ≤1h alt existiert")
    parser.add_argument(
        "--with-media",
        action="store_true",
        help="Zusätzlich collection.media als ZIP sichern (bei --check auch prüfen)",
    )
    parser.add_argument(
        "--with-profile",
        action="store_true",
        help="Zusätzlich komplettes Anki-Profil als ZIP sichern (bei --check auch prüfen)",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Faellige Backups nach Hierarchie automatisch ausfuehren (DB/Media: 1h, Profil: 24h)",
    )
    args = parser.parse_args()

    if args.auto and args.check:
        print("--auto und --check koennen nicht kombiniert werden.", file=sys.stderr)
        return 2

    if args.check:
        age = latest_backup_age()
        if age is None or age > MAX_AGE_S:
            print("Kein aktuelles DB-Backup (≤1h). Bitte: python scripts/backup_collection.py")
            return 1
        if args.with_media:
            media_age = latest_media_backup_age()
            if media_age is None or media_age > MAX_AGE_S:
                print("Kein aktuelles Media-Backup (≤1h). Bitte: python scripts/backup_collection.py --with-media")
                return 1
            print(f"OK – DB-Backup ist {age / 60:.0f} min alt, Media-Backup {media_age / 60:.0f} min.")
        else:
            print(f"OK – DB-Backup ist {age / 60:.0f} min alt.")

        if args.with_profile:
            profile_age = latest_profile_backup_age()
            if profile_age is None or profile_age > MAX_AGE_S:
                print("Kein aktuelles Profil-Backup (≤1h). Bitte: python scripts/backup_collection.py --with-profile")
                return 1
            print(f"OK – Profil-Backup ist {profile_age / 60:.0f} min alt.")
        return 0

    if args.auto:
        db_age = latest_backup_age()
        media_age = latest_media_backup_age()
        profile_age = latest_profile_backup_age()

        due_db = db_age is None or db_age > MAX_AGE_S
        due_media = media_age is None or media_age > MAX_AGE_S
        due_profile = profile_age is None or profile_age > PROFILE_MAX_AGE_S

        print(
            "Status – DB: "
            f"{_fmt_age(db_age)}, Media: {_fmt_age(media_age)}, Profil: {_fmt_age(profile_age)}"
        )

        if not (due_db or due_media or due_profile):
            print("Auto: Keine Backups faellig.")
            return 0

        args.with_media = due_media or due_db
        args.with_profile = due_profile

    src = collection_db()
    if not src.is_file():
        print(f"collection.anki2 nicht gefunden: {src}\n(Profil '{ANKI_PROFILE}' – ANKI_PROFILE in .env prüfen)", file=sys.stderr)
        return 1

    BACKUP_DIR.mkdir(exist_ok=True)
    dest = BACKUP_DIR / f"collection_{datetime.now():%Y%m%d_%H%M%S}.anki2"
    if args.auto and not (args.with_media or args.with_profile):
        print("Auto: Nur DB faellig.")
    elif args.auto:
        parts: list[str] = ["DB"]
        if args.with_media:
            parts.append("Media")
        if args.with_profile:
            parts.append("Profil")
        print(f"Auto: Fuehre Backup aus fuer {', '.join(parts)}.")

    shutil.copy2(src, dest)
    print(f"Backup: {dest.name} (Profil {ANKI_PROFILE}, {dest.stat().st_size // 1024} KB)")

    if args.with_media:
        media_src = collection_media()
        if not media_src.is_dir():
            print(f"collection.media nicht gefunden: {media_src}", file=sys.stderr)
            return 1
        media_base = BACKUP_DIR / f"collection_media_{datetime.now():%Y%m%d_%H%M%S}"
        archive_path = shutil.make_archive(str(media_base), "zip", root_dir=media_src)
        media_zip = Path(archive_path)
        print(f"Media-Backup: {media_zip.name} ({media_zip.stat().st_size // 1024} KB)")

    if args.with_profile:
        if not ANKI_BASE.is_dir():
            print(f"Anki-Profilordner nicht gefunden: {ANKI_BASE}", file=sys.stderr)
            return 1
        profile_base = BACKUP_DIR / f"anki_profile_{datetime.now():%Y%m%d_%H%M%S}"
        archive_path = shutil.make_archive(str(profile_base), "zip", root_dir=ANKI_BASE.parent, base_dir=ANKI_BASE.name)
        profile_zip = Path(archive_path)
        print(f"Profil-Backup: {profile_zip.name} ({profile_zip.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
