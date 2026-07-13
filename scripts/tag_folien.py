#!/usr/bin/env python3
"""Tag Anki notes: folie-XX, uebung, praktikum-NN."""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from lecture_import.anki_client import AnkiClient
from lecture_import.config import load_course_config
from lecture_import.norm import norm_key
from lecture_import.source_index import (
    PageEntry,
    SourceIndex,
    build_curated_index,
    classify_pdf,
    load_processed_pages,
    match_note,
    pages_from_pdf,
)
from lecture_import.workflow_tags import PIPELINE_TAGS, is_workflow_tag

FOLIE_UNKNOWN = "folie-unbekannt"

DECK_UEBUNG_HINTS: dict[str, tuple[str, ...]] = {
    "speichermanagement": ("speichermanagement", "speicher"),
    "dateisysteme": ("dateisystem",),
    "scheduling": ("scheduling",),
    "synchronisation": ("synchron",),
    "prozesse": ("prozess", "thread"),
}

UEBUNG_SLUG_DECK_LEAF: dict[str, str] = {
    "uebungsblatt-speichermanagement": "speichermanagement",
    "uebungsblatt-dateisysteme": "dateisysteme",
    "uebungsblatt-scheduling": "scheduling",
    "uebungsblatt-synchronisation": "synchronisation",
}

REDUNDANT_EXACT = frozenset(
    {
        "vorlesung",
        "auto-extracted",
        "speicher",
        "dateisysteme",
        "scheduling",
        "sync",
        "synchronisation",
    }
)
REDUNDANT_PREFIXES = ("kapitel", "quelle-", "betriebssysteme", "compiler", "datenschutz", "cgbv")


def is_redundant_tag(tag: str) -> bool:
    if tag in PIPELINE_TAGS or is_workflow_tag(tag):
        return False
    if tag == "uebung" or tag.startswith(("folie-", "praktikum-", "uebung-")):
        return False
    if tag in REDUNDANT_EXACT:
        return True
    return any(tag.startswith(p) for p in REDUNDANT_PREFIXES)


def note_texts(info: dict) -> list[str]:
    model = info.get("modelName", "")
    fields = {k: v["value"] for k, v in info["fields"].items()}
    texts: list[str] = []
    if model == "AllInOne (kprim, mc, sc)":
        texts.extend(
            [
                fields.get("Question", ""),
                fields.get("Extra 1", ""),
                *[fields.get(f"Q_{i}", "") for i in range(1, 6)],
            ]
        )
    elif model == "Lückentext":
        texts.extend([fields.get("Text", ""), fields.get("Rückseite Extra", "")])
    elif model == "Image Occlusion Enhanced":
        texts.extend(
            [
                fields.get("Header", ""),
                fields.get("Footer", ""),
                fields.get("Remarks", ""),
                fields.get("Extra 1", ""),
            ]
        )
    else:
        texts.extend([fields.get("Vorderseite", ""), fields.get("Rückseite", "")])
    return [t for t in texts if t and t.strip()]


def deck_for_note(info: dict, deck_lookup: dict[int, str]) -> str:
    for cid in info.get("cards") or []:
        if cid in deck_lookup:
            return deck_lookup[cid]
    return ""


def folie_tag(page: int | None) -> str:
    return f"folie-{page:02d}" if page else FOLIE_UNKNOWN


def source_tags(kind: str, tag: str) -> list[str]:
    """Extra tags beyond folie-XX."""
    if kind == "uebung":
        extras = ["uebung"]
        if tag.startswith("uebung-aufgabe-"):
            extras.append(tag)
        return extras
    if kind == "praktikum" and tag.startswith("praktikum-"):
        return [tag]
    return []


def resolve_tags(
    texts: list[str],
    index: SourceIndex,
    *,
    prefer_uebung: bool = False,
) -> list[str]:
    hit = match_note(texts, index)
    uebung_hit = match_note(texts, index, prefer=["uebung", "vorlesung"])

    if prefer_uebung and uebung_hit:
        hit = uebung_hit
    elif uebung_hit and hit and uebung_hit[1] == "uebung" and hit[1] == "vorlesung":
        hit = uebung_hit
    elif not hit and uebung_hit:
        hit = uebung_hit

    if not hit:
        return [FOLIE_UNKNOWN]
    page, kind, src_tag = hit
    tags = [folie_tag(page)]
    tags.extend(source_tags(kind, src_tag))
    return sorted(set(tags))


