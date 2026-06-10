# Projekt: Erstellung von Anki-Karteikarten aus Vorlesungsmaterialien

## Ziel
Aus Vorlesungs-PDFs **strukturierte Lernmaterialien** erzeugen und daraus optimale Karteikarten per MCP in Anki importieren.

## KI-Rolle
Du bist ein Lernmethodik-Assistent. Du erstellst Karteikarten nach den Prinzipien der minimalen Information und aktiven Abfrage (FSRS). Du nutzt ausschließlich die MCP-Tools für Anki.

**Verboten für die Karteikartenerstellung:** Roh-PDFs oder unstrukturierte Quellen direkt lesen.  
**Pflicht:** Nur Dateien unter `processed/` und optional `cards/` verwenden.

---

## Ordnerstruktur (verbindlich)

```
anki-workflow/
├── backups/                    # Anki collection.anki2 Sicherungen
├── scripts/                    # Pipeline-Skripte (getrackt, s. scripts/README.md)
│   ├── lecture_import/         # Import-Modul
│   └── _scratch/               # kurzlebig, gitignored (short/ | long/)
├── lectures/
│   ├── _template/              # Vorlage für neue Kurse (raw / processed / cards)
│   └── semester{N}/
│       └── {Kursname}/
│           ├── exam.md           # Prüfungsformat & Schwerpunkte (von Cursor gelesen)
│           ├── anki.json         # Deck/Tags/Kapitel-Konfiguration
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
| `exam.md` | Prüfungsformat, Schwerpunkte, Kartentyp-Hinweise | Benutzer | **Cursor** (vor Kartenerstellung) |

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
2. `anki_create_notes` für Basic / Cloze / Type-In / Multiple Choice
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
   - **Vergleiche, Prüfungsfragen, True/False** → MC (Add-on) — siehe Abschnitt MC unten
   - **Aktiver Code** → Type-In

2. **Spezifische Regeln**:
   - Code-Lücken: eine logische Einheit pro Lücke
   - Bildkarten: bevorzugt eingebettete Grafik aus `images/`, sonst Seitenrender
   - SC: mindestens 4 Optionen, eine richtig; in `anki_curated.json` als `"type": "sc"` mit `distractors`
   - MC: mindestens 4 Optionen, mindestens eine richtig in `anki_curated.json`als `"type": "mc"`mit `distractors`
   - TF: mit Hilfe von Single Choice modellieren, für tiefere Zusammenhänge oder viele TF Fragen auch eventuell KPRIM verwenden
   - SC/MC/KPRIM/TF: vor allem um Wissen auf anderen Karten nochmal zu Wiederholen und damit zu festigen (nicht als alleinige Quelle für Wissen da nichts richtig "gemerkt" werden muss) und vor allem bei Konzepten mit hoher Verwechslungsgefahr und bekannten Pitfalls
   - Folienfragen (`questions` in `slides.json`) → bevorzugte Kartenfronten
   - Redundanzen erlaubt über mehrere Kartentypen um maximalen Lerneffekt bei genügend Abwechslung zu erzielen (um Gefahr von "Karte auswendig lernen" ohne Verständnis zu vermeiden)

3. **Mengenrichtlinie**:
   - Pro 10 **Inhaltsfolien** max. 10 inhaltlich komplexe Karten (ausgenommen SC/MC/KPRIM/TF)
   - Eine Folie mit 4 Stichpunkten → bis zu 4 Karten, nicht eine Sammelkarte
   - Bei zentralen/schwierigen Konzepten 1-3 SC/MC/KPRIM/TF Karten hinzufügen

4. **Sprache**:
   - Folien DE → Karten DE; Fachbegriffe EN mit DE-Erklärung

5. **Multiple Choice (MC)** — Workflow:

   | Stufe | Was | Werkzeug |
   |-------|-----|----------|
   | Entwurf | `mc` / `tf` in `cards/anki_curated.json` | Cursor |
   | Text-Import | Pseudo-MC (`Einfach`, `☐ Ankreuzen:`) | `import_lecture_cards.py` |
   | MC-Import | Interaktive Karten (`AllInOne (kprim, mc, sc)`) | `import_mc_cards.py` |
   | Migration | Bestehende Pseudo- → echte MC | `import_mc_cards.py --migrate --delete-pseudo` |

   **Voraussetzung:** Anki-Add-on [1566095810](https://ankiweb.net/shared/info/1566095810) (Multiple Choice), Anki neu starten.

   **Curated-Format `mc`:** `front`, `back` (mit `✓ ` vor der richtigen Antwort), `distractors` (3 falsche Optionen).

   **Curated-Format `tf`:** `front` mit `Stimmt: …`, `back` mit `✓` oder `✗`.

   Pseudo-MC nicht per MCP `anki_create_notes` nachbauen — immer `import_mc_cards.py` für den Notiztyp `AllInOne`.

6. **Backup‑Pflicht** (mehr als 5 Karten):
   ```bash
   cp ~/Library/Application\ Support/Anki2/${ANKI_PROFILE:-User}/collection.anki2 \
      ./backups/collection_$(date +%Y%m%d_%H%M%S).anki2
   ```
   Profil: Umgebungsvariable `ANKI_PROFILE` (Standard: `User`).

---

## Skripte

Nutzer-Befehle: `docs/commands.md` · Agent/Scratch-Policy: `docs/agents.md`

Neuer Kurs: `_template` kopieren → `exam.md` ausfüllen → PDFs nach `raw/` → `batch_extract_course.py` → `anki.json` → `import_lecture_cards.py --import-io`
