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

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lecture_import.config import CourseConfig, load_course_config
from lecture_import.locks import effective_curated_item, is_curated_item_locked


def invoke(action: str, **params):
    r = requests.post(ANKI_CONNECT, json={"action": action, "version": 6, "params": params}, timeout=120)
    r.raise_for_status()
    payload = r.json()
    if payload.get("error"):
        raise RuntimeError(payload["error"])
    return payload.get("result")


def discover_courses(semester_dir: Path) -> list[Path]:
    semester_dir = semester_dir.resolve()
    if not semester_dir.is_dir():
        print(f"Semester-Ordner fehlt: {semester_dir}", file=sys.stderr)
        sys.exit(1)
    courses = sorted(p.parent for p in semester_dir.glob("*/anki.json"))
    if not courses:
        print(f"Keine Kurse mit anki.json in {semester_dir}", file=sys.stderr)
        sys.exit(1)
    return courses


def load_curated_mc(cfg: CourseConfig) -> list[tuple[str, dict]]:
    items: list[tuple[str, dict]] = []
    for slug, chapter_items in cfg.curated.items():
        for item in chapter_items:
            if item.get("type") not in ("mc", "tf"):
                continue
            if is_curated_item_locked(item, cfg.locks):
                item = effective_curated_item(item, cfg.locks)
            items.append((slug, item))
    return items


def shuffle_options(correct: str, distractors: list[str], seed: str) -> tuple[list[str], str]:
    opts = [correct] + distractors[:3]
    rng = random.Random(hash(seed) & 0xFFFFFFFF)
    rng.shuffle(opts)
    answers = " ".join("1" if o == correct else "0" for o in opts)
    return opts, answers


def mc_item_to_note(item: dict, deck: str) -> dict:
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
            "tags": ["mc-interactive"],
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
    return {"deckName": deck, "modelName": MC_MODEL, "fields": fields, "tags": ["mc-interactive"]}


def parse_pseudo_mc_note(info: dict, *, default_deck: str) -> dict | None:
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
    deck_name = default_deck
    if cids:
        card_info = invoke("cardsInfo", cards=cids[:1])[0]
        deck_name = card_info.get("deckName", deck_name)

    note_fields = {
        "Question": question,
        "Title": "",
        "QType (0=kprim,1=mc,2=sc)": "2",
        "Answers": answers,
        "Sources": "",
        # Kein Antwortbuchstabe: Optionen wurden neu gemischt, der alte Buchstabe
        # aus der Pseudo-Karte wäre falsch.
        "Extra 1": f"✓ {correct}",
    }
    for i in range(5):
        note_fields[f"Q_{i + 1}"] = shuffled[i] if i < len(shuffled) else ""
    return {
        "deckName": deck_name,
        "modelName": MC_MODEL,
        "fields": note_fields,
        "tags": ["mc-interactive"],
        "_source_nid": info["noteId"],
    }


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


def collect_curated_notes(cfg: CourseConfig, *, deck_override: str) -> list[dict]:
    notes: list[dict] = []
    for slug, item in load_curated_mc(cfg):
        ch = cfg.chapter_cfg(slug)
        deck = deck_override or ch.deck
        notes.append(mc_item_to_note(item, deck))
    return notes


def _norm_question(text: str) -> str:
    t = re.sub(r"^(☐ Ankreuzen:|Stimmt:)\s*", "", text.strip())
    t = re.sub(r"<[^>]+>", "", t.lower())
    return " ".join(re.sub(r"[^a-zäöüß0-9]+", " ", t).split())[:100]


def find_text_counterparts(cfg: CourseConfig, notes: list[dict]) -> list[int]:
    """Findet Einfach-Karten (Pseudo-MC ☐ / TF Stimmt:), deren Frage bereits
    als interaktive Karte importiert wird – sie wären sonst Duplikate."""
    locked = {e.note_id for e in cfg.locks.entries if e.note_id is not None}
    questions = {_norm_question(n["fields"]["Question"]) for n in notes}
    nids = invoke("findNotes", query=f'deck:"{cfg.deck}" note:Einfach')
    matches: list[int] = []
    for i in range(0, len(nids), 50):
        for info in invoke("notesInfo", notes=nids[i : i + 50]):
            if info["noteId"] in locked:
                continue
            front = info["fields"].get("Vorderseite", {}).get("value", "")
            if not (front.startswith("☐ Ankreuzen") or front.startswith("Stimmt:")):
                continue
            first_line = front.splitlines()[0]
            if _norm_question(first_line) in questions:
                matches.append(info["noteId"])
    return matches


def collect_migrate_notes(cfg: CourseConfig) -> tuple[list[dict], list[int]]:
    notes: list[dict] = []
    delete_ids: list[int] = []
    query = f'deck:"{cfg.deck}" "☐ Ankreuzen"'
    nids = invoke("findNotes", query=query)
    for i in range(0, len(nids), 50):
        for info in invoke("notesInfo", notes=nids[i : i + 50]):
            converted = parse_pseudo_mc_note(info, default_deck=cfg.deck)
            if converted:
                delete_ids.append(converted.pop("_source_nid"))
                notes.append(converted)
    return notes, delete_ids