def clean_tags(old_tags: list[str], new_source_tags: list[str]) -> list[str]:
    kept = [
        t
        for t in old_tags
        if not t.startswith("folie-")
        and not t.startswith("praktikum-")
        and not t.startswith("uebung")
        and t != "uebung"
        and not is_redundant_tag(t)
    ]
    kept.extend(new_source_tags)
    return sorted(set(kept))


def uebung_pages_for_deck(
    all_uebung: list[PageEntry],
    deck_uebung: dict[str, list[PageEntry]],
    deck_name: str,
) -> list[PageEntry]:
    if deck_name in deck_uebung and deck_uebung[deck_name]:
        return list(deck_uebung[deck_name])
    leaf = deck_name.split("::")[-1].lower()
    for key, hints in DECK_UEBUNG_HINTS.items():
        if key in leaf:
            filtered = [p for p in all_uebung if any(h in p.norm for h in hints)]
            return filtered or all_uebung
    return all_uebung


def build_full_course_index(cfg) -> tuple[SourceIndex, dict[str, SourceIndex]]:
    """Course-wide index plus per-deck lecture subsets."""
    full = SourceIndex()
    slug_pages: dict[str, list[PageEntry]] = {}
    deck_lecture: dict[str, list[PageEntry]] = defaultdict(list)
    deck_uebung: dict[str, list[PageEntry]] = defaultdict(list)

    deck_map: dict[str, list[str]] = defaultdict(list)
    for slug, ch in cfg.chapters.items():
        deck_map[ch.deck].append(slug)

    if cfg.processed_dir.is_dir():
        for slug_dir in sorted(cfg.processed_dir.iterdir()):
            if not slug_dir.is_dir():
                continue
            pages = load_processed_pages(slug_dir)
            if not pages:
                continue
            slug = slug_dir.name
            slug_pages[slug] = pages
            kind = pages[0].source_kind
            tag = pages[0].source_tag
            if kind == "vorlesung":
                full.lecture.extend(pages)
                for deck, slugs in deck_map.items():
                    if slug in slugs:
                        deck_lecture[deck].extend(pages)
            elif kind == "uebung":
                full.uebung.extend(pages)
                leaf = UEBUNG_SLUG_DECK_LEAF.get(slug)
                if leaf:
                    for deck in deck_map:
                        if leaf in deck.split("::")[-1].lower():
                            deck_uebung[deck].extend(pages)
            elif kind == "praktikum":
                full.praktika.setdefault(tag, []).extend(pages)

    raw = cfg.course_dir / "raw"
    if raw.is_dir():
        for pdf in sorted(raw.rglob("*.pdf")):
            lower = pdf.name.lower()
            if "musterloesung" in lower or "loesung" in lower or "do-not-read" in lower:
                continue
            kind, tag = classify_pdf(pdf)
            if kind == "skip":
                continue
            # Skip wenn bereits unter processed/ extrahiert
            stem_norm = pdf.stem.lower().replace("ü", "u").replace("ö", "o")
            already = any(
                stem_norm.replace("_", "-") in d.name
                for d in cfg.processed_dir.iterdir()
                if d.is_dir() and (d / "slides.json").exists()
            ) if cfg.processed_dir.is_dir() else False
            if already:
                continue
            pages = pages_from_pdf(pdf, source_kind=kind, source_tag=tag)
            if not pages:
                continue
            if kind == "vorlesung":
                full.lecture.extend(pages)
            elif kind == "uebung":
                full.uebung.extend(pages)
            elif kind == "praktikum":
                full.praktika.setdefault(tag, []).extend(pages)

    full.curated = build_curated_index(cfg, slug_pages)

    per_deck: dict[str, SourceIndex] = {}
    all_decks = set(deck_map) | {cfg.deck}
    for deck in all_decks:
        sub = SourceIndex()
        sub.lecture = list(deck_lecture.get(deck, full.lecture))
        sub.uebung = uebung_pages_for_deck(full.uebung, deck_uebung, deck)
        sub.praktika = {k: list(v) for k, v in full.praktika.items()}
        sub.curated = dict(full.curated)
        per_deck[deck] = sub

    return full, per_deck


