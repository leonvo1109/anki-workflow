# Anki Notiztypen – Übersicht

**Empfohlener Workflow (automatisch):**

```bash
# 1. Global CSS nach Anki
python scripts/sync_anki_style.py push

# 2. Notiztyp-Vorlagen nach Anki (alle editierbaren Typen)
python scripts/sync_anki_note_types.py push

# Status prüfen
python scripts/sync_anki_note_types.py status
python scripts/sync_anki_style.py status
```

**Bearbeiten:** JSON-Dateien in diesem Ordner (`*.json`) – dann `push`.  
**Von Anki holen:** `python scripts/sync_anki_note_types.py pull`

| Datei | Notiztyp | Bearbeitbar |
|-------|----------|-------------|
| `einfach.json` | Einfach | ✓ |
| `l-ckentext.json` | Lückentext | ✓ |
| `einfach-antwort-eintippen.json` | Einfach (Antwort eintippen) | ✓ |
| `einfach-und-die-umgekehrte-richtung.json` | Einfach (und die umgekehrte Richtung) | ✓ |
| `einfach-und-wahlweise-die-umgekehrte-richtung.json` | Einfach (und wahlweise …) | ✓ |
| `allinone-kprim-mc-sc.json` | Multiple Choice (Add-on) | 🔒 Referenz |
| `image-occlusion-enhanced.json` | Image Occlusion Enhanced | 🔒 Referenz |
| `bildverdeckung.json` | Bildverdeckung | 🔒 Referenz |

Gemeinsames Styling (alle editierbaren Typen):

```css
@import url("_global_style.css");
```

---

## Einfach

**Felder:** `Vorderseite`, `Rückseite`

### Styling

```css
@import url("_global_style.css");
```

### Karte 1 – Vorderseite

```html
<div class="card-box">
  {{Vorderseite}}
</div>
```

### Karte 1 – Rückseite

```html
<div class="card-box">
  {{Vorderseite}}
  <hr id="answer">
  {{Rückseite}}
</div>
```

---

## Lückentext

**Felder:** `Text`, `Rückseite Extra`

### Styling

```css
@import url("_global_style.css");
```

### Lückentext – Vorderseite

```html
<div class="card-box">
  {{cloze:Text}}
</div>
```

### Lückentext – Rückseite

```html
<div class="card-box">
  {{cloze:Text}}
  {{#Rückseite Extra}}
    <hr id="answer">
    {{Rückseite Extra}}
  {{/Rückseite Extra}}
</div>
```

---

## Einfach (Antwort eintippen)

Wie **Einfach**, zusätzlich mit Type-In über `{{type:Rückseite}}`:

### Vorderseite

```html
<div class="card-box">
  {{Vorderseite}}
  <div class="type-answer">{{type:Rückseite}}</div>
</div>
```

### Rückseite

```html
<div class="card-box">
  {{Vorderseite}}
  <hr id="answer">
  <div class="type-answer">{{type:Rückseite}}</div>
</div>
```

Vorne erscheint das Eingabefeld; hinten der Vergleich (getippt vs. korrekt).  
Styling: `#typeans` / `.type-answer` in `_global_style.css` (Desktop vs. Mobile unterschiedlich).

---

## Einfach (und die umgekehrte Richtung)

**Karte 1:** wie Einfach  
**Karte 2 (umgekehrt):**

### Vorderseite

```html
<div class="card-box">
  {{Rückseite}}
</div>
```

### Rückseite

```html
<div class="card-box">
  {{Rückseite}}
  <hr id="answer">
  {{Vorderseite}}
</div>
```

---

## Einfach (und wahlweise die umgekehrte Richtung)

**Karte 1:** wie Einfach  
**Karte 2** (nur wenn Feld `Umgekehrte Richtung hinzufügen` gesetzt):

### Vorderseite

```html
{{#Umgekehrte Richtung hinzufügen}}
<div class="card-box">
  {{Rückseite}}
</div>
{{/Umgekehrte Richtung hinzufügen}}
```

### Rückseite

```html
{{#Umgekehrte Richtung hinzufügen}}
<div class="card-box">
  {{Rückseite}}
  <hr id="answer">
  {{Vorderseite}}
</div>
{{/Umgekehrte Richtung hinzufügen}}
```

---

## Add-on-Typen (nur Referenz)

Diese werden vom Add-on verwaltet – **nicht** per `push` überschreiben (außer `--force-addon`).

- **AllInOne (kprim, mc, sc)** – Multiple Choice Add-on `1566095810`
- **Image Occlusion Enhanced** – IO-Add-on
- **Bildverdeckung** – natives IO-Modell

Aktuelle Vorlagen als Backup: `allinone-kprim-mc-sc.json`, `image-occlusion-enhanced.json`, `bildverdeckung.json`

---

## Manuell in Anki einfügen

1. **Werkzeuge → Notiztypen verwalten** → Typ wählen → **Karten…**
2. **Styling** → CSS aus diesem Dokument
3. Pro Karte **Vorderseite** / **Rückseite** aus den Blöcken oben
4. Oder: `pull` ausführen, JSON bearbeiten, `push` ausführen
