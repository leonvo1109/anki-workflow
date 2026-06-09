# anki-workflow

PDF-Vorlesungsfolien → strukturierte Daten → Anki-Karten (per Cursor + MCP/AnkiConnect).

Details und Regeln für die KI-Pipeline: `project_config.md`  
Fortschritt lokal: `workflow_status.md` (Vorlage: `workflow_status.example.md`)

---

## Voraussetzungen

- Python 3, [Anki](https://apps.ankiweb.net/) mit [AnkiConnect](https://foosoft.net/projects/anki-connect/)
- Optional: Cursor + MCP-Server `user-anki` für Kartenimport per Chat
- Bild-Klassifikation: macOS + Apple Vision (`classify_images.py`); Extraktion funktioniert überall mit `pymupdf`

```bash
pip install -r scripts/requirements.txt
```

### Umgebungsvariablen

| Variable | Standard | Wirkung |
|----------|----------|---------|
| `ANKI_PROFILE` | `User` | Anki-Profilname (Ordner unter dem Anki-Datenverzeichnis) |

Einmalig lokal anlegen (`.env` ist gitignored):

```bash
cp .env.example .env
# ANKI_PROFILE auf deinen Profilnamen setzen (macOS: ls ~/Library/Application\ Support/Anki2/)
```

`scripts/anki_paths.py` lädt `.env` automatisch; eine gesetzte Shell-Variable (`export ANKI_PROFILE=…`) hat Vorrang.

---

## Schnellstart: neuer Kurs

```bash
cp -r lectures/_template "lectures/semester{N}/{Kursname}"
# PDFs nach lectures/semester{N}/{Kursname}/raw/

python scripts/batch_extract_course.py "lectures/semester{N}/{Kursname}"
```

---

## Manuelle Befehle

Alle Befehle vom **Projektroot** ausführen. Platzhalter:

- `{Kurs}` → `lectures/semester{N}/{Kursname}`
- `{Kapitel}` → `lectures/.../processed/{kapitel-slug}`
- `{Deck}` → Anki-Deck, z. B. `4. Semester::Mein Kurs::Kapitel`

### 1. Extraktion & Bilder

```bash
# Alle PDFs eines Kurses (mit Bild-Klassifikation)
python scripts/batch_extract_course.py "{Kurs}"

# Ohne Klassifikation
python scripts/batch_extract_course.py "{Kurs}" --no-classify

# Einzelne PDF
python scripts/extract_lecture.py \
  "{Kurs}/raw/datei.pdf" \
  --course-dir "{Kurs}"

# Mit Klassifikation direkt nach Extraktion
python scripts/extract_lecture.py \
  "{Kurs}/raw/datei.pdf" \
  --course-dir "{Kurs}" \
  --classify

# Klassifikation nachträglich (ein Kapitel)
python scripts/classify_images.py "{Kapitel}"
```

### 2. Anki-Styling & Notiztypen

Dateien im Repo bearbeiten, dann nach Anki synchronisieren.

```bash
# Global CSS (media/_global_style.css)
python scripts/sync_anki_style.py status
python scripts/sync_anki_style.py pull    # Anki → Repo
python scripts/sync_anki_style.py push    # Repo → Anki

# Notiztyp-Vorlagen (media/note-types/*.json)
python scripts/sync_anki_note_types.py list
python scripts/sync_anki_note_types.py status
python scripts/sync_anki_note_types.py pull              # alle Typen
python scripts/sync_anki_note_types.py pull einfach      # ein Typ (slug)
python scripts/sync_anki_note_types.py push              # alle editierbaren Typen
python scripts/sync_anki_note_types.py push l-ckentext   # ein Typ

# Copy/Paste-Referenz (ohne Skript)
# → media/note-types/OVERVIEW.md
```

**Reihenfolge nach Änderungen:** zuerst `sync_anki_style.py push`, dann `sync_anki_note_types.py push`.

Add-on-Notiztypen (Multiple Choice, Image Occlusion) sind im Repo nur als Referenz – nicht per `push` überschreiben.

### 3. Karten importieren (AnkiConnect)

Anki muss laufen. Vor größeren Imports: Backup (Abschnitt 4).

```bash
# Karten aus slides.json (Bulk, mit Cleanup/Dedup)
python scripts/import_lecture_cards.py "{Kurs}" --dry-run
python scripts/import_lecture_cards.py "{Kurs}"

# Nur bestimmte Kapitel
python scripts/import_lecture_cards.py "{Kurs}" --chapter bs-kapitel1-einfuehrung

# Image-Occlusion-Stubs (Masken danach in Anki Desktop setzen)
python scripts/import_io_stubs.py "{Kapitel}" --deck "{Deck}" --dry-run
python scripts/import_io_stubs.py "{Kapitel}" --deck "{Deck}"

# Echte Multiple-Choice-Karten (Add-on 1566095810 nötig)
python scripts/import_mc_cards.py --dry-run
python scripts/import_mc_cards.py --migrate --delete-pseudo
```

Kleinere Imports und Updates laufen in der Regel über **Cursor + MCP** (`anki_create_notes`, `anki_update_note`, …).

### 4. Backup & Wiederherstellung

```bash
# Backup erstellen (collection.anki2 → backups/)
python -c "
import sys; sys.path.insert(0, 'scripts')
from pathlib import Path
import shutil, datetime
from anki_paths import collection_db
dst = Path('backups') / f'collection_{datetime.datetime.now():%Y%m%d_%H%M%S}.anki2'
dst.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(collection_db(), dst)
print(dst)
"

# Neuestes Backup wiederherstellen
python scripts/restore_backup.py

# Bestimmtes Backup
python scripts/restore_backup.py collection_20260101_120000.anki2

# Nur anzeigen, nichts ändern
python scripts/restore_backup.py --dry-run
```

**Hinweis:** Anki vor `restore_backup.py` schließen.

---

## Ordnerstruktur

| Pfad | Inhalt |
|------|--------|
| `scripts/` | Extraktion, Sync, Import, Backup |
| `media/` | `_global_style.css`, `note-types/` (Vorlagen) |
| `lectures/` | Kurse: `raw/`, `processed/`, `cards/` |
| `backups/` | Anki-`collection.anki2`-Sicherungen |
| `project_config.md` | Pipeline-Regeln für Cursor |
| `workflow_status.md` | Lokaler Fortschritt (nicht committen) |

Typischer Kurs:

```
lectures/semester{N}/{Kursname}/
├── raw/                    # PDFs (nur für Extraktion)
├── processed/{kapitel}/    # slides.json, images/, occlusion/
└── cards/                  # Kartenentwürfe (optional)
```

---

## Skript-Übersicht

| Skript | Zweck |
|--------|--------|
| `extract_lecture.py` | Einzel-PDF → `processed/{slug}/` |
| `batch_extract_course.py` | Alle PDFs in `raw/` |
| `classify_images.py` | IO-Kandidaten filtern (Vision) |
| `sync_anki_style.py` | `_global_style.css` ↔ Anki |
| `sync_anki_note_types.py` | Notiztyp-Vorlagen ↔ Anki |
| `import_lecture_cards.py` | Karten aus `slides.json` |
| `import_io_stubs.py` | IO-Stub-Karten |
| `import_mc_cards.py` | Multiple-Choice (Add-on) |
| `restore_backup.py` | Backup einspielen |
