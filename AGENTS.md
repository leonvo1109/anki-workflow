# Agent instructions

Anki-Karten aus Vorlesungsfolien. Nutzer-Doku: [README.md](README.md) · Befehle: [docs/commands.md](docs/commands.md)

## Before you act

1. Read `workflow_status.md` (local, not in git)
2. Follow `project_config.md` for pipeline, card types, IO workflow

## Hard rules

- **Cards only from** `lectures/**/processed/` (`slides.json`, `slides.md`) and `lectures/**/cards/`
- **Never** read `lectures/**/raw/` PDFs for card creation
- New PDFs → `batch_extract_course.py` first, then cards
- Anki bulk changes (>5 cards): check/create backup in `backups/` (≤1h old or new)
- Log progress in `workflow_status.md`

## Import & tools

- Course config: `lectures/.../{Kurs}/anki.json`
- Curated/cleanup: `cards/anki_curated.json`, `cards/anki_cleanup.json`
- Import: `python scripts/import_lecture_cards.py "{Kurs}"` or MCP `user-anki`
- IO stubs: `import_io_stubs.py --course`; masks only in Anki Desktop manually

## Scripts

| Location | Use |
|----------|-----|
| `scripts/` | Permanent pipeline tools (tracked) |
| `scripts/_scratch/short/` | Session debug (gitignored) |
| `scripts/_scratch/long/` | Dated experiments (`YYYYMMDD-name.py`) |

No hardcoded user IDs or note IDs in tracked scripts. After session: `python scripts/prune_scratch.py --apply --short`

## Card quality (summary)

~10 cards per 10 content slides · prefer slide `questions` · skip `organizational` slides · details in `project_config.md`
