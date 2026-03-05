"""
cogs/moderation.py — Commandes de modération
"""

import discord
from discord import app_commands
from discord.ext import commands

from config import charger_data, sauvegarder_data, get_joueur, get_config, ajouter_sanction, get_sanctions


class Moderation(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def get_canal_log(self, guild):
        cfg      = get_config(guild.id)
        salon_id = cfg.get("logs_moderation")
        if not salon_id:
            return None
        return guild.get_channel(int(salon_id))

    async def envoyer_log_mod(self, guild, action, moderateur, cible, raison):
        canal = self.get_canal_log(guild)
        if not canal:
            return
        couleurs = {
            "Kick":  discord.Color.orange(),
            "Ban":   discord.Color.red(),
            "Warn":  discord.Color.yellow(),
            "Unban": discord.Color.green(),
            "Mute":  discord.Color.orange(),
        }
        embed = discord.Embed(
            description=f"{moderateur.mention} a effectué une action sur {cible.mention}",
            color=couleurs.get(action, discord.Color.blurple()),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=f"{action} — {moderateur.display_name}", icon_url=moderateur.display_avatar.url)
        embed.add_field(name="👤 Membre",     value=cible.mention,      inline=True)
        embed.add_field(name="🛡️ Modérateur", value=moderateur.mention,  inline=True)
        embed.add_field(name="📝 Raison",     value=raison,              inline=False)
        embed.set_footer(text=guild.name, icon_url=guild.icon.url if guild.icon else None)
        await canal.send(embed=embed)

    # ── /kick ──────────────────────────────────

    @app_commands.command(name="kick", description="Expulse un membre du serveur")
    @app_commands.describe(membre="Le membre à expulser", raison="La raison de l'expulsion")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune raison donnée"):
        await membre.kick(reason=raison)
        ajouter_sanction(interaction.guild_id, membre.id, "Kick", interaction.user.id, interaction.user.display_name, raison)
        await self.envoyer_log_mod(interaction.guild, "Kick", interaction.user, membre, raison)
        embed = discord.Embed(title="👢 Membre expulsé", color=discord.Color.orange())
        embed.add_field(name="Membre", value=membre.mention, inline=True)
        embed.add_field(name="Raison", value=raison,         inline=False)
        await interaction.response.send_message(embed=embed)

    # ── /ban ───────────────────────────────────

    @app_commands.command(name="ban", description="Bannit un membre du serveur")
    @app_commands.describe(membre="Le membre à bannir", raison="La raison du bannissement")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune raison donnée"):
        await membre.ban(reason=raison)
        ajouter_sanction(interaction.guild_id, membre.id, "Ban", interaction.user.id, interaction.user.display_name, raison)
        await self.envoyer_log_mod(interaction.guild, "Ban", interaction.user, membre, raison)
        embed = discord.Embed(title="🔨 Membre banni", color=discord.Color.red())
        embed.add_field(name="Membre", value=membre.mention, inline=True)
        embed.add_field(name="Raison", value=raison,         inline=False)
        await interaction.response.send_message(embed=embed)

    # ── /unban ─────────────────────────────────

    @app_commands.command(name="unban", description="Débannit un membre via son ID")
    @app_commands.describe(user_id="L'ID Discord du membre à débannir")
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str):
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user)
            ajouter_sanction(interaction.guild_id, int(user_id), "Unban", interaction.user.id, interaction.user.display_name, "Débannissement manuel")
            await self.envoyer_log_mod(interaction.guild, "Unban", interaction.user, user, "Débannissement manuel")
            await interaction.response.send_message(f"✅ **{user.name}** a été débanni !")
        except Exception:
            await interaction.response.send_message("Impossible de débannir. Vérifie l'ID.", ephemeral=True)

    # ── /warn ──────────────────────────────────

    @app_commands.command(name="warn", description="Avertit un membre")
    @app_commands.describe(membre="Le membre à avertir", raison="La raison de l'avertissement")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def warn(self, interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune raison donnée"):
        data   = charger_data()
        joueur = get_joueur(data, interaction.guild_id, membre.id)
        joueur["warnings"] += 1
        nb = joueur["warnings"]
        sauvegarder_data(data)
        ajouter_sanction(interaction.guild_id, membre.id, "Warn", interaction.user.id, interaction.user.display_name, raison)
        await self.envoyer_log_mod(interaction.guild, "Warn", interaction.user, membre, raison)
        embed = discord.Embed(title="⚠️ Avertissement", color=discord.Color.yellow())
        embed.add_field(name="Membre",      value=membre.mention,           inline=True)
        embed.add_field(name="Raison",      value=raison,                   inline=False)
        embed.add_field(name="Total warns", value=f"{nb} avertissement(s)", inline=False)
        await interaction.response.send_message(embed=embed)
        if nb >= 3:
            await membre.kick(reason="3 avertissements atteints")
            ajouter_sanction(interaction.guild_id, membre.id, "Kick auto", interaction.user.id, "Bot", "3 avertissements atteints")
            await interaction.channel.send(
                f"{membre.mention} a été expulsé automatiquement après **3 avertissements**."
            )

    # ── /modlog ────────────────────────────────

    @app_commands.command(name="modlog", description="Voir l'historique de modération d'un membre")
    @app_commands.describe(membre="Le membre à consulter")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def modlog(self, interaction: discord.Interaction, membre: discord.Member):
        sanctions = get_sanctions(interaction.guild_id, membre.id)

        embed = discord.Embed(
            title=f"📋 Historique de {membre.display_name}",
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url=membre.display_avatar.url)

        if not sanctions:
            embed.description = "✅ Aucune sanction enregistrée."
        else:
            emojis = {
                "Ban":       "🔨",
                "Kick":      "👢",
                "Kick auto": "🤖",
                "Warn":      "⚠️",
                "Unban":     "✅",
                "Mute":      "🔇",
            }
            # Compte par type
            counts = {}
            for s in sanctions:
                counts[s["action"]] = counts.get(s["action"], 0) + 1

            resume = " | ".join(f"{emojis.get(a, '📌')} {a} x{n}" for a, n in counts.items())
            embed.description = f"**Résumé :** {resume}\n\u200b"

            # Affiche les 10 dernières sanctions
            for s in reversed(sanctions[-10:]):
                emoji = emojis.get(s["action"], "📌")
                embed.add_field(
                    name=f"{emoji} {s['action']} — {s['date']}",
                    value=f"**Par :** {s['moderateur_nom']}\n**Raison :** {s['raison']}",
                    inline=False
                )

        data   = charger_data()
        joueur = get_joueur(data, interaction.guild_id, membre.id)
        embed.set_footer(text=f"Total : {len(sanctions)} sanction(s) | {joueur['warnings']} warn(s) actif(s)")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /clear ─────────────────────────────────

    @app_commands.command(name="clear", description="Supprime des messages dans le salon")
    @app_commands.describe(nombre="Nombre de messages à supprimer (max 100)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, nombre: int):
        if nombre > 100:
            await interaction.response.send_message("Maximum 100 messages à la fois !", ephemeral=True)
            return
        await interaction.response.defer()
        await interaction.channel.purge(limit=nombre)
        await interaction.followup.send(f"✅ **{nombre} messages** supprimés !", ephemeral=True)

    # ── /nick ──────────────────────────────────

    @app_commands.command(name="nick", description="Change le pseudo d'un membre")
    @app_commands.describe(membre="Le membre", pseudo="Le nouveau pseudo (vide pour reset)")
    @app_commands.checks.has_permissions(manage_nicknames=True)
    async def nick(self, interaction: discord.Interaction, membre: discord.Member, pseudo: str = None):
        ancien = membre.display_name
        await membre.edit(nick=pseudo)
        cfg      = get_config(interaction.guild_id)
        salon_id = cfg.get("logs_pseudos")
        if salon_id:
            canal = interaction.guild.get_channel(int(salon_id))
            if canal:
                embed = discord.Embed(
                    description=f"{membre.mention} a changé de pseudo",
                    color=discord.Color.blurple(),
                    timestamp=discord.utils.utcnow()
                )
                embed.set_author(name=f"Pseudo modifié — {membre.display_name}", icon_url=membre.display_avatar.url)
                embed.add_field(name="Avant", value=ancien,           inline=True)
                embed.add_field(name="Après", value=pseudo or ancien,  inline=True)
                embed.set_footer(text=interaction.guild.name)
                await canal.send(embed=embed)
        if pseudo:
            await interaction.response.send_message(f"✅ Pseudo de **{ancien}** changé en **{pseudo}** !")
        else:
            await interaction.response.send_message(f"✅ Pseudo de **{ancien}** remis à zéro !")

    # ── /stop ──────────────────────────────────

    @app_commands.command(name="stop", description="Arrête le bot")
    @app_commands.checks.has_permissions(administrator=True)
    async def stop(self, interaction: discord.Interaction):
        await interaction.response.send_message("🔴 Bot arrêté !", ephemeral=True)
        import os
        os._exit(0)

    # ── /dm ────────────────────────────────────

    @app_commands.command(name="dm", description="Envoie un message privé à un membre via le bot")
    @app_commands.describe(membre="Le membre à contacter", message="Le message à envoyer")
    @app_commands.checks.has_permissions(administrator=True)
    async def dm(self, interaction: discord.Interaction, membre: discord.Member, message: str):
        try:
            embed = discord.Embed(
                title=f"📩 Message de {interaction.guild.name}",
                description=message,
                color=discord.Color.blurple()
            )
            embed.set_footer(text=f"Envoyé par {interaction.user.display_name}")
            await membre.send(embed=embed)
            await interaction.response.send_message(f"✅ Message envoyé à {membre.mention} !", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ Impossible d'envoyer un MP à {membre.mention} — ses DMs sont fermés.", ephemeral=True
            )

    # ── Gestion des erreurs ────────────────────

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("Tu n'as pas la permission !", ephemeral=True)
        else:
            await interaction.response.send_message(f"Erreur : {error}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))