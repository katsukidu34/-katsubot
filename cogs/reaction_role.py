"""
cogs/reaction_role.py — Rôles via réactions
=============================================
Commandes : /reaction_role_add, /reaction_role_remove, /reaction_role_list
Un membre clique sur une réaction → il obtient/perd le rôle automatiquement.
Anti-spam : cooldown 3s par membre + vérification si le rôle est déjà attribué.
"""

import time
import discord
from discord import app_commands
from discord.ext import commands

from config import charger_config, sauvegarder_config


# ══════════════════════════════════════════════
# FONCTIONS
# ══════════════════════════════════════════════

def get_reaction_roles(guild_id: int) -> dict:
    """Retourne les reaction roles du serveur. Format : {message_id: {emoji: role_name}}"""
    config = charger_config()
    return config.get(str(guild_id), {}).get("reaction_roles", {})

def set_reaction_roles(guild_id: int, data: dict):
    """Sauvegarde les reaction roles."""
    config = charger_config()
    gid = str(guild_id)
    if gid not in config:
        config[gid] = {}
    config[gid]["reaction_roles"] = data
    sauvegarder_config(config)


# ══════════════════════════════════════════════
# COG
# ══════════════════════════════════════════════

COOLDOWN_SECONDS = 3  # Délai entre chaque action par membre

class ReactionRole(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._cooldowns: dict[int, float] = {}  # {user_id: timestamp}

    def _check_cooldown(self, user_id: int) -> bool:
        """Retourne True si le membre peut agir, False s'il est en cooldown."""
        now = time.time()
        last = self._cooldowns.get(user_id, 0)
        if now - last < COOLDOWN_SECONDS:
            return False
        self._cooldowns[user_id] = now
        return True

    # ── Listeners ─────────────────────────────

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Donne le rôle quand un membre ajoute une réaction."""
        if payload.user_id == self.bot.user.id:
            return

        if not self._check_cooldown(payload.user_id):
            return  # En cooldown, on ignore

        rr     = get_reaction_roles(payload.guild_id)
        msg_id = str(payload.message_id)
        emoji  = str(payload.emoji)

        if msg_id not in rr or emoji not in rr[msg_id]:
            return

        guild  = self.bot.get_guild(payload.guild_id)
        membre = guild.get_member(payload.user_id)
        role   = discord.utils.get(guild.roles, name=rr[msg_id][emoji])

        if membre and role:
            if role in membre.roles:
                return  # A déjà le rôle, on ignore

            await membre.add_roles(role)
            try:
                await membre.send(f"✅ Tu as obtenu le rôle **{role.name}** sur **{guild.name}** !")
            except discord.Forbidden:
                pass  # DMs désactivés

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Retire le rôle quand un membre enlève sa réaction."""
        if not self._check_cooldown(payload.user_id):
            return  # En cooldown, on ignore

        rr     = get_reaction_roles(payload.guild_id)
        msg_id = str(payload.message_id)
        emoji  = str(payload.emoji)

        if msg_id not in rr or emoji not in rr[msg_id]:
            return

        guild  = self.bot.get_guild(payload.guild_id)
        membre = guild.get_member(payload.user_id)
        role   = discord.utils.get(guild.roles, name=rr[msg_id][emoji])

        if membre and role:
            if role not in membre.roles:
                return  # N'a pas le rôle, on ignore

            await membre.remove_roles(role)
            try:
                await membre.send(f"❌ Tu as perdu le rôle **{role.name}** sur **{guild.name}** !")
            except discord.Forbidden:
                pass  # DMs désactivés

    # ── /reaction_role_add ─────────────────────

    @app_commands.command(name="reaction_role_add", description="Associe un emoji à un rôle sur un message")
    @app_commands.describe(
        message_id="L'ID du message",
        emoji="L'emoji à utiliser",
        role="Le rôle à attribuer"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def reaction_role_add(self, interaction: discord.Interaction, message_id: str, emoji: str, role: discord.Role):
        rr     = get_reaction_roles(interaction.guild_id)
        msg_id = message_id.strip()

        try:
            msg = await interaction.channel.fetch_message(int(msg_id))
        except Exception:
            await interaction.response.send_message(
                "Message introuvable ! Assure-toi d'être dans le bon salon.", ephemeral=True
            )
            return

        if msg_id not in rr:
            rr[msg_id] = {}

        rr[msg_id][emoji] = role.name
        set_reaction_roles(interaction.guild_id, rr)

        await msg.add_reaction(emoji)

        await interaction.response.send_message(
            f"✅ Réaction **{emoji}** associée au rôle **{role.name}** !", ephemeral=True
        )

    # ── /reaction_role_remove ──────────────────

    @app_commands.command(name="reaction_role_remove", description="Supprime une association emoji/rôle")
    @app_commands.describe(message_id="L'ID du message", emoji="L'emoji à supprimer")
    @app_commands.checks.has_permissions(administrator=True)
    async def reaction_role_remove(self, interaction: discord.Interaction, message_id: str, emoji: str):
        rr     = get_reaction_roles(interaction.guild_id)
        msg_id = message_id.strip()

        if msg_id not in rr or emoji not in rr[msg_id]:
            await interaction.response.send_message(
                "Cette association n'existe pas !", ephemeral=True
            )
            return

        del rr[msg_id][emoji]
        if not rr[msg_id]:
            del rr[msg_id]
        set_reaction_roles(interaction.guild_id, rr)

        await interaction.response.send_message(
            f"✅ Association **{emoji}** supprimée !", ephemeral=True
        )

    # ── /reaction_role_list ────────────────────

    @app_commands.command(name="reaction_role_list", description="Liste tous les reaction roles du serveur")
    @app_commands.checks.has_permissions(administrator=True)
    async def reaction_role_list(self, interaction: discord.Interaction):
        rr = get_reaction_roles(interaction.guild_id)

        if not rr:
            await interaction.response.send_message(
                "Aucun reaction role configuré !", ephemeral=True
            )
            return

        embed = discord.Embed(title="🎭 Reaction Roles", color=discord.Color.blurple())
        for msg_id, emojis in rr.items():
            valeur = "\n".join(f"{e} → **{r}**" for e, r in emojis.items())
            embed.add_field(name=f"Message {msg_id}", value=valeur, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("Tu n'as pas la permission !", ephemeral=True)
        else:
            await interaction.response.send_message(f"Erreur : {error}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ReactionRole(bot))