#!/usr/bin/env python3
"""
Erstellt: 2026-06-09
Kurzbeschreibung: Echte Multiple-Choice-Karten via Add-on „Multiple Choice“ (anki-mc).
Benötigt: Anki-Add-on 1566095810 installiert + Anki einmal neu gestartet.
          pip install requests, AnkiConnect aktiv.

Notiztyp: „AllInOne (kprim, mc, sc)“
  QType: 0=Kprim, 1=Multiple Choice (mehrere richtig), 2=Single Choice (eine richtig)
  Answers: „1 0 0 0“ = erste Option richtig (1=ja, 0=nein), Leerzeichen-getrennt
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("Fehler: requests fehlt. Bitte: pip install requests", file=sys.stderr)
    sys.exit(1)

ANKI_CONNECT = "http://127.0.0.1:8765"
MC_MODEL = "AllInOne (kprim, mc, sc)"
COURSE = "4. Semester::Betriebssysteme 1"

# Add-on installieren: Anki → Extras → Add-ons → Herunterladen → Code: 1566095810
# Danach Anki neu starten (Notiztyp wird automatisch angelegt).

SCRIPT_DIR = Path(__file__).resolve().parent


def invoke(action: str, **params):
    r = requests.post(ANKI_CONNECT, json={"action": action, "version": 6, "params": params}, timeout=120)
    r.raise_for_status()
    payload = r.json()
    if payload.get("error"):
        raise RuntimeError(payload["error"])
    return payload.get("result")


def load_curated_mc(course_dir: Path | None = None) -> list[dict]:
    course_dir = course_dir or Path("lectures/semester4/Betriebssysteme 1")
    curated_path = course_dir / "cards" / "anki_curated.json"
    if not curated_path.exists():
        print(f"Fehler: {curated_path} fehlt", file=sys.stderr)
        sys.exit(1)
    data = json.loads(curated_path.read_text(encoding="utf-8"))
    items: list[dict] = []
    for chapter_items in data.values():
        for item in chapter_items:
            if item["type"] in ("mc", "tf"):
                items.append(item)
    return items


def shuffle_options(correct: str, distractors: list[str], seed: str) -> tuple[list[str], str]:
    opts = [correct] + distractors[:3]
    rng = random.Random(hash(seed) & 0xFFFFFFFF)
    rng.shuffle(opts)
    answers = " ".join("1" if o == correct else "0" for o in opts)
    return opts, answers


def mc_item_to_note(item: dict, deck: str, tag: str) -> dict:
    if item["type"] == "tf":
        front = item["front"].replace("Stimmt: ", "").strip()
        is_true = item["back"].startswith("✓")
        return {
            "deckName": deck,
            "modelName": MC_MODEL,
            "fields": {
                "Question": front,
                "Title": "",
                "QType (0=kprim,1=mc,2=sc)": "2",
                "Q_1": "Ja, stimmt",
                "Q_2": "Nein, stimmt nicht",
                "Q_3": "",
                "Q_4": "",
                "Q_5": "",
                "Answers": "1 0" if is_true else "0 1",
                "Sources": "",
                "Extra 1": item["back"],
            },
            "tags": [tag, "mc-interactive"],
        }

    correct = item["back"].replace("✓ ", "").strip()
    opts, answers = shuffle_options(correct, item.get("distractors", []), item["front"])
    question = item["front"].replace("☐ Ankreuzen: ", "").strip()
    fields = {
        "Question": question,
        "Title": "",
        "QType (0=kprim,1=mc,2=sc)": "2",
        "Answers": answers,
        "Sources": "",
        "Extra 1": f"✓ {correct}",
    }
    for i in range(5):
        fields[f"Q_{i + 1}"] = opts[i] if i < len(opts) else ""
    return {"deckName": deck, "modelName": MC_MODEL, "fields": fields, "tags": [tag, "mc-interactive"]}


def parse_pseudo_mc_note(info: dict) -> dict | None:
    """Konvertiert bestehende Einfach-Karte mit ☐ Ankreuzen-Format."""
    fields = info["fields"]
    front = fields.get("Vorderseite", {}).get("value", "")
    back = fields.get("Rückseite", {}).get("value", "")
    if "☐ Ankreuzen" not in front:
        return None
    m_q = re.search(r"☐ Ankreuzen:\s*(.+?)(?:\n\n|\n\(A\))", front, re.S)
    if not m_q:
        return None
    question = m_q.group(1).strip()
    opts = re.findall(r"\([A-D]\)\s*(.+)", front)
    m_ans = re.search(r"✓\s*\([A-D]\)\s*(.+)", back)
    if not opts or not m_ans:
        return None
    correct = m_ans.group(1).strip()
    distractors = [o.strip() for o in opts if o.strip() != correct]
    shuffled, answers = shuffle_options(correct, distractors, question)
    cids = info.get("cards") or []
    deck_name = COURSE
    if cids:
        card_info = invoke("cardsInfo", cards=cids[:1])[0]
        deck_name = card_info.get("deckName", deck_name)

    note_fields = {
        "Question": question,
        "Title": "",
        "QType (0=kprim,1=mc,2=sc)": "2",
        "Answers": answers,
        "Sources": "",
        "Extra 1": back,
    }
    for i in range(5):
        note_fields[f"Q_{i + 1}"] = shuffled[i] if i < len(shuffled) else ""
    return {
        "deckName": deck_name,
        "modelName": MC_MODEL,
        "fields": note_fields,
        "tags": list(info.get("tags", [])) + ["mc-interactive"],
        "_source_nid": info["noteId"],
    }


def deck_for_tag(tags: list[str]) -> str:
    if "betriebssysteme::prozesse" in tags:
        return f"{COURSE}::Prozesse & Threads"
    if "betriebssysteme::scheduling" in tags:
        return f"{COURSE}::Scheduling"
    if "betriebssysteme::synchronisation" in tags:
        return f"{COURSE}::Synchronisation"
    return f"{COURSE}::Allgemein"


def ensure_mc_model() -> None:
    models = invoke("modelNames")
    if MC_MODEL not in models:
        print(
            f"Notiztyp „{MC_MODEL}“ fehlt.\n"
            "Bitte Add-on installieren:\n"
            "  Anki → Extras → Add-ons → Herunterladen & Installieren → Code: 1566095810\n"
            "  Anki neu starten, dann dieses Skript erneut ausführen.",
            file=sys.stderr,
        )
        sys.exit(2)


def main() -> int:
    parser = argparse.ArgumentParser(description="Echte MC-Karten (anki-mc Add-on)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--migrate", action="store_true", help="Bestehende ☐-Pseudo-Karten ersetzen")
    parser.add_argument("--deck", default="", help="Ziel-Deck (Standard: je nach Tag/Kapitel)")
    parser.add_argument("--delete-pseudo", action="store_true", help="Nach Migration Pseudo-Karten löschen")
    args = parser.parse_args()

    invoke("version")
    ensure_mc_model()

    notes: list[dict] = []
    delete_ids: list[int] = []

    if args.migrate:
        nids = invoke("findNotes", query=f'deck:"{COURSE}" "☐ Ankreuzen"')
        for i in range(0, len(nids), 50):
            for info in invoke("notesInfo", notes=nids[i : i + 50]):
                converted = parse_pseudo_mc_note(info)
                if converted:
                    delete_ids.append(converted.pop("_source_nid"))
                    notes.append(converted)
        print(f"Migration: {len(notes)} Pseudo-Karten gefunden")
    else:
        tag = "betriebssysteme::allgemein"
        deck = args.deck or f"{COURSE}::Allgemein"
        for item in load_curated_mc():
            note = mc_item_to_note(item, deck, tag)
            # besseres Deck je Kapitel wäre bei Neuimport aus CURATED-Keys möglich
            notes.append(note)
        print(f"Kuratiert: {len(notes)} MC/TF-Karten")

    if args.dry_run:
        for n in notes[:3]:
            print(f"  [{n['deckName']}] {n['fields']['Question'][:60]}…")
            print(f"    Answers: {n['fields']['Answers']}")
        if len(notes) > 3:
            print(f"  … und {len(notes) - 3} weitere")
        if delete_ids:
            print(f"  Würde löschen: {len(delete_ids)} Pseudo-Karten")
        return 0

    created = 0
    batch = 30
    for i in range(0, len(notes), batch):
        result = invoke("addNotes", notes=notes[i : i + batch])
        created += sum(1 for x in result if x)
    print(f"Importiert: {created}/{len(notes)} echte MC-Karten")

    if args.delete_pseudo and delete_ids:
        invoke("deleteNotes", notes=delete_ids)
        print(f"Gelöscht: {len(delete_ids)} Pseudo-Karten")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
