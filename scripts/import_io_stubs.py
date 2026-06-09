#!/usr/bin/env python3
"""
Erstellt: 2026-06-09
Kurzbeschreibung: Kopiert IO-Kandidaten ins Anki-Mediapaket und legt Stub-Notizen per AnkiConnect an.
Benötigte Abhängigkeiten: pip install requests (Anki mit AnkiConnect muss laufen)

Hinweis: Image-Occlusion-Masken (SVG) erzeugt das Anki-Addon normalerweise interaktiv.
Dieses Skript legt Karten mit Bild + Header an; Masken in Anki nachträglich ergänzen.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import uuid
from pathlib import Path

try:
    import requests
except ImportError:
    print("Fehler: requests fehlt. Bitte: pip install requests", file=sys.stderr)
    sys.exit(1)

from anki_paths import collection_media

ANKI_CONNECT = "http://127.0.0.1:8765"
ANKI_MEDIA = collection_media()
IO_MODEL = "Image Occlusion Enhanced"


def invoke(action: str, **params):
    r = requests.post(ANKI_CONNECT, json={"action": action, "version": 6, "params": params}, timeout=30)
    r.raise_for_status()
    payload = r.json()
    if payload.get("error"):
        raise RuntimeError(payload["error"])
    return payload.get("result")


def copy_to_media(src: Path) -> str:
    ANKI_MEDIA.mkdir(parents=True, exist_ok=True)
    dest_name = f"lec-{uuid.uuid4().hex[:12]}{src.suffix}"
    shutil.copy2(src, ANKI_MEDIA / dest_name)
    return dest_name


def import_chapter_stubs(processed_dir: Path, deck: str, *, dry_run: bool = False, limit: int = 0) -> int:
    """Importiert io_recommended aus einem processed/{kapitel}/ Ordner. Gibt Anzahl Stubs zurück."""
    processed = processed_dir.resolve()
    manifest_path = processed / "occlusion" / "manifest.json"
    if not manifest_path.exists():
        return 0

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    candidates = manifest.get("io_recommended") or manifest.get("candidates", [])
    if limit:
        candidates = candidates[:limit]

    if dry_run:
        for c in candidates:
            desc = c.get("description", "")[:60]
            print(f"[dry-run] Folie {c['slide']} (score {c.get('io_score', '?')}): {desc} ← {c['image']}")
        return len(candidates)

    notes = []
    for c in candidates:
        img_rel = c["image"]
        src = processed / img_rel
        if not src.exists():
            print(f"Übersprungen (Bild fehlt): {src}", file=sys.stderr)
            continue
        media_name = copy_to_media(src)
        stub_id = f"stub-{uuid.uuid4().hex[:16]}"
        notes.append(
            {
                "deckName": deck,
                "modelName": IO_MODEL,
                "fields": {
                    "ID (hidden)": stub_id,
                    "Header": c.get("header", f"Folie {c['slide']}"),
                    "Image": f'<img src="{media_name}" />',
                    "Question Mask": " ",
                    "Answer Mask": " ",
                    "Original Mask": " ",
                    "Footer": f"Folie {c['slide']} – Masken ergänzen",
                    "Remarks": "Auto-Stub; IO-Masken in Anki nachbearbeiten.",
                    "Sources": "",
                    "Extra 1": "",
                    "Extra 2": "",
                },
                "tags": ["io-stub", "auto-extracted"],
            }
        )

    if not notes:
        return 0

    created = 0
    for note in notes:
        try:
            result = invoke("addNotes", notes=[note])
            if result and result[0]:
                created += 1
        except RuntimeError as e:
            header = note["fields"].get("Header", "?")
            print(f"IO übersprungen ({header}): {e}", file=sys.stderr)
    return created


def import_course_stubs(course_dir: Path, *, dry_run: bool = False) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from lecture_import.config import load_course_config

    cfg = load_course_config(course_dir)
    total = 0
    for slug in cfg.chapter_slugs():
        ch = cfg.chapter_cfg(slug)
        n = import_chapter_stubs(cfg.processed_dir / slug, ch.deck, dry_run=dry_run)
        if n:
            print(f"{slug}: {n} IO-Stubs → {ch.deck}")
            total += n
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description="Image-Occlusion-Stubs aus occlusion/manifest.json importieren")
    parser.add_argument(
        "target",
        type=Path,
        help="processed/{kapitel}/ oder Kursordner mit anki.json (--course)",
    )
    parser.add_argument("--deck", help='Anki-Deck (Pflicht ohne --course), z. B. "4. Semester::…"')
    parser.add_argument("--course", action="store_true", help="Alle Kapitel des Kurses importieren")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="Max. Anzahl Kandidaten pro Kapitel (0 = alle)")
    args = parser.parse_args()

    if args.course:
        if args.dry_run:
            import_course_stubs(args.target, dry_run=True)
            return 0
        try:
            invoke("version")
        except Exception as e:
            print(f"AnkiConnect nicht erreichbar ({ANKI_CONNECT}): {e}", file=sys.stderr)
            return 1
        total = import_course_stubs(args.target)
        print(f"{total} IO-Stubs angelegt. Masken in Anki ergänzen.")
        return 0 if total else 1

    if not args.deck:
        print("Fehler: --deck ist erforderlich (oder --course für Kursordner)", file=sys.stderr)
        return 1

    if args.dry_run:
        import_chapter_stubs(args.target, args.deck, dry_run=True, limit=args.limit)
        return 0

    try:
        invoke("version")
    except Exception as e:
        print(f"AnkiConnect nicht erreichbar ({ANKI_CONNECT}): {e}", file=sys.stderr)
        return 1

    created = import_chapter_stubs(args.target, args.deck, limit=args.limit)
    print(f"{created} IO-Stubs angelegt. Masken in Anki ergänzen.")
    return 0 if created else 1


if __name__ == "__main__":
    raise SystemExit(main())
