"""
cogs/reaction_role.py — Rôles via boutons (Button Roles)
==========================================================
/role-panel   → Crée un panel avec boutons pour obtenir des rôles
/role-add     → Ajoute un bouton rôle à un panel existant
/role-remove  → Retire un bouton rôle d'un panel
/role-list    → Liste tous les panels du serveur

Plus moderne et fiable que les reaction roles classiques !
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime

from config import get_config, set_config


# ══════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════

def get_panels(guild_id: int) -> dict:
    return get_config(guild_id).get("reaction_roles", {})

def save_panels(guild_id: int, panels: dict):
    set_config(guild_id, "reaction_roles", panels)


# ══════════════════════════════════════════════
# VUE DYNAMIQUE (boutons rôles)
# ══════════════════════════════════════════════

class VueRoles(discord.ui.View):
    def __init__(self, panel_id: str, boutons: list):
        super().__init__(timeout=None)
        for b in boutons:
            self.add_item(BoutonRole(
                role_id    = b["role_id"],
                label      = b["label"],
                emoji      = b.get("emoji", "🎭"),
                couleur    = b.get("couleur", "blurple"),
                panel_id   = panel_id,
            ))


COULEURS = {
    "blurple": discord.ButtonStyle.primary,
    "vert":    discord.ButtonStyle.success,
    "rouge":   discord.ButtonStyle.danger,
    "gris":    discord.ButtonStyle.secondary,
}


class BoutonRole(discord.ui.Button):
    def __init__(self, role_id: int, label: str, emoji: str, couleur: str, panel_id: str):
        super().__init__(
            label     = label,
            emoji     = emoji,
            style     = COULEURS.get(couleur, discord.ButtonStyle.primary),
            custom_id = f"role_{panel_id}_{role_id}",
        )
        self.role_id = role_id

    async def callback(self, interaction: discord.Interaction):
        role = interaction.guild.get_role(self.role_id)
        if not role:
            await interaction.response.send_message("❌ Ce rôle n'existe plus !", ephemeral=True)
            return

        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            embed = discord.Embed(
                description=f"❌ Le rôle **{role.name}** t'a été retiré.",
                color=discord.Color.orange()
            )
        else:
            await interaction.user.add_roles(role)
            embed = discord.Embed(
                description=f"✅ Tu as obtenu le rôle {role.mention} !",
                color=discord.Color.green()
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)


# ══════════════════════════════════════════════
# COG
# ══════════════════════════════════════════════

class ReactionRole(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """Recharge tous les panels au démarrage."""
        for guild in self.bot.guilds:
            panels = get_panels(guild.id)
            for panel_id, panel in panels.items():
                boutons = panel.get("boutons", [])
                if boutons:
                    self.bot.add_view(VueRoles(panel_id, boutons))

    # ── /role-panel ────────────────────────────

    @app_commands.command(name="role-panel", description="Crée un panel de sélection de rôles")
    @app_commands.describe(
        titre="Titre du panel",
        description="Description du panel",
        couleur="Couleur de l'embed (blurple/vert/rouge/gris)"
    )
    @app_commands.choices(couleur=[
        app_commands.Choice(name="💜 Blurple", value="blurple"),
        app_commands.Choice(name="💚 Vert",    value="vert"),
        app_commands.Choice(name="❤️ Rouge",   value="rouge"),
        app_commands.Choice(name="🩶 Gris",    value="gris"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def role_panel(self, interaction: discord.Interaction, titre: str, description: str, couleur: str = "blurple"):
        await interaction.response.defer(ephemeral=True)

        COULEURS_EMBED = {
            "blurple": discord.Color.blurple(),
            "vert":    discord.Color.green(),
            "rouge":   discord.Color.red(),
            "gris":    discord.Color.greyple(),
        }

        embed = discord.Embed(
            title       = titre,
            description = description,
            color       = COULEURS_EMBED.get(couleur, discord.Color.blurple()),
            timestamp   = datetime.utcnow()
        )
        embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url if interaction.guild.icon else None)

        # Panel vide au départ
        msg = await interaction.channel.send(embed=embed, view=discord.ui.View())

        # Sauvegarde
        panels = get_panels(interaction.guild_id)
        panel_id = str(msg.id)
        panels[panel_id] = {
            "message_id": msg.id,
            "channel_id": interaction.channel_id,
            "titre":      titre,
            "boutons":    [],
        }
        save_panels(interaction.guild_id, panels)

        await interaction.followup.send(
            f"✅ Panel créé ! Utilise `/role-add` avec l'ID `{panel_id}` pour ajouter des rôles.",
            ephemeral=True
        )

    # ── /role-add ──────────────────────────────

    @app_commands.command(name="role-add", description="Ajoute un bouton rôle à un panel")
    @app_commands.describe(
        panel_id  = "L'ID du panel (message)",
        role      = "Le rôle à attribuer",
        label     = "Texte du bouton",
        emoji     = "Emoji du bouton",
        couleur   = "Couleur du bouton"
    )
    @app_commands.choices(couleur=[
        app_commands.Choice(name="💜 Blurple", value="blurple"),
        app_commands.Choice(name="💚 Vert",    value="vert"),
        app_commands.Choice(name="❤️ Rouge",   value="rouge"),
        app_commands.Choice(name="🩶 Gris",    value="gris"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def role_add(self, interaction: discord.Interaction, panel_id: str, role: discord.Role, label: str, emoji: str = "🎭", couleur: str = "blurple"):
        panels = get_panels(interaction.guild_id)

        if panel_id not in panels:
            await interaction.response.send_message("❌ Panel introuvable !", ephemeral=True)
            return

        panel   = panels[panel_id]
        boutons = panel.get("boutons", [])

        if len(boutons) >= 25:
            await interaction.response.send_message("❌ Maximum 25 boutons par panel !", ephemeral=True)
            return

        if any(b["role_id"] == role.id for b in boutons):
            await interaction.response.send_message("❌ Ce rôle est déjà dans le panel !", ephemeral=True)
            return

        boutons.append({
            "role_id": role.id,
            "label":   label,
            "emoji":   emoji,
            "couleur": couleur,
        })
        panel["boutons"] = boutons
        save_panels(interaction.guild_id, panels)

        # Met à jour le message
        try:
            canal = interaction.guild.get_channel(panel["channel_id"])
            msg   = await canal.fetch_message(int(panel_id))
            vue   = VueRoles(panel_id, boutons)
            self.bot.add_view(vue)
            await msg.edit(view=vue)
        except Exception as e:
            await interaction.response.send_message(f"❌ Impossible de mettre à jour le panel : {e}", ephemeral=True)
            return

        await interaction.response.send_message(
            f"✅ Bouton **{label}** ({emoji}) ajouté pour le rôle {role.mention} !",
            ephemeral=True
        )

    # ── /role-remove ───────────────────────────

    @app_commands.command(name="role-remove", description="Retire un bouton rôle d'un panel")
    @app_commands.describe(panel_id="L'ID du panel", role="Le rôle à retirer")
    @app_commands.checks.has_permissions(administrator=True)
    async def role_remove(self, interaction: discord.Interaction, panel_id: str, role: discord.Role):
        panels = get_panels(interaction.guild_id)

        if panel_id not in panels:
            await interaction.response.send_message("❌ Panel introuvable !", ephemeral=True)
            return

        panel   = panels[panel_id]
        boutons = panel.get("boutons", [])
        nouveaux = [b for b in boutons if b["role_id"] != role.id]

        if len(nouveaux) == len(boutons):
            await interaction.response.send_message("❌ Ce rôle n'est pas dans le panel !", ephemeral=True)
            return

        panel["boutons"] = nouveaux
        save_panels(interaction.guild_id, panels)

        try:
            canal = interaction.guild.get_channel(panel["channel_id"])
            msg   = await canal.fetch_message(int(panel_id))
            vue   = VueRoles(panel_id, nouveaux) if nouveaux else discord.ui.View()
            await msg.edit(view=vue)
        except Exception as e:
            await interaction.response.send_message(f"❌ Impossible de mettre à jour le panel : {e}", ephemeral=True)
            return

        await interaction.response.send_message(
            f"✅ Bouton pour **{role.name}** retiré du panel !",
            ephemeral=True
        )

    # ── /role-list ─────────────────────────────

    @app_commands.command(name="role-list", description="Liste tous les panels de rôles du serveur")
    @app_commands.checks.has_permissions(administrator=True)
    async def role_list(self, interaction: discord.Interaction):
        panels = get_panels(interaction.guild_id)

        if not panels:
            await interaction.response.send_message("❌ Aucun panel configuré !", ephemeral=True)
            return

        embed = discord.Embed(
            title     = "🎭 Panels de rôles",
            color     = discord.Color.blurple(),
            timestamp = datetime.utcnow()
        )

        for panel_id, panel in panels.items():
            boutons = panel.get("boutons", [])
            if boutons:
                lignes = []
                for b in boutons:
                    role = interaction.guild.get_role(b["role_id"])
                    nom  = role.mention if role else f"~~{b['label']}~~ (supprimé)"
                    lignes.append(f"{b.get('emoji','🎭')} {b['label']} → {nom}")
                valeur = "\n".join(lignes)
            else:
                valeur = "*Aucun bouton*"

            embed.add_field(
                name   = f"📋 {panel.get('titre', 'Panel')} (ID: {panel_id})",
                value  = valeur,
                inline = False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ Tu n'as pas la permission !", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Erreur : {error}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ReactionRole(bot))