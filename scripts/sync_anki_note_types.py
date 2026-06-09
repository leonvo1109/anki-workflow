#!/usr/bin/env python3
"""
Erstellt: 2026-06-09
Kurzbeschreibung: Synchronisiert Notiztyp-Vorlagen (media/note-types/*.json) ↔ Anki.
Benötigte Abhängigkeiten: requests (AnkiConnect muss laufen)

Befehle:
  pull              – alle Notiztypen von Anki ins Repo exportieren
  push [slug]       – einen oder alle editierbaren Typen nach Anki pushen
  status            – vergleicht Repo mit Anki (CSS + Template-Hashes)
  list              – zeigt verfügbare JSON-Dateien
"""
from __future__ import annotations

import argparse
import hashlib
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
NOTE_TYPES_DIR = Path(__file__).resolve().parent.parent / "media" / "note-types"
ADDON_MANAGED = {
    "AllInOne (kprim, mc, sc)",
    "Image Occlusion Enhanced",
}


def invoke(action: str, **params):
    r = requests.post(ANKI_CONNECT, json={"action": action, "version": 6, "params": params}, timeout=60)
    r.raise_for_status()
    payload = r.json()
    if payload.get("error"):
        raise RuntimeError(payload["error"])
    return payload.get("result")


def slugify(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def model_from_anki(name: str) -> dict:
    models = invoke("findModelsByName", modelNames=[name])
    if not models:
        raise RuntimeError(f"Notiztyp nicht gefunden: {name}")
    m = models[0]
    return {
        "name": m["name"],
        "type": "cloze" if m["type"] == 1 else "standard",
        "managed_by_addon": m["name"] in ADDON_MANAGED,
        "fields": [f["name"] for f in m["flds"]],
        "css": m["css"],
        "templates": {t["name"]: {"Front": t["qfmt"], "Back": t["afmt"]} for t in m["tmpls"]},
    }


def export_model_to_file(model: dict, path: Path) -> None:
    path.write_text(json.dumps(model, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def fingerprint(model: dict) -> str:
    payload = json.dumps({"css": model["css"], "templates": model["templates"]}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


def cmd_pull(slug: str | None) -> int:
    names = invoke("modelNames")
    if slug:
        matches = [p for p in NOTE_TYPES_DIR.glob("*.json") if p.stem == slug]
        if not matches:
            print(f"Unbekannter slug: {slug}", file=sys.stderr)
            return 1
        names = [load_json(matches[0])["name"]]

    NOTE_TYPES_DIR.mkdir(parents=True, exist_ok=True)
    for name in names:
        model = model_from_anki(name)
        path = NOTE_TYPES_DIR / f"{slugify(name)}.json"
        export_model_to_file(model, path)
        flag = " [addon]" if model["managed_by_addon"] else ""
        print(f"pull: {path.name}{flag}")
    return 0


def push_one(path: Path, *, force_addon: bool) -> bool:
    model = load_json(path)
    name = model["name"]
    if model.get("managed_by_addon") and not force_addon:
        print(f"skip: {name} (managed_by_addon – nur Referenz im Repo)")
        return False

    invoke("updateModelStyling", model={"name": name, "css": model["css"]})
    invoke("updateModelTemplates", model={"name": name, "templates": model["templates"]})
    print(f"push: {name} ← {path.name}")
    return True


def cmd_push(slug: str | None, force_addon: bool) -> int:
    paths = sorted(NOTE_TYPES_DIR.glob("*.json"))
    if slug:
        paths = [p for p in paths if p.stem == slug]
        if not paths:
            print(f"Unbekannter slug: {slug}", file=sys.stderr)
            return 1

    pushed = sum(push_one(p, force_addon=force_addon) for p in paths)
    if pushed:
        print("Tipp: Auch CSS pushen → python scripts/sync_anki_style.py push")
    return 0


def cmd_status() -> int:
    paths = sorted(NOTE_TYPES_DIR.glob("*.json"))
    if not paths:
        print("Keine Dateien in media/note-types/")
        return 1

    drift = 0
    for path in paths:
        repo = load_json(path)
        try:
            live = model_from_anki(repo["name"])
        except RuntimeError as e:
            print(f"✗ {path.stem}: {e}")
            drift += 1
            continue
        same = fingerprint(repo) == fingerprint(live)
        tag = "✓" if same else "✗"
        extra = " [addon-ref]" if repo.get("managed_by_addon") else ""
        print(f"{tag} {repo['name']}{extra}")
        if not same:
            drift += 1
    return 1 if drift else 0


def cmd_list() -> int:
    for path in sorted(NOTE_TYPES_DIR.glob("*.json")):
        m = load_json(path)
        cards = ", ".join(m["templates"].keys())
        addon = " 🔒 addon" if m.get("managed_by_addon") else ""
        print(f"{path.stem:45} {m['name']}{addon}")
        print(f"{'':45} Karten: {cards}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Anki note type templates")
    sub = parser.add_subparsers(dest="command", required=True)

    p_pull = sub.add_parser("pull", help="Anki → Repo")
    p_pull.add_argument("slug", nargs="?", help="Nur einen Typ (Dateiname ohne .json)")

    p_push = sub.add_parser("push", help="Repo → Anki")
    p_push.add_argument("slug", nargs="?", help="Nur einen Typ")
    p_push.add_argument("--force-addon", action="store_true", help="Auch Add-on-Typen überschreiben (riskant)")

    sub.add_parser("status", help="Vergleich Repo vs. Anki")
    sub.add_parser("list", help="Übersicht der JSON-Dateien")

    args = parser.parse_args()
    try:
        invoke("version")
    except Exception as e:
        print(f"AnkiConnect nicht erreichbar: {e}", file=sys.stderr)
        return 1

    if args.command == "pull":
        return cmd_pull(args.slug)
    if args.command == "push":
        return cmd_push(args.slug, args.force_addon)
    if args.command == "status":
        return cmd_status()
    return cmd_list()


if __name__ == "__main__":
    raise SystemExit(main())
