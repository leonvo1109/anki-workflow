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

REPO_MEDIA = Path(__file__).resolve().parent.parent / "media"
REPO_CSS = REPO_MEDIA / "_global_style.css"
ANKI_CSS_NAME = "_global_style.css"

# Mit sync_anki_style.py push nach collection.media (AnkiMobile braucht Medien-Sync)
MEDIA_FILES = (
    "_global_style.css",
    "_highlight.min.js",
    "_code_highlight.js",
    "_hljs_github.min.css",
    "_hljs_github-dark.min.css",
)


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
    drift = 0
    print(f"Profil:     {ANKI_PROFILE}")
    for name in MEDIA_FILES:
        repo = REPO_MEDIA / name
        anki = collection_media() / name
        if not repo.exists():
            print(f"✗ {name}: fehlt im Projekt")
            drift += 1
            continue
        if not anki.exists():
            print(f"✗ {name}: fehlt in Anki")
            drift += 1
            continue
        same = filecmp.cmp(repo, anki, shallow=False)
        print(f"{'✓' if same else '✗'} {name}")
        if not same:
            drift += 1
    return 1 if drift else 0


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
    dest_dir = collection_media()
    dest_dir.mkdir(parents=True, exist_ok=True)
    missing = [name for name in MEDIA_FILES if not (REPO_MEDIA / name).exists()]
    if missing:
        print("Fehlende Projektdateien: " + ", ".join(missing), file=sys.stderr)
        return 1
    for name in MEDIA_FILES:
        src = REPO_MEDIA / name
        dest = dest_dir / name
        if dest.exists():
            dest.unlink()
        shutil.copy2(src, dest)
        print(f"push: {src} → {dest}")
    beacon = dest_dir / "_global_style.sync"
    beacon.write_text(str((dest_dir / MEDIA_FILES[0]).stat().st_mtime_ns), encoding="utf-8")
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
