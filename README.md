# anki-workflow

PDF-Vorlesungsfolien → strukturierte Daten → Anki-Karten (per Cursor + MCP).

## Voraussetzungen

- macOS, Python 3, [Anki](https://apps.ankiweb.net/) mit MCP/AnkiConnect
- `pip install -r scripts/requirements.txt`
- Optional: `export ANKI_PROFILE=DeinAnkiProfil` (Standard: `User`)

## Schnellstart

```bash
cp -r lectures/_template "lectures/semester4/Mein Kurs"
# PDFs nach lectures/.../raw/
python scripts/batch_extract_course.py "lectures/semester4/Mein Kurs"
```

Details und Regeln: `project_config.md`. Fortschritt lokal: `workflow_status.md` (von `workflow_status.example.md` kopieren).

## Ordner

| Pfad | Inhalt |
|------|--------|
| `scripts/` | Extraktion, Klassifikation, Anki-Hilfsskripte |
| `lectures/` | Lokal: PDFs & verarbeitete Daten (**nicht** im Repo) |
| `backups/` | Anki-DB-Backups (**nicht** im Repo) |
