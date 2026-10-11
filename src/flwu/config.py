"""Configuration loading and validation for Florida Litigator Weekly Update.

Reads JSON configuration with strict key validation. Exports no environment
secrets. Provides defaults from the ARCHITECTURE specification.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# Default configuration values derived from ARCHITECTURE.md defaults
_DEFAULTS: dict[str, Any] = {
    "schema_version": 1,
    "mode": "fixture",
    "timezone": "America/New_York",
    "schedule": {"weekday": 0, "hour": 8, "minute": 0},
    "research": {"overlap_days": 14, "bootstrap_days": 14},
    "limits": {
        "external_usd": 0,
        "http_timeout_seconds": 30,
        "http_retries": 3,
        "host_spacing_seconds": 1,
        "run_minutes": 120,
        "source_minutes": 15,
        "requests_per_run": 2000,
        "model_calls_per_run": 250,
        "model_timeout_seconds": 300,
        "model_repairs_per_item": 2,
        "state_gib": 5,
        "retention_days": 30,
    },
    "model": {
        "base_url": None,
        "model_id": None,
        "cloud_fallback": False,
    },
    "publication": {"mode": "manual"},
    "state_root": None,
}

_CONFIG_PATHS: list[Path] = [
    Path("config/defaults.json"),
]


class ConfigError(Exception):
    """Raised when configuration is invalid or missing."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


def _load_defaults() -> dict[str, Any]:
    """Return a deep copy of the default configuration."""
    return json.loads(json.dumps(_DEFAULTS))


def _validate_config_keys(loaded: dict[str, Any], defaults: dict[str, Any]) -> None:
    """Validate that loaded config contains only allowed keys at every depth."""
    allowed_keys = set(defaults.keys())
    unknown = set(loaded.keys()) - allowed_keys
    if unknown:
        raise ConfigError(
            "UNKNOWN_KEYS",
            f"Unexpected configuration keys: {sorted(unknown)}",
        )

    for key, default_val in defaults.items():
        if isinstance(default_val, dict):
            loaded_val = loaded.get(key)
            if loaded_val is not None and not isinstance(loaded_val, dict):
                raise ConfigError(
                    "TYPE_MISMATCH",
                    f"Key '{key}' must be null or an object",
                )
            if isinstance(loaded_val, dict):
                _validate_config_keys(loaded_val, default_val)


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Load and validate configuration from a JSON file.

    If *path* is None, searches the standard paths for ``config/defaults.json``.
    The file must contain exactly the keys defined in the default schema.

    Returns a new dict; never mutates inputs.
    """
    defaults = _load_defaults()

    if path is None:
        for p in _CONFIG_PATHS:
            if p.is_file():
                path = p
                break
        if path is None:
            return defaults

    text = path.read_text(encoding="utf-8")
    loaded: dict[str, Any] = json.loads(text)

    _validate_config_keys(loaded, defaults)
    return loaded


def _enforce_production(loaded: dict[str, Any]) -> dict[str, Any]:
    """Enforce production security constraints on a loaded configuration.

    In production mode: external_usd must be 0, model.base_url must be None or
    loopback-only, and state_root must not point to the fixture directory.
    """
    result = json.loads(json.dumps(loaded))
    limits = result.get("limits")
    if isinstance(limits, dict):
        if limits.get("external_usd", 0) != 0:
            raise ConfigError(
                "PRODUCTION_EXTERNAL_SPENDING",
                "Production mode requires external_usd=0",
            )

    model = result.get("model")
    if isinstance(model, dict):
        base_url = model.get("base_url")
        if base_url is not None:
            if not (
                base_url.startswith("http://127.0.0.1")
                or base_url.startswith("http://localhost")
                or base_url.startswith("unix:")
            ):
                raise ConfigError(
                    "PRODUCTION_MODEL_URL",
                    "Production mode requires loopback-only model URL",
                )
        cloud_fallback = model.get("cloud_fallback", False)
        if cloud_fallback is not False:
            raise ConfigError(
                "PRODUCTION_CLOUD_FALLBACK",
                "Production mode requires cloud_fallback=false",
            )

    state_root = result.get("state_root")
    if state_root is not None:
        if isinstance(state_root, str) and "/fixture" in state_root:
            raise ConfigError(
                "PRODUCTION_STATE_ROOT",
                "Production mode must not use fixture state root",
            )

    return result
