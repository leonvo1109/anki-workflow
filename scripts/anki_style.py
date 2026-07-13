"""Gemeinsame Hilfen für _global_style.css (Repo ↔ Anki)."""
from __future__ import annotations

import re
from pathlib import Path

REPO_CSS = Path(__file__).resolve().parent.parent / "media" / "_global_style.css"
# Nur @import am Anfang des Notiztyp-CSS (nicht in Kommentaren der eingebetteten Datei).
IMPORT_RE = re.compile(
    r'^\s*@import\s+url\(["\']_global_style\.css["\']\)\s*;?\s*',
    re.MULTILINE,
)


def load_global_css() -> str:
    return REPO_CSS.read_text(encoding="utf-8")


def resolve_css(css: str) -> str:
    """Ersetzt führendes @import _global_style.css durch den Dateiinhalt."""
    m = IMPORT_RE.match(css)
    if not m:
        return css
    rest = css[m.end() :].lstrip("\n")
    global_css = load_global_css().rstrip()
    if rest:
        return global_css + "\n\n" + rest
    return global_css + "\n"
