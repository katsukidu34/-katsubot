"""
cogs/tickets.py — Système de tickets avancé
=============================================
/ticket-panel  → Envoie le panel d'ouverture
/ticket-add    → Ajoute un membre au ticket
/ticket-remove → Retire un membre du ticket
"""

import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime

from config import get_config


# ══════════════════════════════════════════════
# SÉLECTEUR DE CATÉGORIE
# ══════════════════════════════════════════════

class SelectCategorie(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="🛠️ Support général",  value="support",      description="Aide générale sur le serveur"),
            discord.SelectOption(label="🐛 Signaler un bug",   value="bug",          description="Un bug ou un problème technique"),
            discord.SelectOption(label="🤝 Partenariat",       value="partenariat",  description="Proposition de partenariat"),
            discord.SelectOption(label="⚠️ Signaler un membre",value="signalement",  description="Signaler un comportement inapproprié"),
            discord.SelectOption(label="💡 Suggestion",        value="suggestion",   description="Proposer une amélioration"),
        ]
        super().__init__(
            placeholder="📂 Choisir une catégorie...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="select_categorie_ticket"
        )

    async def callback(self, interaction: discord.Interaction):
        categorie = self.values[0]
        await interaction.response.send_modal(ModalTicket(categorie))


class VuePanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(SelectCategorie())


# ══════════════════════════════════════════════
# MODAL (formulaire)
# ══════════════════════════════════════════════

LABELS = {
    "support":     "Support général",
    "bug":         "Signaler un bug",
    "partenariat": "Partenariat",
    "signalement": "Signaler un membre",
    "suggestion":  "Suggestion",
}

EMOJIS = {
    "support":     "🛠️",
    "bug":         "🐛",
    "partenariat": "🤝",
    "signalement": "⚠️",
    "suggestion":  "💡",
}

COULEURS = {
    "support":     discord.Color.blurple(),
    "bug":         discord.Color.red(),
    "partenariat": discord.Color.green(),
    "signalement": discord.Color.orange(),
    "suggestion":  discord.Color.gold(),
}


class ModalTicket(discord.ui.Modal):
    def __init__(self, categorie: str):
        super().__init__(title=f"Ouvrir un ticket — {LABELS[categorie]}")
        self.categorie = categorie

        self.sujet = discord.ui.TextInput(
            label="Sujet",
            placeholder="Résume ton problème en quelques mots...",
            max_length=100,
            required=True
        )
        self.description = discord.ui.TextInput(
            label="Description",
            placeholder="Décris ton problème en détail...",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=True
        )
        self.add_item(self.sujet)
        self.add_item(self.description)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        cfg   = get_config(guild.id)

        # Vérifie si ticket déjà ouvert
        nom_salon = f"ticket-{interaction.user.name}".lower().replace(" ", "-")[:32]
        existant  = discord.utils.get(guild.text_channels, name=nom_salon)
        if existant:
            await interaction.followup.send(
                f"❌ Tu as déjà un ticket ouvert : {existant.mention} !", ephemeral=True
            )
            return

        categorie_salon = guild.get_channel(int(cfg["categorie_tickets"])) if cfg["categorie_tickets"] else None

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user:   discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me:           discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True),
        }
        for role in guild.roles:
            if role.permissions.administrator or role.permissions.manage_channels:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        canal = await guild.create_text_channel(
            name=nom_salon,
            overwrites=overwrites,
            category=categorie_salon,
            topic=f"{EMOJIS[self.categorie]} {LABELS[self.categorie]} | {interaction.user} | {self.sujet.value}"
        )

        embed = discord.Embed(
            title=f"{EMOJIS[self.categorie]} Ticket — {self.sujet.value}",
            description=(
                f"Bienvenue {interaction.user.mention} !\n"
                f"Un membre de l'équipe va te répondre bientôt.\n\n"
                f"**📋 Catégorie :** {LABELS[self.categorie]}\n"
                f"**📝 Description :**\n{self.description.value}"
            ),
            color=COULEURS[self.categorie],
            timestamp=datetime.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"ID : {interaction.user.id}")

        await canal.send(
            content=f"{interaction.user.mention} | 📬 Ticket ouvert",
            embed=embed,
            view=VueTicket(interaction.user.id)
        )
        await interaction.followup.send(
            f"✅ Ton ticket a été créé : {canal.mention}", ephemeral=True
        )


