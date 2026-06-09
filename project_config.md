# Projekt: Erstellung von Anki-Karteikarten aus Vorlesungsmaterialien

## Ziel
Aus Vorlesungs-PDFs **strukturierte Lernmaterialien** erzeugen und daraus optimale Karteikarten per MCP in Anki importieren.

## KI-Rolle
Du bist ein Lernmethodik-Assistent. Du erstellst Karteikarten nach den Prinzipien der minimalen Information und aktiven Abfrage (SM-2). Du nutzt ausschließlich die MCP-Tools für Anki.

**Verboten für die Karteikartenerstellung:** Roh-PDFs oder unstrukturierte Quellen direkt lesen.  
**Pflicht:** Nur Dateien unter `processed/` und optional `cards/` verwenden.

---

## Ordnerstruktur (verbindlich)

```
anki-workflow/
├── backups/                    # Anki collection.anki2 Sicherungen
├── scripts/                    # Extraktion, IO-Stubs, Wiederherstellung
├── lectures/
│   ├── _template/              # Vorlage für neue Kurse (raw / processed / cards)
│   └── semester{N}/
│       └── {Kursname}/
│           ├── raw/              # Rohdaten: PDFs, Scans, Originalbilder (unverändert)
│           ├── processed/        # Aufbereitete Daten (von Skripten erzeugt)
│           │   └── {kapitel-slug}/
│           │       ├── meta.json
│           │       ├── slides.json       # maschinenlesbar, primäre KI-Quelle
│           │       ├── slides.md         # menschenlesbar, gleicher Inhalt
│           │       ├── .staging/images/  # temporär (nur bis classify läuft)
│           │       ├── images/         # nur behaltene Diagramme (nach classify)
│           │       └── occlusion/
│           │           └── manifest.json   # IO-Kandidaten
│           └── cards/            # Kartenentwürfe vor Anki-Import (optional)
│               └── {kapitel}-draft.md
├── project_config.md
└── workflow_status.md
```

### Bedeutung der Ebenen

| Ebene | Inhalt | Wer schreibt | Wer liest |
|-------|--------|--------------|-----------|
| `raw/` | Original-PDFs | Benutzer | **nur** Extraktions-Skripte |
| `processed/` | Folien, JSON, Bilder, IO-Manifest | Skripte | **Cursor** (Kartenerstellung) |
| `cards/` | Freigegebene Kartenentwürfe | Cursor | Cursor → MCP Import |

---

## Pipeline (verbindlicher Ablauf)

### Phase 1 – Extraktion (Skripte, nicht Cursor manuell)

```bash
# Abhängigkeiten (einmalig)
pip install -r scripts/requirements.txt

# Einzelnes Kapitel
python scripts/extract_lecture.py \
  "lectures/semester4/Betriebssysteme 1/raw/Betriebssysteme_Kapitel1_Einfuehrung.pdf" \
  --course-dir "lectures/semester4/Betriebssysteme 1"

# Gesamter Kurs
python scripts/batch_extract_course.py "lectures/semester4/Betriebssysteme 1"
```

**Erzeugt pro PDF:**
- `slides.json` / `slides.md` – Folie für Folie: Titel, Stichpunkte, Folienfragen, Flags (`organizational`, `occlusion_candidate`)
- `images/` – PNG-Seitenrender + extrahierte Diagramme
- `occlusion/manifest.json` – nach Klassifikation: `io_recommended` + `rejected`

### Phase 1b – Bild-Klassifikation (on-device, optional `--classify`)

```bash
python scripts/classify_images.py "lectures/.../processed/bs-kapitel1-einfuehrung"
# oder bei Extraktion: extract_lecture.py ... --classify
```

- **Apple Vision** (macOS, kein Modell-Download): kurze Labels + Heuristiken
- Pro Bild: `description`, `category`, `io_score` (0–1)
- Buchcover/Logos/Titelfolien → `rejected`; echte Diagramme → `io_recommended`
- **Speicherung:** Extraktion → `.staging/images/` (Zwischenspeicher für Vision). Nach Klassifikation werden verworfene Dateien gelöscht; nur `io_recommended` bleibt in `images/`.
- Übersicht: `occlusion/classification.md`

### Phase 2 – Kartenentwurf (Cursor)

1. `workflow_status.md` lesen
2. **`processed/{kapitel}/slides.json`** (oder `slides.md`) lesen – **nicht** `raw/`
3. Organisatorische Folien (`organizational: true`) **überspringen**
4. Entwurf nach Regeln unten in `cards/{kapitel}-draft.md` schreiben
5. Fragen: „Soll ich diese N Karten importieren? (Ja/Nein/Bearbeiten)“

### Phase 3 – Anki-Import (MCP)

