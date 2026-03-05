"""
cogs/suggestion.py — Système de suggestions
=============================================
Commandes : /suggestion
Les membres envoient des suggestions, le staff vote avec ✅/❌
"""

import discord
from discord import app_commands
from discord.ext import commands

from config import get_config


class Suggestion(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /suggestion ────────────────────────────

    @app_commands.command(name="suggestion", description="Envoie une suggestion au staff")
    @app_commands.describe(suggestion="Ta suggestion")
    async def suggestion(self, interaction: discord.Interaction, suggestion: str):
        cfg      = get_config(interaction.guild_id)
        salon_id = cfg.get("salon_suggestions")

        if not salon_id:
            await interaction.response.send_message(
                "⚠️ Aucun salon de suggestions configuré ! Un admin doit configurer `/config`.",
                ephemeral=True
            )
            return

        canal = interaction.guild.get_channel(int(salon_id))
        if not canal:
            await interaction.response.send_message(
                "⚠️ Le salon de suggestions est introuvable !", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="💡 Nouvelle suggestion",
            description=suggestion,
            color=discord.Color.yellow()
        )
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        embed.set_footer(text=f"ID : {interaction.user.id}")

        msg = await canal.send(embed=embed)

        # Ajoute les réactions pour voter
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")

        await interaction.response.send_message(
            "✅ Ta suggestion a été envoyée !", ephemeral=True
        )

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await interaction.response.send_message(f"Erreur : {error}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Suggestion(bot))