def ensure_decks(notes: list[dict]) -> None:
    for deck in {n["deckName"] for n in notes if n.get("deckName")}:
        invoke("createDeck", deck=deck)


def import_notes(notes: list[dict]) -> tuple[int, int]:
    ensure_decks(notes)
    created = skipped = 0
    for note in notes:
        try:
            result = invoke("addNotes", notes=[note])
            if result and result[0]:
                created += 1
            else:
                skipped += 1
        except RuntimeError as e:
            if "duplicate" in str(e).lower():
                skipped += 1
            else:
                front = note["fields"].get("Question", "")[:60]
                raise RuntimeError(f"{e} | {front}") from e
    return created, skipped


def process_course(
    course_dir: Path,
    *,
    migrate: bool,
    deck_override: str,
    dry_run: bool,
    delete_pseudo: bool,
    keep_pseudo: bool = False,
) -> tuple[int, int, int, int]:
    try:
        cfg = load_course_config(course_dir)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 0, 0, 0, 0

    delete_ids: list[int] = []
    if migrate:
        notes, delete_ids = collect_migrate_notes(cfg)
        print(f"{course_dir.name}: Migration – {len(notes)} Pseudo-Karten")
    else:
        notes = collect_curated_notes(cfg, deck_override=deck_override)
        print(f"{course_dir.name}: Kuratiert – {len(notes)} MC/TF-Karten")
        if notes and not keep_pseudo:
            # Text-Import (Stufe 1) hat dieselben Fragen als Einfach-Karten angelegt
            # (Pseudo-MC ☐ / TF "Stimmt:") – nach dem interaktiven Import löschen,
            # sonst bleiben Duplikate zurück.
            delete_ids = find_text_counterparts(cfg, notes)
            if delete_ids:
                print(f"  Text-Duplikate (Pseudo/TF) zum Löschen: {len(delete_ids)}")

    if not notes and not delete_ids:
        return 0, 0, 0, 0

    if dry_run:
        for n in notes[:2]:
            print(f"  [{n['deckName']}] {n['fields']['Question'][:60]}…")
        if len(notes) > 2:
            print(f"  … und {len(notes) - 2} weitere")
        if delete_ids:
            print(f"  Würde löschen: {len(delete_ids)} Pseudo-Karten")
        return len(notes), 0, 0, len(delete_ids)

    created, skipped = import_notes(notes)
    if skipped:
        print(f"  Übersprungen (Duplikat): {skipped}")
    deleted = 0
    if delete_ids and (delete_pseudo or not migrate):
        invoke("deleteNotes", notes=delete_ids)
        deleted = len(delete_ids)
    return len(notes), created, skipped, deleted


def main() -> int:
    parser = argparse.ArgumentParser(description="Echte MC-Karten (anki-mc Add-on), kursübergreifend")
    parser.add_argument(
        "course_dir",
        nargs="?",
        type=Path,
        help='Kursordner mit anki.json, z. B. "lectures/semester4/Compiler"',
    )
    parser.add_argument(
        "--semester",
        type=Path,
        help="Alle Kurse unter diesem Ordner (z. B. lectures/semester4)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--migrate", action="store_true", help="Bestehende ☐-Pseudo-Karten ersetzen")
    parser.add_argument("--deck", default="", help="Ziel-Deck-Override (nur Kuratiert-Import)")
    parser.add_argument("--delete-pseudo", action="store_true", help="Nach Migration Pseudo-Karten löschen")
    parser.add_argument(
        "--keep-pseudo",
        action="store_true",
        help="Kuratiert-Import: Einfach-Duplikate (Pseudo-MC/TF) NICHT automatisch löschen",
    )
    args = parser.parse_args()

    if not args.course_dir and not args.semester:
        parser.error("course_dir oder --semester angeben")

    invoke("version")
    ensure_mc_model()

    if args.semester:
        course_dirs = discover_courses(args.semester)
    else:
        course_dirs = [args.course_dir.resolve()]

    total_notes = total_created = total_skipped = total_deleted = 0
    for course_dir in course_dirs:
        n, created, skipped, deleted = process_course(
            course_dir,
            migrate=args.migrate,
            deck_override=args.deck,
            dry_run=args.dry_run,
            delete_pseudo=args.delete_pseudo,
            keep_pseudo=args.keep_pseudo,
        )
        total_notes += n
        total_created += created
        total_skipped += skipped
        total_deleted += deleted

    if args.dry_run:
        print(f"Gesamt: {total_notes} Karten, {total_deleted} Löschungen (dry-run)")
    else:
        print(f"Importiert: {total_created}/{total_notes} echte MC-Karten ({total_skipped} Duplikate)")
        if total_deleted:
            print(f"Gelöscht: {total_deleted} Pseudo-Karten")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
