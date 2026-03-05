"""
cogs/tickets.py — Système de tickets de support
=================================================
Commandes : /ticket
Fermeture via bouton dans l'embed
"""

import asyncio
import discord
from discord import app_commands
from discord.ext import commands

from config import get_config


# ══════════════════════════════════════════════
# BOUTON FERMER
# ══════════════════════════════════════════════

class VueTicket(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Pas d'expiration

    @discord.ui.button(label="🔒 Fermer le ticket", style=discord.ButtonStyle.danger, custom_id="fermer_ticket")
    async def fermer(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Vérifie que c'est un mod ou l'auteur du ticket
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message(
                "Seul un modérateur peut fermer le ticket !", ephemeral=True
            )
            return

        await interaction.response.send_message("🔒 Ticket fermé. Suppression dans 5 secondes...")
        await asyncio.sleep(5)
        await interaction.channel.delete()


# ══════════════════════════════════════════════
# COG
# ══════════════════════════════════════════════

class Tickets(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Ré-enregistre la vue au démarrage pour que le bouton fonctionne après redémarrage
        self.bot.add_view(VueTicket())

    # ── /ticket ────────────────────────────────

    @app_commands.command(name="ticket", description="Ouvre un ticket de support")
    @app_commands.describe(sujet="Le sujet de ton ticket")
    async def ticket(self, interaction: discord.Interaction, sujet: str):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        cfg   = get_config(guild.id)

        # Vérifie si le membre a déjà un ticket ouvert
        nom_salon = f"ticket-{interaction.user.name}".lower().replace(" ", "-")
        ticket_existant = discord.utils.get(guild.text_channels, name=nom_salon)
        if ticket_existant:
            await interaction.followup.send(
                f"Tu as déjà un ticket ouvert : {ticket_existant.mention} !", ephemeral=True
            )
            return

        categorie = guild.get_channel(int(cfg["categorie_tickets"])) if cfg["categorie_tickets"] else None

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user:   discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me:           discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        for role in guild.roles:
            if role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        canal = await guild.create_text_channel(
            name=nom_salon,
            overwrites=overwrites,
            category=categorie,
            topic=f"Ticket de {interaction.user} | Sujet : {sujet}"
        )

        embed = discord.Embed(
            title=f"🎫 Ticket — {sujet}",
            description=(
                f"Bonjour {interaction.user.mention} !\n"
                f"Un modérateur va te répondre bientôt.\n\n"
                f"Clique sur le bouton ci-dessous pour fermer le ticket."
            ),
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Ouvert par {interaction.user.display_name}")

        await canal.send(embed=embed, view=VueTicket())
        await interaction.followup.send(
            f"Ton ticket a été créé : {canal.mention}", ephemeral=True
        )

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("Tu n'as pas la permission !", ephemeral=True)
        else:
            await interaction.response.send_message(f"Erreur : {error}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))