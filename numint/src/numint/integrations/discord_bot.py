"""Discord bot - control numint from Discord with slash commands.

A gateway bot (it dials out to Discord; no public URL or port-forwarding
needed), so `numint discord-bot` just works from a laptop. Commands:

    /scan number:<E.164> [presence:<bool>] [country:<ISO>]
    /providers

Reuses the shared `Engine` and the same embed builder as the webhook push, so
Discord output matches everything else. Requires the `discord` extra:

    pip install "numint[discord]"

and a bot token in DISCORD_BOT_TOKEN.

SECURITY: whoever can see the bot's channel can run lookups. `/scan presence`
actively probes third-party sites - authorized use only. Invite the bot only
to a private server you control.
"""

from __future__ import annotations

from ..core.config import get_settings
from ..core.engine import Engine
from .discord import build_discord_embed


def run_bot(token: str | None = None) -> None:
    """Connect and serve slash commands until interrupted."""
    try:
        import discord
        from discord import app_commands
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "The Discord bot needs the 'discord.py' package. "
            'Install with: pip install "numint[discord]"'
        ) from exc

    settings = get_settings()
    token = token or settings.get("DISCORD_BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "No bot token. Set DISCORD_BOT_TOKEN "
            "(numint config set DISCORD_BOT_TOKEN <token>) or pass --token."
        )

    engine = Engine()
    intents = discord.Intents.default()  # slash commands need no privileged intents
    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)

    @client.event
    async def on_ready() -> None:
        await tree.sync()
        print(f"numint bot online as {client.user} - slash commands synced.")

    @tree.command(name="scan", description="Scan a phone number.")
    @app_commands.describe(
        number="Phone number in E.164, e.g. +14155550123",
        presence="Actively probe sites for account presence (authorized use only)",
        country="Default region (ISO) for a national-format number, e.g. US",
    )
    async def scan(
        interaction: discord.Interaction,
        number: str,
        presence: bool = False,
        country: str | None = None,
    ) -> None:
        # Lookups can take a few seconds; defer so Discord doesn't time out.
        await interaction.response.defer(thinking=True)
        try:
            profile = await engine.scan(
                number,
                default_region=country.upper() if country else None,
                with_footprint=False,
                with_presence=presence,
                with_ai=False,
            )
        except Exception as exc:  # noqa: BLE001 - surface a clean message
            await interaction.followup.send(
                f"⚠ Scan failed: {exc.__class__.__name__}: {exc}"
            )
            return
        embed = discord.Embed.from_dict(build_discord_embed(profile))
        await interaction.followup.send(embed=embed)

    @tree.command(name="providers", description="List configured data providers.")
    async def providers(interaction: discord.Interaction) -> None:
        infos = engine.provider_infos()
        lines = [
            f"{'●' if i['configured'] else '○'} {i['name']}"
            + ("" if i["configured"] else "  (no key)")
            for i in infos
        ]
        await interaction.response.send_message(
            "**Data providers**\n" + "\n".join(lines), ephemeral=True
        )

    client.run(token)
