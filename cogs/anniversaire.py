"""
cogs/anniversaire.py — Système d'anniversaires
================================================
Commandes : /anniversaire_set, /anniversaire, /anniversaires
Le bot vérifie chaque jour et fête les anniversaires automatiquement.
"""

import discord
import asyncio
from discord import app_commands
from discord.ext import commands
from datetime import datetime

from config import get_config, charger_data, sauvegarder_data


class Anniversaire(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.task = bot.loop.create_task(self.verifier_anniversaires())

    def cog_unload(self):
        self.task.cancel()

    # ── Tâche automatique ─────────────────────

    async def verifier_anniversaires(self):
        """Vérifie chaque jour à minuit si c'est l'anniversaire de quelqu'un."""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            now  = datetime.now()
            data = charger_data()

            for guild in self.bot.guilds:
                cfg      = get_config(guild.id)
                salon_id = cfg.get("salon_anniversaire")
                if not salon_id:
                    continue
                canal = guild.get_channel(int(salon_id))
                if not canal:
                    continue

                annivs = data.get(f"anniversaires_{guild.id}", {})
                for user_id, date_str in annivs.items():
                    try:
                        date = datetime.strptime(date_str, "%d/%m")
                        if date.day == now.day and date.month == now.month:
                            membre = guild.get_member(int(user_id))
                            if membre:
                                embed = discord.Embed(
                                    title="🎂 Joyeux Anniversaire !",
                                    description=f"Toute l'équipe souhaite un joyeux anniversaire à {membre.mention} ! 🥳🎉",
                                    color=discord.Color.gold()
                                )
                                embed.set_thumbnail(url=membre.display_avatar.url)
                                await canal.send(embed=embed)
                    except Exception:
                        continue

            # Attend jusqu'au lendemain minuit
            demain = now.replace(hour=0, minute=0, second=0, day=now.day + 1)
            await asyncio.sleep((demain - now).seconds)

    # ── /anniversaire_set ──────────────────────

    @app_commands.command(name="anniversaire_set", description="Enregistre ta date d'anniversaire")
    @app_commands.describe(date="Ta date d'anniversaire au format JJ/MM (ex: 25/12)")
    async def anniversaire_set(self, interaction: discord.Interaction, date: str):
        try:
            datetime.strptime(date, "%d/%m")
        except ValueError:
            await interaction.response.send_message(
                "Format invalide ! Utilise **JJ/MM** (ex: `25/12`)", ephemeral=True
            )
            return

        data = charger_data()
        cle  = f"anniversaires_{interaction.guild_id}"
        if cle not in data:
            data[cle] = {}
        data[cle][str(interaction.user.id)] = date
        sauvegarder_data(data)

        await interaction.response.send_message(
            f"🎂 Anniversaire enregistré le **{date}** ! Le bot te fêtera ce jour-là.", ephemeral=True
        )

 

    # ── /anniversaires ─────────────────────────

    @app_commands.command(name="anniversaires", description="Liste tous les anniversaires du serveur")
    async def anniversaires(self, interaction: discord.Interaction):
        data   = charger_data()
        annivs = data.get(f"anniversaires_{interaction.guild_id}", {})

        if not annivs:
            await interaction.response.send_message("Aucun anniversaire enregistré pour l'instant !")
            return

        tries = sorted(annivs.items(), key=lambda x: datetime.strptime(x[1], "%d/%m").strftime("%m%d"))

        embed = discord.Embed(title="🎂 Anniversaires du serveur", color=discord.Color.gold())
        desc  = ""
        for user_id, date in tries:
            membre = interaction.guild.get_member(int(user_id))
            nom    = membre.display_name if membre else "Membre introuvable"
            desc  += f"**{date}** — {nom}\n"

        embed.description = desc
        await interaction.response.send_message(embed=embed)

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("Tu n'as pas la permission !", ephemeral=True)
        else:
            await interaction.response.send_message(f"Erreur : {error}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Anniversaire(bot))