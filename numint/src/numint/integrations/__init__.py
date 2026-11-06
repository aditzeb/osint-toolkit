"""Outbound integrations (push results elsewhere). Currently: Discord webhook."""

from .discord import (
    build_discord_embed,
    send_discord_async,
    send_discord_sync,
)

__all__ = [
    "build_discord_embed",
    "send_discord_async",
    "send_discord_sync",
]
