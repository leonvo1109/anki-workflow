#!/usr/bin/env python3
"""
Erstellt: 2026-06-09
Kurzbeschreibung: Synchronisiert media/_global_style.css ↔ Anki collection.media.
Benötigte Abhängigkeiten: keine (nur stdlib)

Workflow:
  pull   – Anki → Projekt (Startpunkt / nach manueller Anki-Bearbeitung)
  push   – Projekt → Anki (nach Bearbeitung in Cursor)
  status – zeigt, ob Dateien identisch sind
"""
from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

from anki_paths import ANKI_PROFILE, collection_media

REPO_CSS = Path(__file__).resolve().parent.parent / "media" / "_global_style.css"
ANKI_CSS_NAME = "_global_style.css"


def anki_css_path() -> Path:
    return collection_media() / ANKI_CSS_NAME


def ensure_repo_file() -> None:
    REPO_CSS.parent.mkdir(parents=True, exist_ok=True)
    if not REPO_CSS.exists():
        REPO_CSS.write_text(
            "/* Paste your Anki global styles here. Then: python scripts/sync_anki_style.py push */\n",
            encoding="utf-8",
        )


def cmd_status() -> int:
    ensure_repo_file()
    anki = anki_css_path()
    if not anki.exists():
        print(f"Anki: fehlt ({anki})")
        print(f"Projekt: {REPO_CSS} ({REPO_CSS.stat().st_size} bytes)")
        return 1
    same = filecmp.cmp(REPO_CSS, anki, shallow=False)
    print(f"Profil:     {ANKI_PROFILE}")
    print(f"Projekt:    {REPO_CSS}")
    print(f"Anki media: {anki}")
    if same:
        print("Status:     ✓ synchron")
        return 0
    print("Status:     ✗ unterschiedlich")
    print(f"  Projekt: {REPO_CSS.stat().st_mtime:.0f}  Anki: {anki.stat().st_mtime:.0f}")
    return 1


def cmd_pull() -> int:
    ensure_repo_file()
    src = anki_css_path()
    if not src.exists():
        print(f"Keine Datei in Anki: {src}", file=sys.stderr)
        return 1
    shutil.copy2(src, REPO_CSS)
    print(f"pull: {src} → {REPO_CSS}")
    return 0


def cmd_push() -> int:
    ensure_repo_file()
    if not REPO_CSS.exists() or REPO_CSS.stat().st_size == 0:
        print(f"Projektdatei leer oder fehlt: {REPO_CSS}", file=sys.stderr)
        return 1
    dest = anki_css_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Anki erkennt nur geänderte Inhalte oft nicht – Datei neu anlegen triggert Media-Sync.
    if dest.exists():
        dest.unlink()
    shutil.copy2(REPO_CSS, dest)
    beacon = dest.parent / "_global_style.sync"
    beacon.write_text(str(dest.stat().st_mtime_ns), encoding="utf-8")
    print(f"push: {REPO_CSS} → {dest}")
    print("Wichtig: In Anki Desktop synchronisieren und auf „Medien-Sync abgeschlossen“ warten.")
    print("Danach AnkiMobile synchronisieren. CSS liegt zusätzlich in den Notiztypen eingebettet.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync _global_style.css zwischen Repo und Anki")
    parser.add_argument("command", choices=["pull", "push", "status"], help="Sync-Richtung oder Vergleich")
    args = parser.parse_args()
    if args.command == "status":
        return cmd_status()
    if args.command == "pull":
        return cmd_pull()
    return cmd_push()


if __name__ == "__main__":
    raise SystemExit(main())
