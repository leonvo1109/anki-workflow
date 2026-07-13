#!/usr/bin/env python3
"""
Erstellt: 2026-07-07
Kurzbeschreibung: Erzeugt aus bestehenden kuratierten Karten (anki_curated.json)
    viele schnelle "Quiz"-Varianten (Cloze / Single-Choice / True-False /
    Multiple-Choice / KPRIM) und importiert sie in ein separates Quiz-Deck.
    Ziel: Masse statt Qualitaet — schnelles, wiederholendes Anfangslernen.
    Die kuratierten Originalkarten werden NICHT veraendert.
Benoetigt: pip install requests, laufendes Anki mit AnkiConnect,
    Add-on 1566095810 (Notiztyp "AllInOne (kprim, mc, sc)") fuer SC/TF/MC/KPRIM.

Quelle wahlweise:
  - kuratierte JSON (--curated) oder
  - ein bestehendes Anki-Deck (--from-deck), z. B. wenn die Karten direkt in
    Anki gepflegt werden (keine anki_curated.json vorhanden).

Nutzung:
  python scripts/generate_quiz_cards.py \
    --curated "lectures/semester4/Computergrafik und Bildverarbeitung/cards/anki_curated.json" \
    --deck "Quiz::Computergrafik und Bildverarbeitung"

  python scripts/generate_quiz_cards.py \
    --from-deck "4. Semester::Software-Architektur" \
    --deck "Quiz::Software-Architektur"
  # Optional: --dry-run, --out dump.json, --seed 42
"""
from __future__ import annotations

import argparse
import hashlib
import html as _html
import json
import random
import re
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("Fehler: requests fehlt. Bitte: pip install requests", file=sys.stderr)
    sys.exit(1)

ANKI_CONNECT = "http://127.0.0.1:8765"
MC_MODEL = "AllInOne (kprim, mc, sc)"
CLOZE_MODEL = "Lückentext"
BASIC_MODEL = "Einfach"

STOPWORDS = {
    "oder", "und", "aber", "denn", "sondern", "sowie", "bzw", "eine", "einer",
    "eines", "einem", "einen", "kann", "wird", "werden", "wurde", "durch",
    "beim", "beim", "beim", "muss", "sein", "sind", "nicht", "nur", "auch",
    "mehr", "sehr", "z. b", "bspw", "etwa", "diese", "dieser", "dieses",
    "welche", "welcher", "welches", "aller", "alle", "allen", "sich", "dass",
    "wenn", "dann", "also", "somit", "damit", "dabei", "hierbei", "jeder",
    "jede", "jedes", "keine", "keiner", "gegenueber", "zwischen", "innerhalb",
    "ausserhalb", "wegen", "ueber", "unter", "gegen", "ohne", "immer",
    "moeglich", "moeglichen", "ihrer", "ihren", "seine", "seiner", "ihre",
    "vorliegenden", "jeweils", "folgende", "folgenden", "the", "and", "for",
    "with", "that", "this", "from", "sowie", "einer", "sowie",
}


# --------------------------------------------------------------------------- #
# AnkiConnect
# --------------------------------------------------------------------------- #
def invoke(action: str, **params):
    r = requests.post(
        ANKI_CONNECT,
        json={"action": action, "version": 6, "params": params},
        timeout=120,
    )
    r.raise_for_status()
    payload = r.json()
    if payload.get("error"):
        raise RuntimeError(payload["error"])
    return payload.get("result")


# --------------------------------------------------------------------------- #
# Text-Helfer
# --------------------------------------------------------------------------- #
def html_to_text(text: str) -> str:
    """Wandelt HTML-Kartenfelder in kompakten Klartext (Listen -> ' · ')."""
    t = text or ""
    t = re.sub(r"(?i)<\s*br\s*/?>", " · ", t)
    t = re.sub(r"(?i)</\s*(li|p|div|tr)\s*>", " · ", t)
    t = re.sub(r"(?i)<\s*li\s*>", "", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = _html.unescape(t)
    t = re.sub(r"\s*·\s*(?:·\s*)+", " · ", t)  # mehrfach-Trenner
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"^(?:·\s*)+|(?:\s*·)+$", "", t).strip()
    return t


