"""Indizes für Vorlesungsfolien, Übungen und nummerierte Praktika."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .config import CourseConfig
from .norm import norm_key, norm_match, norm_filename

STOPWORDS = frozenset(
    "was wie welche warum wieso wann der die das ein eine und oder ist sind bei mit für von"
    "the a an is are in on at to of and or nicht nur auch als aus dem den des".split()
)

PRAKTIKUM_RE = re.compile(r"(?:übungsblatt|uebungsblatt|u\s*bungsblatt)[_-]?0*(\d+)", re.I)
AUFGABE_RE = re.compile(r"aufgabe[_-]0*(\d+)", re.I)
UEBUNG_DIR_RE = re.compile(r"uebung", re.I)


@dataclass
class PageEntry:
    page: int
    text: str
    norm: str
    source_kind: str  # vorlesung | uebung | praktikum
    source_tag: str  # folie basis; praktikum-01; uebung


@dataclass
class SourceIndex:
    lecture: list[PageEntry] = field(default_factory=list)
    uebung: list[PageEntry] = field(default_factory=list)
    praktika: dict[str, list[PageEntry]] = field(default_factory=dict)
    curated: dict[str, tuple[int, str]] = field(default_factory=dict)  # norm_key -> (page, kind)

    def all_corpora(self) -> list[tuple[str, list[PageEntry]]]:
        out: list[tuple[str, list[PageEntry]]] = [("vorlesung", self.lecture)]
        if self.uebung:
            out.append(("uebung", self.uebung))
        for tag, pages in sorted(self.praktika.items()):
            out.append((tag, pages))
        return out


def significant_words(text: str, *, min_len: int = 3) -> set[str]:
    return {
        w
        for w in norm_match(text).split()
        if len(w) >= min_len and w not in STOPWORDS
    }


def slide_parts(slide: dict) -> str:
    parts = [slide.get("title") or ""]
    parts.extend(slide.get("bullets") or [])
    parts.extend(slide.get("questions") or [])
    parts.extend(slide.get("body") or [])
    return " ".join(p.strip() for p in parts if p and str(p).strip())


def pages_from_slides(
    slides: list[dict], *, source_kind: str, source_tag: str
) -> list[PageEntry]:
    out: list[PageEntry] = []
    for slide in slides:
        full = slide_parts(slide)
        if not full.strip():
            continue
        out.append(
            PageEntry(
                page=int(slide["number"]),
                text=full,
                norm=norm_match(full),
                source_kind=source_kind,
                source_tag=source_tag,
            )
        )
    return out


def pages_from_pdf(pdf_path: Path, *, source_kind: str, source_tag: str) -> list[PageEntry]:
    try:
        import fitz
    except ImportError:
        return []
    if not pdf_path.exists():
        return []
    doc = fitz.open(pdf_path)
    out: list[PageEntry] = []
    for i, page in enumerate(doc, 1):
        text = (page.get_text("text") or "").strip()
        if len(text) < 15:
            continue
        out.append(
            PageEntry(
                page=i,
                text=text,
                norm=norm_match(text),
                source_kind=source_kind,
                source_tag=source_tag,
            )
        )
    return out


def classify_pdf(pdf_path: Path) -> tuple[str, str]:
    """Return (source_kind, source_tag). kind=skip means ignore."""
    name = pdf_path.name
    path_s = str(pdf_path).lower()
    name_norm = norm_filename(name)

    if "musterloesung" in name_norm or "loesung" in name_norm or "do-not-read" in path_s:
        return "skip", ""

    m = re.search(r"(?:u|ü)bungsblatt[_-]?0*(\d+)", name_norm)
    if m and ("compiler" in path_s or "excercise" in path_s or "exercises" in path_s):
        return "praktikum", f"praktikum-{int(m.group(1)):02d}"

    m = AUFGABE_RE.search(name_norm)
    if m and "uebung" in path_s:
        return "uebung", f"uebung-aufgabe-{int(m.group(1)):02d}"

    if "uebung" in name_norm or UEBUNG_DIR_RE.search(pdf_path.parent.name):
        return "uebung", "uebung"

    if any(
        k in name_norm
        for k in ("vorlesung", "kapitel", "handout", "skript", "slides")
    ):
        return "vorlesung", "vorlesung"

    return "vorlesung", "vorlesung"


def classify_processed_slug(slug: str, course_dir: Path) -> tuple[str, str] | None:
    """Fallback when meta filename uses unicode variants."""
    s = slug.lower()
    m = re.search(r"u-bungsblatt-0*(\d+)$", s)
    if m and "compiler" in str(course_dir).lower():
        return "praktikum", f"praktikum-{int(m.group(1)):02d}"
    if s.startswith("uebungsblatt-"):
        return "uebung", "uebung"
    return None


def load_processed_pages(processed_dir: Path) -> list[PageEntry]:
    slides_path = processed_dir / "slides.json"
    if not slides_path.exists():
        return []
    slides = json.loads(slides_path.read_text(encoding="utf-8"))
    if not slides:
        return []
    meta_path = processed_dir / "meta.json"
    kind, tag = "vorlesung", "vorlesung"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        pdf_ref = meta.get("source_pdf") or meta.get("source_filename", "")
        kind, tag = classify_pdf(Path(pdf_ref))
        if kind == "skip":
            return []
    slug_hint = classify_processed_slug(processed_dir.name, processed_dir.parent.parent)
    if slug_hint and kind == "vorlesung":
        kind, tag = slug_hint
    return pages_from_slides(slides, source_kind=kind, source_tag=tag)


def build_curated_index(cfg: CourseConfig, slug_pages: dict[str, list[PageEntry]]) -> dict[str, tuple[int, str, str]]:
    """Map norm_key(front/back/text) -> (page, source_kind, source_tag)."""
    index: dict[str, tuple[int, str, str]] = {}
    for slug, items in cfg.curated.items():
        pages = slug_pages.get(slug, [])
        if not pages:
            continue
        for item in items:
            texts = [item.get("front", ""), item.get("back", ""), item.get("text", "")]
            for text in texts:
                if not text:
                    continue
                nk = norm_key(text)
                if nk in index:
                    continue
                hit = _match_pages([text], pages)
                if hit:
                    page, entry = hit
                    index[nk] = (page, entry.source_kind, entry.source_tag)
                # Also index bare question for MC
                bare = re.sub(r"^(☐ Ankreuzen:|Stimmt:)\s*", "", text).strip()
                if bare:
                    bn = norm_key(bare)
                    if bn not in index:
                        hit = _match_pages([bare], pages)
                        if hit:
                            page, entry = hit
                            index[bn] = (page, entry.source_kind, entry.source_tag)
    return index


def _score_overlap(note_words: set[str], page_words: set[str]) -> float:
    if not note_words or not page_words:
        return 0.0
    overlap = note_words & page_words
    if not overlap:
        return 0.0
    score = sum(1.0 + (0.5 if len(w) >= 6 else 0) for w in overlap)
    ratio = len(overlap) / len(note_words)
    return score + ratio


TOKEN_HINTS = frozenset(
    {
        "vmrss",
        "vmsize",
        "vmstk",
        "vmheap",
        "aslr",
        "pgrep",
        "min_vruntime",
        "mutex",
        "sticky",
        "sgid",
        "magic",
        "btrfs",
        "ext4",
        "inode",
        "dentry",
        "semaphore",
        "deadlock",
        "priority",
        "inversion",
    }
)


def _match_pages(
    texts: list[str], pages: list[PageEntry]
) -> tuple[int, PageEntry] | None:
    if not pages or not texts:
        return None

    for text in texts:
        nk = norm_key(text)
        if not nk:
            continue
        for entry in pages:
            if nk == entry.norm:
                return entry.page, entry
            if len(nk) >= 16 and (nk in entry.norm or entry.norm in nk):
                return entry.page, entry

    for text in texts:
        for token in norm_match(text).split():
            if token not in TOKEN_HINTS:
                continue
            for entry in pages:
                if token in entry.norm:
                    return entry.page, entry

    best: tuple[float, int, PageEntry] | None = None
    combined = " ".join(texts)
    note_words = significant_words(combined)
    if not note_words:
        return None

    for entry in pages:
        page_words = significant_words(entry.text)
        sc = _score_overlap(note_words, page_words)
        if sc <= 0:
            continue
        if best is None or sc > best[0]:
            best = (sc, entry.page, entry)

    if best is None:
        return None
    sc, page, entry = best
    if sc >= 2.5:
        return page, entry
    if sc >= 1.8 and len(note_words) <= 4:
        return page, entry
    return None


def match_note(
    texts: list[str],
    index: SourceIndex,
    *,
    prefer: list[str] | None = None,
) -> tuple[int, str, str] | None:
    """Return (page, source_kind, source_tag) or None."""
    for text in texts:
        nk = norm_key(text)
        if nk in index.curated:
            page, kind, tag = index.curated[nk]
            return page, kind, tag
        bare = re.sub(r"^(☐ Ankreuzen:|Stimmt:)\s*", "", text).strip()
        if bare:
            bn = norm_key(bare)
            if bn in index.curated:
                page, kind, tag = index.curated[bn]
                return page, kind, tag

    order = prefer or ["vorlesung", "uebung"]
    corpora: list[tuple[str, list[PageEntry]]] = []
    for name in order:
        if name == "vorlesung":
            corpora.append(("vorlesung", index.lecture))
        elif name == "uebung":
            corpora.append(("uebung", index.uebung))
        elif name in index.praktika:
            corpora.append((name, index.praktika[name]))

    best: tuple[float, int, str, str] | None = None
    for _name, pages in corpora:
        hit = _match_pages(texts, pages)
        if not hit:
            continue
        page, entry = hit
        note_words = significant_words(" ".join(texts))
        page_words = significant_words(entry.text)
        sc = _score_overlap(note_words, page_words)
        if best is None or sc > best[0]:
            best = (sc, page, entry.source_kind, entry.source_tag)

    if best is None:
        return None
    _sc, page, kind, tag = best
    return page, kind, tag
