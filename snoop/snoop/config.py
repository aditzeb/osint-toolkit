"""Runtime configuration. Secrets are optional and never exposed by diagnostics."""

from __future__ import annotations

import os
from pathlib import Path
from typing import ClassVar

_EXPLICIT_ENV_KEYS = frozenset(os.environ)
_ENV_FILES = tuple(
    dict.fromkeys((Path.cwd() / ".env", Path(__file__).resolve().parent.parent / ".env"))
)

try:
    from dotenv import dotenv_values, load_dotenv

    # A project-local .env is convenient for development. Installed copies also
    # honour .env in the current directory; neither file is required.
    for _env_file in _ENV_FILES:
        load_dotenv(_env_file)
except Exception:  # pragma: no cover
    dotenv_values = None  # type: ignore[assignment]

PACKAGE_DIR = Path(__file__).resolve().parent
_LEGACY_DATA = PACKAGE_DIR.parent / "data"
_DEFAULT_DATA = _LEGACY_DATA if (_LEGACY_DATA / "dossiers").is_dir() else (Path.home() / ".snoop")
DATA_DIR = Path(os.getenv("SNOOP_DATA_DIR") or _DEFAULT_DATA).expanduser()
CASES_DIR = DATA_DIR / "dossiers"
CASES_DIR.mkdir(parents=True, exist_ok=True)


def _clean(v: str | None) -> str:
    v = (v or "").strip()
    if not v or "your-key" in v or "your-id" in v or v == "here":
        return ""
    return v


def _live_env_value(*names: str) -> str:
    """Reread a setting so long-running web sessions notice .env edits.

    Variables present in the process environment at startup retain precedence
    over dotenv files. Dotenv-only values are read from disk on demand.
    """
    for name in names:
        if name in _EXPLICIT_ENV_KEYS:
            return _clean(os.getenv(name))
    if dotenv_values is not None:
        for path in _ENV_FILES:
            try:
                values = dotenv_values(path)
            except (OSError, UnicodeError):
                continue
            for name in names:
                if name in values:
                    return _clean(values.get(name))
    return _clean(next((os.getenv(name) for name in names if os.getenv(name) is not None), ""))


def _env_signature() -> tuple[tuple[str, int, int], ...]:
    rows = []
    for path in _ENV_FILES:
        try:
            stat = path.stat()
        except OSError:
            rows.append((str(path), 0, 0))
        else:
            rows.append((str(path), stat.st_mtime_ns, stat.st_size))
    return tuple(rows)


