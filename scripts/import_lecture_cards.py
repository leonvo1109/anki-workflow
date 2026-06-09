#!/usr/bin/env python3
"""
Erstellt: 2026-06-09
Kurzbeschreibung: Erzeugt und importiert BS-Karten aus slides.json (Einfach, Lückentext, Ankreuz).
Benötigte Abhängigkeiten: pip install requests (Anki mit AnkiConnect muss laufen)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("Fehler: requests fehlt. Bitte: pip install requests", file=sys.stderr)
    sys.exit(1)

ANKI_CONNECT = "http://127.0.0.1:8765"
COURSE = "4. Semester::Betriebssysteme 1"

CHAPTERS = {
    "bs-kapitel1-einfuehrung": {"deck": f"{COURSE}::Allgemein", "tag": "betriebssysteme::allgemein"},
    "bs-kapitel2-prozesse-threads-teil1": {"deck": f"{COURSE}::Prozesse & Threads", "tag": "betriebssysteme::prozesse"},
    "bs-kapitel2-prozesse-threads-2": {"deck": f"{COURSE}::Prozesse & Threads", "tag": "betriebssysteme::prozesse"},
    "bs-kapitel3-scheduling-1": {"deck": f"{COURSE}::Scheduling", "tag": "betriebssysteme::scheduling"},
    "bs-kapitel3-scheduling-2": {"deck": f"{COURSE}::Scheduling", "tag": "betriebssysteme::scheduling"},
    "bs-kapitel3-scheduling-3": {"deck": f"{COURSE}::Scheduling", "tag": "betriebssysteme::scheduling"},
    "bs-kapitel4-synchronisation-teil-1": {"deck": f"{COURSE}::Synchronisation", "tag": "betriebssysteme::synchronisation"},
    "bs-kapitel4-synchronisation-teil-2": {"deck": f"{COURSE}::Synchronisation", "tag": "betriebssysteme::synchronisation"},
}

SKIP_TITLE_PATTERNS = re.compile(
    r"^(University of|Recap|About us|Agenda|Literatur|Prüfung|Organisatorisches|𝑛෍)$",
    re.I,
)
SKIP_BULLET_PATTERNS = re.compile(
    r"^(https?://|▪\s*$|𝑛$|𝑖=1$|München$|Applied Sciences$)",
    re.I,
)
LOW_QUALITY_FRONT = re.compile(
    r"(innerhalb crt0|# noch nicht|▪acloser|▪apid ist|▪aint fork|▪Register, Virtual|"
    r"Division durch 0, Segmentation|Speicherabbildung, s\. später\)|"
    r"Zustandsdiagramm\?$|Dumps: Erstmalig|main\(\) …: Linker)",
    re.I,
)

# Handkuratierte Karten (Qualität + Spaßfaktor)
CURATED: dict[str, list[dict]] = {
    "bs-kapitel1-einfuehrung": [
        {"type": "mc", "front": "Welches BS ist monolithisch?", "back": "✓ Linux/Unix – alle Komponenten im Kernel", "distractors": ["MINIX (Mikrokernel)", "QNX (Mikrokernel)", "L4 (Mikrokernel)"]},
        {"type": "mc", "front": "Ring 0 auf x86?", "back": "✓ Supervisor Mode (Kernel)", "distractors": ["User Mode", "Treiber-Only Mode", "BIOS Mode"]},
        {"type": "tf", "front": "Stimmt: Ein Mikrokernel teilt seinen Adressraum mit Treibern.", "back": "✗ Nein – Treiber laufen im Userspace, großer Sicherheitsgewinn."},
        {"type": "tf", "front": "Stimmt: Kooperatives Scheduling = Timer reißt CPU weg.", "back": "✗ Nein – Programme geben CPU freiwillig ab."},
        {"type": "mc", "front": "Welcher System Call auf arm64?", "back": "✓ svc #0", "distractors": ["int 0x80", "ecall nur RISC-V Desktop", "syscall nur 32-bit"]},
    ],
    "bs-kapitel2-prozesse-threads-teil1": [
        {"type": "einfach", "front": "Was ist der Unterschied Programm vs. Prozess?", "back": "Programm = Datei/Code; Prozess = laufende Instanz mit eigenem Adressraum und Ressourcen."},
        {"type": "luecke", "text": "Nach {{c1::fork()}} gibt das Kind {{c2::0}} zurück, der Elternprozess die {{c3::PID des Kindes}}."},
        {"type": "einfach", "front": "Was macht `execve()`?", "back": "Ersetzt das aktuelle Programm durch ein neues – kehrt bei Erfolg nie zurück."},
        {"type": "mc", "front": "☐ Ankreuzen: Welches Signal ist nicht abfangbar?", "back": "✓ SIGKILL (9)", "distractors": ["SIGTERM (15)", "SIGINT (2)", "SIGHUP (1)"]},
        {"type": "luecke", "text": "Prozesszustände: {{c1::new}} → {{c2::ready}} → {{c3::running}} → {{c4::waiting}} → {{c5::terminated}}"},
        {"type": "einfach", "front": "Was speichert das PCB?", "back": "Zustand, PID, CPU-Register, VM-Mapping, offene Dateien."},
        {"type": "einfach", "front": "Warum ist Kontextwechsel teuer?", "back": "Register/PCB sichern, TLB invalidieren, Cache-Misses."},
        {"type": "mc", "front": "☐ Ankreuzen: ELF – Sektionen vs. Segmente?", "back": "✓ Sektionen = Linker, Segmente = Loader/OS", "distractors": ["Beides nur für Debugger", "Sektionen = Loader", "Segmente = Compiler"]},
        {"type": "einfach", "front": "Was macht crt0?", "back": "Initialisiert Binary (data/BSS), MCU-Services, springt in main()."},
        {"type": "tf", "front": "Stimmt: PE ist das Executable-Format unter Windows.", "back": "✓ Ja – Portable Executable."},
        {"type": "einfach", "front": "Was ist Pseudo-Parallelität?", "back": "Mehrere Prozesse wirken parallel, teilen sich aber zeitlich die CPU."},
        {"type": "mc", "front": "☐ Ankreuzen: Welches Format nutzt Linux?", "back": "✓ ELF", "distractors": ["PE", "Mach-O", "COFF only"]},
    ],
    "bs-kapitel2-prozesse-threads-2": [
        {"type": "einfach", "front": "Thread vs. Prozess – kurz?", "back": "Thread = Ablaufeinheit im Prozess (eigener Stack); Prozess = Ressourcencontainer mit ≥1 Thread."},
        {"type": "mc", "front": "☐ Ankreuzen: Linux NPTL Modell?", "back": "✓ 1:1 (ein Kernel-Thread pro User-Thread)", "distractors": ["M:1 Green Threads", "M:N Hybrid only", "Kein Threading"]},
        {"type": "einfach", "front": "Kernel-Level vs. User-Level Threads?", "back": "Kernel-Level: OS schedult; User-Level: Scheduler im Prozess, Kernel sieht nur einen Prozess."},
        {"type": "einfach", "front": "Was sind Kernel-Threads (kthreads)?", "back": "Threads in Ring 0, vom Kernel gestartet – ≠ Kernel-Level User-Threads."},
        {"type": "einfach", "front": "Problem User-Level Threads?", "back": "Blockierendes I/O blockiert ganzen Prozess; keine echte Multi-Core-Parallelität."},
        {"type": "luecke", "text": "POSIX: {{c1::pthread_create}} startet, {{c2::pthread_join}} wartet, {{c3::pthread_detach}} gibt Ressourcen frei."},
        {"type": "tf", "front": "Stimmt: Green Threads werden vom Linux-Kernel einzeln geschedult.", "back": "✗ Nein – Kernel kennt nur den Prozess."},
        {"type": "mc", "front": "☐ Ankreuzen: `clone()` in Linux?", "back": "✓ Erzeugt Thread/Prozess mit geteilten Ressourcen", "distractors": ["Nur Speicher kopieren", "Nur Signal senden", "Ersetzt execve"]},
    ],
    "bs-kapitel3-scheduling-1": [
        {"type": "mc", "front": "☐ Ankreuzen: Kooperativ vs. präemptiv?", "back": "✓ Präemptiv = Timer entzieht CPU", "distractors": ["Kooperativ = Timer entzieht CPU", "Beides identisch", "Nur Echtzeit ist präemptiv"]},
        {"type": "einfach", "front": "CPU-bound vs. I/O-bound?", "back": "CPU-bound: lange Rechenphasen; I/O-bound: viel Warten auf Ein-/Ausgabe."},
        {"type": "einfach", "front": "Wann läuft der Scheduler?", "back": "Prozessende, I/O-Wait, Timer-Tick, HW-Interrupt, Syscall."},
        {"type": "tf", "front": "Stimmt: Häufige Kontextwechsel erhöhen immer den Durchsatz.", "back": "✗ Nein – mehr Overhead, Reaktivität steigt."},
    ],
    "bs-kapitel3-scheduling-2": [
        {"type": "einfach", "front": "Turnaround-Zeit?", "back": "t_ende − t_start; nur zum Vergleich von Scheduling-Verfahren."},
        {"type": "luecke", "text": "Reaktionszeit > {{c1::100–200 ms}} wird als {{c2::störend}} empfunden."},
        {"type": "einfach", "front": "Nachteil FCFS?", "back": "Convoy-Effekt: lange Jobs verlängern Wartezeit kurzer Jobs."},
        {"type": "mc", "front": "☐ Ankreuzen: SJF Problem?", "back": "✓ Starvation langer Jobs", "distractors": ["Zu viel Overhead", "Nur für Echtzeit", "Kein Preemption möglich"]},
        {"type": "einfach", "front": "SRTF?", "back": "Präemptives SJF nach kürzester Restlaufzeit."},
        {"type": "mc", "front": "☐ Ankreuzen: RR Quantum typisch?", "back": "✓ 10–100 ms", "distractors": ["1–5 ms immer optimal", "1–2 s", "Unbegrenzt"]},
        {"type": "mc", "front": "☐ Ankreuzen: Priorität in Linux/nice?", "back": "✓ Höhere Priorität = niedrigere nice-Zahl", "distractors": ["Höhere nice = höhere Priorität", "Priorität nur für Root", "Keine Prioritäten in Linux"]},
        {"type": "einfach", "front": "Was ist Aging?", "back": "Priorität wartender Prozesse wird schrittweise erhöht → verhindert Starvation."},
        {"type": "einfach", "front": "MLFQ – Priority Boost?", "back": "Verhindert Starvation und Cheating (I/O-Jobs dauerhaft oben)."},
        {"type": "tf", "front": "Stimmt: SJF minimiert die durchschnittliche Ausführungsdauer.", "back": "✓ Ja – optimal bei bekannter Laufzeit."},
        {"type": "einfach", "front": "Gang Scheduling?", "back": "Gleiche Prozesse auf gleiche CPUs legen → Cache-Warmbleiben."},
    ],
    "bs-kapitel3-scheduling-3": [
        {"type": "luecke", "text": "CFS: Prozess mit kleinster {{c1::vruntime}} läuft als nächstes ({{c2::Rot-Schwarz-Baum}})."},
        {"type": "einfach", "front": "Was ist vruntime?", "back": "Virtuelle Laufzeit – wer am wenigsten CPU bekam, wird bevorzugt."},
        {"type": "mc", "front": "☐ Ankreuzen: SCHED_FIFO?", "back": "✓ Echtzeit, läuft bis Blockade/Preemption", "distractors": ["Nur Batch", "Fair Share für alle", "Niedrigste Priorität"]},
        {"type": "einfach", "front": "EEVDF (Linux ≥6.6)?", "back": "Wählt eligible Prozess mit frühester virtual deadline – bessere Latenz-Garantien als CFS."},
        {"type": "tf", "front": "Stimmt: `nice 19` bedeutet niedrigste User-Priorität.", "back": "✓ Ja – höhere nice = niedrigere Priorität."},
    ],
    "bs-kapitel4-synchronisation-teil-1": [
        {"type": "einfach", "front": "Was ist eine Race Condition?", "back": "Ergebnis hängt von der Ausführungsreihenfolge ab – kritischer Abschnitt ungeschützt."},
        {"type": "mc", "front": "☐ Ankreuzen: Spin Lock sinnvoll wenn…?", "back": "✓ Kritischer Abschnitt sehr kurz", "distractors": ["Lock lange gehalten", "Nur in User-Space ohne Atomics", "Immer besser als Mutex"]},
        {"type": "luecke", "text": "Semaphore: {{c1::P()}}/wait dekrementiert, {{c2::V()}}/signal inkrementiert – beides muss {{c3::atomar}} sein."},
        {"type": "mc", "front": "☐ Ankreuzen: Binäre Semaphore Init=1?", "back": "✓ Mutex", "distractors": ["N Ressourcen zählen", "Nur für Signale", "Deadlock-Detektor"]},
        {"type": "einfach", "front": "`volatile` thread-safe?", "back": "Nein – verhindert nur Compiler-Optimierung, kein atomares Read-Modify-Write."},
        {"type": "einfach", "front": "TSL und XCHG?", "back": "Atomare Hardware-Primitiven (Test-and-Set, Exchange) für Locks."},
        {"type": "einfach", "front": "Deadlock – ein Satz?", "back": "Gegenseitiges Warten auf Ressourcen (zirkuläre Lock-Abhängigkeit)."},
        {"type": "mc", "front": "☐ Ankreuzen: Message Passing vs. Shared Memory?", "back": "✓ Message Passing = klarer, mehr Overhead", "distractors": ["Shared Memory immer sicherer", "Beides identisch", "Nur Pipes möglich"]},
        {"type": "tf", "front": "Stimmt: `counter++` ist atomar.", "back": "✗ Nein – load, add, store in drei Schritten."},
    ],
    "bs-kapitel4-synchronisation-teil-2": [
        {"type": "einfach", "front": "Was ist ein Futex?", "back": "Fast Userspace Mutex – Syscall nur bei Blockierung, sonst atomare Ops."},
        {"type": "einfach", "front": "Condition Variable – wozu?", "back": "Warten auf beliebige Bedingung; `pthread_cond_wait` gibt Mutex atomar frei."},
        {"type": "einfach", "front": "Rekursives Mutex – wann?", "back": "Wenn derselbe Thread Lock erneut nimmt (z.B. init→open), sonst Self-Deadlock."},
        {"type": "luecke", "text": "Prod/Cons: {{c1::empty=N}}, {{c2::full=0}}, {{c3::mutex=1}}"},
        {"type": "einfach", "front": "ABA-Problem bei CAS?", "back": "Wert wird A→B→A; Compare sieht unverändert, obwohl Zustand gewechselt hat."},
        {"type": "mc", "front": "☐ Ankreuzen: Pipe nach fork()?", "back": "✓ Eltern schreibt fd[1], Kind liest fd[0]", "distractors": ["Gemeinsamer Speicher ohne fd", "Nur Kernel-Threads", "Automatisch thread-safe Counter"]},
        {"type": "tf", "front": "Stimmt: RCU erlaubt paralleles Lesen ohne Lock.", "back": "✓ Ja – Schreiben auf Kopie, dann atomarer Tausch."},
    ],
}

# Updates + Löschungen bestehender Notizen
CLEANUP = {
    "delete_note_ids": [1778345420611],  # IPC-Duplikat
    "updates": [
        {
            "id": 1778344016345,
            "fields": {
                "Rückseite": "Zugriff auf Ressourcen nur über das BS (Multiplexing). Programme können nicht direkt auf fremden Speicher/Hardware zugreifen – Isolation verhindert Datenmischung und unberechtigte Zugriffe."
            },
        },
        {
            "id": 1778344360066,
            "fields": {
                "Text": "<b>CPU-Modi</b><br>Generell: {{c1::Supervisor Mode}} + {{c1::User Mode}}<br>x86 Ring 0 = {{c2::Kernel}}, Ring 3 = {{c2::User}}"
            },
        },
        {
            "id": 1779191159137,
            "fields": {
                "Vorderseite": "Semaphore – wofür? (kurz)",
                "Rückseite": "Zähler für begrenzte Ressourcen + Warteschlange. P() = nehmen/warten, V() = freigeben/wecken.",
            },
        },
        {
            "id": 1779191316415,
            "fields": {
                "Vorderseite": "P() und V() – was passiert?",
                "Rückseite": "<b>P()</b> (Proberen): Zähler−1, blockiert wenn &lt;0.<br><b>V()</b> (Verhogen): Zähler+1, weckt einen Wartenden.",
            },
        },
        {
            "id": 1781032033558,
            "fields": {
                "Vorderseite": "VMM Variante 2 – in einem Satz?",
                "Rückseite": "Jeder Prozess hat eigenen virtuellen Adressraum; MMU mappt auf physischen Speicher.",
            },
        },
        {
            "id": 1778344687739,
            "fields": {
                "Vorderseite": "VMM Variante 1 – in einem Satz?",
                "Rückseite": "Jedes Programm bekommt eigene physische Bereiche; Code muss relokierbar (PIC) sein.",
            },
        },
    ],
    "move_to_sync_deck": [1779191159137, 1779191316415],
}


def invoke(action: str, **params):
    r = requests.post(ANKI_CONNECT, json={"action": action, "version": 6, "params": params}, timeout=120)
    r.raise_for_status()
    payload = r.json()
    if payload.get("error"):
        raise RuntimeError(payload["error"])
    return payload.get("result")


def is_skip_slide(slide: dict) -> bool:
    if slide.get("organizational"):
        return True
    title = (slide.get("title") or "").strip()
    if SKIP_TITLE_PATTERNS.match(title):
        return True
    if title.lower() in ("recap", "zusammenfassung") and not slide.get("bullets"):
        return True
    bullets = slide.get("bullets") or []
    questions = slide.get("questions") or []
    body = slide.get("body") or []
    if not bullets and not questions and len(" ".join(body)) < 30:
        if slide.get("diagram_heavy"):
            return True
    return False


def clean_bullet(text: str) -> str | None:
    t = re.sub(r"\s+", " ", text.strip())
    if len(t) < 12 or len(t) > 200:
        return None
    if SKIP_BULLET_PATTERNS.match(t):
        return None
    if t.startswith("Beispiel:") and len(t) < 25:
        return None
    return t


def bullet_to_question(title: str, bullet: str) -> str:
    title = (title or "BS").strip()[:40]
    b = bullet[:60]
    if "?" in bullet:
        return bullet.strip()
    if re.match(r"^(Was|Wie|Welche|Warum|Wieso|Wann)\b", bullet, re.I):
        return bullet.strip()
    return f"{title}: {b}?"


def bullet_to_answer(bullet: str, next_bullet: str | None) -> str:
    ans = bullet.strip()
    if next_bullet and len(ans) < 40 and not ans.endswith("."):
        nb = clean_bullet(next_bullet)
        if nb and len(nb) < 80:
            return f"{ans} – {nb}"
    return ans


def make_mc_card(front: str, back: str, distractors: list[str]) -> dict:
    opts = [back.replace("✓ ", "").replace("✗ ", "")] + distractors[:3]
    import random
    rng = random.Random(hash(front) & 0xFFFFFFFF)
    rng.shuffle(opts)
    correct = back.replace("✓ ", "").replace("✗ ", "")
    letters = "ABCD"
    lines = [f"☐ Ankreuzen: {front.replace('☐ Ankreuzen: ', '')}", ""]
    answer_letter = "A"
    for i, o in enumerate(opts[:4]):
        lines.append(f"({letters[i]}) {o}")
        if o == correct:
            answer_letter = letters[i]
    return {
        "modelName": "Einfach",
        "fields": {"Vorderseite": "\n".join(lines), "Rückseite": f"✓ ({answer_letter}) {correct}"},
    }


def curated_to_note(item: dict, deck: str, tag: str) -> dict:
    if item["type"] == "luecke":
        return {"deckName": deck, "modelName": "Lückentext", "fields": {"Text": item["text"], "Rückseite Extra": ""}, "tags": [tag]}
    if item["type"] == "mc":
        base = make_mc_card(item["front"], item["back"], item.get("distractors", []))
        base["deckName"] = deck
        base["tags"] = [tag]
        return base
    if item["type"] == "tf":
        return {"deckName": deck, "modelName": "Einfach", "fields": {"Vorderseite": item["front"], "Rückseite": item["back"]}, "tags": [tag]}
    return {"deckName": deck, "modelName": "Einfach", "fields": {"Vorderseite": item["front"], "Rückseite": item["back"]}, "tags": [tag]}


def norm_key(text: str) -> str:
    t = re.sub(r"<[^>]+>", "", text.lower())
    t = re.sub(r"[^a-zäöüß0-9]+", " ", t)
    return " ".join(t.split())[:100]


def is_low_quality_card(front: str, back: str) -> bool:
    if LOW_QUALITY_FRONT.search(front):
        return True
    f, b = norm_key(front), norm_key(back)
    if b and len(b) < 120 and (b in f or f in b):
        return True
    if len(back.strip()) < 20 and front.rstrip("?") == back.rstrip("?"):
        return True
    if ":" in front:
        bullet = front.split(":", 1)[-1].strip().rstrip("?")
        if bullet and len(bullet) > 10 and back.strip().startswith(bullet):
            return True
    if " – " in back:
        left = back.split(" – ")[0].strip()
        if left and (front.endswith(left + "?") or left in front):
            return True
    if front.strip().startswith("▪") or "…" in front:
        return True
    return False


def load_existing_fronts(deck_prefix: str) -> set[str]:
    try:
        nids = invoke("findNotes", query=f'deck:"{deck_prefix}"')
        keys: set[str] = set()
        for nid in nids:
            info = invoke("notesInfo", notes=[nid])[0]
            for fld in info["fields"].values():
                keys.add(norm_key(fld["value"]))
        return keys
    except Exception:
        return set()


def generate_from_slides(
    slides: list[dict],
    deck: str,
    tag: str,
    chapter: str,
    seen: set[str],
    *,
    auto_bullets: bool = True,
    max_per_slide: int = 2,
) -> list[dict]:
    notes: list[dict] = []

    for item in CURATED.get(chapter, []):
        note = curated_to_note(item, deck, tag)
        front = note["fields"].get("Vorderseite") or note["fields"].get("Text", "")
        key = norm_key(front)
        if key in seen:
            continue
        seen.add(key)
        notes.append(note)

    if not auto_bullets:
        return notes

    for slide in slides:
        if is_skip_slide(slide):
            continue
        title = slide.get("title") or f"Folie {slide['number']}"
        bullets = [clean_bullet(b) for b in (slide.get("bullets") or [])]
        bullets = [b for b in bullets if b]
        added = 0

        for q in slide.get("questions") or []:
            if added >= max_per_slide:
                break
            q = re.sub(r"^[▪\s]+", "", q.strip())
            if len(q) < 12 or "bis -ende" in q:
                continue
            if not q.endswith("?"):
                q = q + "?"
            key = norm_key(q)
            if key in seen:
                continue
            seen.add(key)
            back = "; ".join(bullets[:2]) if bullets else title
            notes.append({"deckName": deck, "modelName": "Einfach", "fields": {"Vorderseite": q[:120], "Rückseite": back[:280]}, "tags": [tag]})
            added += 1

        for i, bullet in enumerate(bullets):
            if added >= max_per_slide:
                break
            front = bullet_to_question(title, bullet)
            key = norm_key(front)
            if key in seen:
                continue
            seen.add(key)
            back = bullet_to_answer(bullet, bullets[i + 1] if i + 1 < len(bullets) else None)
            if re.search(r"\(\)|fork|exec|pthread|sem_|mq_|syscall", bullet):
                cloze = re.sub(r"(`?\w+\(\)`?)", r"{{c1::\1}}", bullet)
                if "{{c1::" in cloze:
                    notes.append({
                        "deckName": deck,
                        "modelName": "Lückentext",
                        "fields": {"Text": f"<i>{title[:30]}</i><br>{cloze}", "Rückseite Extra": ""},
                        "tags": [tag],
                    })
                    added += 1
                    continue
            if is_low_quality_card(front, back):
                continue
            notes.append({
                "deckName": deck,
                "modelName": "Einfach",
                "fields": {"Vorderseite": front[:110], "Rückseite": back[:220]},
                "tags": [tag],
            })
            added += 1

    return notes


def run_cleanup(dry_run: bool) -> None:
    if CLEANUP["delete_note_ids"]:
        if dry_run:
            print(f"[dry-run] Löschen: {CLEANUP['delete_note_ids']}")
        else:
            invoke("deleteNotes", notes=CLEANUP["delete_note_ids"])
            print(f"Gelöscht: {len(CLEANUP['delete_note_ids'])} Duplikate")

    for upd in CLEANUP["updates"]:
        if dry_run:
            print(f"[dry-run] Update Notiz {upd['id']}")
        else:
            invoke("updateNoteFields", note={"id": upd["id"], "fields": upd["fields"]})
    if CLEANUP["updates"] and not dry_run:
        print(f"Aktualisiert: {len(CLEANUP['updates'])} Notizen")

    sync_deck = f"{COURSE}::Synchronisation"
    for nid in CLEANUP.get("move_to_sync_deck", []):
        if dry_run:
            print(f"[dry-run] Verschiebe {nid} → {sync_deck}")
            continue
        cids = invoke("findCards", query=f"nid:{nid}")
        if cids:
            invoke("changeDeck", cards=cids, deck=sync_deck)
    if CLEANUP.get("move_to_sync_deck") and not dry_run:
        print(f"Verschoben: {len(CLEANUP['move_to_sync_deck'])} Notizen → Synchronisation")


def main() -> int:
    parser = argparse.ArgumentParser(description="Karten aus slides.json importieren")
    parser.add_argument(
        "course_dir",
        type=Path,
        help='Kursordner, z. B. "lectures/semester4/Mein Kurs"',
    )
    parser.add_argument("--chapter", action="append", help="Nur bestimmtes Kapitel (slug)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-cleanup", action="store_true")
    parser.add_argument(
        "--chapter1-mode",
        choices=["skip", "curated-only", "full"],
        default="curated-only",
        help="Kapitel 1: skip | nur MC/TF | voll",
    )
    args = parser.parse_args()

    course = args.course_dir.resolve()
    processed = course / "processed"
    if not processed.is_dir():
        print(f"processed/ fehlt: {processed}", file=sys.stderr)
        return 1

    chapters = args.chapter or list(CHAPTERS.keys())

    if not args.dry_run:
        try:
            invoke("version")
        except Exception as e:
            print(f"AnkiConnect nicht erreichbar: {e}", file=sys.stderr)
            return 1

    if not args.skip_cleanup:
        run_cleanup(args.dry_run)

    seen: set[str] = set()
    if not args.dry_run:
        seen = load_existing_fronts(COURSE)
        print(f"Bereits in Anki (Dedup): {len(seen)} Fronten")

    all_notes: list[dict] = []
    for slug in chapters:
        cfg = CHAPTERS.get(slug)
        if not cfg:
            print(f"Unbekanntes Kapitel: {slug}", file=sys.stderr)
            continue
        slides_path = processed / slug / "slides.json"
        if not slides_path.exists():
            print(f"Übersprungen (fehlt): {slides_path}", file=sys.stderr)
            continue
        slides = json.loads(slides_path.read_text(encoding="utf-8"))
        if slug == "bs-kapitel1-einfuehrung":
            if args.chapter1_mode == "skip":
                continue
            auto = args.chapter1_mode == "full"
        else:
            auto = True
        notes = generate_from_slides(slides, cfg["deck"], cfg["tag"], slug, seen, auto_bullets=auto)
        print(f"{slug}: {len(notes)} Karten")
        all_notes.extend(notes)

    print(f"Gesamt: {len(all_notes)} Karten")

    if args.dry_run:
        for n in all_notes[:5]:
            f = n["fields"]
            front = f.get("Vorderseite") or f.get("Text", "")[:60]
            print(f"  [{n['deckName']}] {front}…")
        if len(all_notes) > 5:
            print(f"  … und {len(all_notes) - 5} weitere")
        return 0

    batch = 40
    created = 0
    for i in range(0, len(all_notes), batch):
        chunk = all_notes[i : i + batch]
        result = invoke("addNotes", notes=chunk)
        created += sum(1 for x in result if x)
    print(f"Importiert: {created}/{len(all_notes)} Karten")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
