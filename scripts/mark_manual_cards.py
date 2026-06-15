#!/usr/bin/env python3
"""
Manuell überarbeitete Karten sperren (anki_locked.json).

Bevorzugt: In Anki Tag wf::lock setzen, dann:
  python scripts/process_session_tags.py "{Kurs}" --sync-locks

Alternativ weiterhin per Notiz-ID oder kuratiertem Index.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lecture_import.anki_client import AnkiClient
from lecture_import.chapter import chapter_from_note
from lecture_import.config import load_course_config
from lecture_import.locks import (
    keys_for_anki_note,
    keys_for_curated_item,
    load_locks,
    merge_curated_locks,
    new_lock_entry,
    save_locks,
    snapshot_from_anki_note,
    snapshot_from_curated_item,
    is_curated_item_locked,
)
from lecture_import.workflow_tags import WF_LOCK


def lock_note(
    cfg,
    client: AnkiClient,
    note_id: int,
    *,
    chapter: str | None,
    comment: str,
) -> str:
    infos = client.invoke("notesInfo", notes=[note_id])
    if not infos:
        raise SystemExit(f"Notiz nicht gefunden: {note_id}")
    info = infos[0]
    keys = keys_for_anki_note(info)
    if not keys:
        raise SystemExit(f"Keine match_keys für nid {note_id}")

    deck_name = None
    if info.get("cards"):
        cards = client.invoke("cardsInfo", cards=info["cards"][:1])
        if cards:
            deck_name = cards[0].get("deckName")
    ch = chapter or chapter_from_note(cfg, info, deck_name=deck_name)
    snapshot = snapshot_from_anki_note(info)
    registry = merge_curated_locks(cfg.curated, load_locks(cfg.cards_dir))
    entry = new_lock_entry(
        match_keys=keys,
        chapter=ch,
        note_id=note_id,
        comment=comment,
        source="anki",
        snapshot=snapshot,
    )
    registry.add(entry)
    path = save_locks(cfg.cards_dir, registry)
    client.invoke("addTags", notes=[note_id], tags=WF_LOCK)
    fields = info["fields"]
    front = fields.get("Vorderseite", fields.get("Question", {})).get("value", "")[:70]
    return f"Gesperrt nid:{note_id} → {path.name} ({front!r})"


def lock_curated(cfg, chapter: str, index: int, *, comment: str) -> str:
    items = cfg.curated.get(chapter)
    if items is None:
        raise SystemExit(f"Kapitel fehlt in anki_curated.json: {chapter}")
    if index < 0 or index >= len(items):
        raise SystemExit(f"Index außerhalb: {chapter}[{index}] (hat {len(items)} Einträge)")

    item = items[index]
    keys = keys_for_curated_item(item)
    registry = merge_curated_locks(cfg.curated, load_locks(cfg.cards_dir))
    entry = new_lock_entry(
        match_keys=keys,
        chapter=chapter,
        comment=comment,
        source="curated",
        snapshot=snapshot_from_curated_item(item),
    )
    registry.add(entry)

    curated_path = cfg.cards_dir / "anki_curated.json"
    data = json.loads(curated_path.read_text(encoding="utf-8"))
    data[chapter][index]["locked"] = True
    curated_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    path = save_locks(cfg.cards_dir, registry)
    front = item.get("front") or item.get("text", "")[:70]
    return f"Gesperrt {chapter}[{index}] → {path.name} ({front!r})"


def list_locks(cfg) -> int:
    registry = merge_curated_locks(cfg.curated, load_locks(cfg.cards_dir))
    if not registry.entries:
        print("Keine gesperrten Karten.")
        return 0
    print(f"{len(registry.entries)} gesperrte Karte(n):")
    for entry in registry.entries:
        preview = ""
        if entry.snapshot:
            preview = entry.snapshot.get("front") or entry.snapshot.get("text", "")
        elif entry.note_id:
            preview = f"nid:{entry.note_id}"
        line = f"  {entry.id}"
        if entry.note_id:
            line += f"  nid:{entry.note_id}"
        if entry.chapter:
            line += f"  [{entry.chapter}]"
        if preview:
            line += f"  {preview[:60]!r}"
        if entry.comment:
            line += f"  // {entry.comment}"
        print(line)
    return 0


def sync_curated(cfg, client: AnkiClient) -> int:
    registry = merge_curated_locks(cfg.curated, load_locks(cfg.cards_dir))
    curated_path = cfg.cards_dir / "anki_curated.json"
    if not curated_path.exists():
        curated_path.parent.mkdir(parents=True, exist_ok=True)
        data: dict[str, list] = {}
    else:
        data = json.loads(curated_path.read_text(encoding="utf-8"))

    updated = 0
    for entry in registry.entries:
        snapshot = entry.snapshot
        if entry.note_id:
            infos = client.invoke("notesInfo", notes=[entry.note_id])
            if infos:
                fresh = snapshot_from_anki_note(infos[0])
                if fresh:
                    snapshot = fresh
                    entry.snapshot = fresh

        if not snapshot or not entry.chapter:
            continue

        chapter = entry.chapter
        items = data.setdefault(chapter, [])
        keys = set(entry.match_keys)
        target_idx = None
        for idx, item in enumerate(items):
            if any(k in keys_for_curated_item(item) for k in keys):
                target_idx = idx
                break

        payload = dict(snapshot)
        payload["locked"] = True
        if target_idx is None:
            items.append(payload)
        else:
            items[target_idx] = payload
        updated += 1

    if updated:
        curated_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        save_locks(cfg.cards_dir, registry)
    print(f"sync-curated: {updated} Eintrag/Einträge in {curated_path.name} aktualisiert.")
    return 0


def unlock_entry(cfg, token: str) -> int:
    registry = merge_curated_locks(cfg.curated, load_locks(cfg.cards_dir))
    removed = False
    if token.isdigit():
        removed = registry.remove(note_id=int(token))
        if not removed:
            removed = registry.remove(lock_id=token)
    else:
        removed = registry.remove(lock_id=token)

    if not removed:
        raise SystemExit(f"Keine Sperre gefunden für: {token}")

    save_locks(cfg.cards_dir, registry)

    curated_path = cfg.cards_dir / "anki_curated.json"
    if curated_path.exists():
        data = json.loads(curated_path.read_text(encoding="utf-8"))
        changed = False
        for chapter, items in data.items():
            for item in items:
                if "locked" not in item:
                    continue
                if not is_curated_item_locked(item, registry):
                    item.pop("locked")
                    changed = True
        if changed:
            curated_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Sperre aufgehoben: {token}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Manuell überarbeitete Karten sperren (anki_locked.json)")
    parser.add_argument("course_dir", type=Path, help='Kursordner, z. B. "lectures/semester4/Compiler"')
    parser.add_argument("--note-id", action="append", type=int, default=[], metavar="NID", help="Anki-Notiz-ID")
    parser.add_argument("--chapter", help="Kapitel-Slug (optional bei --note-id)")
    parser.add_argument("--comment", default="", help="Kurznotiz warum gesperrt")
    parser.add_argument("--curated", nargs=2, metavar=("KAPITEL", "INDEX"), help="Kuratierten Eintrag sperren")
    parser.add_argument("--list", action="store_true", help="Gesperrte Karten anzeigen")
    parser.add_argument("--sync-curated", action="store_true", help="Gesperrte Karten nach anki_curated.json schreiben")
    parser.add_argument("--unlock", metavar="ID", help="Lock-ID oder Anki note-id")
    args = parser.parse_args()

    try:
        cfg = load_course_config(args.course_dir)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 1

    if args.list:
        return list_locks(cfg)

    if args.unlock:
        return unlock_entry(cfg, args.unlock)

    if args.sync_curated:
        client = AnkiClient()
        client.ping()
        return sync_curated(cfg, client)

    if args.curated:
        chapter, idx_s = args.curated
        if not idx_s.isdigit():
            print("INDEX muss eine Zahl sein", file=sys.stderr)
            return 1
        print(lock_curated(cfg, chapter, int(idx_s), comment=args.comment))
        return 0

    if not args.note_id:
        parser.error("Mindestens --note-id, --curated, --list, --sync-curated oder --unlock angeben")

    client = AnkiClient()
    client.ping()
    for nid in args.note_id:
        print(lock_note(cfg, client, nid, chapter=args.chapter, comment=args.comment))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