class Config:
    # --- AI ---
    openai_key = _clean(os.getenv("OPENAI_API_KEY"))
    openai_model = _clean(os.getenv("OPENAI_MODEL")) or "gpt-4o-mini"
    ai_provider_name = _clean(os.getenv("SNOOP_AI_PROVIDER")).casefold()
    reasoning_effort = _clean(os.getenv("SNOOP_REASONING_EFFORT")) or "medium"
    ai_max_output_tokens = int(os.getenv("SNOOP_AI_MAX_OUTPUT_TOKENS", "16000"))
    ai_timeout = float(os.getenv("SNOOP_AI_TIMEOUT", "180"))
    anthropic_key = _clean(os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))
    anthropic_model = _clean(os.getenv("CLAUDE_MODEL")) or "claude-3-5-sonnet-latest"
    gemini_key = _clean(os.getenv("GEMINI_API_KEY"))
    gemini_model = _clean(os.getenv("GEMINI_MODEL")) or "gemini-1.5-flash"
    ollama_base_url = _clean(os.getenv("OLLAMA_BASE_URL")) or "http://localhost:11434"
    ollama_model = _clean(os.getenv("OLLAMA_MODEL"))
    # --- enrichment keys ---
    hibp_key = _clean(os.getenv("HIBP_API_KEY"))
    github_token = _clean(os.getenv("GITHUB_TOKEN"))
    brave_search_key = _clean(os.getenv("BRAVE_SEARCH_API_KEY"))
    serpapi_key = _clean(os.getenv("SERPAPI_KEY") or os.getenv("SERPAPI_API_KEY"))

    # --- search ---
    # Preferred engine label: "google" (via SerpAPI) or "brave".
    search_engine = (_clean(os.getenv("SNOOP_SEARCH_ENGINE")) or "google").casefold()
    search_language = _clean(os.getenv("SNOOP_SEARCH_HL"))  # e.g. "en"
    search_region = _clean(os.getenv("SNOOP_SEARCH_GL"))  # e.g. "us"
    # Allow the other configured engine to be used as a labelled fallback/cross-check.
    search_fallback = os.getenv("SNOOP_SEARCH_FALLBACK", "1").lower() not in {"0", "false", "no"}

    # --- investigation workflow ---
    workflow_preset = (_clean(os.getenv("SNOOP_WORKFLOW_PRESET")) or "standard").casefold()
    common_crawl_index = _clean(os.getenv("SNOOP_CC_INDEX")) or "CC-MAIN-2026-34"
    # Optional OCR / reverse-image extras are documented optional dependencies.

    # --- tuning ---
    concurrency = int(os.getenv("SNOOP_CONCURRENCY", "30"))
    http_timeout = float(os.getenv("SNOOP_HTTP_TIMEOUT", "12"))
    http_retries = int(os.getenv("SNOOP_HTTP_RETRIES", "2"))
    # One bad page or parser must not hold an investigation open forever.
    action_timeout = float(os.getenv("SNOOP_ACTION_TIMEOUT", "45"))
    document_parse_timeout = float(os.getenv("SNOOP_DOCUMENT_PARSE_TIMEOUT", "8"))
    # Seconds to wait for an answer before a question is skipped and work continues (0 = wait forever).
    question_timeout = int(os.getenv("SNOOP_QUESTION_TIMEOUT", "60") or 0)
    per_host_concurrency = int(os.getenv("SNOOP_PER_HOST_CONCURRENCY", "3"))
    presenter = os.getenv("SNOOP_PRESENTER_MODE", "").lower() in {"1", "true", "yes"}
    redact_values: ClassVar[list[str]] = [
        v.strip() for v in os.getenv("SNOOP_REDACT_VALUES", "").split(",") if v.strip()
    ]
    web_host = os.getenv("SNOOP_WEB_HOST", "127.0.0.1")
    web_port = int(os.getenv("SNOOP_WEB_PORT", "8000"))
    _provider_env_signature: ClassVar[tuple[tuple[str, int, int], ...]] = _env_signature()

    def refresh_provider_credentials(self) -> None:
        """Refresh provider secrets without returning or logging their values."""
        signature = _env_signature()
        if signature == self._provider_env_signature:
            return
        self.openai_key = _live_env_value("OPENAI_API_KEY")
        self.openai_model = _live_env_value("OPENAI_MODEL") or self.openai_model
        self.ai_provider_name = _live_env_value("SNOOP_AI_PROVIDER").casefold()
        self.reasoning_effort = _live_env_value("SNOOP_REASONING_EFFORT") or self.reasoning_effort
        self.anthropic_key = _live_env_value("CLAUDE_API_KEY", "ANTHROPIC_API_KEY")
        self.gemini_key = _live_env_value("GEMINI_API_KEY")
        self.ollama_base_url = _live_env_value("OLLAMA_BASE_URL") or self.ollama_base_url
        self.ollama_model = _live_env_value("OLLAMA_MODEL")
        self.hibp_key = _live_env_value("HIBP_API_KEY")
        self.github_token = _live_env_value("GITHUB_TOKEN")
        self.brave_search_key = _live_env_value("BRAVE_SEARCH_API_KEY")
        self.serpapi_key = _live_env_value("SERPAPI_KEY", "SERPAPI_API_KEY")
        self._provider_env_signature = signature

    def ai_provider(self) -> str | None:
        self.refresh_provider_credentials()
        if self.ai_provider_name:
            return self.ai_provider_name if {
                "openai": self.openai_key, "anthropic": self.anthropic_key,
                "gemini": self.gemini_key, "ollama": self.ollama_model,
            }.get(self.ai_provider_name) else None
        if self.openai_key:
            return "openai"
        if self.anthropic_key:
            return "anthropic"
        if self.gemini_key:
            return "gemini"
        if self.ollama_model:
            return "ollama"
        return None


config = Config()
