"""Kartengenerierung aus slides.json."""
from __future__ import annotations

import random
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import CourseConfig

DEFAULT_SKIP_TITLE = (
    r"^(University of|Recap|About us|Agenda|Literatur|Prüfung|Organisatorisches|𝑛෍|"
    r"COMPUTER ARCHITECTURE|Course Organization|Danke|Aktivit|Beispiel-Pr|Themen aus|"
    r"Visual Studio Code Plugin|Upcoming lab|Brainstorming|Orientation$|"
    r"4-bit microprocessor|Example: 4-bit|Example Execution|Example: Ariane|"
    r"Unconditional Branches: Jumps$|Adaptive Predictors: IPC$)"
)
DEFAULT_SKIP_BODY = (
    r"^(©|Prof\. Dr\.|Computer Architecture –|clk$|FE$|DE$|EX$|MA$|WB$|PC$|t$|\.\.\.|"
    r"North$|Bridge$|SATA$|USB$|PCIe$|FSB$|DDR$|GPU$|Peripherals$|Main Memory$)"
)
DEFAULT_SKIP_BULLET = r"^(https?://|▪\s*$|𝑛$|𝑖=1$|München$|Applied Sciences$)"
DEFAULT_LOW_QUALITY = (
    r"(innerhalb crt0|# noch nicht|▪acloser|▪apid ist|▪aint fork|▪Register, Virtual|"
    r"Division durch 0, Segmentation|Speicherabbildung, s\. später\)|"
    r"Zustandsdiagramm\?$|Dumps: Erstmalig|main\(\) …: Linker|"
    r"^▶Als akademisches|^Visual Code Plugin|^Different processor core$|"
    r"^Equal to addition$|^Meaning:$|^Observation:$|^Examples:$|^Form:$|^Example:$|"
    r"arXiv:|^\[cs\.|Computer Architecture and :|Public Domain|CC BY|Pix-)"
)


def _compile_filters(cfg: CourseConfig) -> dict[str, re.Pattern]:
    f = cfg.filters
    return {
        "skip_title": re.compile(f.get("skip_title", DEFAULT_SKIP_TITLE), re.I),
        "skip_body": re.compile(f.get("skip_body", DEFAULT_SKIP_BODY), re.I),
        "skip_bullet": re.compile(f.get("skip_bullet", DEFAULT_SKIP_BULLET), re.I),
        "low_quality": re.compile(f.get("low_quality", DEFAULT_LOW_QUALITY), re.I),
    }


def norm_key(text: str) -> str:
    t = re.sub(r"<[^>]+>", "", text.lower())
    t = re.sub(r"[^a-zäöüß0-9]+", " ", t)
    return " ".join(t.split())[:100]


def body_to_bullets(slide: dict, skip_body: re.Pattern) -> list[str]:
    bullets: list[str] = []
    for line in slide.get("body") or []:
        line = line.strip()
        if not line or skip_body.match(line):
            continue
        if line.startswith("▶"):
            line = re.sub(r"^▶\s*", "", line)
        if len(line) < 15 or len(line) > 220:
            continue
        if re.match(r"^[x0-9,\s\[\]()+\-]+$", line):
            continue
        if line in bullets:
            continue
        bullets.append(line)
    return bullets


def is_skip_slide(slide: dict, filters: dict[str, re.Pattern], *, parse_body: bool) -> bool:
    if slide.get("organizational"):
        return True
    title = (slide.get("title") or "").strip()
    if filters["skip_title"].search(title):
        return True
    bullets = slide.get("bullets") or []
    body_bullets = body_to_bullets(slide, filters["skip_body"]) if parse_body else []
    if title.lower() in ("recap", "zusammenfassung") and not bullets and not body_bullets:
        return True
    questions = slide.get("questions") or []
    body = slide.get("body") or []
    if not bullets and not body_bullets and not questions and len(" ".join(body)) < 30:
        if slide.get("diagram_heavy"):
            return True
    return False


