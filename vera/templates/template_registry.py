"""
vera.templates.template_registry — TemplateRegistry.

Loads every `*.yaml` file under a directory tree (default:
vera/templates/yaml/shared/ for goal-mapped templates, plus
vera/templates/yaml/fallbacks/ for the two-level fallback chain Phase 8
uses when nothing else is usable) into a flat, queryable pool of
Template objects.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from vera.templates.template import Template

__all__ = ["TemplateRegistry"]

#: Anchored to this file's own location, not the process's working
#: directory. A bare relative string here silently returns an empty
#: registry (see _load_directory's `if not path.exists(): return []`)
#: whenever the process is started from anywhere other than the repo
#: root — no exception, just zero templates, which then makes every
#: FallbackChain.resolve() call raise "no L0/L1/L2 candidate available"
#: and every /v1/tick trigger silently produce no action.
_PACKAGE_DIR = Path(__file__).resolve().parent
_DEFAULT_SHARED_DIR = str(_PACKAGE_DIR / "yaml" / "shared")
_DEFAULT_FALLBACK_DIR = str(_PACKAGE_DIR / "yaml" / "fallbacks")


class TemplateRegistry:
    """An in-memory index of every known Template."""

    def __init__(self, templates: tuple[Template, ...]) -> None:
        by_id: dict[str, Template] = {}
        for t in templates:
            if t.template_id in by_id:
                raise ValueError(f"duplicate template_id: {t.template_id!r}")
            by_id[t.template_id] = t
        self._templates = templates
        self._by_id = by_id

    @classmethod
    def from_directories(
        cls, shared_dir: str = _DEFAULT_SHARED_DIR, fallback_dir: str = _DEFAULT_FALLBACK_DIR
    ) -> TemplateRegistry:
        templates: list[Template] = []
        for directory, is_fallback in ((shared_dir, False), (fallback_dir, True)):
            templates.extend(cls._load_directory(directory, is_fallback=is_fallback))
        return cls(tuple(templates))

    @staticmethod
    def _load_directory(directory: str, *, is_fallback: bool) -> list[Template]:
        import yaml

        path = Path(directory)
        if not path.exists():
            return []
        templates: list[Template] = []
        for yaml_file in sorted(path.glob("*.yaml")):
            data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
            for raw in data.get("templates", []):
                templates.append(TemplateRegistry._parse(raw, is_fallback=is_fallback))
        return templates

    @staticmethod
    def _parse(raw: dict[str, Any], *, is_fallback: bool) -> Template:
        body = raw.get("body", {})
        return Template(
            template_id=raw["id"],
            goal=raw.get("goal", "*"),
            levers=tuple(raw.get("levers", ())),
            cta_type=raw.get("cta_type", "open_ended"),
            required_slots=tuple(raw.get("required_slots", ())),
            body_en=body["en"],
            body_hi_en=body.get("hi_en", body["en"]),
            is_fallback=is_fallback,
            fallback_level=raw.get("fallback_level", 0),
            category=raw.get("category", "*"),
        )

    @property
    def templates(self) -> tuple[Template, ...]:
        return self._templates

    def get(self, template_id: str) -> Template | None:
        return self._by_id.get(template_id)

    def for_goal(self, goal: str) -> tuple[Template, ...]:
        return tuple(t for t in self._templates if not t.is_fallback and t.goal == goal)

    def fallbacks(self) -> tuple[Template, ...]:
        return tuple(t for t in self._templates if t.is_fallback)

    def fallback_at_level(self, level: int) -> tuple[Template, ...]:
        return tuple(t for t in self._templates if t.is_fallback and t.fallback_level == level)

    @property
    def is_empty(self) -> bool:
        return not self._templates
