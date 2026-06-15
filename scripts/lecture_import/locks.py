"""Sperrliste für manuell überarbeitete Karten (nicht erneut generieren/überschreiben)."""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .norm import norm_key

MC_MODEL = "AllInOne (kprim, mc, sc)"
LOCK_FILE = "anki_locked.json"


@dataclass
class LockEntry:
    id: str
    match_keys: list[str]
    chapter: str | None = None
    note_id: int | None = None
    locked_at: str = ""
    comment: str = ""
    source: str = "anki"
    snapshot: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "match_keys": self.match_keys,
            "locked_at": self.locked_at,
            "source": self.source,
        }
        if self.chapter:
            data["chapter"] = self.chapter
        if self.note_id is not None:
            data["note_id"] = self.note_id
        if self.comment:
            data["comment"] = self.comment
        if self.snapshot:
            data["snapshot"] = self.snapshot
        return data

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> LockEntry:
        return cls(
            id=raw["id"],
            match_keys=list(raw.get("match_keys") or []),
            chapter=raw.get("chapter"),
            note_id=raw.get("note_id"),
            locked_at=raw.get("locked_at", ""),
            comment=raw.get("comment", ""),
            source=raw.get("source", "anki"),
            snapshot=raw.get("snapshot"),
        )


@dataclass
class LockRegistry:
    entries: list[LockEntry] = field(default_factory=list)

    @property
    def all_keys(self) -> set[str]:
        keys: set[str] = set()
        for entry in self.entries:
            keys.update(k for k in entry.match_keys if k)
        return keys

    def is_locked_key(self, key: str) -> bool:
        return bool(key) and key in self.all_keys

    def is_locked_note(self, note_id: int) -> bool:
        return any(e.note_id == note_id for e in self.entries)

    def find_by_id(self, lock_id: str) -> LockEntry | None:
        for entry in self.entries:
            if entry.id == lock_id:
                return entry
        return None

    def find_by_note_id(self, note_id: int) -> LockEntry | None:
        for entry in self.entries:
            if entry.note_id == note_id:
                return entry
        return None

    def add(self, entry: LockEntry) -> None:
        if entry.note_id is not None:
            self.entries = [e for e in self.entries if e.note_id != entry.note_id]
        self.entries.append(entry)

    def remove(self, *, lock_id: str | None = None, note_id: int | None = None) -> bool:
        before = len(self.entries)
        if lock_id:
            self.entries = [e for e in self.entries if e.id != lock_id]
        elif note_id is not None:
            self.entries = [e for e in self.entries if e.note_id != note_id]
        return len(self.entries) < before

    def to_dict(self) -> dict[str, Any]:
        return {"version": 1, "entries": [e.to_dict() for e in self.entries]}


def locks_path(cards_dir: Path) -> Path:
    return cards_dir / LOCK_FILE


def load_locks(cards_dir: Path) -> LockRegistry:
    path = locks_path(cards_dir)
    if not path.exists():
        return LockRegistry()
    raw = json.loads(path.read_text(encoding="utf-8"))
    return LockRegistry(entries=[LockEntry.from_dict(e) for e in raw.get("entries", [])])


