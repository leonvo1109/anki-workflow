"""Gemeinsame Logik für Kartenimport aus processed/slides.json."""

from .config import CourseConfig, load_course_config
from .generator import generate_from_slides
from .anki_client import AnkiClient
from .locks import LockRegistry, load_locks, merge_curated_locks

__all__ = [
    "CourseConfig",
    "load_course_config",
    "generate_from_slides",
    "AnkiClient",
    "LockRegistry",
    "load_locks",
    "merge_curated_locks",
]
