"""Workflow-Tags für Lern-Sessions (Kommunikation Nutzer ↔ KI ohne Notiz-IDs)."""
from __future__ import annotations

WF_PREFIX = "wf::"
WF_LOCK = "wf::lock"
WF_DONE = "wf::done"

# Während des Lernens in Anki setzen (Strg+T / Tags), dann Easy drücken.
FIX_TAGS: dict[str, str] = {
    "wf::fix::unclear": "Frage unklar oder mehrdeutig – umformulieren",
    "wf::fix::answer": "Antwort falsch, unvollständig oder zu lang",
    "wf::fix::typo": "Tippfehler oder Formatierung",
    "wf::fix::distractor": "MC/SC: Distraktor prüfen oder ersetzen",
    "wf::fix::split": "Zu viel Inhalt – Karte aufteilen",
    "wf::fix::merge": "Redundant – mit anderer Karte zusammenführen oder löschen",
    "wf::fix::type": "Falscher Kartentyp (z. B. Einfach statt Lücke)",
    "wf::fix::image": "Bild/IO-Stub fehlt oder unpassend",
}

PIPELINE_TAGS = frozenset({"io-stub", "auto-extracted", "mc-interactive"})

ALL_WF_TAGS = frozenset([WF_LOCK, WF_DONE, *FIX_TAGS])


def is_workflow_tag(tag: str) -> bool:
    return tag.startswith(WF_PREFIX)


def is_fix_tag(tag: str) -> bool:
    return tag.startswith(f"{WF_PREFIX}fix::")


def fix_tags_on(note_tags: list[str]) -> list[str]:
    return sorted(t for t in note_tags if is_fix_tag(t))


def format_tag_help() -> str:
    lines = ["Workflow-Tags (Prefix wf::):", ""]
    lines.append(f"  {WF_LOCK}")
    lines.append("    Manuell überarbeitet – Import/KI überschreibt nicht")
    lines.append("")
    lines.append("  Fix-Tags (beliebig kombinierbar):")
    for tag, desc in FIX_TAGS.items():
        lines.append(f"    {tag}")
        lines.append(f"      {desc}")
    lines.append("")
    lines.append(f"  {WF_DONE}")
    lines.append("    Von der KI abgearbeitet (wird beim --complete gesetzt)")
    return "\n".join(lines)
