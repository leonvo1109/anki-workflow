"""AnkiConnect-Hilfsfunktionen."""
from __future__ import annotations

import requests

ANKI_CONNECT = "http://127.0.0.1:8765"


class AnkiClient:
    def __init__(self, url: str = ANKI_CONNECT, timeout: int = 120):
        self.url = url
        self.timeout = timeout

    def invoke(self, action: str, **params):
        r = requests.post(
            self.url,
            json={"action": action, "version": 6, "params": params},
            timeout=self.timeout,
        )
        r.raise_for_status()
        payload = r.json()
        if payload.get("error"):
            raise RuntimeError(payload["error"])
        return payload.get("result")

    def ping(self) -> None:
        self.invoke("version")

    def load_existing_keys(self, deck: str) -> set[str]:
        from .norm import norm_key

        try:
            nids = self.invoke("findNotes", query=f'deck:"{deck}"')
            keys: set[str] = set()
            for nid in nids:
                info = self.invoke("notesInfo", notes=[nid])[0]
                for fld in info["fields"].values():
                    keys.add(norm_key(fld["value"]))
            return keys
        except Exception:
            return set()

    def ensure_decks(self, notes: list[dict]) -> None:
        """Legt fehlende Ziel-Decks an (createDeck ist idempotent)."""
        for deck in {n["deckName"] for n in notes if n.get("deckName")}:
            self.invoke("createDeck", deck=deck)

    def import_notes(self, notes: list[dict]) -> tuple[int, int]:
        created = skipped = 0
        self.ensure_decks(notes)
        for note in notes:
            try:
                result = self.invoke("addNotes", notes=[note])
                if result and result[0]:
                    created += 1
                else:
                    skipped += 1
            except RuntimeError as e:
                if "duplicate" in str(e).lower():
                    skipped += 1
                else:
                    front = note["fields"].get("Vorderseite") or note["fields"].get("Text", "")
                    raise RuntimeError(f"{e} | {front[:60]}") from e
        return created, skipped

    def run_cleanup(self, cleanup: dict, *, dry_run: bool = False, locked_note_ids: set[int] | None = None) -> None:
        # Tolerant gegenüber bereits gelöschten Notizen: cleanup-Dateien bleiben
        # im Repo liegen und dürfen wiederholte Importe nicht zum Absturz bringen.
        locked = locked_note_ids or set()
        for nid in cleanup.get("delete_note_ids", []):
            if nid in locked:
                print(f"Cleanup-Löschen übersprungen (gesperrt): {nid}")
                continue
            if dry_run:
                print(f"[dry-run] Löschen: {nid}")
            else:
                self.invoke("deleteNotes", notes=[nid])

        for upd in cleanup.get("updates", []):
            if upd.get("id") in locked:
                print(f"Cleanup-Update übersprungen (gesperrt): {upd['id']}")
                continue
            if dry_run:
                print(f"[dry-run] Update {upd['id']}")
                continue
            try:
                fields = upd.get("fields")
                if fields:
                    self.invoke("updateNoteFields", note={"id": upd["id"], "fields": fields})
                tags = upd.get("tags")
                if tags:
                    self.invoke("addTags", notes=[upd["id"]], tags=" ".join(tags))
            except RuntimeError as e:
                if "not found" in str(e).lower():
                    print(f"Cleanup-Update übersprungen (Notiz fehlt): {upd['id']}")
                else:
                    raise

        for nid in cleanup.get("move_to_sync_deck", []):
            deck = cleanup.get("move_deck")
            if not deck:
                continue
            if dry_run:
                print(f"[dry-run] Verschiebe {nid} → {deck}")
                continue
            cids = self.invoke("findCards", query=f"nid:{nid}")
            if cids:
                self.invoke("changeDeck", cards=cids, deck=deck)
