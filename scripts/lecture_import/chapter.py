"""Kapitel-Zuordnung aus Deck-Namen (ohne Kapitel-Tags)."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import CourseConfig


def chapter_from_deck(cfg: "CourseConfig", deck_name: str) -> str | None:
    if not deck_name:
        return None
    for slug, ch in cfg.chapters.items():
        if ch.deck == deck_name:
            return slug
    if cfg.deck and deck_name.startswith(f"{cfg.deck}::"):
        suffix = deck_name[len(cfg.deck) + 2 :]
        for slug, ch in cfg.chapters.items():
            if ch.deck.endswith(suffix) or slug == suffix:
                return slug
        return suffix
    return None


def chapter_from_note(cfg: "CourseConfig", info: dict, *, deck_name: str | None = None) -> str | None:
    if deck_name:
        ch = chapter_from_deck(cfg, deck_name)
        if ch:
            return ch
    # Legacy: alte Karten mit Kapitel-Tags (tag_prefix::slug)
    tags = info.get("tags") or []
    tag_set = set(tags)
    prefix = cfg.tag_prefix
    if prefix:
        for tag in tags:
            if tag.startswith(f"{prefix}::"):
                return tag.split("::", 1)[1]
    for slug in cfg.chapter_slugs():
        if slug in tag_set:
            return slug
    for tag in tags:
        if tag in tag_set and "::" in tag and tag not in {"mc-interactive", "io-stub", "auto-extracted"}:
            if not tag.startswith("wf::"):
                return tag.rsplit("::", 1)[-1]
    return None


def deck_from_note_info(info: dict, deck_lookup: dict[int, str] | None = None) -> str | None:
    if deck_lookup:
        for cid in info.get("cards") or []:
            if cid in deck_lookup:
                return deck_lookup[cid]
    return None
