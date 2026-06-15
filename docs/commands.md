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

Pro Kurs: `anki.json` (Deck-Hierarchie), optional `cards/anki_curated.json`, `anki_cleanup.json`, `anki_locked.json`.

**Keine Kapitel-Tags mehr** — Zuordnung läuft über Subdecks (`deck_suffix` in `anki.json`). Tags nur für Workflow (`wf::…`) und Pipeline (`mc-interactive`, `io-stub`).

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

# 2. Echte MC aus curated (Deck aus anki.json je Kapitel)
#    Löscht automatisch die Einfach-Duplikate aus Stufe 1 (Pseudo-MC + TF).
#    Opt-out: --keep-pseudo
python scripts/import_mc_cards.py "{Kurs}" --dry-run
python scripts/import_mc_cards.py "{Kurs}"

# 3. Bestehende (Alt-)Pseudo-MC migrieren (ein Kurs oder ganzes Semester)
python scripts/import_mc_cards.py "{Kurs}" --migrate --dry-run
python scripts/import_mc_cards.py "{Kurs}" --migrate --delete-pseudo
python scripts/import_mc_cards.py --semester lectures/semester4 --migrate --delete-pseudo
```

Notiztyp: `AllInOne (kprim, mc, sc)` · Single Choice = Feld `QType` = `2`.

## Qualitätsprüfung

Vor dem Import (curated JSON) und nach dem Import (Live-Deck) laufen lassen:

```bash
python scripts/lint_cards.py "{Kurs}"          # nur cards/anki_curated.json
python scripts/lint_cards.py "{Kurs}" --live   # zusätzlich das Anki-Deck
```

Findet u. a.: Meta-Karten (Klausurorganisation statt Stoff), doppelte Fronten,
Einfach-Duplikate interaktiver MC/TF-Karten, Pseudo-MC-Reste, veraltete
Antwortbuchstaben in `Extra 1`, kaputte MC/TF-Formate, Abweichungen gesperrter Karten.

## Lern-Session (Workflow-Tags)

Tags mit Prefix `wf::` — Kommunikation während/nach dem Lernen **ohne Notiz-IDs**.

```bash
# Verfügbare Tags anzeigen
python scripts/process_session_tags.py --list-tags

# Nach der Lern-Session: Queue für die KI erzeugen
python scripts/process_session_tags.py "{Kurs}"

# wf::lock → Sperrliste (Import überschreibt nicht)
python scripts/process_session_tags.py "{Kurs}" --sync-locks

# Nach KI-Arbeit: Fix-Tags entfernen, wf::done setzen
python scripts/process_session_tags.py "{Kurs}" --complete
```

| Tag | Bedeutung |
|-----|-----------|
| `wf::fix::unclear` | Frage unklar |
| `wf::fix::answer` | Antwort falsch/unvollständig |
| `wf::fix::typo` | Tippfehler |
| `wf::fix::distractor` | MC-Distraktor prüfen |
| `wf::fix::split` | Karte aufteilen |
| `wf::fix::merge` | Redundant |
| `wf::fix::type` | Falscher Kartentyp |
| `wf::fix::image` | Bild/IO-Problem |
| `wf::lock` | Manuell bearbeitet — nicht überschreiben |
| `wf::done` | Von KI erledigt (wird bei `--complete` gesetzt) |

Ausgabe: `cards/session_queue.json` — im Chat: „Session-Tags auswerten“.

## Manuell überarbeitete Karten sperren (Alternativ)

Bevorzugt `wf::lock` in Anki + `--sync-locks`. Sonst:

```bash
# Anki-Notiz-ID sperren (Notiz-ID: Rechtsklick → ID kopieren, oder Browser)
python scripts/mark_manual_cards.py "{Kurs}" --note-id 1234567890 --comment "Antwort gekürzt"

# Kuratierten JSON-Eintrag sperren (Kapitel + 0-basierter Index)
python scripts/mark_manual_cards.py "{Kurs}" --curated kapitel-slug 2

# Gesperrte Karten anzeigen
python scripts/mark_manual_cards.py "{Kurs}" --list

# Anki-Stand gesperrter Karten nach anki_curated.json zurückschreiben
python scripts/mark_manual_cards.py "{Kurs}" --sync-curated

# Sperre aufheben (Lock-ID oder note-id)
python scripts/mark_manual_cards.py "{Kurs}" --unlock 1234567890
```

Gesperrte Karten werden beim Import nicht neu erzeugt; Cleanup-Updates/Löschungen für diese Notiz-IDs werden übersprungen. Die KI darf gesperrte `anki_curated.json`-Einträge nicht überschreiben.

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
python scripts/backup_collection.py            # Backup anlegen (Profil aus .env)
python scripts/backup_collection.py --check    # Exit 0, wenn Backup ≤1h alt

python scripts/restore_backup.py
python scripts/restore_backup.py collection_20260101_120000.anki2
```

Anki vor `restore_backup.py` schließen.

## Skript-Übersicht

| Skript | Zweck |
|--------|--------|
| `batch_extract_course.py` | Alle PDFs in `raw/` (rekursiv) |
| `extract_lecture.py` | Einzel-PDF |
| `classify_images.py` | IO-Kandidaten filtern |
| `import_lecture_cards.py` | Text-Karten aus `slides.json` |
| `import_io_stubs.py` | IO-Stub-Karten |
| `import_mc_cards.py` | Multiple-Choice (Add-on) |
| `lint_cards.py` | Karten-Qualitätsprüfung (curated + Live-Deck) |
| `process_session_tags.py` | Session-Tags auswerten (`wf::…` → `session_queue.json`) |
| `mark_manual_cards.py` | Sperrliste pflegen (`anki_locked.json`, Fallback) |
| `backup_collection.py` | Backup anlegen / Aktualität prüfen |
| `sync_anki_style.py` | `_global_style.css` ↔ Anki |
| `sync_anki_note_types.py` | Notiztyp-Vorlagen ↔ Anki |
| `restore_backup.py` | Backup einspielen |
