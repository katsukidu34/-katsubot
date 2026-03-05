"""
cogs/vocal.py — Commandes vocales avancées
===========================================
Commandes : /vocal_move, /vocal_stats
"""

import discord
from discord import app_commands
from discord.ext import commands

from config import charger_data, get_joueur


def formater(secondes):
    h = secondes // 3600
    m = (secondes % 3600) // 60
    s = secondes % 60
    if h > 0:
        return f"{h}h {m}min"
    elif m > 0:
        return f"{m}min {s}s"
    else:
        return f"{s}s"


class Vocal(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /vocal_move ────────────────────────────

    @app_commands.command(name="vocal_move", description="Déplace tous les membres d'un vocal vers un autre")
    @app_commands.describe(
        source="Le salon vocal source",
        destination="Le salon vocal destination"
    )
    @app_commands.checks.has_permissions(move_members=True)
    async def vocal_move(self, interaction: discord.Interaction, source: discord.VoiceChannel, destination: discord.VoiceChannel):
        if not source.members:
            await interaction.response.send_message("Ce salon vocal est vide !", ephemeral=True)
            return

        await interaction.response.defer()
        deplacer = 0
        for membre in source.members:
            try:
                await membre.move_to(destination)
                deplacer += 1
            except Exception:
                pass

        embed = discord.Embed(
            title="🔀 Membres déplacés !",
            description=f"**{deplacer} membre(s)** déplacés de {source.mention} vers {destination.mention}",
            color=discord.Color.blurple()
        )
        await interaction.followup.send(embed=embed)

    # ── /vocal_stats ───────────────────────────

    @app_commands.command(name="vocal_stats", description="Tes statistiques vocales détaillées")
    @app_commands.describe(membre="Le membre à consulter (toi par défaut)")
    async def vocal_stats(self, interaction: discord.Interaction, membre: discord.Member = None):
        cible  = membre or interaction.user
        data   = charger_data()
        joueur = get_joueur(data, interaction.guild_id, cible.id)

        total   = joueur.get("temps_vocal", 0)
        semaine = joueur.get("temps_vocal_semaine", 0)
        mois    = joueur.get("temps_vocal_mois", 0)
        record  = joueur.get("temps_vocal_record", 0)

        embed = discord.Embed(
            title=f"🎤 Stats vocales de {cible.display_name}",
            color=discord.Color.purple()
        )
        embed.set_thumbnail(url=cible.display_avatar.url)
        embed.add_field(name="📅 Cette semaine",  value=formater(semaine), inline=True)
        embed.add_field(name="📆 Ce mois",        value=formater(mois),    inline=True)
        embed.add_field(name="🏆 Total",          value=formater(total),   inline=True)
        embed.add_field(name="⚡ Record session", value=formater(record),  inline=True)
        embed.set_footer(text="Continue comme ça !")
        await interaction.response.send_message(embed=embed)

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("Tu n'as pas la permission !", ephemeral=True)
        else:
            await interaction.response.send_message(f"Erreur : {error}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Vocal(bot))