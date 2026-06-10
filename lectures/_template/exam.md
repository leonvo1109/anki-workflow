# Prüfung – {Kursname}

> **Für Agents:** Diese Datei **vor** Kartenerstellung lesen. Sie steuert Kartentyp, Tiefe und Ausschlüsse.
> Folien sind oft Einstiegsmaterial — `exam.md` definiert, was prüfungsrelevant ist.

## Format

- **Art:** (z. B. schriftliche Klausur / Moodle-Test / mündlich)
- **Dauer:** (z. B. 90 min)
- **Hilfsmittel:** (z. B. keine / ein Blatt Formelsammlung)
- **Antwortform:** (z. B. 100 % Multiple Choice, auch Zuordnung / Lückentext in Moodle)

## Schwerpunkte

Welche Themen sind prüfungsrelevant? Was wird eher vertieft abgefragt?

- 
- 

## Kartenausrichtung

| Prüfungsformat | Bevorzugter Kartentyp in `anki_curated.json` |
|----------------|-----------------------------------------------|
| Single-Choice / Ankreuzen | `"type": "mc"` (4 Optionen, 1 richtig) |
| Wahr/Falsch | `"type": "tf"` |
| Definitionen, Erklärungen | `"type": "einfach"` |
| Formeln, Syntax, Schrittfolgen | `"type": "luecke"` |
| Diagramme | IO aus `occlusion/manifest.json` |

**Tiefe:** Nur zentrale, prüfbare Konzepte — keine Organisatorik, Anekdoten, PINGO-Folien, Implementierungs-Walkthroughs Zeile für Zeile.

**Distraktoren (MC):** Plausible Fehlantworten aus typischen Verwechslungen der Vorlesung, nicht absurd.

## Nicht prüfungsrelevant (weglassen)

- Organisatorisches (Moodle, Termine, Schein)
- Reine Motivations-/Geschichtsfolien
- 

## Beispielaufgaben / Altklausur

Kurzbeschreibung oder Link — hilft bei Stil und Schwierigkeit der Distraktoren:

- 

## Notizen

Freitext (z. B. „Prof. betont LL(1)-Tabellen“, „kein Assembler-Code auswendig“):
