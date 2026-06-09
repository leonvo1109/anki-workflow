#!/usr/bin/env python3
"""
Erstellt: 2026-06-09
Kurzbeschreibung: Extrahiert alle PDFs aus einem Kurs-raw/-Ordner rekursiv.
Benötigte Abhängigkeiten: pip install -r scripts/requirements.txt
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

EXTRACT_SCRIPT = Path(__file__).resolve().parent / "extract_lecture.py"


def main() -> int:
    parser = argparse.ArgumentParser(description="Alle PDFs eines Kurses extrahieren")
    parser.add_argument(
        "course_dir",
        type=Path,
        help="Kursordner mit Unterordner raw/ (z. B. lectures/semester4/Betriebssysteme 1)",
    )
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--no-classify", action="store_true", help="Bild-Klassifikation nach Extraktion überspringen")
    args = parser.parse_args()

    course_dir = args.course_dir.resolve()
    raw_dir = course_dir / "raw"
    if not raw_dir.is_dir():
        print(f"raw/-Ordner fehlt: {raw_dir}", file=sys.stderr)
        return 1

    pdfs = sorted(raw_dir.glob("*.pdf"))
    if not pdfs:
        print(f"Keine PDFs in {raw_dir}", file=sys.stderr)
        return 1

    failed = 0
    for pdf in pdfs:
        print(f"\n=== {pdf.name} ===")
        cmd = [sys.executable, str(EXTRACT_SCRIPT), str(pdf), "--course-dir", str(course_dir), "--dpi", str(args.dpi)]
        if not args.no_classify:
            cmd.append("--classify")
        rc = subprocess.call(cmd)
        if rc != 0:
            failed += 1

    print(f"\nFertig: {len(pdfs) - failed}/{len(pdfs)} erfolgreich.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
