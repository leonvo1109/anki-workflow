#!/usr/bin/env python3
"""
Erstellt: 2026-06-09
Kurzbeschreibung: Bewertet extrahierte Folienbilder für Image Occlusion (on-device Vision + Heuristiken).
Benötigte Abhängigkeiten: pip install -r scripts/requirements.txt
Optional: macOS + Swift (vision_classify.swift) für KI-Labels; sonst nur Heuristiken.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from PIL import Image, ImageStat
except ImportError:
    print("Fehler: Pillow fehlt. pip install -r scripts/requirements.txt", file=sys.stderr)
    sys.exit(1)

SCRIPT_DIR = Path(__file__).resolve().parent
VISION_SWIFT = SCRIPT_DIR / "vision_classify.swift"
STAGING_IMAGES = Path(".staging/images")
FINAL_IMAGES = Path("images")

IO_THRESHOLD = 0.6

DIAGRAM_LABELS = re.compile(
    r"(flowchart|chart|plot|graph|schematic|blueprint|infographic|"
    r"architecture|crossword|puzzle)",
    re.IGNORECASE,
)
DECOR_LABELS = re.compile(
    r"(book|logo|illustration|cartoon|art|painting|poster|comic|people|"
    r"envelope|stamp|currency|portrait|fashion|food|animal|plant|sky|sign)",
    re.IGNORECASE,
)
GENERIC_VISION = re.compile(r"^(document|structure|text|media|machine|keypad|diskette)$", re.IGNORECASE)
TITLE_SKIP = re.compile(
    r"^(münchen|university|applied sciences|hochschule|fakultät|fk\d+|about us|folie \d+)$",
    re.IGNORECASE,
)
DIAGRAM_TITLE = re.compile(
    r"(architektur|diagramm|schema|struktur|kernel|hardware|pipeline|"
    r"scheduling|prozess|thread|speicher|modell|übersicht|rolle des)",
    re.IGNORECASE,
)
ORG_SLIDE = re.compile(
    r"(prüfung|praktikum|literatur|willkommen|organisatorisch|moodle|about us)",
    re.IGNORECASE,
)

CATEGORY_DE = {
    "diagram": "Technisches Diagramm",
    "flowchart": "Flussdiagramm",
    "logo": "Logo / Markenzeichen",
    "book_cover": "Buchcover",
    "decoration": "Dekoration / Stock-Bild",
    "photo": "Foto",
    "slide_layout": "Folien-Layout (Titelfolie)",
    "unknown": "Unklarer Bildtyp",
}


def vision_classify(image_path: Path) -> list[dict]:
    if sys.platform != "darwin" or not VISION_SWIFT.exists():
        return []
    try:
        proc = subprocess.run(
            ["swift", str(VISION_SWIFT), str(image_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return []
        return json.loads(proc.stdout.strip())
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return []


def image_stats(path: Path) -> dict:
    with Image.open(path) as img:
        img = img.convert("RGB")
        w, h = img.size
        stat = ImageStat.Stat(img)
        # Farbvarianz als Proxy für Foto vs. flaches Diagramm
        var = sum(stat.stddev) / max(len(stat.stddev), 1)
        return {
            "width": w,
            "height": h,
            "pixels": w * h,
            "aspect": w / h if h else 1.0,
            "color_stddev": var,
        }


def pick_category(
    vision: list[dict],
    stats: dict,
    is_embedded: bool,
    slide: dict,
) -> str:
    title = slide.get("title") or ""
    slide_text = " ".join(slide.get("bullets", []) + slide.get("body", [])).lower()

    if slide.get("organizational") or ORG_SLIDE.search(title) or ORG_SLIDE.search(slide_text):
        if stats["pixels"] < 200_000 or "literatur" in slide_text:
            return "book_cover"
        return "decoration"

    top_labels = [v["label"] for v in vision[:3]]
    labels = " ".join(top_labels)

    if any(DECOR_LABELS.search(lbl) for lbl in top_labels):
        if not DIAGRAM_TITLE.search(title):
            return "decoration"
    if "book" in labels.lower() or (stats["aspect"] < 0.85 and stats["height"] > stats["width"] and stats["pixels"] < 150_000):
        if "literatur" in slide_text or stats["pixels"] < 120_000:
            return "book_cover"
    if "logo" in labels.lower() or (stats["pixels"] < 50_000 and stats["color_stddev"] < 40):
        return "logo"
    if DIAGRAM_LABELS.search(labels):
        return "flowchart" if "flowchart" in labels.lower() else "diagram"
    if not is_embedded and slide.get("text_char_count", 999) < 120:
        return "slide_layout"
    if TITLE_SKIP.match(title.strip()):
        return "slide_layout"
    if "generiert mit ki" in slide_text:
        return "decoration"
    if DIAGRAM_TITLE.search(title):
        return "diagram"
    if all(GENERIC_VISION.match(lbl) for lbl in top_labels[:2]) if len(top_labels) >= 2 else False:
        return "unknown"
    return "unknown"


def score_image(
    vision: list[dict],
    stats: dict,
    slide: dict,
    is_embedded: bool,
    category: str,
) -> float:
    score = 0.45
    title = slide.get("title") or ""
    slide_text = " ".join(slide.get("bullets", []) + slide.get("body", [])).lower()

    if slide.get("organizational") or ORG_SLIDE.search(title) or ORG_SLIDE.search(slide_text):
        score -= 0.35
    if TITLE_SKIP.match(title.strip()):
        score -= 0.4
    if "generiert mit ki" in slide_text:
        score -= 0.35
    if category in ("diagram", "flowchart"):
        score += 0.3
    elif category == "unknown":
        score -= 0.2
    if category in ("logo", "book_cover", "decoration", "slide_layout"):
        score -= 0.35
    if is_embedded:
        score += 0.15
    else:
        score -= 0.1
    if stats["pixels"] < 40_000:
        score -= 0.25
    elif stats["pixels"] > 200_000 and is_embedded:
        score += 0.1
    if stats["aspect"] > 4 or stats["aspect"] < 0.25:
        score -= 0.15
    if DIAGRAM_TITLE.search(title):
        score += 0.2
    if slide.get("questions"):
        score += 0.1
    for v in vision[:3]:
        lbl = v["label"]
        if DIAGRAM_LABELS.search(lbl):
            score += 0.15 * v["confidence"]
        elif DECOR_LABELS.search(lbl):
            score -= 0.15 * v["confidence"]
        elif GENERIC_VISION.match(lbl):
            score -= 0.02

    return max(0.0, min(1.0, round(score, 3)))


def build_description(category: str, vision: list[dict], slide: dict, stats: dict, is_embedded: bool) -> str:
  """Kurzbeschreibung auf Deutsch (Vision-Labels + Kontext)."""
  parts: list[str] = []
  cat_de = CATEGORY_DE.get(category, category)
  parts.append(cat_de)

  if vision:
    top = vision[0]
    label_de = top["label"].replace("_", " ")
    conf = int(top["confidence"] * 100)
    parts.append(f"Vision: „{label_de}“ ({conf}%)")

  title = (slide.get("title") or "").strip()
  if title and not TITLE_SKIP.match(title):
    parts.append(f"Folie: {title[:80]}")

  if slide.get("questions"):
    parts.append(f"Frage: {slide['questions'][0][:60]}")

  kind = "eingebettete Grafik" if is_embedded else "Seitenrender"
  parts.append(f"{kind}, {stats['width']}×{stats['height']} px")

  return ". ".join(parts) + "."


def reject_reason(category: str, io_score: float, slide: dict) -> str | None:
    if io_score >= IO_THRESHOLD:
        return None
    if slide.get("organizational"):
        return "organizational_slide"
    if category == "logo":
        return "logo"
    if category == "book_cover":
        return "book_cover"
    if category == "decoration":
        return "decoration"
    if category == "slide_layout":
        return "slide_layout"
    if io_score < 0.35:
        return "low_diagram_likelihood"
    return "below_threshold"


def resolve_image_file(processed_dir: Path, rel_path: str) -> Path | None:
    """Findet Bilddatei unabhängig von staging/images-Pfad in slides.json."""
    direct = processed_dir / rel_path
    if direct.is_file():
        return direct
    name = Path(rel_path).name
    for sub in (STAGING_IMAGES, FINAL_IMAGES):
        candidate = processed_dir / sub / name
        if candidate.is_file():
            return candidate
    return None


def finalize_image_storage(
    processed_dir: Path,
    io_recommended: list[dict],
    rejected: list[dict],
    slides: list[dict],
) -> tuple[list[dict], dict]:
    """
    Verschiebt nur io_recommended nach images/, löscht Rest inkl. .staging/.
    Verworfene Bilder werden nicht dauerhaft gespeichert.
    """
    processed_dir = processed_dir.resolve()
    staging_dir = processed_dir / STAGING_IMAGES
    final_dir = processed_dir / FINAL_IMAGES
    final_dir.mkdir(exist_ok=True)

    kept_names = {Path(e["image"]).name for e in io_recommended}
    removed = 0
    moved = 0

    search_dirs: list[Path] = []
    if staging_dir.is_dir():
        search_dirs.append(staging_dir)
    if final_dir.is_dir():
        search_dirs.append(final_dir)

    handled: set[str] = set()
    for src_dir in search_dirs:
        for f in sorted(src_dir.iterdir()):
            if not f.is_file():
                continue
            name = f.name
            if name in handled:
                continue
            handled.add(name)
            if name in kept_names:
                dest = final_dir / name
                if f.resolve() != dest.resolve():
                    if dest.exists():
                        dest.unlink()
                    shutil.move(str(f), str(dest))
                moved += 1
            else:
                f.unlink()
                removed += 1

    staging_root = processed_dir / ".staging"
    if staging_root.exists():
        shutil.rmtree(staging_root)

    for entry in io_recommended:
        entry["image"] = f"{FINAL_IMAGES}/{Path(entry['image']).name}"

    for slide in slides:
        embedded = [
            f"{FINAL_IMAGES}/{Path(p).name}"
            for p in slide.get("images", {}).get("embedded", [])
            if Path(p).name in kept_names
        ]
        slide["images"]["embedded"] = embedded
        pr = slide.get("images", {}).get("page_render", "")
        if pr and Path(pr).name in kept_names:
            slide["images"]["page_render"] = f"{FINAL_IMAGES}/{Path(pr).name}"
        else:
            slide["images"]["page_render"] = ""
        if not embedded and not slide["images"]["page_render"]:
            slide["occlusion_candidate"] = False

    stats = {"images_kept": len(kept_names), "images_removed": removed, "images_moved": moved}
    return slides, stats


def regenerate_slides_md(processed_dir: Path, slides: list[dict]) -> None:
    meta_path = processed_dir / "meta.json"
    if not meta_path.exists():
        return
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    pdf_name = meta.get("source_filename", processed_dir.name)
    lines = [
        f"# Extrahiert: {pdf_name}",
        "",
        f"- Seiten: {meta.get('page_count', '?')}",
        f"- Inhaltsfolien: {meta.get('slide_count_content', '?')}",
        f"- Bilder behalten: {meta.get('images_kept', '?')}",
        f"- Extrahiert: {meta.get('extracted_at', '?')}",
        "",
        "> Karten aus diesem File / `slides.json` – nicht aus dem PDF.",
        "",
    ]
    for s in slides:
        flags = []
        if s.get("organizational"):
            flags.append("organisatorisch")
        if s.get("occlusion_candidate"):
            flags.append("IO-Kandidat")
        flag_str = f" `[{', '.join(flags)}]`" if flags else ""
        lines.append(f"## Folie {s['number']}: {s.get('title') or '(ohne Titel)'}{flag_str}")
        if s.get("questions"):
            lines.append("### Fragen")
            for q in s["questions"]:
                lines.append(f"- {q}")
        if s.get("bullets"):
            lines.append("### Stichpunkte")
            for b in s["bullets"]:
                lines.append(f"- {b}")
        imgs = s.get("images", {}).get("embedded", [])
        pr = s.get("images", {}).get("page_render", "")
        if imgs or pr:
            lines.append("### Bilder")
            for img in imgs:
                lines.append(f"- `{img}`")
            if pr and not imgs:
                lines.append(f"- `{pr}`")
        lines.append("")
    (processed_dir / "slides.md").write_text("\n".join(lines), encoding="utf-8")


def collect_image_jobs(slides: list[dict]) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()

    for slide in slides:
        sn = slide["number"]
        embedded = slide.get("images", {}).get("embedded", [])
        page_render = slide.get("images", {}).get("page_render", "")

        for rel in embedded:
            if rel not in seen:
                seen.add(rel)
                jobs.append({"slide": sn, "image": rel, "is_embedded": True, "slide_data": slide})

        if not embedded and slide.get("occlusion_candidate") and page_render and page_render not in seen:
            seen.add(page_render)
            jobs.append({"slide": sn, "image": page_render, "is_embedded": False, "slide_data": slide})

    return jobs


def classify_processed_dir(
    processed_dir: Path,
    threshold: float = IO_THRESHOLD,
    purge: bool = True,
) -> dict:
    processed_dir = processed_dir.resolve()
    slides_path = processed_dir / "slides.json"
    if not slides_path.exists():
        raise FileNotFoundError(f"slides.json fehlt: {slides_path}")

    slides = json.loads(slides_path.read_text(encoding="utf-8"))
    slide_by_num = {s["number"]: s for s in slides}

    io_recommended: list[dict] = []
    rejected: list[dict] = []
    all_classified: list[dict] = []

    for job in collect_image_jobs(slides):
        img_rel = job["image"]
        img_path = resolve_image_file(processed_dir, img_rel)
        if img_path is None:
            continue

        slide = job["slide_data"]
        vision = vision_classify(img_path)
        stats = image_stats(img_path)
        category = pick_category(vision, stats, job["is_embedded"], slide)
        io_score = score_image(vision, stats, slide, job["is_embedded"], category)
        description = build_description(category, vision, slide, stats, job["is_embedded"])
        reason = reject_reason(category, io_score, slide)

        entry = {
            "slide": job["slide"],
            "header": slide.get("title") or f"Folie {job['slide']}",
            "image": img_rel,
            "is_embedded": job["is_embedded"],
            "category": category,
            "io_score": io_score,
            "description": description,
            "vision_labels": vision,
            "questions_on_slide": slide.get("questions", []),
            "io_status": "pending_masks" if io_score >= threshold else "rejected",
            "reject_reason": reason,
        }
        all_classified.append(entry)

        is_diagram_type = category in ("diagram", "flowchart")
        has_diagram_title = bool(DIAGRAM_TITLE.search(entry["header"]))
        qualifies = (
            io_score >= threshold
            and is_diagram_type
            and not slide.get("organizational")
            and (job["is_embedded"] or has_diagram_title)
        )
        if qualifies:
            io_recommended.append(entry)
        else:
            if io_score >= threshold:
                entry["reject_reason"] = (
                    "organizational_slide"
                    if slide.get("organizational")
                    else "category_not_diagram"
                    if not is_diagram_type
                    else "weak_diagram_signal"
                )
                entry["io_status"] = "rejected"
            rejected.append(entry)

    io_recommended.sort(key=lambda x: -x["io_score"])
    rejected.sort(key=lambda x: -x["io_score"])

    purge_stats = {}
    if purge:
        slides, purge_stats = finalize_image_storage(
            processed_dir, io_recommended, rejected, slides
        )
        (processed_dir / "slides.json").write_text(
            json.dumps(slides, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        meta_path = processed_dir / "meta.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta.update(
                {
                    "images_kept": purge_stats["images_kept"],
                    "images_removed": purge_stats["images_removed"],
                    "images_finalized": True,
                    "classified_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        regenerate_slides_md(processed_dir, slides)

    manifest = {
        "classified_at": datetime.now(timezone.utc).isoformat(),
        "classifier": "classify_images.py",
        "classifier_version": "1.0",
        "vision_backend": "apple_vision" if sys.platform == "darwin" else "heuristics_only",
        "io_threshold": threshold,
        "io_recommended": io_recommended,
        "rejected": rejected,
        "summary": {
            "total_images": len(all_classified),
            "recommended": len(io_recommended),
            "rejected": len(rejected),
            **purge_stats,
        },
        # Rückwärtskompatibel für import_io_stubs.py
        "candidates": io_recommended,
    }

    occlusion_dir = processed_dir / "occlusion"
    occlusion_dir.mkdir(exist_ok=True)
    manifest_path = occlusion_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    # Kurzübersicht für Menschen
    summary_lines = [
        f"# Bild-Klassifikation: {processed_dir.name}",
        "",
        f"- Empfohlen für IO: **{len(io_recommended)}**",
        f"- Verworfen: **{len(rejected)}**",
        f"- Schwellwert: {threshold}",
        f"- Vision: {manifest['vision_backend']}",
        "",
        "## Empfohlen",
        "",
    ]
    for e in io_recommended:
        summary_lines.append(
            f"- Folie {e['slide']} (Score {e['io_score']:.2f}): {e['description']}"
        )
    summary_lines.extend(["", "## Verworfen", ""])
    for e in rejected[:15]:
        summary_lines.append(
            f"- Folie {e['slide']} (Score {e['io_score']:.2f}, {e['reject_reason']}): {e['description']}"
        )
    if len(rejected) > 15:
        summary_lines.append(f"- … und {len(rejected) - 15} weitere")
    (occlusion_dir / "classification.md").write_text("\n".join(summary_lines), encoding="utf-8")

    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Folienbilder für IO vorsortieren (on-device Vision)")
    parser.add_argument("processed_dir", type=Path, help="Ordner mit slides.json und images/")
    parser.add_argument("--threshold", type=float, default=IO_THRESHOLD, help="IO-Score-Schwelle (0–1)")
    parser.add_argument(
        "--no-purge",
        action="store_true",
        help="Verworfene Bilder nicht löschen (Staging bleibt für Debugging)",
    )
    args = parser.parse_args()

    try:
        manifest = classify_processed_dir(
            args.processed_dir, threshold=args.threshold, purge=not args.no_purge
        )
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 1

    s = manifest["summary"]
    print(f"Klassifiziert: {s['total_images']} Bilder")
    print(f"  IO empfohlen: {s['recommended']}")
    print(f"  Verworfen:    {s['rejected']}")
    print(f"  Vision:       {manifest['vision_backend']}")
    if s.get("images_kept") is not None:
        print(f"  Behalten:     {s['images_kept']} → images/")
        print(f"  Gelöscht:     {s.get('images_removed', 0)}")
    print(f"  Manifest:     {args.processed_dir / 'occlusion' / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