1. Backup prüfen/erstellen (s. unten)
2. `anki_create_notes` für Basic / Cloze / Type-In
3. **Image Occlusion** – siehe Abschnitt IO unten
4. `workflow_status.md` aktualisieren

---

## Image Occlusion (Diagramme)

Die MCP-Tools können **keine SVG-Masken** automatisch zeichnen. Der Workflow ist daher zweistufig:

| Schritt | Werkzeug | Ergebnis |
|---------|----------|----------|
| 1. Bilder extrahieren | `extract_lecture.py` | PNGs + `occlusion/manifest.json` |
| 2a. IO-Stubs importieren | `import_io_stubs.py` oder MCP `anki_create_notes` | Karte mit Bild + Header, **ohne Masken** |
| 2b. Masken ergänzen | Anki Desktop → Image Occlusion Enhanced Editor | Fertige IO-Karte |

**MCP-Stub-Felder** (Modell `Image Occlusion Enhanced`):
- `Header` – Folientitel
- `Image` – `<img src="…" />` (Datei vorher ins Anki-Mediapaket kopieren)
- `Question Mask` / `Answer Mask` – leer lassen bei Stubs
- `Footer` – z. B. Foliennummer
- Tag: `io-stub`

**Skript für Stubs (AnkiConnect):**
```bash
python scripts/import_io_stubs.py \
  "lectures/semester4/Betriebssysteme 1/processed/bs-kapitel1-einfuehrung" \
  --deck "4. Semester::Betriebssysteme 1::Allgemein"
```

Alternativ kann Cursor dieselben Notizen per `anki_create_notes` anlegen, wenn Bilder bereits in `collection.media` liegen.

---

## Regeln für die Karteikartenerstellung (Informatik)

1. **Kartentypen nach Inhalt**:
   - **Definitionen, Begriffe, Konzepte** → `Einfach` (ggf. `Einfach (und die umgekehrte Richtung)`)
   - **Code, Syntax, SQL, Regex** → `Lückentext`
   - **Algorithmen (Schrittfolgen)** → Sequential Cloze oder Ordering
   - **O-Notation** → `Einfach` (umgekehrt) oder Matching
   - **Diagramme, Architekturbilder** → `Image Occlusion Enhanced` (aus `occlusion/manifest.json`)
   - **Formeln** → `Lückentext` oder `Einfach (Antwort eintippen)`
   - **Vergleiche (TCP vs. UDP)** → MC / True-False
   - **Aktiver Code** → Type-In

2. **Spezifische Regeln**:
   - Code-Lücken: eine logische Einheit pro Lücke
   - Bildkarten: bevorzugt eingebettete Grafik aus `images/`, sonst Seitenrender
   - MC: mindestens 4 Optionen, eine richtig
   - Folienfragen (`questions` in `slides.json`) → bevorzugte Kartenfronten
   - Redundanzen erlaubt über mehrere Kartentypen

3. **Mengenrichtlinie**:
   - Pro 10 **Inhaltsfolien** max. 10 Karten
   - Eine Folie mit 4 Stichpunkten → bis zu 4 Karten, nicht eine Sammelkarte

4. **Sprache**:
   - Folien DE → Karten DE; Fachbegriffe EN mit DE-Erklärung

5. **Backup‑Pflicht** (mehr als 5 Karten):
   ```bash
   cp ~/Library/Application\ Support/Anki2/${ANKI_PROFILE:-User}/collection.anki2 \
      ./backups/collection_$(date +%Y%m%d_%H%M%S).anki2
   ```
   Profil: Umgebungsvariable `ANKI_PROFILE` (Standard: `User`).

---

## Skripte (`/scripts`)

| Skript | Zweck |
|--------|--------|
| `extract_lecture.py` | PDF → `processed/{slug}/` |
| `classify_images.py` | Bilder bewerten (Vision + Heuristiken) → gefiltertes Manifest |
| `vision_classify.swift` | Apple Vision Hilfsskript (macOS) |
| `batch_extract_course.py` | Alle PDFs in `raw/` eines Kurses (+ `--classify`) |
| `import_io_stubs.py` | IO-Kandidaten → Anki (AnkiConnect) |
| `restore_backup.py` | Backup zurückspielen |

- Dateinamen: klein, Unterstriche
- Kopfkommentar: Datum, Beschreibung, Abhängigkeiten
- Neue PDFs **immer zuerst** nach `lectures/.../raw/` legen, dann extrahieren

---

## Neuen Kurs anlegen

```bash
cp -r lectures/_template "lectures/semester4/Mein Kurs"
# PDFs nach .../Mein Kurs/raw/
python scripts/batch_extract_course.py "lectures/semester4/Mein Kurs"
```