def clean(text: str) -> str:
    t = html_to_text(text)
    t = re.sub(r"^(☐\s*Ankreuzen:|Stimmt:)\s*", "", t)
    t = re.sub(r"^[✓✗]\s*", "", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def shorten(text: str, limit: int = 120) -> str:
    t = clean(text)
    if len(t) <= limit:
        return t
    cut = t[: limit - 1]
    # an Wortgrenze abschneiden
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut + "…"


def norm(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", (text or "").lower())
    t = re.sub(r"\{\{c\d+::(.*?)\}\}", r"\1", t)
    return " ".join(re.sub(r"[^a-zäöüß0-9]+", " ", t).split())[:140]


def pick_cloze_term(answer: str, avoid: str = "") -> str | None:
    """Waehlt einen inhaltstragenden Begriff in der Antwort zum Verdecken."""
    avoid_tokens = set(re.findall(r"[a-zäöüß]{4,}", (avoid or "").lower()))
    candidates: list[tuple[int, int, str]] = []
    for m in re.finditer(r"[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß\-]{3,}", answer):
        tok = m.group(0)
        low = tok.lower()
        if low in STOPWORDS or low in avoid_tokens:
            continue
        is_cap = 1 if tok[0].isupper() else 0
        candidates.append((is_cap, len(tok), tok))
    if not candidates:
        return None
    candidates.sort(reverse=True)  # zuerst grossgeschrieben, dann laengster
    return candidates[0][2]


def make_cloze_text(front: str, answer: str) -> str | None:
    term = pick_cloze_term(answer, avoid=front)
    if not term:
        return None
    clozed = re.sub(
        re.escape(term), lambda _m: f"{{{{c1::{term}}}}}", answer, count=1
    )
    if "{{c1::" not in clozed:
        return None
    return f"<i>{shorten(front, 90)}</i><br>{clozed}"


# --------------------------------------------------------------------------- #
# Notiz-Builder
# --------------------------------------------------------------------------- #
def note_cloze(deck: str, text: str | None, topic: str) -> dict | None:
    if not text or "{{c" not in text:
        return None
    return {
        "deckName": deck,
        "modelName": CLOZE_MODEL,
        "fields": {"Text": text, "Rückseite Extra": ""},
        "tags": ["quiz", "quiz::cloze", f"quiz-topic::{topic}"],
    }


def _allinone(deck: str, qtype: str, question: str, options: list[str],
              answers: list[int], topic: str, subtag: str, extra: str = "") -> dict:
    fields = {
        "Question": question,
        "Title": "",
        "QType (0=kprim,1=mc,2=sc)": qtype,
        "Answers": " ".join(str(a) for a in answers),
        "Sources": "",
        "Extra 1": extra,
    }
    for i in range(5):
        fields[f"Q_{i + 1}"] = options[i] if i < len(options) else ""
    return {
        "deckName": deck,
        "modelName": MC_MODEL,
        "fields": fields,
        "tags": ["quiz", f"quiz::{subtag}", f"quiz-topic::{topic}"],
    }


def note_sc(deck: str, question: str, correct: str, distractors: list[str],
            topic: str, seed: str) -> dict | None:
    correct = shorten(correct, 130)
    opts = [correct] + [shorten(d, 130) for d in distractors[:3]]
    opts = list(dict.fromkeys(o for o in opts if o))  # dedup, leere raus
    if len(opts) < 3:
        return None
    rng = random.Random(hash("sc" + seed) & 0xFFFFFFFF)
    rng.shuffle(opts)
    answers = [1 if o == correct else 0 for o in opts]
    if sum(answers) != 1:
        return None
    return _allinone(deck, "2", shorten(question, 200), opts, answers,
                     topic, "sc", extra=f"✓ {correct}")


def note_tf(deck: str, statement: str, is_true: bool, topic: str,
            extra: str = "") -> dict:
    opts = ["Wahr", "Falsch"]
    answers = [1, 0] if is_true else [0, 1]
    return _allinone(deck, "2", statement, opts, answers, topic, "tf",
                     extra=extra or ("✓ Aussage ist wahr" if is_true
                                     else "✗ Aussage ist falsch"))


def note_group(deck: str, qtype: str, prompt: str, statements: list[tuple[str, int]],
               topic: str, subtag: str) -> dict | None:
    if len(statements) < 4:
        return None
    stmts = statements[:4]
    opts = [s for s, _ in stmts]
    answers = [a for _, a in stmts]
    if sum(answers) == 0:  # mind. eine richtige Aussage
        return None
    # Anki dedupliziert Notizen ueber das erste Feld (Question). Der Anweisungstext
    # ist bei allen KPRIM/MC gleich -> ohne eindeutigen Zusatz wuerde Anki alle
    # bis auf eine als Duplikat verwerfen. Stabiler Hash der Optionen sorgt fuer
    # Eindeutigkeit und idempotenten Re-Import.
    h = hashlib.md5("|".join(opts).encode("utf-8")).hexdigest()[:6]
    question = (f"{prompt}"
                f"<br><span style=\"color:#9aa0a6;font-size:11px\">"
                f"Block {topic} · {h}</span>")
    return _allinone(deck, qtype, question, opts, answers, topic, subtag)


# --------------------------------------------------------------------------- #
# Quelle vorbereiten
# --------------------------------------------------------------------------- #
def answer_of(item: dict) -> str:
    t = item.get("type")
    if t == "mc":
        return clean(item.get("back", ""))
    if t in ("basic", "einfach"):
        return clean(item.get("back", ""))
    return ""


def build_notes(curated: dict, deck: str, seed: int) -> list[dict]:
    rng = random.Random(seed)
    notes: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def add(note: dict | None):
        if not note:
            return
        f = note["fields"]
        first = f.get("Text") or f.get("Question", "")
        if note["modelName"] == MC_MODEL:
            opts = "|".join(f.get(f"Q_{i + 1}", "") for i in range(5))
            key = (note["modelName"], norm(first + " " + opts))
        else:
            key = (note["modelName"], norm(first))
        if key in seen:
            return
        seen.add(key)
        notes.append(note)

    # Antwort-Pool je Kapitel fuer Distraktoren / Falsch-Aussagen
    pools: dict[str, list[str]] = {}
    for slug, items in curated.items():
        pool = [answer_of(it) for it in items if answer_of(it)]
        pools[slug] = [shorten(p, 130) for p in pool if len(p) > 3]

    global_pool = [p for lst in pools.values() for p in lst]

    def distractors_for(slug: str, correct: str, n: int) -> list[str]:
        pool = [p for p in pools.get(slug, []) if norm(p) != norm(correct)]
        rng.shuffle(pool)
        picked = pool[:n]
        if len(picked) < n:
            extra = [p for p in global_pool
                     if norm(p) != norm(correct) and p not in picked]
            rng.shuffle(extra)
            picked += extra[: n - len(picked)]
        return picked

    for slug, items in curated.items():
        basics = [it for it in items if it.get("type") in ("basic", "einfach")]
        for i, it in enumerate(items):
            typ = it.get("type")
            front = clean(it.get("front", ""))
            if not front:
                continue

            if typ in ("basic", "einfach"):
                answer = clean(it.get("back", ""))
                if not answer:
                    continue
                q = front if front.endswith("?") else front
                dists = distractors_for(slug, answer, 3)
                variants = i % 3
                if variants == 0:
                    add(note_cloze(deck, make_cloze_text(front, answer), slug))
                    add(note_sc(deck, q, answer, dists, slug, seed=front))
                elif variants == 1:
                    add(note_sc(deck, q, answer, dists, slug, seed=front))
                    # False-TF: Frage mit fremder Antwort paaren
                    wrong = dists[0] if dists else None
                    if wrong:
                        stmt = (f"Passt diese Antwort zur Frage?<br>"
                                f"<b>Frage:</b> {shorten(front, 140)}<br>"
                                f"<b>Antwort:</b> {shorten(wrong, 140)}")
                        add(note_tf(deck, stmt, is_true=False, topic=slug,
                                    extra=f"✗ Richtig wäre: {shorten(answer, 160)}"))
                else:
                    add(note_cloze(deck, make_cloze_text(front, answer), slug))
                    # True-TF: korrekte Paarung
                    stmt = (f"Passt diese Antwort zur Frage?<br>"
                            f"<b>Frage:</b> {shorten(front, 140)}<br>"
                            f"<b>Antwort:</b> {shorten(answer, 140)}")
                    add(note_tf(deck, stmt, is_true=True, topic=slug))

            elif typ == "mc":
                correct = clean(it.get("back", ""))
                dists = [clean(d) for d in it.get("distractors", []) if clean(d)]
                add(note_sc(deck, front, correct, dists, slug, seed=front))
                add(note_cloze(deck, make_cloze_text(front, correct), slug))

            elif typ == "tf":
                is_true = it.get("back", "").strip().startswith("✓")
                add(note_tf(deck, front, is_true=is_true, topic=slug,
                            extra=clean(it.get("back", ""))))
                add(note_cloze(deck, make_cloze_text("Ergänze die Aussage:",
                                                     front), slug))

            elif typ == "luecke":
                text = it.get("text", "")
                if "{{c" in text:
                    add(note_cloze(deck, text, slug))

        # Kapitel-Bundles: KPRIM + MC-multi aus je 4 Frage->Antwort-Aussagen
        if len(basics) >= 4:
            n_bundles = min(3, max(1, len(basics) // 6))
            pool = basics[:]
            rng.shuffle(pool)
            for b in range(n_bundles):
                chunk = pool[b * 4:(b + 1) * 4]
                if len(chunk) < 4:
                    break
                statements: list[tuple[str, int]] = []
                truth_plan = [1, 0, 1, 0]
                rng.shuffle(truth_plan)
                for card, truth in zip(chunk, truth_plan):
                    f = shorten(clean(card["front"]), 90)
                    correct = clean(card["back"])
                    if truth:
                        ans = shorten(correct, 90)
                    else:
                        wrong = distractors_for(slug, correct, 1)
                        if not wrong:
                            truth = 1
                            ans = shorten(correct, 90)
                        else:
                            ans = shorten(wrong[0], 90)
                    statements.append((f"{f} → {ans}", truth))
                if sum(a for _, a in statements) == 0:
                    statements[0] = (statements[0][0], 1)
                qtype = "0" if b % 2 == 0 else "1"
                subtag = "kprim" if qtype == "0" else "mc"
                prompt = ("Bewerte jede Zuordnung Frage → Antwort "
                          "(richtig/falsch):" if qtype == "0"
                          else "Welche Zuordnungen Frage → Antwort sind korrekt?")
                add(note_group(deck, qtype, prompt, statements, slug, subtag))

    return notes


# --------------------------------------------------------------------------- #
# Import
# --------------------------------------------------------------------------- #
def import_notes(notes: list[dict]) -> tuple[int, int]:
    for deck in {n["deckName"] for n in notes}:
        invoke("createDeck", deck=deck)
    created = skipped = 0
    for note in notes:
        try:
            result = invoke("addNotes", notes=[note])
            if result and result[0]:
                created += 1
            else:
                skipped += 1
        except RuntimeError as e:
            if "duplicate" in str(e).lower():
                skipped += 1
            else:
                q = note["fields"].get("Question") or note["fields"].get("Text") or ""
                raise RuntimeError(f"{e} | {q[:60]}") from e
    return created, skipped


def load_from_anki(deck: str) -> dict:
    """Liest Q/A- und Cloze-Karten eines bestehenden Decks als curated-Struktur.

    Gruppierung nach Subdeck (letzte Deck-Ebene) als Thema; Image-Occlusion und
    triviale/leere Karten werden ausgelassen. Quiz-Decks werden ignoriert.
    """
    nids = invoke("findNotes", query=f'deck:"{deck}" -deck:"Quiz::*" -tag:quiz')
    curated: dict[str, list[dict]] = {}
    infos: list[dict] = []
    for i in range(0, len(nids), 100):
        infos += invoke("notesInfo", notes=nids[i : i + 100])
    # Deck je Notiz (ueber erste Karte) bestimmen
    for info in infos:
        model = info["modelName"]
        cids = info.get("cards") or []
        subdeck = deck.split("::")[-1]
        if cids:
            cinfo = invoke("cardsInfo", cards=cids[:1])
            if cinfo:
                subdeck = cinfo[0].get("deckName", deck).split("::")[-1]
        fields = info["fields"]
        item: dict | None = None
        if model in ("Einfach", "Basic", "Einfach (und Rückrichtung)"):
            front = clean(fields.get("Vorderseite", {}).get("value", ""))
            back = clean(fields.get("Rückseite", {}).get("value", ""))
            if len(front) >= 6 and len(back) >= 4:
                item = {"type": "basic", "front": front, "back": back}
        elif model in ("Lückentext", "Cloze"):
            text = fields.get("Text", {}).get("value", "")
            plain = re.sub(r"\{\{c\d+::(.*?)\}\}", r"\1", text)
            if "{{c" in text and len(html_to_text(plain)) >= 10:
                item = {"type": "luecke", "text": text}
        if item:
            curated.setdefault(subdeck, []).append(item)
    return curated


def main() -> int:
    ap = argparse.ArgumentParser(description="Quiz-Karten aus curated/Anki-Deck erzeugen")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--curated", type=Path, help="Pfad zu anki_curated.json")
    src.add_argument("--from-deck", help="Bestehendes Anki-Deck als Quelle")
    ap.add_argument("--deck", required=True, help="Ziel-Quiz-Deck")
    ap.add_argument("--seed", type=int, default=20260707)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", type=Path, help="Notizen zusätzlich als JSON dumpen")
    args = ap.parse_args()

    need_anki = not args.dry_run or bool(args.from_deck)
    if need_anki:
        try:
            invoke("version")
        except Exception as e:
            print(f"AnkiConnect nicht erreichbar: {e}", file=sys.stderr)
            return 1
        if not args.dry_run and MC_MODEL not in invoke("modelNames"):
            print(f"Notiztyp „{MC_MODEL}“ fehlt (Add-on 1566095810).",
                  file=sys.stderr)
            return 2

    if args.from_deck:
        curated = load_from_anki(args.from_deck)
        n_src = sum(len(v) for v in curated.values())
        print(f"Quelle: Deck „{args.from_deck}“ – {n_src} Karten in "
              f"{len(curated)} Themen")
    else:
        if not args.curated.exists():
            print(f"Nicht gefunden: {args.curated}", file=sys.stderr)
            return 1
        curated = json.loads(args.curated.read_text(encoding="utf-8"))

    notes = build_notes(curated, args.deck, args.seed)

    from collections import Counter
    by_type = Counter(n["fields"].get("QType (0=kprim,1=mc,2=sc)", "cloze")
                      if n["modelName"] == MC_MODEL else "cloze"
                      for n in notes)
    label = {"cloze": "Cloze", "0": "KPRIM", "1": "MC", "2": "SC/TF"}
    summary = ", ".join(f"{label.get(k, k)}={v}" for k, v in sorted(by_type.items()))
    print(f"{args.deck}: {len(notes)} Quiz-Karten ({summary})")

    if args.out:
        args.out.write_text(json.dumps(notes, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        print(f"  JSON-Dump: {args.out}")

    if args.dry_run:
        for n in notes[:6]:
            first = n["fields"].get("Text") or n["fields"].get("Question", "")
            print(f"  [{n['modelName']}] {first[:80]}")
        return 0

    created, skipped = import_notes(notes)
    print(f"Importiert: {created}/{len(notes)} ({skipped} Duplikate/übersprungen)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