def process_course(cfg, client: AnkiClient, *, dry_run: bool = False) -> dict[str, int]:
    stats = {
        "tagged": 0,
        "unknown": 0,
        "uebung": 0,
        "praktikum": 0,
        "unchanged": 0,
        "updated": 0,
    }
    nids = client.invoke("findNotes", query=f'deck:"{cfg.deck}"')
    if not nids:
        return stats

    _full, per_deck = build_full_course_index(cfg)

    deck_lookup: dict[int, str] = {}
    for i in range(0, len(nids), 50):
        batch = nids[i : i + 50]
        cids = []
        infos = client.invoke("notesInfo", notes=batch)
        for info in infos:
            cids.extend(info.get("cards") or [])
        for j in range(0, len(cids), 100):
            for card in client.invoke("cardsInfo", cards=cids[j : j + 100]):
                deck_lookup[card["cardId"]] = card.get("deckName", "")

    for i in range(0, len(nids), 50):
        infos = client.invoke("notesInfo", notes=nids[i : i + 50])
        for info in infos:
            deck_name = deck_for_note(info, deck_lookup) or cfg.deck
            index = per_deck.get(deck_name) or per_deck.get(cfg.deck) or _full
            texts = note_texts(info)

            src_tags = resolve_tags(texts, index)
            if FOLIE_UNKNOWN in src_tags:
                src_tags_uebung = resolve_tags(texts, index, prefer_uebung=True)
                if FOLIE_UNKNOWN not in src_tags_uebung:
                    src_tags = src_tags_uebung

            if FOLIE_UNKNOWN not in src_tags:
                stats["tagged"] += 1
            else:
                stats["unknown"] += 1
            if "uebung" in src_tags:
                stats["uebung"] += 1
            if any(t.startswith("praktikum-") for t in src_tags):
                stats["praktikum"] += 1

            old_tags = list(info.get("tags") or [])
            new_tags = clean_tags(old_tags, src_tags)
            if sorted(old_tags) == new_tags:
                stats["unchanged"] += 1
                continue

            stats["updated"] += 1
            if dry_run:
                print(f"[dry-run] nid {info['noteId']}: {old_tags} -> {new_tags}")
                continue

            for tag in old_tags:
                if (
                    tag.startswith("folie-")
                    or tag.startswith("praktikum-")
                    or tag.startswith("uebung")
                    or tag == "uebung"
                    or is_redundant_tag(tag)
                ):
                    client.invoke("removeTags", notes=[info["noteId"]], tags=tag)
            to_add = [t for t in new_tags if t not in old_tags]
            if to_add:
                client.invoke("addTags", notes=[info["noteId"]], tags=" ".join(to_add))

    return stats


def find_courses(semester_dir: Path) -> list[Path]:
    return sorted(p.parent for p in semester_dir.rglob("anki.json"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Tag Anki-Karten mit folie-XX / uebung / praktikum-NN")
    parser.add_argument(
        "--semester",
        type=Path,
        default=ROOT / "lectures" / "semester4",
    )
    parser.add_argument("--course", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    courses = [args.course.resolve()] if args.course else find_courses(args.semester.resolve())
    client = AnkiClient()
    client.ping()

    total = defaultdict(int)
    for course_dir in courses:
        try:
            cfg = load_course_config(course_dir)
        except FileNotFoundError:
            continue
        stats = process_course(cfg, client, dry_run=args.dry_run)
        print(
            f"{course_dir.name}: updated={stats['updated']} folie={stats['tagged']} "
            f"unknown={stats['unknown']} uebung={stats['uebung']} praktikum={stats['praktikum']}"
        )
        for k, v in stats.items():
            total[k] += v

    for deck in (
        "4. Semester::Software-Architektur",
        "4. Semester::IT-Sicherheit und Datenschutz::IT-Sicherheit",
    ):
        nids = client.invoke("findNotes", query=f'deck:"{deck}"')
        for i in range(0, len(nids), 50):
            for info in client.invoke("notesInfo", notes=nids[i : i + 50]):
                old = list(info.get("tags") or [])
                new = clean_tags(old, [FOLIE_UNKNOWN])
                if sorted(old) == new:
                    continue
                total["updated"] += 1
                total["unknown"] += 1
                if not args.dry_run:
                    for tag in old:
                        if tag.startswith("folie-") or is_redundant_tag(tag):
                            client.invoke("removeTags", notes=[info["noteId"]], tags=tag)
                    to_add = [t for t in new if t not in old]
                    if to_add:
                        client.invoke("addTags", notes=[info["noteId"]], tags=" ".join(to_add))

    print(
        f"Gesamt: updated={total['updated']} folie={total['tagged']} "
        f"unknown={total['unknown']} uebung={total['uebung']} praktikum={total['praktikum']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
