# Cursor / KI

Regeln für den Agenten in diesem Repo. Nutzer-Dokumentation: [README](../README.md), [commands.md](commands.md).

## Pflichtlektüre

1. `project_config.md` – Pipeline, Kartentypen, IO-Workflow
2. `workflow_status.md` – aktueller Stand (lokal, nicht committen)
3. `.cursorrules` – Kurzregeln

## Datenquellen

| Erlaubt | Verboten |
|---------|----------|
| `lectures/**/processed/` (`slides.json`, `slides.md`) | `lectures/**/raw/` (PDFs) für Karten |
| `lectures/**/cards/` | |

Neue PDFs: zuerst `batch_extract_course.py`, dann Karten.

## Anki-Änderungen

- Backup vor Bulk-Import (>5 Karten): jünger 1h oder neu in `backups/`
- Import: `import_lecture_cards.py` + Kurs-`anki.json`, oder MCP `user-anki`
- IO: Stubs via `import_io_stubs.py`; Masken nur manuell in Anki Desktop
- Status in `workflow_status.md` protokollieren

## Skripte

**Dauerhaft** – nur `scripts/` (getrackt). Keine User-IDs, Note-IDs oder persönlichen Pfade hardcoden → `anki.json`, `.env`, `cards/anki_*.json`.

**Kurzlebig** – nur `scripts/_scratch/`:

| Ordner | Lebensdauer |
|--------|-------------|
| `_scratch/short/` | bis Session-Ende |
| `_scratch/long/` | Dateiname `YYYYMMDD-slug.py` = Löschdatum |

Kopfkommentar: `# SCRATCH short|long | …`

```bash
python scripts/prune_scratch.py --apply --short   # nach Session
python scripts/prune_scratch.py --apply           # + abgelaufene long
```

Promotion: Scratch → `scripts/` nur wenn dauerhaft nötig, dann in `docs/commands.md` eintragen.

## Kartenqualität

Siehe `project_config.md` – u. a. max. ~10 Karten pro 10 Inhaltsfolien, Folienfragen bevorzugen, organisatorische Folien überspringen.