def save_locks(cards_dir: Path, registry: LockRegistry) -> Path:
    cards_dir.mkdir(parents=True, exist_ok=True)
    path = locks_path(cards_dir)
    path.write_text(json.dumps(registry.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _unique_keys(*keys: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for key in keys:
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out


def keys_for_curated_item(item: dict) -> list[str]:
    typ = item.get("type", "basic")
    if typ == "luecke":
        return _unique_keys(norm_key(item.get("text", "")))
    front = item.get("front", "")
    keys = [norm_key(front)]
    if typ in ("mc", "tf", "sc"):
        bare = re.sub(r"^(☐ Ankreuzen:|Stimmt:)\s*", "", front).strip()
        keys.append(norm_key(bare))
    return _unique_keys(*keys)


def keys_for_anki_note(info: dict) -> list[str]:
    model = info.get("modelName", "")
    fields = {k: v["value"] for k, v in info["fields"].items()}
    if model == MC_MODEL:
        question = fields.get("Question", "")
        return _unique_keys(norm_key(question), norm_key(f"Stimmt: {question}"))
    if model == "Lückentext":
        return _unique_keys(norm_key(fields.get("Text", "")))
    front = fields.get("Vorderseite", "")
    keys = [norm_key(front)]
    bare = re.sub(r"^(☐ Ankreuzen:|Stimmt:)\s*", "", front).strip()
    keys.append(norm_key(bare))
    return _unique_keys(*keys)


def snapshot_from_curated_item(item: dict) -> dict[str, Any]:
    snap = dict(item)
    snap.pop("locked", None)
    return snap


def snapshot_from_anki_note(info: dict) -> dict[str, Any] | None:
    model = info.get("modelName", "")
    fields = {k: v["value"] for k, v in info["fields"].items()}
    if model == MC_MODEL:
        q = fields.get("Question", "").strip()
        qtype = fields.get("QType (0=kprim,1=mc,2=sc)", "2").strip()
        opts = [fields.get(f"Q_{i}", "").strip() for i in range(1, 6)]
        opts = [o for o in opts if o]
        answers = [a == "1" for a in fields.get("Answers", "").split()]
        if qtype == "2" and len(opts) == 2 and opts[0].lower().startswith("ja"):
            is_true = answers[0] if answers else True
            return {
                "type": "tf",
                "front": f"Stimmt: {q}",
                "back": f"{'✓' if is_true else '✗'} {q if is_true else 'Nein'}",
            }
        correct_idx = next((i for i, ok in enumerate(answers) if ok), 0)
        correct = opts[correct_idx] if correct_idx < len(opts) else ""
        distractors = [o for i, o in enumerate(opts) if i != correct_idx][:3]
        if not correct:
            return None
        return {"type": "mc", "front": q, "back": f"✓ {correct}", "distractors": distractors}
    if model == "Lückentext":
        text = fields.get("Text", "")
        if "{{c1::" not in text:
            return None
        return {"type": "luecke", "text": text}
    front = fields.get("Vorderseite", "")
    back = fields.get("Rückseite", "")
    if front.startswith("Stimmt:"):
        return {"type": "tf", "front": front, "back": back}
    if "☐ Ankreuzen" in front:
        return None
    return {"type": "basic", "front": front, "back": back}


def new_lock_entry(
    *,
    match_keys: list[str],
    chapter: str | None = None,
    note_id: int | None = None,
    comment: str = "",
    source: str = "anki",
    snapshot: dict[str, Any] | None = None,
) -> LockEntry:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return LockEntry(
        id=uuid.uuid4().hex[:12],
        match_keys=_unique_keys(*match_keys),
        chapter=chapter,
        note_id=note_id,
        locked_at=now,
        comment=comment,
        source=source,
        snapshot=snapshot,
    )


def merge_curated_locks(curated: dict[str, list[dict]], registry: LockRegistry) -> LockRegistry:
    """Einträge mit \"locked\": true in anki_curated.json in die Sperrliste aufnehmen."""
    merged = LockRegistry(entries=list(registry.entries))
    for chapter, items in curated.items():
        for item in items:
            if not item.get("locked"):
                continue
            keys = keys_for_curated_item(item)
            if any(merged.is_locked_key(k) for k in keys):
                continue
            merged.add(
                new_lock_entry(
                    match_keys=keys,
                    chapter=chapter,
                    source="curated",
                    snapshot=snapshot_from_curated_item(item),
                )
            )
    return merged


def is_curated_item_locked(item: dict, registry: LockRegistry) -> bool:
    if item.get("locked"):
        return True
    return any(registry.is_locked_key(k) for k in keys_for_curated_item(item))


def effective_curated_item(item: dict, registry: LockRegistry) -> dict:
    """Gesperrte Karten: Snapshot aus der Sperrliste hat Vorrang vor curated."""
    if not is_curated_item_locked(item, registry):
        return item
    keys = keys_for_curated_item(item)
    for entry in registry.entries:
        if entry.snapshot and any(k in entry.match_keys for k in keys):
            merged = dict(entry.snapshot)
            merged["locked"] = True
            return merged
    locked = dict(item)
    locked["locked"] = True
    return locked
