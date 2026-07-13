#!/usr/bin/env python3
"""Mermaid Chart → Lückentext: Modell, Vorlagen, Notizen vereinheitlichen."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("Fehler: pip install requests", file=sys.stderr)
    sys.exit(1)

ANKI = "http://127.0.0.1:8765"
OLD_MODELS = ("Mermaid Chart", "Mermaid Diagram")
TARGET_MODEL = "Mermaid Chart (Lückentext)"
REPO = Path(__file__).resolve().parent.parent
HELPER_SRC = REPO / "media" / "anki-workflow-helper"
NOTE_TYPE = REPO / "media" / "note-types" / "mermaid-chart.json"
ADDONS = Path.home() / "Library/Application Support/Anki2/addons21"
HELPER_DST = ADDONS / "anki-workflow-helper"


def invoke(action: str, **params):
    r = requests.post(ANKI, json={"action": action, "version": 6, "params": params}, timeout=60)
    r.raise_for_status()
    payload = r.json()
    if payload.get("error"):
        raise RuntimeError(payload["error"])
    return payload.get("result")


def load_spec() -> dict:
    return json.loads(NOTE_TYPE.read_text(encoding="utf-8"))


def ensure_helper_addon() -> None:
    if HELPER_DST.is_symlink() or HELPER_DST.is_dir():
        return
    ADDONS.mkdir(parents=True, exist_ok=True)
    os.symlink(HELPER_SRC, HELPER_DST)
    print(f"Helper-Addon installiert: {HELPER_DST}")
    print("→ Anki einmal neu starten für In-Place-Konvertierung (optional).")


def ensure_cloze_model() -> None:
    names = invoke("modelNames")
    if TARGET_MODEL in names:
        return
    spec = load_spec()
    templates = [
        {"Name": tpl_name, "Front": tpl["Front"], "Back": tpl["Back"]}
        for tpl_name, tpl in spec["templates"].items()
    ]
    invoke(
        "createModel",
        modelName=TARGET_MODEL,
        inOrderFields=spec["fields"],
        cardTemplates=templates,
        css=spec["css"],
        isCloze=True,
    )
    print(f"Modell erstellt: {TARGET_MODEL}")


def migrate_notes() -> int:
    nids: list[int] = []
    for model in (*OLD_MODELS, TARGET_MODEL):
        nids.extend(invoke("findNotes", query=f'note:"{model}"'))
    nids = sorted(set(nids))
    if not nids:
        return 0

    count = 0
    for note in invoke("notesInfo", notes=nids):
        if note["modelName"] == TARGET_MODEL:
            continue
        fields = {k: v["value"] for k, v in note["fields"].items()}
        invoke(
            "updateNoteModel",
            note={
                "id": note["noteId"],
                "modelName": TARGET_MODEL,
                "fields": fields,
                "tags": note.get("tags", []),
            },
        )
        count += 1
        print(f"Notiz {note['noteId']}: {note['modelName']} → {TARGET_MODEL}")
    return count


def push_templates() -> None:
    spec = load_spec()
    invoke("updateModelStyling", model={"name": TARGET_MODEL, "css": spec["css"]})
    invoke("updateModelTemplates", model={"name": TARGET_MODEL, "templates": spec["templates"]})
    print(f"Vorlagen gepusht: {TARGET_MODEL}")


def deploy_js() -> None:
    js_src = REPO / "media" / "_mermaid_card.js"
    sys.path.insert(0, str(REPO / "scripts"))
    from anki_paths import collection_media

    media = collection_media() / "_mermaid_card.js"
    if js_src.is_file() and media.parent.is_dir():
        media.write_text(js_src.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"JS aktualisiert: {media}")


def main() -> int:
    ensure_helper_addon()
    try:
        invoke("version")
    except Exception as exc:
        print(f"AnkiConnect nicht erreichbar ({exc})", file=sys.stderr)
        return 1

    ensure_cloze_model()
    migrated = migrate_notes()
    push_templates()
    deploy_js()

    print(f"\nFertig ({migrated} Notiz(en) migriert).")
    print(f"Nutze Notiztyp: „{TARGET_MODEL}“")
    print("Alte Typen „Mermaid Chart“ / „Mermaid Diagram“ kannst du in Anki löschen.")
    print("\nAnkiWeb: Diagramme werden dort nicht gerendert (nur Rohtext-Fallback).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