def clean_bullet(text: str, filters: dict[str, re.Pattern], *, min_len: int = 12) -> str | None:
    t = re.sub(r"\s+", " ", text.strip())
    if len(t) < min_len or len(t) > 200:
        return None
    if filters["skip_bullet"].match(t):
        return None
    if filters["low_quality"].search(t):
        return None
    if t.startswith("Beispiel:") and len(t) < 25:
        return None
    return t


def bullet_to_question(title: str, bullet: str, default_prefix: str = "") -> str:
    prefix = (title or default_prefix or "Folie").strip()[:40]
    b = bullet[:70]
    if "?" in bullet:
        return bullet.strip()
    if re.match(r"^(Was|Wie|Welche|Warum|Wieso|Wann|What|Why|How)\b", bullet, re.I):
        return bullet.strip() if bullet.endswith("?") else bullet.strip() + "?"
    return f"{prefix[:35]}: {b}?"


def bullet_to_answer(bullet: str, next_bullet: str | None, filters: dict[str, re.Pattern]) -> str:
    ans = bullet.strip()
    if next_bullet and len(ans) < 40 and not ans.endswith("."):
        nb = clean_bullet(next_bullet, filters)
        if nb and len(nb) < 80:
            return f"{ans} – {nb}"
    return ans


def make_mc_card(front: str, back: str, distractors: list[str]) -> dict:
    opts = [back.replace("✓ ", "").replace("✗ ", "")] + distractors[:3]
    rng = random.Random(hash(front) & 0xFFFFFFFF)
    rng.shuffle(opts)
    correct = back.replace("✓ ", "").replace("✗ ", "")
    letters = "ABCD"
    lines = [f"☐ Ankreuzen: {front.replace('☐ Ankreuzen: ', '')}", ""]
    answer_letter = "A"
    for i, o in enumerate(opts[:4]):
        lines.append(f"({letters[i]}) {o}")
        if o == correct:
            answer_letter = letters[i]
    return {
        "modelName": "Einfach",
        "fields": {"Vorderseite": "\n".join(lines), "Rückseite": f"✓ ({answer_letter}) {correct}"},
    }


def curated_to_note(item: dict, deck: str, tag: str) -> dict:
    if item["type"] == "luecke":
        return {"deckName": deck, "modelName": "Lückentext", "fields": {"Text": item["text"], "Rückseite Extra": ""}, "tags": [tag]}
    if item["type"] == "mc":
        base = make_mc_card(item["front"], item["back"], item.get("distractors", []))
        base["deckName"] = deck
        base["tags"] = [tag]
        return base
    if item["type"] == "tf":
        return {"deckName": deck, "modelName": "Einfach", "fields": {"Vorderseite": item["front"], "Rückseite": item["back"]}, "tags": [tag]}
    return {"deckName": deck, "modelName": "Einfach", "fields": {"Vorderseite": item["front"], "Rückseite": item["back"]}, "tags": [tag]}


def is_low_quality(front: str, back: str, filters: dict[str, re.Pattern]) -> bool:
    if filters["low_quality"].search(front) or filters["low_quality"].search(back):
        return True
    f, b = norm_key(front), norm_key(back)
    if b and len(b) < 120 and (b in f or f in b):
        return True
    if len(back.strip()) < 18:
        return True
    if front.rstrip("?") == back.rstrip("?"):
        return True
    if ":" in front:
        bullet = front.split(":", 1)[-1].strip().rstrip("?")
        if bullet and len(bullet) > 10 and back.strip().startswith(bullet):
            return True
    if " – " in back:
        left = back.split(" – ")[0].strip()
        if left and (front.endswith(left + "?") or left in front):
            return True
    if front.strip().startswith("▪") or front.strip().startswith("Example:"):
        return True
    return False


