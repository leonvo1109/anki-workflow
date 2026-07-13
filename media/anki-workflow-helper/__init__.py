"""Anki-workflow: AnkiConnect-Erweiterung (Modell → Lückentext)."""

from __future__ import annotations

from aqt import gui_hooks


def _patch_ankiconnect() -> None:
    try:
        import importlib

        acmod = importlib.import_module("2055492159")
    except ImportError:
        return

    ac_cls = acmod.AnkiConnect
    if getattr(ac_cls, "_anki_workflow_patched", False):
        return

    util = acmod.util

    @util.api()
    def ankiWorkflowConvertModelToCloze(self, modelName):
        from anki.consts import MODEL_CLOZE

        models = self.collection().models
        model = models.by_name(modelName)
        if model is None:
            raise Exception(f"Notiztyp nicht gefunden: {modelName}")
        if model["type"] == MODEL_CLOZE:
            return {"changed": False, "modelName": modelName}
        model["type"] = MODEL_CLOZE
        models.change(model)
        self.save_model(models, model)
        return {"changed": True, "modelName": modelName}

    ac_cls.ankiWorkflowConvertModelToCloze = ankiWorkflowConvertModelToCloze
    ac_cls._anki_workflow_patched = True


gui_hooks.main_window_did_init.append(_patch_ankiconnect)
