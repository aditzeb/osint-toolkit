"""Provider auto-discovery registry.

Providers self-register via the `@register` decorator. Importing the
`numint.providers` package triggers discovery of every module in it, so a new
provider file is picked up with zero wiring.
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..providers.base import BaseProvider

_REGISTRY: list[type[BaseProvider]] = []


def register(cls: type[BaseProvider]) -> type[BaseProvider]:
    """Class decorator that adds a provider to the registry."""
    if cls not in _REGISTRY:
        _REGISTRY.append(cls)
    return cls


def discover() -> list[type[BaseProvider]]:
    """Import all provider modules so their `@register` runs, then return them."""
    import numint.providers as providers_pkg

    for mod in pkgutil.iter_modules(providers_pkg.__path__):
        if mod.name == "base":
            continue
        importlib.import_module(f"numint.providers.{mod.name}")
    return list(_REGISTRY)
