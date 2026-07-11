"""YAML config file source for pydantic-settings.

Precedence (highest → lowest): env vars → .env → config.yaml → defaults.

Config file resolution order:
  1. ``AURALYNQ_CONFIG`` env var (explicit path)
  2. ``config.yaml`` in the current working directory
  3. ``config.yml`` in the current working directory
  4. ``.auralynq.yaml`` in the current working directory
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic.fields import FieldInfo
from pydantic_settings import PydanticBaseSettingsSource

_CONFIG_ENV_VAR = "AURALYNQ_CONFIG"
_DEFAULT_NAMES = ("config.yaml", "config.yml", ".auralynq.yaml")


def find_config_file() -> Path | None:
    env = os.getenv(_CONFIG_ENV_VAR)
    if env:
        return Path(env)
    for name in _DEFAULT_NAMES:
        p = Path(name)
        if p.exists():
            return p
    return None


class YamlConfigSettingsSource(PydanticBaseSettingsSource):
    """Pydantic-settings v2 source that reads a YAML config file."""

    def __init__(self, settings_cls, yaml_file: Path | str | None = None) -> None:
        super().__init__(settings_cls)
        path = Path(yaml_file) if yaml_file else find_config_file()
        self._data: dict[str, Any] = {}
        self._path = path
        if path and path.exists():
            try:
                import yaml

                with open(path) as f:
                    self._data = yaml.safe_load(f) or {}
            except Exception:
                pass

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        val = self._data.get(field_name)
        return val, field_name, self.field_is_complex(field)

    def prepare_field_value(
        self, field_name: str, field: FieldInfo, value: Any, value_is_complex: bool
    ) -> Any:
        return value

    def __call__(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for field_name, field_info in self.settings_cls.model_fields.items():
            val, key, _ = self.get_field_value(field_info, field_name)
            if val is not None:
                out[key] = val
        return out
