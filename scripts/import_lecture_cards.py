#!/usr/bin/env python3
"""
Erstellt: 2026-06-09, refactored 2026-06-10
Kurzbeschreibung: Importiert Karten aus slides.json für beliebige Kurse (konfiguriert via anki.json).
Benötigte Abhängigkeiten: pip install requests (Anki mit AnkiConnect muss laufen)

Kurs-Konfiguration: lectures/.../{Kurs}/anki.json
Kuratierte Karten:  lectures/.../{Kurs}/cards/anki_curated.json (optional)
Cleanup/Updates:     lectures/.../{Kurs}/cards/anki_cleanup.json (optional)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import requests  # noqa: F401
except ImportError:
    print("Fehler: requests fehlt. Bitte: pip install requests", file=sys.stderr)
    sys.exit(1)

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lecture_import.anki_client import AnkiClient
from lecture_import.config import load_course_config
from lecture_import.generator import generate_from_slides


def import_io_stubs(course_dir: Path, *, dry_run: bool = False) -> int:
    from import_io_stubs import import_chapter_stubs

    cfg = load_course_config(course_dir)
    total = 0
    for slug in cfg.chapter_slugs():
        ch = cfg.chapter_cfg(slug)
        processed = cfg.processed_dir / slug
        if not (processed / "occlusion" / "manifest.json").exists():
            continue
        n = import_chapter_stubs(processed, ch.deck, dry_run=dry_run)
        if n:
            print(f"IO {slug}: {n} Stubs")
            total += n
    print(f"IO gesamt: {total} Stubs")
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description="Karten aus slides.json importieren (kursübergreifend)")
    parser.add_argument("course_dir", type=Path, help='Kursordner mit anki.json, z. B. "lectures/semester4/Rechnerarchitektur"')
    parser.add_argument("--chapter", action="append", help="Nur bestimmtes Kapitel (slug)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-cleanup", action="store_true")
    parser.add_argument("--import-io", action="store_true", help="IO-Stubs aus occlusion/manifest.json importieren (Masken manuell)")
    parser.add_argument(
        "--chapter1-mode",
        choices=["skip", "curated-only", "full"],
        default=None,
        help="Override für bs-kapitel1-einfuehrung (Legacy-Flag)",
    )
    args = parser.parse_args()

    try:
        cfg = load_course_config(args.course_dir)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 1

    if not cfg.processed_dir.is_dir():
        print(f"processed/ fehlt: {cfg.processed_dir}", file=sys.stderr)
        return 1

    client = AnkiClient()
    slugs = cfg.chapter_slugs(args.chapter)

    if not args.dry_run:
        try:
            client.ping()
        except Exception as e:
            print(f"AnkiConnect nicht erreichbar: {e}", file=sys.stderr)
            return 1

    if not args.skip_cleanup and cfg.cleanup:
        client.run_cleanup(cfg.cleanup, dry_run=args.dry_run)
        if cfg.cleanup.get("updates") and not args.dry_run:
            print(f"Aktualisiert: {len(cfg.cleanup['updates'])} Notizen")

    seen: set[str] = set()
    if not args.dry_run:
        seen = client.load_existing_keys(cfg.deck)
        print(f"Bereits in Anki (Dedup): {len(seen)} Fronten")

    all_notes: list[dict] = []
    for slug in slugs:
        ch = cfg.chapter_cfg(slug)
        slides_path = cfg.processed_dir / slug / "slides.json"
        if not slides_path.exists():
            print(f"Übersprungen (fehlt): {slides_path}", file=sys.stderr)
            continue

        auto_mode = ch.auto_mode
        if args.chapter1_mode and slug == "bs-kapitel1-einfuehrung":
            auto_mode = args.chapter1_mode

        auto = auto_mode == "full"
        if auto_mode == "skip":
            continue

        slides = json.loads(slides_path.read_text(encoding="utf-8"))
        notes = generate_from_slides(
            slides, ch.deck, ch.tag, slug, seen, cfg, auto_bullets=auto,
        )
        print(f"{slug}: {len(notes)} Karten")
        all_notes.extend(notes)

    print(f"Gesamt: {len(all_notes)} neue Karten")

    if args.dry_run:
        for n in all_notes[:5]:
            f = n["fields"]
            front = f.get("Vorderseite") or f.get("Text", "")[:60]
            print(f"  [{n.get('tags', ['?'])[0]}] {front}…")
        if len(all_notes) > 5:
            print(f"  … und {len(all_notes) - 5} weitere")
    elif all_notes:
        created, skipped = client.import_notes(all_notes)
        print(f"Importiert: {created}/{len(all_notes)} Karten ({skipped} übersprungen/Duplikate)")

    if args.import_io:
        import_io_stubs(cfg.course_dir, dry_run=args.dry_run)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
