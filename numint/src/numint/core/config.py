"""Configuration and key resolution.

Resolution priority for any key:
    1. explicit environment variable (also set by a CLI flag)
    2. the user config file  ~/.config/numint/config.toml
    3. a project-local .env  (loaded into the environment on import)

`numint config set` writes to the user config file so keys persist across runs
without a project .env.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

try:  # Python 3.11+ ships tomllib; tomli is the backport.
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

from dotenv import load_dotenv

APP_NAME = "numint"


def config_dir() -> Path:
    """Cross-platform per-user config directory."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(
            os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
        )
    return base / APP_NAME


def config_path() -> Path:
    return config_dir() / "config.toml"


def cache_dir() -> Path:
    if os.name == "nt":
        base = Path(
            os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
        )
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / APP_NAME


def _load_toml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return {}


class Settings:
    """Lazily resolves keys and options from env, config file and .env."""

    def __init__(self, project_env: str | None = ".env") -> None:
        # Load project .env into os.environ without overriding real env vars.
        if project_env:
            load_dotenv(project_env, override=False)
        self._file = _load_toml(config_path())

    # --- generic key lookup -------------------------------------------------
    def get(self, key: str, default: str | None = None) -> str | None:
        env_val = os.environ.get(key)
        if env_val:
            return env_val
        # config file stores keys case-insensitively under [keys] or top-level.
        keys_table = self._file.get("keys", {})
        for table in (keys_table, self._file):
            if key in table and isinstance(table[key], str):
                return table[key]
            lower = key.lower()
            if lower in table and isinstance(table[lower], str):
                return table[lower]
        return default

    # --- typed options ------------------------------------------------------
    @property
    def cache_ttl(self) -> int:
        val = self.get("NUMINT_CACHE_TTL", "86400")
        try:
            return int(val)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 86400

    @property
    def provider_timeout(self) -> float:
        val = self.get("NUMINT_PROVIDER_TIMEOUT", "10")
        try:
            return float(val)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 10.0

    @property
    def rate_limit_per_sec(self) -> float:
        val = self.get("NUMINT_RATE_LIMIT", "3")
        try:
            return float(val)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 3.0

    @property
    def discord_webhook_url(self) -> str | None:
        return self.get("DISCORD_WEBHOOK_URL")

    @property
    def ai_provider(self) -> str | None:
        return self.get("AI_PROVIDER")

    @property
    def ai_model(self) -> str | None:
        return self.get("AI_MODEL")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    """Force re-read of config (used by tests and after `config set`)."""
    get_settings.cache_clear()


# --- config file mutation (used by `numint config set`) --------------------
def write_key(provider_key: str, value: str) -> Path:
    """Persist a key into the [keys] table of the user config file."""
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _load_toml(path)
    keys = data.setdefault("keys", {})
    keys[provider_key] = value
    _dump_toml(path, data)
    reset_settings_cache()
    return path


def _dump_toml(path: Path, data: dict) -> None:
    """Minimal TOML writer (stdlib has no writer). Handles our flat schema."""
    lines: list[str] = []
    top_level = {k: v for k, v in data.items() if not isinstance(v, dict)}
    for k, v in top_level.items():
        lines.append(f'{k} = "{v}"')
    for table, values in data.items():
        if not isinstance(values, dict):
            continue
        lines.append(f"\n[{table}]")
        for k, v in values.items():
            escaped = str(v).replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{k} = "{escaped}"')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
