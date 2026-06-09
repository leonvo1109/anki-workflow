# anki-workflow

PDF-Vorlesungsfolien extrahieren und daraus Anki-Karten erzeugen.

## Voraussetzungen

- Python 3, [Anki](https://apps.ankiweb.net/) + [AnkiConnect](https://foosoft.net/projects/anki-connect/)
- Optional: Cursor für Kartenimport per Chat

```bash
pip install -r scripts/requirements.txt
cp .env.example .env   # ANKI_PROFILE setzen (s. unten)
```

| Variable | Standard | Bedeutung |
|----------|----------|-----------|
| `ANKI_PROFILE` | `User` | Anki-Profilordner unter `~/Library/Application Support/Anki2/` |

## Schnellstart

```bash
# 1. Kurs anlegen, PDFs nach raw/
cp -r lectures/_template "lectures/semester4/Mein Kurs"

# 2. Extrahieren
python scripts/batch_extract_course.py "lectures/semester4/Mein Kurs"

# 3. anki.json im Kursordner anpassen, dann importieren (Anki muss laufen)
python scripts/import_lecture_cards.py "lectures/semester4/Mein Kurs" --dry-run
python scripts/import_lecture_cards.py "lectures/semester4/Mein Kurs" --import-io
```

IO-Stubs liefern Bilder ohne Masken – Masken in Anki Desktop setzen.

Vor größeren Imports: Backup nach `backups/` (s. [Befehle](docs/commands.md#backup)).

## Ordner

| Pfad | Inhalt |
|------|--------|
| `lectures/…/raw/` | PDFs |
| `lectures/…/processed/` | `slides.json`, Bilder, IO-Manifest |
| `lectures/…/anki.json` | Deck, Tags, Kapitel |
| `media/` | Anki-CSS und Notiztyp-Vorlagen |
| `backups/` | Anki-Sicherungen |

## Weiteres

- **[Befehle](docs/commands.md)** – Extraktion, Sync, Import, Backup
- **[Notiztypen](media/note-types/OVERVIEW.md)** – CSS/Typen mit Anki synchronisieren
