"""Consistent presenter-mode masking without ever touching secret values."""

from __future__ import annotations

import re
from typing import Any

from snoop.config import config


def case_identifiers(dossier: Any) -> list[str]:
    """Return public case identifiers that presenter mode must mask."""
    values = [
        str(getattr(dossier, "id", "")),
        str(getattr(dossier, "target", "")),
        *map(str, getattr(dossier, "handles_tried", []) or []),
        *map(str, getattr(dossier, "emails", []) or []),
        *map(str, getattr(dossier, "authorized_emails", []) or []),
    ]
    for account in getattr(dossier, "all_accounts", []) or []:
        values.extend(
            str(account.get(key, ""))
            for key in (
                "display_name",
                "matched_handle",
                "platform_id",
            )
        )
    subject = getattr(dossier, "subject", {}) or {}
    values.extend(str(subject.get(key, "")) for key in ("input", "corrected_name"))
    values.extend(str(row.get("value", "")) for row in getattr(dossier, "interview", []) or [])
    return [value for value in values if value]


def mask_text(value: str, extra_values: list[str] | None = None) -> str:
    output = str(value)
    values = [*config.redact_values, *(extra_values or [])]
    ordered = sorted(set(values), key=lambda item: (-len(item), item.casefold()))
    for index, raw in enumerate(ordered, 1):
        if raw:
            output = re.sub(re.escape(raw), f"PERSONAL_{index}", output, flags=re.IGNORECASE)
    return output


def mask_obj(value, extra_values: list[str] | None = None, *, force: bool = False):
    if not (config.presenter or force):
        return value
    if isinstance(value, dict):
        return {
            mask_text(str(k), extra_values): mask_obj(v, extra_values, force=True)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [mask_obj(v, extra_values, force=True) for v in value]
    if isinstance(value, tuple):
        return tuple(mask_obj(v, extra_values, force=True) for v in value)
    if isinstance(value, str):
        return mask_text(value, extra_values)
    return value