def _try_cloze(bullet: str, title: str, deck: str, tag: str, cfg: CourseConfig) -> dict | None:
    patterns = cfg.filters.get("cloze_patterns") or []
    if cfg.parse_body_bullets:
        patterns = list(patterns) + [r"\b(add|sub|slt|beq|bne|jal|jalr|lw|sw)\s+"]
    else:
        patterns = list(patterns) + [r"\(\)|fork|exec|pthread|sem_|mq_|syscall"]

    for pat in patterns:
        if not re.search(pat, bullet, re.I):
            continue
        if cfg.parse_body_bullets:
            cloze = re.sub(
                r"\b(add|sub|slt|beq|bne|jal|jalr|lw|sw)\b",
                r"{{c1::\1}}",
                bullet,
                count=1,
                flags=re.I,
            )
        else:
            cloze = re.sub(r"(`?\w+\(\)`?)", r"{{c1::\1}}", bullet)
        if "{{c1::" in cloze:
            return {
                "deckName": deck,
                "modelName": "Lückentext",
                "fields": {"Text": f"<i>{title[:30]}</i><br>{cloze}", "Rückseite Extra": ""},
                "tags": [tag],
            }
    return None


def generate_from_slides(
    slides: list[dict],
    deck: str,
    tag: str,
    chapter: str,
    seen: set[str],
    cfg: CourseConfig,
    *,
    auto_bullets: bool = True,
    max_per_slide: int | None = None,
) -> list[dict]:
    filters = _compile_filters(cfg)
    limit = max_per_slide if max_per_slide is not None else cfg.max_per_slide
    notes: list[dict] = []

    for item in cfg.curated.get(chapter, []):
        note = curated_to_note(item, deck, tag)
        front = note["fields"].get("Vorderseite") or note["fields"].get("Text", "")
        keys = {norm_key(front)}
        if item.get("type") in ("mc", "tf"):
            # Bare Frage zusätzlich prüfen: so blockiert eine bereits existierende
            # interaktive AllInOne-Karte (Question-Feld ohne Präfixe) den Re-Import.
            bare = re.sub(r"^(☐ Ankreuzen:|Stimmt:)\s*", "", item.get("front", "")).strip()
            keys.add(norm_key(bare))
        if keys & seen:
            continue
        seen.update(keys)
        notes.append(note)

    if not auto_bullets:
        return notes

    default_prefix = cfg.tag_prefix or "Folie"
    for slide in slides:
        if is_skip_slide(slide, filters, parse_body=cfg.parse_body_bullets):
            continue
        title = slide.get("title") or f"Folie {slide['number']}"
        raw = list(slide.get("bullets") or [])
        if cfg.parse_body_bullets:
            raw = body_to_bullets(slide, filters["skip_body"]) + raw
        bullets = [clean_bullet(b, filters, min_len=15 if cfg.parse_body_bullets else 12) for b in raw]
        bullets = [b for b in bullets if b]
        added = 0

        for q in slide.get("questions") or []:
            if added >= limit:
                break
            q = re.sub(r"^[▪\s]+", "", q.strip())
            if len(q) < 12 or q.lower() in ("fragen", "questions") or "bis -ende" in q:
                continue
            if not q.endswith("?"):
                q = q + "?"
            key = norm_key(q)
            if key in seen:
                continue
            seen.add(key)
            back = "; ".join(bullets[:2]) if bullets else title
            if len(back) < 18:
                continue
            notes.append({
                "deckName": deck,
                "modelName": "Einfach",
                "fields": {"Vorderseite": q[:120], "Rückseite": back[:280]},
                "tags": [tag],
            })
            added += 1

        for i, bullet in enumerate(bullets):
            if added >= limit:
                break
            front = bullet_to_question(title, bullet, default_prefix)
            key = norm_key(front)
            if key in seen:
                continue
            back = bullet_to_answer(bullet, bullets[i + 1] if i + 1 < len(bullets) else None, filters)
            if is_low_quality(front, back, filters):
                continue
            seen.add(key)
            cloze_note = _try_cloze(bullet, title, deck, tag, cfg)
            if cloze_note:
                notes.append(cloze_note)
                added += 1
                continue
            notes.append({
                "deckName": deck,
                "modelName": "Einfach",
                "fields": {"Vorderseite": front[:110], "Rückseite": back[:220]},
                "tags": [tag],
            })
            added += 1

    return notes
