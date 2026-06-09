#!/usr/bin/env python3
"""
Erstellt: 2026-06-10
Kurzbeschreibung: Räumt scripts/_scratch/ auf (short + abgelaufene long-Dateien).
Benötigte Abhängigkeiten: keine
"""
from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path

SCRATCH = Path(__file__).resolve().parent / "_scratch"
LONG_NAME = re.compile(r"^(\d{8})-.+\.py$")


def long_expired(path: Path, today: date) -> bool:
    m = LONG_NAME.match(path.name)
    if not m:
        return False
    y, mth, d = int(m.group(1)[:4]), int(m.group(1)[4:6]), int(m.group(1)[6:8])
    try:
        return date(y, mth, d) <= today
    except ValueError:
        return False


def collect(short_only: bool, today: date) -> list[Path]:
    targets: list[Path] = []
    short_dir = SCRATCH / "short"
    if short_dir.is_dir():
        targets.extend(sorted(p for p in short_dir.glob("*.py") if p.is_file()))
    if not short_only:
        long_dir = SCRATCH / "long"
        if long_dir.is_dir():
            for p in long_dir.glob("*.py"):
                if p.is_file() and long_expired(p, today):
                    targets.append(p)
            # long ohne Datums-Prefix: als verwaist melden, nicht auto-löschen
    return targets


def main() -> int:
    parser = argparse.ArgumentParser(description="scripts/_scratch/ aufräumen")
    parser.add_argument("--apply", action="store_true", help="Dateien wirklich löschen")
    parser.add_argument("--short", action="store_true", help="Nur short/ (long unberührt)")
    args = parser.parse_args()

    today = date.today()
    paths = collect(short_only=args.short, today=today)

    long_dir = SCRATCH / "long"
    orphans: list[Path] = []
    if long_dir.is_dir() and not args.short:
        orphans = sorted(
            p for p in long_dir.glob("*.py")
            if p.is_file() and not LONG_NAME.match(p.name)
        )

    if not paths and not orphans:
        print("Nichts aufzuräumen.")
        return 0

    for p in paths:
        label = "short" if "short" in p.parts else "long (abgelaufen)"
        if args.apply:
            p.unlink()
            print(f"Gelöscht [{label}]: {p.name}")
        else:
            print(f"[dry-run] [{label}]: {p.name}")

    for p in orphans:
        print(f"Hinweis: long ohne YYYYMMDD-Prefix (manuell prüfen): {p.name}")

    if not args.apply and paths:
        print(f"\n{len(paths)} Datei(en). Mit --apply löschen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
