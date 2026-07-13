#!/usr/bin/env python3
"""Einmalig: Mermaid Diagram von Lückentext → Standard-Notiztyp migrieren."""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("pip install requests", file=sys.stderr)
    sys.exit(1)

ANKI = "http://127.0.0.1:8765"
OLD_MODEL = "Mermaid Diagram"
NEW_MODEL = "Mermaid Chart"
NOTE_TYPE = Path(__file__).resolve().parent.parent / "media" / "note-types" / "mermaid-chart.json"


def invoke(action: str, **params):
    r = requests.post(ANKI, json={"action": action, "version": 6, "params": params}, timeout=60)
    r.raise_for_status()
    payload = r.json()
    if payload.get("error"):
        raise RuntimeError(payload["error"])
    return payload.get("result")


def ensure_standard_model() -> None:
    names = invoke("modelNames")
    if NEW_MODEL in names:
        print(f"Modell existiert: {NEW_MODEL}")
        return

    spec = json.loads(NOTE_TYPE.read_text(encoding="utf-8"))
    templates = [
        {"Name": name, "Front": t["Front"], "Back": t["Back"]}
        for name, t in spec["templates"].items()
    ]
    invoke(
        "createModel",
        modelName=NEW_MODEL,
        inOrderFields=spec["fields"],
        cardTemplates=templates,
        css=spec["css"],
        isCloze=False,
    )
    print(f"Modell erstellt: {NEW_MODEL}")


def migrate_notes() -> int:
    nids = invoke("findNotes", query=f'note:"{OLD_MODEL}"')
    if not nids:
        nids = invoke("findNotes", query=f'note:"{NEW_MODEL}"')
        if nids:
            print("Keine Notizen unter altem Modell; bereits migriert?")
        return 0

    notes = invoke("notesInfo", notes=nids)
    for note in notes:
        fields = {k: v["value"] for k, v in note["fields"].items()}
        invoke(
            "updateNoteModel",
            note={
                "id": note["noteId"],
                "modelName": NEW_MODEL,
                "fields": fields,
                "tags": note.get("tags", []),
            },
        )
        print(f"Migriert: note {note['noteId']}")
    return len(notes)


def push_templates() -> None:
    spec = json.loads(NOTE_TYPE.read_text(encoding="utf-8"))
    spec["name"] = NEW_MODEL
    invoke("updateModelStyling", model={"name": NEW_MODEL, "css": spec["css"]})
    invoke("updateModelTemplates", model={"name": NEW_MODEL, "templates": spec["templates"]})
    print(f"Vorlagen gepusht: {NEW_MODEL}")


def main() -> int:
    ensure_standard_model()
    count = migrate_notes()
    push_templates()
    print(f"Fertig ({count} Notiz(en)). Optional: altes Modell „{OLD_MODEL}“ in Anki löschen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