# ══════════════════════════════════════════════
# VUE TICKET (boutons dans le ticket)
# ══════════════════════════════════════════════

class VueTicket(discord.ui.View):
    def __init__(self, auteur_id: int = None):
        super().__init__(timeout=None)
        self.auteur_id = auteur_id

    @discord.ui.button(label="✅ Prendre en charge", style=discord.ButtonStyle.success, custom_id="claim_ticket")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("❌ Réservé aux modérateurs !", ephemeral=True)
            return
        button.disabled = True
        button.label    = f"✅ Pris en charge par {interaction.user.display_name}"
        await interaction.response.edit_message(view=self)
        await interaction.channel.send(
            embed=discord.Embed(
                description=f"📌 {interaction.user.mention} a pris en charge ce ticket.",
                color=discord.Color.green()
            )
        )

    @discord.ui.button(label="🔒 Fermer", style=discord.ButtonStyle.danger, custom_id="fermer_ticket")
    async def fermer(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("❌ Réservé aux modérateurs !", ephemeral=True)
            return

        await interaction.response.send_message(
            embed=discord.Embed(
                description="🔒 Ticket en cours de fermeture... Suppression dans **5 secondes**.",
                color=discord.Color.red()
            )
        )

        # Transcript
        messages = []
        async for msg in interaction.channel.history(limit=200, oldest_first=True):
            if not msg.author.bot:
                messages.append(f"[{msg.created_at.strftime('%H:%M')}] {msg.author.display_name}: {msg.content}")

        transcript = "\n".join(messages) if messages else "Aucun message."

        # Envoie le transcript en DM au modérateur
        try:
            embed_log = discord.Embed(
                title=f"📋 Transcript — {interaction.channel.name}",
                description=f"```\n{transcript[:3900]}\n```",
                color=discord.Color.blurple(),
                timestamp=datetime.utcnow()
            )
            embed_log.set_footer(text=f"Fermé par {interaction.user.display_name}")
            await interaction.user.send(embed=embed_log)
        except Exception:
            pass

        await asyncio.sleep(5)
        await interaction.channel.delete()


# ══════════════════════════════════════════════
# COG
# ══════════════════════════════════════════════

class Tickets(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(VuePanel())
        self.bot.add_view(VueTicket())

    # ── /ticket-panel ──────────────────────────

    @app_commands.command(name="ticket-panel", description="Envoie le panel d'ouverture de tickets")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_panel(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎫 Ouvrir un ticket",
            description=(
                "Besoin d'aide ou tu veux contacter l'équipe ?\n\n"
                "**Sélectionne une catégorie** dans le menu ci-dessous pour ouvrir un ticket.\n\n"
                "🛠️ **Support général** — Aide sur le serveur\n"
                "🐛 **Bug** — Signaler un problème technique\n"
                "🤝 **Partenariat** — Proposition de partenariat\n"
                "⚠️ **Signalement** — Signaler un membre\n"
                "💡 **Suggestion** — Proposer une amélioration"
            ),
            color=discord.Color.blurple()
        )
        embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
        await interaction.channel.send(embed=embed, view=VuePanel())
        await interaction.response.send_message("✅ Panel envoyé !", ephemeral=True)

    # ── /ticket-add ────────────────────────────

    @app_commands.command(name="ticket-add", description="Ajoute un membre au ticket actuel")
    @app_commands.describe(membre="Le membre à ajouter")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_add(self, interaction: discord.Interaction, membre: discord.Member):
        await interaction.channel.set_permissions(membre, read_messages=True, send_messages=True)
        await interaction.response.send_message(
            embed=discord.Embed(
                description=f"✅ {membre.mention} a été ajouté au ticket.",
                color=discord.Color.green()
            )
        )

    # ── /ticket-remove ─────────────────────────

    @app_commands.command(name="ticket-remove", description="Retire un membre du ticket actuel")
    @app_commands.describe(membre="Le membre à retirer")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_remove(self, interaction: discord.Interaction, membre: discord.Member):
        await interaction.channel.set_permissions(membre, read_messages=False)
        await interaction.response.send_message(
            embed=discord.Embed(
                description=f"✅ {membre.mention} a été retiré du ticket.",
                color=discord.Color.orange()
            )
        )

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ Tu n'as pas la permission !", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Erreur : {error}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))