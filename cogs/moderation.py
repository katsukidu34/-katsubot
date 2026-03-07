"""
cogs/moderation.py — Commandes de modération
Accès direct MongoDB, defer() partout, gestion d'erreurs propre.
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime

from config import col_data, get_config, ajouter_sanction, get_sanctions


# ══════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════

EMOJIS_ACTIONS = {
    "Ban":       "🔨",
    "Kick":      "👢",
    "Kick auto": "🤖",
    "Warn":      "⚠️",
    "Unban":     "✅",
    "Mute":      "🔇",
}

COULEURS_ACTIONS = {
    "Kick":  discord.Color.orange(),
    "Ban":   discord.Color.red(),
    "Warn":  discord.Color.yellow(),
    "Unban": discord.Color.green(),
    "Mute":  discord.Color.orange(),
}


def _get_warnings(guild_id: int, user_id: int) -> int:
    gid, uid = str(guild_id), str(user_id)
    doc = col_data.find_one({"guild_id": gid, "user_id": uid}, {"warnings": 1})
    return doc.get("warnings", 0) if doc else 0


def _increment_warning(guild_id: int, user_id: int) -> int:
    gid, uid = str(guild_id), str(user_id)
    result = col_data.find_one_and_update(
        {"guild_id": gid, "user_id": uid},
        {"$inc": {"warnings": 1}, "$setOnInsert": {"xp": 0, "niveau": 0}},
        upsert=True,
        return_document=True
    )
    return result.get("warnings", 1)


# ══════════════════════════════════════════════
# COG
# ══════════════════════════════════════════════

class Moderation(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Log modération ─────────────────────────

    async def log_mod(self, guild: discord.Guild, action: str, moderateur: discord.Member, cible, raison: str):
        cfg      = get_config(guild.id)
        salon_id = cfg.get("logs_moderation")
        if not salon_id:
            return
        canal = guild.get_channel(int(salon_id))
        if not canal:
            return

        embed = discord.Embed(
            description=f"{moderateur.mention} a effectué une action sur {cible.mention if hasattr(cible, 'mention') else str(cible)}",
            color=COULEURS_ACTIONS.get(action, discord.Color.blurple()),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=f"{action} — {moderateur.display_name}", icon_url=moderateur.display_avatar.url)
        embed.add_field(name="👤 Membre",     value=cible.mention if hasattr(cible, 'mention') else str(cible), inline=True)
        embed.add_field(name="🛡️ Modérateur", value=moderateur.mention, inline=True)
        embed.add_field(name="📝 Raison",     value=raison, inline=False)
        embed.set_footer(text=guild.name, icon_url=guild.icon.url if guild.icon else None)

        try:
            await canal.send(embed=embed)
        except discord.Forbidden:
            pass

    # ── /kick ──────────────────────────────────

    @app_commands.command(name="kick", description="Expulse un membre du serveur")
    @app_commands.describe(membre="Le membre à expulser", raison="La raison de l'expulsion")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune raison donnée"):
        await interaction.response.defer()
        await membre.kick(reason=raison)
        ajouter_sanction(interaction.guild_id, membre.id, "Kick", interaction.user.id, interaction.user.display_name, raison)
        await self.log_mod(interaction.guild, "Kick", interaction.user, membre, raison)

        embed = discord.Embed(title="👢 Membre expulsé", color=discord.Color.orange(), timestamp=discord.utils.utcnow())
        embed.add_field(name="Membre", value=membre.mention, inline=True)
        embed.add_field(name="Raison", value=raison, inline=False)
        embed.set_thumbnail(url=membre.display_avatar.url)
        await interaction.followup.send(embed=embed)

    # ── /ban ───────────────────────────────────

    @app_commands.command(name="ban", description="Bannit un membre du serveur")
    @app_commands.describe(membre="Le membre à bannir", raison="La raison du bannissement")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune raison donnée"):
        await interaction.response.defer()
        await membre.ban(reason=raison)
        ajouter_sanction(interaction.guild_id, membre.id, "Ban", interaction.user.id, interaction.user.display_name, raison)
        await self.log_mod(interaction.guild, "Ban", interaction.user, membre, raison)

        embed = discord.Embed(title="🔨 Membre banni", color=discord.Color.red(), timestamp=discord.utils.utcnow())
        embed.add_field(name="Membre", value=membre.mention, inline=True)
        embed.add_field(name="Raison", value=raison, inline=False)
        embed.set_thumbnail(url=membre.display_avatar.url)
        await interaction.followup.send(embed=embed)

    # ── /unban ─────────────────────────────────

    @app_commands.command(name="unban", description="Débannit un membre via son ID")
    @app_commands.describe(user_id="L'ID Discord du membre à débannir")
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str):
        await interaction.response.defer()
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user)
            ajouter_sanction(interaction.guild_id, int(user_id), "Unban", interaction.user.id, interaction.user.display_name, "Débannissement manuel")
            await self.log_mod(interaction.guild, "Unban", interaction.user, user, "Débannissement manuel")

            embed = discord.Embed(title="✅ Membre débanni", color=discord.Color.green(), timestamp=discord.utils.utcnow())
            embed.add_field(name="Membre", value=f"{user.name} (`{user.id}`)", inline=False)
            await interaction.followup.send(embed=embed)
        except ValueError:
            await interaction.followup.send("❌ ID invalide — entrez uniquement des chiffres.", ephemeral=True)
        except discord.NotFound:
            await interaction.followup.send("❌ Membre introuvable ou pas banni.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Erreur : {e}", ephemeral=True)

    # ── /warn ──────────────────────────────────

    @app_commands.command(name="warn", description="Avertit un membre")
    @app_commands.describe(membre="Le membre à avertir", raison="La raison de l'avertissement")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def warn(self, interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune raison donnée"):
        await interaction.response.defer()

        nb = _increment_warning(interaction.guild_id, membre.id)
        ajouter_sanction(interaction.guild_id, membre.id, "Warn", interaction.user.id, interaction.user.display_name, raison)
        await self.log_mod(interaction.guild, "Warn", interaction.user, membre, raison)

        embed = discord.Embed(title="⚠️ Avertissement", color=discord.Color.yellow(), timestamp=discord.utils.utcnow())
        embed.add_field(name="Membre",      value=membre.mention,           inline=True)
        embed.add_field(name="Warns",       value=f"**{nb}**/3",            inline=True)
        embed.add_field(name="Raison",      value=raison,                   inline=False)
        embed.set_thumbnail(url=membre.display_avatar.url)
        await interaction.followup.send(embed=embed)

        if nb >= 3:
            try:
                await membre.kick(reason="3 avertissements atteints")
                ajouter_sanction(interaction.guild_id, membre.id, "Kick auto", interaction.user.id, "Bot", "3 avertissements atteints")
                await self.log_mod(interaction.guild, "Kick auto", interaction.user, membre, "3 avertissements atteints")
                await interaction.channel.send(
                    f"🤖 {membre.mention} a été expulsé automatiquement après **3 avertissements**."
                )
            except discord.Forbidden:
                await interaction.channel.send("⚠️ Impossible d'expulser automatiquement — permissions insuffisantes.")

    # ── /modlog ────────────────────────────────

    @app_commands.command(name="modlog", description="Voir l'historique de modération d'un membre")
    @app_commands.describe(membre="Le membre à consulter")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def modlog(self, interaction: discord.Interaction, membre: discord.Member):
        await interaction.response.defer(ephemeral=True)

        sanctions = get_sanctions(interaction.guild_id, membre.id)
        warnings  = _get_warnings(interaction.guild_id, membre.id)

        embed = discord.Embed(
            title=f"📋 Historique — {membre.display_name}",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=membre.display_avatar.url)

        if not sanctions:
            embed.description = "✅ Aucune sanction enregistrée."
        else:
            counts = {}
            for s in sanctions:
                counts[s["action"]] = counts.get(s["action"], 0) + 1
            resume = " · ".join(f"{EMOJIS_ACTIONS.get(a,'📌')} {a} ×{n}" for a, n in counts.items())
            embed.description = f"**Résumé :** {resume}\n\u200b"

            for s in reversed(sanctions[-10:]):
                emoji = EMOJIS_ACTIONS.get(s["action"], "📌")
                embed.add_field(
                    name=f"{emoji} {s['action']} — {s['date']}",
                    value=f"**Par :** {s['moderateur_nom']}\n**Raison :** {s['raison']}",
                    inline=False
                )

        embed.set_footer(text=f"{len(sanctions)} sanction(s) · {warnings} warn(s) actif(s)")
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── /clear ─────────────────────────────────

    @app_commands.command(name="clear", description="Supprime des messages dans le salon")
    @app_commands.describe(nombre="Nombre de messages à supprimer (max 100)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, nombre: int):
        if not 1 <= nombre <= 100:
            await interaction.response.send_message("❌ Entre 1 et 100 messages seulement.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        supprimés = await interaction.channel.purge(limit=nombre)
        await interaction.followup.send(f"✅ **{len(supprimés)} messages** supprimés !", ephemeral=True)

    # ── /nick ──────────────────────────────────

    @app_commands.command(name="nick", description="Change le pseudo d'un membre")
    @app_commands.describe(membre="Le membre", pseudo="Le nouveau pseudo (vide pour reset)")
    @app_commands.checks.has_permissions(manage_nicknames=True)
    async def nick(self, interaction: discord.Interaction, membre: discord.Member, pseudo: str = None):
        await interaction.response.defer()
        ancien = membre.display_name
        await membre.edit(nick=pseudo)

        cfg      = get_config(interaction.guild_id)
        salon_id = cfg.get("logs_pseudos")
        if salon_id:
            canal = interaction.guild.get_channel(int(salon_id))
            if canal:
                embed_log = discord.Embed(
                    description=f"Pseudo de {membre.mention} modifié",
                    color=discord.Color.blurple(),
                    timestamp=discord.utils.utcnow()
                )
                embed_log.set_author(name=f"Pseudo — {membre.display_name}", icon_url=membre.display_avatar.url)
                embed_log.add_field(name="Avant", value=ancien,          inline=True)
                embed_log.add_field(name="Après", value=pseudo or ancien, inline=True)
                embed_log.set_footer(text=f"Par {interaction.user.display_name}")
                try:
                    await canal.send(embed=embed_log)
                except discord.Forbidden:
                    pass

        msg = f"✅ Pseudo de **{ancien}** changé en **{pseudo}** !" if pseudo else f"✅ Pseudo de **{ancien}** remis à zéro !"
        await interaction.followup.send(msg)

    # ── /slowmode ──────────────────────────────

    @app_commands.command(name="slowmode", description="Active/désactive le slowmode dans ce salon")
    @app_commands.describe(secondes="Délai en secondes (0 pour désactiver, max 21600)")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def slowmode(self, interaction: discord.Interaction, secondes: int = 0):
        await interaction.response.defer()
        if not 0 <= secondes <= 21600:
            await interaction.followup.send("❌ Entre 0 et 21600 secondes.", ephemeral=True)
            return
        await interaction.channel.edit(slowmode_delay=secondes)
        if secondes == 0:
            await interaction.followup.send("✅ Slowmode **désactivé**.")
        else:
            await interaction.followup.send(f"✅ Slowmode réglé à **{secondes}s**.")

    # ── /tempban ───────────────────────────────

    @app_commands.command(name="tempban", description="Bannit temporairement un membre")
    @app_commands.describe(membre="Le membre", duree="Durée en minutes", raison="La raison")
    @app_commands.checks.has_permissions(ban_members=True)
    async def tempban(self, interaction: discord.Interaction, membre: discord.Member, duree: int, raison: str = "Aucune raison donnée"):
        await interaction.response.defer()
        await membre.ban(reason=f"[Tempban {duree}min] {raison}")
        ajouter_sanction(interaction.guild_id, membre.id, "Ban", interaction.user.id, interaction.user.display_name, f"[Tempban {duree}min] {raison}")
        await self.log_mod(interaction.guild, "Ban", interaction.user, membre, f"Tempban {duree} min — {raison}")

        embed = discord.Embed(title="⏱️ Ban temporaire", color=discord.Color.red(), timestamp=discord.utils.utcnow())
        embed.add_field(name="Membre", value=membre.mention, inline=True)
        embed.add_field(name="Durée",  value=f"{duree} min",  inline=True)
        embed.add_field(name="Raison", value=raison,           inline=False)
        embed.set_thumbnail(url=membre.display_avatar.url)
        await interaction.followup.send(embed=embed)

        # Unban automatique après la durée
        import asyncio
        await asyncio.sleep(duree * 60)
        try:
            await interaction.guild.unban(membre, reason="Tempban expiré")
            ajouter_sanction(interaction.guild_id, membre.id, "Unban", self.bot.user.id, "Bot", "Tempban expiré")
        except Exception:
            pass

    # ── Erreurs globales ───────────────────────

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        msg = "❌ Permission refusée." if isinstance(error, app_commands.MissingPermissions) else f"❌ Erreur : {error}"
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))