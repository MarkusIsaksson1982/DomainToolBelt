from __future__ import annotations

from pathlib import Path
from typing import Any


class PromptLoader:
    """Load markdown prompt templates with lightweight variable injection."""

    def __init__(self, template_dir: str | Path, user_override_dir: str | Path | None = None):
        self.template_dir = Path(template_dir)
        self.user_override_dir = Path(user_override_dir) if user_override_dir else None
        self._cache: dict[tuple[str, tuple[tuple[str, str], ...]], str] = {}

    def load(self, filename: str, **variables: Any) -> str:
        cache_key = (filename, tuple(sorted((key, str(value)) for key, value in variables.items())))
        if cache_key in self._cache:
            return self._cache[cache_key]

        path = self._resolve_path(filename)
        content = path.read_text(encoding="utf-8")
        rendered = self._inject(content, **variables)
        self._cache[cache_key] = rendered
        return rendered

    def clear_cache(self) -> None:
        self._cache.clear()

    def _resolve_path(self, filename: str) -> Path:
        candidates = []
        if self.user_override_dir:
            candidates.append(self.user_override_dir / filename)
        candidates.append(self.template_dir / filename)

        for candidate in candidates:
            if candidate.is_file():
                return candidate
        joined = ", ".join(str(candidate) for candidate in candidates)
        raise FileNotFoundError(f"Prompt template not found: {filename}. Checked: {joined}")

    @staticmethod
    def _inject(template: str, **variables: Any) -> str:
        rendered = template
        for key, value in variables.items():
            rendered = rendered.replace("{" + key + "}", str(value))
        return rendered
