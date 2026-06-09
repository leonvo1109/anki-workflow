#!/usr/bin/env python3
"""
Erstellt: 2026-06-09
Kurzbeschreibung: Extrahiert Folien aus PDFs in strukturierte Markdown/JSON inkl. Bilder.
Benötigte Abhängigkeiten: pip install -r scripts/requirements.txt
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import fitz  # pymupdf
except ImportError:
    print("Fehler: pymupdf fehlt. Bitte: pip install -r scripts/requirements.txt", file=sys.stderr)
    sys.exit(1)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

ORG_KEYWORDS = re.compile(
    r"(prüfung|praktikum|organisatorisch|about us|willkommen|empfohlene literatur|"
    r"moodle|schein|zulassungsvoraussetzung|hochschule münchen)",
    re.IGNORECASE,
)
QUESTION_RE = re.compile(r"^(Was|Wie|Welche|Warum|Wozu|Nenne|Erkläre|Beschreibe)\b", re.IGNORECASE)
BULLET_RE = re.compile(r"^[\s]*[▪•\-–]\s+")
FOOTER_RE = re.compile(
    r"(hochschule|university of applied|fakultät|@hm\.edu|generiert mit ki|"
    r"profs?\.\s*dr|^\d{1,3}$)",
    re.IGNORECASE,
)
TITLE_SKIP_RE = re.compile(
    r"^(münchen|university|applied sciences|hochschule|fakultät|fk\d+|about us)$",
    re.IGNORECASE,
)
DIAGRAM_KEYWORDS = re.compile(
    r"(architektur|diagramm|schema|modell|graph|ablauf|übersicht|struktur|"
    r"hardware|kernel|pipeline|zustand)",
    re.IGNORECASE,
)


def slugify(name: str) -> str:
    s = name.lower()
    s = re.sub(r"\.pdf$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"betriebssysteme[_-]?", "bs-", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def clean_lines(text: str) -> list[str]:
    raw_lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if FOOTER_RE.search(line) and len(line) < 120:
            continue
        if line.startswith("-- ") and " of " in line:
            continue
        raw_lines.append(line)

    merged: list[str] = []
    i = 0
    while i < len(raw_lines):
        line = raw_lines[i]
        if line in ("▪", "•", "–", "-") and i + 1 < len(raw_lines):
            merged.append("▪ " + raw_lines[i + 1])
            i += 2
            continue
        merged.append(line)
        i += 1
    return merged


def parse_slide_content(lines: list[str]) -> dict:
    title = ""
    bullets: list[str] = []
    questions: list[str] = []
    body: list[str] = []

    for line in lines:
        if QUESTION_RE.match(line) or line.endswith("?"):
            questions.append(line.rstrip("?").strip() + ("?" if not line.endswith("?") else ""))
            continue
        if BULLET_RE.match(line):
            bullets.append(BULLET_RE.sub("", line).strip())
            continue
        if (
            not title
            and len(line) < 120
            and not line.startswith("http")
            and not TITLE_SKIP_RE.match(line)
        ):
            title = line
        else:
            body.append(line)

    combined = " ".join(lines).lower()
    organizational = bool(ORG_KEYWORDS.search(combined))
    if bullets and not organizational and len(bullets) >= 3:
        if any(k in combined for k in ("prüfung", "moodle", "schein", "praktikum")):
            organizational = True

    text_len = len(" ".join(bullets + body + questions))
    return {
        "title": title,
        "bullets": bullets,
        "questions": questions,
        "body": body,
        "organizational": organizational,
        "text_char_count": text_len,
    }


STAGING_IMAGES = Path(".staging/images")


def extract_pdf(pdf_path: Path, out_dir: Path, dpi: int = 150) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    # Bilder zunächst nur im Staging – nach classify_images.py landen nur behaltene in images/
    images_dir = out_dir / STAGING_IMAGES
    if images_dir.exists():
        for f in images_dir.iterdir():
            if f.is_file():
                f.unlink()
    images_dir.mkdir(parents=True, exist_ok=True)
    occlusion_dir = out_dir / "occlusion"
    occlusion_dir.mkdir(exist_ok=True)

    doc = fitz.open(pdf_path)
    slides: list[dict] = []
    occlusion_candidates: list[dict] = []
    embedded_idx = 0

    for page_num in range(len(doc)):
        page = doc[page_num]
        slide_no = page_num + 1
        text = page.get_text("text")
        lines = clean_lines(text)
        parsed = parse_slide_content(lines)

        page_img = images_dir / f"slide-{slide_no:03d}.png"
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        pix.save(page_img)

        embedded_images: list[str] = []
        for img_info in page.get_images(full=True):
            xref = img_info[0]
            try:
                base = doc.extract_image(xref)
                if base["width"] < 80 or base["height"] < 80:
                    continue
                embedded_idx += 1
                ext = base["ext"]
                emb_path = images_dir / f"slide-{slide_no:03d}-embed-{embedded_idx:02d}.{ext}"
                emb_path.write_bytes(base["image"])
                embedded_images.append(str(emb_path.relative_to(out_dir)))
            except Exception:
                continue

        diagram_heavy = (
            parsed["text_char_count"] < 180
            and not parsed["organizational"]
            and (embedded_images or parsed["text_char_count"] < 80)
        )
        io_suggested = diagram_heavy or (
            bool(DIAGRAM_KEYWORDS.search(parsed["title"] or ""))
            and (embedded_images or parsed["text_char_count"] < 400)
        )

        slide = {
            "number": slide_no,
            "title": parsed["title"],
            "bullets": parsed["bullets"],
            "questions": parsed["questions"],
            "body": parsed["body"],
            "organizational": parsed["organizational"],
            "text_char_count": parsed["text_char_count"],
            "diagram_heavy": diagram_heavy,
            "occlusion_candidate": io_suggested,
            "images": {
                "page_render": str(page_img.relative_to(out_dir)),
                "embedded": embedded_images,
            },
        }
        slides.append(slide)

        if io_suggested and not parsed["organizational"]:
            primary = embedded_images[0] if embedded_images else slide["images"]["page_render"]
            occlusion_candidates.append(
                {
                    "slide": slide_no,
                    "header": parsed["title"] or f"Folie {slide_no}",
                    "image": primary,
                    "questions_on_slide": parsed["questions"],
                    "io_status": "pending_masks",
                    "note": "Masken in Anki (Image Occlusion Enhanced) ergänzen oder per import_io_stubs.py Stubs anlegen.",
                }
            )

    doc.close()

    meta = {
        "source_pdf": str(pdf_path.resolve()),
        "source_filename": pdf_path.name,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "page_count": len(slides),
        "slide_count_content": sum(1 for s in slides if not s["organizational"]),
        "occlusion_candidate_count": len(occlusion_candidates),
        "extractor": "extract_lecture.py",
        "extractor_version": "1.1",
        "images_staging": str(STAGING_IMAGES),
        "images_finalized": False,
    }

    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "slides.json").write_text(json.dumps(slides, indent=2, ensure_ascii=False), encoding="utf-8")
    (occlusion_dir / "manifest.json").write_text(
        json.dumps({"candidates": occlusion_candidates}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_slides_md(out_dir / "slides.md", pdf_path.name, meta, slides)
    return meta


def _write_slides_md(path: Path, pdf_name: str, meta: dict, slides: list[dict]) -> None:
    lines = [
        f"# Extrahiert: {pdf_name}",
        "",
        f"- Seiten: {meta['page_count']}",
        f"- Inhaltsfolien (ohne Organisatorisches): {meta['slide_count_content']}",
        f"- IO-Kandidaten: {meta['occlusion_candidate_count']}",
        f"- Extrahiert: {meta['extracted_at']}",
        "",
        "> **Nur diese Datei** (bzw. `slides.json`) für Karteikartenerstellung verwenden – nicht das PDF.",
        "",
    ]
    for s in slides:
        flags = []
        if s["organizational"]:
            flags.append("organisatorisch")
        if s["occlusion_candidate"]:
            flags.append("IO-Kandidat")
        flag_str = f" `[{', '.join(flags)}]`" if flags else ""
        lines.append(f"## Folie {s['number']}: {s['title'] or '(ohne Titel)'}{flag_str}")
        if s["questions"]:
            lines.append("### Fragen auf der Folie")
            for q in s["questions"]:
                lines.append(f"- {q}")
        if s["bullets"]:
            lines.append("### Stichpunkte")
            for b in s["bullets"]:
                lines.append(f"- {b}")
        if s["body"]:
            lines.append("### Text")
            for b in s["body"]:
                lines.append(f"- {b}")
        if s["images"]["embedded"]:
            lines.append("### Bilder")
            for img in s["images"]["embedded"]:
                lines.append(f"- `{img}`")
        elif s["occlusion_candidate"]:
            lines.append(f"- Seitenrender: `{s['images']['page_render']}`")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def resolve_output_dir(pdf_path: Path, output: Path | None, course_dir: Path | None) -> Path:
    if output:
        return output
    if course_dir:
        return course_dir / "processed" / slugify(pdf_path.stem)
    parent = pdf_path.parent
    if parent.name == "raw":
        return parent.parent / "processed" / slugify(pdf_path.stem)
    return parent / "processed" / slugify(pdf_path.stem)


def main() -> int:
    parser = argparse.ArgumentParser(description="PDF-Folien in strukturierte Daten extrahieren")
    parser.add_argument("pdf", type=Path, help="Pfad zur PDF (typisch unter .../raw/)")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Zielordner unter processed/ (Standard: automatisch aus Dateiname)",
    )
    parser.add_argument(
        "--course-dir",
        type=Path,
        help="Wurzel des Kurses (z. B. lectures/semester4/Betriebssysteme 1)",
    )
    parser.add_argument("--dpi", type=int, default=150, help="Auflösung für Seitenrender (Standard: 150)")
    parser.add_argument("--classify", action="store_true", help="Danach classify_images.py ausführen")
    args = parser.parse_args()

    pdf_path = args.pdf.resolve()
    if not pdf_path.exists():
        print(f"PDF nicht gefunden: {pdf_path}", file=sys.stderr)
        return 1

    out_dir = resolve_output_dir(pdf_path, args.output, args.course_dir)
    meta = extract_pdf(pdf_path, out_dir, dpi=args.dpi)
    print(f"Extrahiert nach: {out_dir}")
    print(f"  Folien: {meta['page_count']}, Inhalt: {meta['slide_count_content']}, IO-Kandidaten: {meta['occlusion_candidate_count']}")
    if args.classify:
        import subprocess

        classify_script = Path(__file__).resolve().parent / "classify_images.py"
        subprocess.call([sys.executable, str(classify_script), str(out_dir)])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
