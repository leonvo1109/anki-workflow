#!/usr/bin/env python3
"""
Erstellt: 2026-06-11
Kurzbeschreibung: Qualitätsprüfung für Karten – kuratierte JSON-Dateien und (optional)
das Live-Deck in Anki. Findet Artefakte, bevor/nachdem sie importiert werden.

Nutzung:
  python scripts/lint_cards.py "lectures/semester4/{Kurs}"          # nur curated JSON
  python scripts/lint_cards.py "lectures/semester4/{Kurs}" --live   # zusätzlich Anki-Deck

Geprüfte Artefaktklassen:
  curated: fehlende Pflichtfelder, Meta-Karten (Klausurrelevanz statt Stoff),
           doppelte Fronten, falsche MC/TF-Formate, Reste wie "(exam)" oder "…"
  live:    Einfach-Duplikate zu interaktiven MC/TF-Karten, Pseudo-MC-Reste,
           veraltete Antwortbuchstaben in "Extra 1", leere Felder
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lecture_import.locks import (
    keys_for_curated_item,
    load_locks,
    merge_curated_locks,
    snapshot_from_curated_item,
    is_curated_item_locked,
)


def norm(text: str) -> str:
    t = re.sub(r"^(☐ Ankreuzen:|Stimmt:)\s*", "", text.strip())
    t = re.sub(r"<[^>]+>", "", t.lower())
    return " ".join(re.sub(r"[^a-zäöüß0-9]+", " ", t).split())[:100]


def lint_curated(course_dir: Path) -> list[str]:
    issues: list[str] = []
    path = course_dir / "cards" / "anki_curated.json"
    if not path.exists():
        return [f"FEHLT: {path}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"Ungültiges JSON: {path}: {e}"]

    # Getrennte Namensräume: MC/TF darf bewusst Wissen von Basic-Karten wiederholen
    # (project_config.md: Redundanz über Kartentypen erlaubt).
    fronts: dict[tuple[str, str], str] = {}
    for chapter, items in data.items():
        for idx, item in enumerate(items):
            where = f"{chapter}[{idx}]"
            typ = item.get("type", "")
            if typ not in KNOWN_TYPES:
                issues.append(f"{where}: unbekannter type '{typ}'")
                continue
            if typ == "luecke":
                if "{{c1::" not in item.get("text", ""):
                    issues.append(f"{where}: Lückentext ohne {{{{c1::…}}}}")
                continue

            front = item.get("front", "").strip()
            back = item.get("back", "").strip()
            if not front or not back:
                issues.append(f"{where}: front/back leer")
                continue
            for label, txt in (("front", front), ("back", back)):
                if META_RE.search(txt):
                    issues.append(f"{where}: Meta-Inhalt in {label} (Klausurorganisation statt Stoff): {txt[:60]!r}")
                if txt.endswith("…"):
                    issues.append(f"{where}: abgeschnittener Text in {label}: {txt[-40:]!r}")
                if "☐" in txt:
                    issues.append(f"{where}: ☐-Pseudo-Markierung in {label} – nicht manuell anlegen")

            group = "interactive" if typ in ("mc", "sc", "tf") else "text"
            key = (group, norm(front))
            if key in fronts:
                issues.append(f"{where}: doppelte Front (auch in {fronts[key]}): {front[:60]!r}")
            fronts[key] = where

            if typ in ("mc", "sc"):
                d = item.get("distractors", [])
                if len(d) != 3:
                    issues.append(f"{where}: mc/sc braucht genau 3 distractors (hat {len(d)})")
                if not back.startswith("✓"):
                    issues.append(f"{where}: mc/sc back muss mit '✓ ' beginnen")
                if back.replace("✓ ", "").strip() in d:
                    issues.append(f"{where}: richtige Antwort auch in distractors")
            if typ == "tf":
                if not front.startswith("Stimmt:"):
                    issues.append(f"{where}: tf front muss mit 'Stimmt:' beginnen")
                if not (back.startswith("✓") or back.startswith("✗")):
                    issues.append(f"{where}: tf back muss mit ✓ oder ✗ beginnen")
    return issues


def lint_locked(course_dir: Path) -> list[str]:
    issues: list[str] = []
    cards_dir = course_dir / "cards"
    curated_path = cards_dir / "anki_curated.json"
    curated: dict = {}
    if curated_path.exists():
        curated = json.loads(curated_path.read_text(encoding="utf-8"))
    registry = merge_curated_locks(curated, load_locks(cards_dir))
    if not registry.entries:
        return issues

    for entry in registry.entries:
        if not entry.snapshot or not entry.chapter:
            continue
        items = curated.get(entry.chapter, [])
        for idx, item in enumerate(items):
            if not any(k in keys_for_curated_item(item) for k in entry.match_keys):
                continue
            if is_curated_item_locked(item, registry):
                snap = snapshot_from_curated_item(item)
                for key in ("front", "back", "text"):
                    if key in entry.snapshot and snap.get(key) != entry.snapshot.get(key):
                        issues.append(
                            f"LOCK-DRIFT {entry.chapter}[{idx}] ({entry.id}): "
                            f"curated.{key} weicht vom gesperrten Snapshot ab"
                        )
                break
    return issues


def lint_live(course_dir: Path) -> list[str]:
    from lecture_import.anki_client import AnkiClient
    from lecture_import.config import load_course_config

    issues: list[str] = []
    cfg = load_course_config(course_dir)
    client = AnkiClient()
    client.ping()

    nids = client.invoke("findNotes", query=f'deck:"{cfg.deck}"')
    infos = []
    for i in range(0, len(nids), 100):
        infos.extend(client.invoke("notesInfo", notes=nids[i : i + 100]))

    interactive_questions = set()
    for info in infos:
        if info["modelName"] == MC_MODEL:
            interactive_questions.add(norm(info["fields"]["Question"]["value"]))

    front_keys: dict[str, int] = {}
    for info in infos:
        nid = info["noteId"]
        fields = {k: v["value"] for k, v in info["fields"].items()}

        if info["modelName"] == MC_MODEL:
            q = fields.get("Question", "")
            extra = fields.get("Extra 1", "")
            if not q.strip():
                issues.append(f"nid:{nid}: leere Question")
            if re.match(r"^[✓✗]\s*\([A-E]\)", extra):
                issues.append(f"nid:{nid}: Antwortbuchstabe in Extra 1 (nach Shuffle ungültig): {extra[:50]!r}")
            opts = [fields.get(f"Q_{i}", "") for i in range(1, 6)]
            answers = fields.get("Answers", "").split()
            if len([o for o in opts if o.strip()]) != len(answers):
                issues.append(f"nid:{nid}: Optionen ({len([o for o in opts if o.strip()])}) ≠ Answers ({len(answers)})")
            if META_RE.search(q) or META_RE.search(extra):
                issues.append(f"nid:{nid}: Meta-Inhalt: {q[:60]!r}")
            continue

        front = fields.get("Vorderseite") or fields.get("Text", "")
        back = fields.get("Rückseite", "")
        if front.startswith("☐ Ankreuzen") and norm(front.splitlines()[0]) in interactive_questions:
            issues.append(f"nid:{nid}: Pseudo-MC-Duplikat einer interaktiven Karte: {front[:60]!r}")
        if front.startswith("Stimmt:") and norm(front) in interactive_questions:
            issues.append(f"nid:{nid}: TF-Einfach-Duplikat einer interaktiven Karte: {front[:60]!r}")
        if META_RE.search(front) or META_RE.search(back):
            issues.append(f"nid:{nid}: Meta-Inhalt: {front[:60]!r}")
        if "(exam)" in front or "(exam)" in back:
            issues.append(f"nid:{nid}: '(exam)'-Artefakt: {front[:60]!r}")
        if not back.strip() and info["modelName"] == "Einfach":
            issues.append(f"nid:{nid}: leere Rückseite: {front[:60]!r}")

        key = norm(front)
        if key and key in front_keys:
            issues.append(f"nid:{nid}: doppelte Front (auch nid:{front_keys[key]}): {front[:60]!r}")
        front_keys[key] = nid
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Karten-Qualitätsprüfung (curated JSON + optional Live-Deck)")
    parser.add_argument("course_dir", type=Path, help='Kursordner, z. B. "lectures/semester4/Compiler"')
    parser.add_argument("--live", action="store_true", help="Zusätzlich das Anki-Deck prüfen (AnkiConnect)")
    args = parser.parse_args()

    course_dir = args.course_dir.resolve()
    issues = lint_curated(course_dir) + lint_locked(course_dir)
    label = "curated"
    if args.live:
        issues += lint_live(course_dir)
        label = "curated + live"

    if issues:
        print(f"{len(issues)} Problem(e) gefunden ({label}):")
        for i in issues:
            print(f"  - {i}")
        return 1
    print(f"OK – keine Probleme gefunden ({label}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
