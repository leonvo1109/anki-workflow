# Befehle

Alle Befehle vom **Projektroot**. Anki muss für Import/Sync laufen.

Platzhalter: `{Kurs}` = `lectures/semester{N}/{Name}` · `{Kapitel}` = `{Kurs}/processed/{slug}` · `{Deck}` = z. B. `4. Semester::Mein Kurs`

## Extraktion

```bash
python scripts/batch_extract_course.py "{Kurs}"
python scripts/batch_extract_course.py "{Kurs}" --no-classify

python scripts/extract_lecture.py "{Kurs}/raw/datei.pdf" --course-dir "{Kurs}"
python scripts/extract_lecture.py "{Kurs}/raw/datei.pdf" --course-dir "{Kurs}" --classify

python scripts/classify_images.py "{Kapitel}"
```

Bild-Klassifikation: macOS + Apple Vision. Extraktion überall mit `pymupdf`.

## Karten importieren

Pro Kurs: `anki.json` (Deck/Tags), optional `cards/anki_curated.json` und `cards/anki_cleanup.json`.

```bash
python scripts/import_lecture_cards.py "{Kurs}" --dry-run
python scripts/import_lecture_cards.py "{Kurs}"
python scripts/import_lecture_cards.py "{Kurs}" --chapter {slug}
python scripts/import_lecture_cards.py "{Kurs}" --import-io   # inkl. IO-Stubs

python scripts/import_io_stubs.py "{Kurs}" --course
python scripts/import_io_stubs.py "{Kapitel}" --deck "{Deck}"
```

MC-Karten (Add-on [1566095810](https://ankiweb.net/shared/info/1566095810) installieren, Anki neu starten):

Entwurf in `cards/anki_curated.json` als `"type": "mc"` / `"tf"`, dann:

```bash
# 1. Text-Karten inkl. Pseudo-MC (Einfach mit ☐ Ankreuzen)
python scripts/import_lecture_cards.py "{Kurs}"

# 2. Echte MC aus curated (Deck/Tag aus anki.json je Kapitel)
python scripts/import_mc_cards.py "{Kurs}" --dry-run
python scripts/import_mc_cards.py "{Kurs}"

# 3. Bestehende Pseudo-MC migrieren (ein Kurs oder ganzes Semester)
python scripts/import_mc_cards.py "{Kurs}" --migrate --dry-run
python scripts/import_mc_cards.py "{Kurs}" --migrate --delete-pseudo
python scripts/import_mc_cards.py --semester lectures/semester4 --migrate --delete-pseudo
```

Notiztyp: `AllInOne (kprim, mc, sc)` · Single Choice = Feld `QType` = `2`.

## Anki-Styling

Repo bearbeiten, dann pushen (Reihenfolge: CSS, dann Notiztypen):

```bash
python scripts/sync_anki_style.py push
python scripts/sync_anki_note_types.py push

python scripts/sync_anki_style.py pull
python scripts/sync_anki_note_types.py pull einfach
```

Add-on-Typen (Image Occlusion, Multiple Choice) nicht per `push` überschreiben.

## Backup

```bash
python -c "
import sys; sys.path.insert(0,'scripts')
from pathlib import Path; import shutil, datetime
from anki_paths import collection_db
dst = Path('backups')/f'collection_{datetime.datetime.now():%Y%m%d_%H%M%S}.anki2'
dst.parent.mkdir(exist_ok=True)
shutil.copy2(collection_db(), dst); print(dst)
"

python scripts/restore_backup.py
python scripts/restore_backup.py collection_20260101_120000.anki2
```

Anki vor `restore_backup.py` schließen.

## Skript-Übersicht

| Skript | Zweck |
|--------|--------|
| `batch_extract_course.py` | Alle PDFs in `raw/` |
| `extract_lecture.py` | Einzel-PDF |
| `classify_images.py` | IO-Kandidaten filtern |
| `import_lecture_cards.py` | Text-Karten aus `slides.json` |
| `import_io_stubs.py` | IO-Stub-Karten |
| `import_mc_cards.py` | Multiple-Choice (Add-on) |
| `sync_anki_style.py` | `_global_style.css` ↔ Anki |
| `sync_anki_note_types.py` | Notiztyp-Vorlagen ↔ Anki |
| `restore_backup.py` | Backup einspielen |
