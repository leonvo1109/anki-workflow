#!/usr/bin/env python3
"""
Lern-Session: Workflow-Tags aus Anki auslesen und für die KI aufbereiten.

Ablauf:
  1. Beim Lernen Karten mit wf::fix::* oder wf::lock taggen, dann Easy.
  2. Nach der Session:
       python scripts/process_session_tags.py "{Kurs}"
  3. Im Chat: „Session-Tags auswerten“ – KI liest cards/session_queue.json.

Weitere Optionen:
  --list-tags     Verfügbare wf:: Tags anzeigen
  --sync-locks    wf::lock → anki_locked.json (Sperrliste)
  --complete      wf::fix::* entfernen, wf::done setzen (nach KI-Arbeit)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lecture_import.anki_client import AnkiClient
from lecture_import.chapter import chapter_from_note, deck_from_note_info
from lecture_import.config import load_course_config
from lecture_import.locks import (
    keys_for_anki_note,
    load_locks,
    merge_curated_locks,
    new_lock_entry,
    save_locks,
    snapshot_from_anki_note,
)
from lecture_import.workflow_tags import (
    FIX_TAGS,
    WF_DONE,
    WF_LOCK,
    fix_tags_on,
    format_tag_help,
    is_fix_tag,
    is_workflow_tag,
)

QUEUE_FILE = "session_queue.json"
MC_MODEL = "AllInOne (kprim, mc, sc)"


def note_preview(info: dict) -> dict:
    model = info.get("modelName", "")
    fields = {k: v["value"] for k, v in info["fields"].items()}
    if model == MC_MODEL:
        return {
            "model": model,
            "question": fields.get("Question", ""),
            "extra": fields.get("Extra 1", ""),
            "options": [fields.get(f"Q_{i}", "") for i in range(1, 6) if fields.get(f"Q_{i}", "").strip()],
        }
    if model == "Lückentext":
        return {"model": model, "text": fields.get("Text", "")}
    return {
        "model": model,
        "front": fields.get("Vorderseite", fields.get("Text", "")),
        "back": fields.get("Rückseite", ""),
    }


def collect_workflow_notes(cfg, client: AnkiClient) -> list[dict]:
    all_nids: set[int] = set()
    search_tags = [WF_LOCK, *FIX_TAGS.keys()]
    for tag in search_tags:
        found = client.invoke("findNotes", query=f'deck:"{cfg.deck}" tag:"{tag}"')
        all_nids.update(found)

    if not all_nids:
        return []

    infos: list[dict] = []
    nids_list = sorted(all_nids)
    for i in range(0, len(nids_list), 50):
        infos.extend(client.invoke("notesInfo", notes=nids_list[i : i + 50]))

    deck_lookup: dict[int, str] = {}
    all_cids: list[int] = []
    for info in infos:
        all_cids.extend(info.get("cards") or [])
    for i in range(0, len(all_cids), 100):
        for card in client.invoke("cardsInfo", cards=all_cids[i : i + 100]):
            deck_lookup[card["cardId"]] = card.get("deckName", "")

    items: list[dict] = []
    for info in infos:
        tags = info.get("tags") or []
        wf_tags = [t for t in tags if is_workflow_tag(t)]
        fix_tags = fix_tags_on(tags)
        locked = WF_LOCK in tags
        if not fix_tags and not locked:
            continue

        deck_name = deck_from_note_info(info, deck_lookup) or ""
        chapter = chapter_from_note(cfg, info, deck_name=deck_name)
        fix_hints = [FIX_TAGS.get(t, t) for t in fix_tags]

        items.append({
            "note_id": info["noteId"],
            "deck": deck_name,
            "chapter": chapter,
            "fix_tags": fix_tags,
            "fix_hints": fix_hints,
            "locked": locked,
            "preview": note_preview(info),
        })
    return items


def export_queue(cfg, items: list[dict]) -> Path:
    path = cfg.cards_dir / QUEUE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "course_dir": str(cfg.course_dir),
        "deck": cfg.deck,
        "count": len(items),
        "items": items,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def print_queue(items: list[dict]) -> None:
    if not items:
        print("Keine offenen Session-Tags (wf::fix::* oder wf::lock).")
        return
    print(f"{len(items)} Karte(n) mit Session-Tags:")
    for item in items:
        tags = ", ".join(item["fix_tags"])
        if item["locked"]:
            tags = (tags + ", " if tags else "") + WF_LOCK
        preview = item["preview"].get("front") or item["preview"].get("question") or item["preview"].get("text", "")
        ch = f" [{item['chapter']}]" if item.get("chapter") else ""
        print(f"  nid:{item['note_id']}{ch}  {tags}")
        print(f"    {preview[:80]!r}")


def sync_locks_from_tags(cfg, client: AnkiClient) -> int:
    nids = client.invoke("findNotes", query=f'deck:"{cfg.deck}" tag:"{WF_LOCK}"')
    if not nids:
        print("Keine Karten mit wf::lock.")
        return 0

    registry = merge_curated_locks(cfg.curated, load_locks(cfg.cards_dir))
    synced = 0
    deck_lookup: dict[int, str] = {}

    for i in range(0, len(nids), 50):
        batch = nids[i : i + 50]
        infos = client.invoke("notesInfo", notes=batch)
        cids = [c for info in infos for c in (info.get("cards") or [])]
        for j in range(0, len(cids), 100):
            for card in client.invoke("cardsInfo", cards=cids[j : j + 100]):
                deck_lookup[card["cardId"]] = card.get("deckName", "")

        for info in infos:
            keys = keys_for_anki_note(info)
            if not keys:
                continue
            deck_name = deck_from_note_info(info, deck_lookup)
            chapter = chapter_from_note(cfg, info, deck_name=deck_name)
            snapshot = snapshot_from_anki_note(info)
            entry = new_lock_entry(
                match_keys=keys,
                chapter=chapter,
                note_id=info["noteId"],
                comment="wf::lock",
                source="anki",
                snapshot=snapshot,
            )
            registry.add(entry)
            synced += 1

    save_locks(cfg.cards_dir, registry)
    print(f"sync-locks: {synced} Karte(n) → anki_locked.json")
    return synced


def complete_session(cfg, client: AnkiClient, *, dry_run: bool = False) -> int:
    items = collect_workflow_notes(cfg, client)
    done = 0
    for item in items:
        nid = item["note_id"]
        remove = [t for t in item["fix_tags"] if is_fix_tag(t)]
        if not remove and not item["locked"]:
            continue
        if dry_run:
            print(f"[dry-run] nid:{nid}: entferne {remove}, setze {WF_DONE}")
            done += 1
            continue
        for tag in remove:
            client.invoke("removeTags", notes=[nid], tags=tag)
        client.invoke("addTags", notes=[nid], tags=WF_DONE)
        done += 1
    print(f"complete: {done} Karte(n) abgearbeitet ({WF_DONE} gesetzt, fix-Tags entfernt)")
    return done


def main() -> int:
    parser = argparse.ArgumentParser(description="Workflow-Tags aus Anki-Sessions auswerten")
    parser.add_argument("course_dir", nargs="?", type=Path, help='Kursordner, z. B. "lectures/semester4/Compiler"')
    parser.add_argument("--list-tags", action="store_true", help="Verfügbare wf:: Tags anzeigen")
    parser.add_argument("--sync-locks", action="store_true", help="wf::lock → anki_locked.json")
    parser.add_argument("--complete", action="store_true", help="Fix-Tags entfernen, wf::done setzen")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.list_tags:
        print(format_tag_help())
        return 0

    if not args.course_dir:
        parser.error("course_dir angeben (außer mit --list-tags)")

    try:
        cfg = load_course_config(args.course_dir)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 1

    client = AnkiClient()
    client.ping()

    if args.sync_locks:
        sync_locks_from_tags(cfg, client)
        return 0

    if args.complete:
        complete_session(cfg, client, dry_run=args.dry_run)
        return 0

    items = collect_workflow_notes(cfg, client)
    path = export_queue(cfg, items)
    print_queue(items)
    print(f"\nQueue: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
