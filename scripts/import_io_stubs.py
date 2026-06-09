#!/usr/bin/env python3
"""
Erstellt: 2026-06-09
Kurzbeschreibung: Kopiert IO-Kandidaten ins Anki-Mediapaket und legt Stub-Notizen per AnkiConnect an.
Benötigte Abhängigkeiten: pip install requests (Anki mit AnkiConnect muss laufen)

Hinweis: Image-Occlusion-Masken (SVG) erzeugt das Anki-Addon normalerweise interaktiv.
Dieses Skript legt Karten mit Bild + Header an; Masken in Anki nachträglich ergänzen
(Browser → Notiz bearbeiten → Image Occlusion Editor), sofern MCP keine Masken liefert.
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Image-Occlusion-Stubs aus occlusion/manifest.json importieren")
    parser.add_argument("processed_dir", type=Path, help="Ordner mit occlusion/manifest.json")
    parser.add_argument("--deck", required=True, help='Anki-Deck, z. B. "4. Semester::Betriebssysteme 1::Allgemein"')
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="Max. Anzahl Kandidaten (0 = alle)")
    args = parser.parse_args()

    processed = args.processed_dir.resolve()
    manifest_path = processed / "occlusion" / "manifest.json"
    if not manifest_path.exists():
        print(f"Manifest nicht gefunden: {manifest_path}", file=sys.stderr)
        return 1

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    candidates = manifest.get("io_recommended") or manifest.get("candidates", [])
    if args.limit:
        candidates = candidates[: args.limit]

    if args.dry_run:
        for c in candidates:
            desc = c.get("description", "")[:60]
            print(f"[dry-run] Folie {c['slide']} (score {c.get('io_score', '?')}): {desc} ← {c['image']}")
        return 0

    try:
        invoke("version")
    except Exception as e:
        print(f"AnkiConnect nicht erreichbar ({ANKI_CONNECT}): {e}", file=sys.stderr)
        print("Anki öffnen und AnkiConnect-Addon aktivieren.", file=sys.stderr)
        return 1

    notes = []
    for c in candidates:
        img_rel = c["image"]
        src = processed / img_rel
        if not src.exists():
            print(f"Übersprungen (Bild fehlt): {src}", file=sys.stderr)
            continue
        media_name = copy_to_media(src)
        notes.append(
            {
                "deckName": args.deck,
                "modelName": IO_MODEL,
                "fields": {
                    "Header": c.get("header", f"Folie {c['slide']}"),
                    "Image": f'<img src="{media_name}" />',
                    "Question Mask": "",
                    "Answer Mask": "",
                    "Footer": f"Folie {c['slide']} – Masken ergänzen",
                    "Remarks": "Auto-Stub aus extract_lecture.py; IO-Masken in Anki nachbearbeiten.",
                },
                "tags": ["io-stub", "auto-extracted"],
            }
        )

    if not notes:
        print("Keine Notizen zum Import.", file=sys.stderr)
        return 1

    result = invoke("addNotes", notes=notes)
    created = sum(1 for x in result if x)
    print(f"{created}/{len(notes)} IO-Stubs angelegt. Masken in Anki ergänzen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
