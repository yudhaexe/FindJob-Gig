"""Read-only access to `config/*.yaml`. Cached; call `reload()` after editing a file."""

from functools import cache
from typing import Any

import yaml

from core.paths import CONFIG_DIR


@cache
def load(name: str) -> Any:
    """Load `config/<name>.yaml`. Returns {} when the file is missing or empty."""
    path = CONFIG_DIR / f"{name}.yaml"
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def reload() -> None:
    load.cache_clear()
