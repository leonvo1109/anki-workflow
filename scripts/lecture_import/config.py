"""Kurs-Konfiguration aus anki.json + cards/anki_*.json."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ChapterConfig:
    slug: str
    deck: str
    tag: str
    auto_mode: str = "full"  # full | curated-only | skip


@dataclass
class CourseConfig:
    course_dir: Path
    deck: str
    tag_prefix: str
    parse_body_bullets: bool = False
    max_per_slide: int = 2
    filters: dict = field(default_factory=dict)
    chapters: dict[str, ChapterConfig] = field(default_factory=dict)
    curated: dict[str, list[dict]] = field(default_factory=dict)
    cleanup: dict = field(default_factory=dict)

    @property
    def processed_dir(self) -> Path:
        return self.course_dir / "processed"

    @property
    def cards_dir(self) -> Path:
        return self.course_dir / "cards"

    def chapter_slugs(self, selected: list[str] | None = None) -> list[str]:
        if selected:
            return selected
        if self.chapters:
            return sorted(self.chapters.keys())
        if not self.processed_dir.is_dir():
            return []
        return sorted(p.name for p in self.processed_dir.iterdir() if p.is_dir() and (p / "slides.json").exists())

    def chapter_cfg(self, slug: str) -> ChapterConfig:
        if slug in self.chapters:
            return self.chapters[slug]
        tag = f"{self.tag_prefix}::{slug}" if self.tag_prefix else slug
        return ChapterConfig(slug=slug, deck=self.deck, tag=tag)


def load_course_config(course_dir: Path) -> CourseConfig:
    course_dir = course_dir.resolve()
    anki_path = course_dir / "anki.json"
    if not anki_path.exists():
        raise FileNotFoundError(
            f"Kurs-Konfiguration fehlt: {anki_path}\n"
            "Lege anki.json im Kursordner an (siehe lectures/_template/anki.json)."
        )

    raw = json.loads(anki_path.read_text(encoding="utf-8"))
    deck = raw["deck"]
    tag_prefix = raw.get("tag_prefix", "")

    chapters: dict[str, ChapterConfig] = {}
    for slug, ch in (raw.get("chapters") or {}).items():
        ch_deck = ch.get("deck") or deck
        if ch.get("deck_suffix"):
            ch_deck = f"{deck}::{ch['deck_suffix']}"
        tag_suffix = ch.get("tag") or slug
        tag = tag_suffix if "::" in tag_suffix else (f"{tag_prefix}::{tag_suffix}" if tag_prefix else tag_suffix)
        chapters[slug] = ChapterConfig(
            slug=slug,
            deck=ch_deck,
            tag=tag,
            auto_mode=ch.get("auto_mode", "full"),
        )

    cards_dir = course_dir / "cards"
    curated: dict[str, list[dict]] = {}
    curated_path = cards_dir / "anki_curated.json"
    if curated_path.exists():
        curated = json.loads(curated_path.read_text(encoding="utf-8"))

    cleanup: dict = {}
    cleanup_path = cards_dir / "anki_cleanup.json"
    if cleanup_path.exists():
        cleanup = json.loads(cleanup_path.read_text(encoding="utf-8"))

    return CourseConfig(
        course_dir=course_dir,
        deck=deck,
        tag_prefix=tag_prefix,
        parse_body_bullets=bool(raw.get("parse_body_bullets")),
        max_per_slide=int(raw.get("max_per_slide", 2)),
        filters=raw.get("filters") or {},
        chapters=chapters,
        curated=curated,
        cleanup=cleanup,
    )
