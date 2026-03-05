"""
cogs/shop.py — Boutique de rôles avec XP
==========================================
Commandes : /shop, /acheter
La gestion du shop se fait via /config
"""

import discord
from discord import app_commands
from discord.ext import commands

from config import charger_data, sauvegarder_data, get_joueur, charger_config, sauvegarder_config


def get_shop(guild_id: int) -> dict:
    """Retourne les articles du shop pour ce serveur."""
    config = charger_config()
    return config.get(str(guild_id), {}).get("shop", {})

def set_shop(guild_id: int, shop: dict):
    """Sauvegarde les articles du shop."""
    config = charger_config()
    gid = str(guild_id)
    if gid not in config:
        config[gid] = {}
    config[gid]["shop"] = shop
    sauvegarder_config(config)


class Shop(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /shop ──────────────────────────────────

    @app_commands.command(name="shop", description="Affiche la boutique de rôles")
    async def shop(self, interaction: discord.Interaction):
        articles = get_shop(interaction.guild_id)

        if not articles:
            await interaction.response.send_message(
                "La boutique est vide ! Un admin peut ajouter des articles via `/config`."
            )
            return

        data   = charger_data()
        joueur = get_joueur(data, interaction.guild_id, interaction.user.id)
        xp     = joueur["xp"]

        embed = discord.Embed(
            title="🛒 Boutique de rôles",
            description=f"Ton XP actuel : **{xp} XP**\nUtilise `/acheter [nom du rôle]` pour acheter !",
            color=discord.Color.gold()
        )
        for nom_role, prix in sorted(articles.items(), key=lambda x: x[1]):
            role        = discord.utils.get(interaction.guild.roles, name=nom_role)
            deja_achete = role in interaction.user.roles if role else False
            statut      = "✅ Possédé" if deja_achete else ("❌ Rôle introuvable" if not role else f"{prix} XP")
            embed.add_field(name=f"🎭 {nom_role}", value=statut, inline=True)

        await interaction.response.send_message(embed=embed)

    # ── /acheter ───────────────────────────────

    @app_commands.command(name="buy", description="Achète un rôle dans la boutique")
    @app_commands.describe(nom_role="Le nom exact du rôle à acheter")
    async def acheter(self, interaction: discord.Interaction, nom_role: str):
        articles = get_shop(interaction.guild_id)

        if nom_role not in articles:
            await interaction.response.send_message(
                "Cet article n'existe pas ! Utilise `/shop` pour voir les articles disponibles.",
                ephemeral=True
            )
            return

        prix = articles[nom_role]
        role = discord.utils.get(interaction.guild.roles, name=nom_role)

        if not role:
            await interaction.response.send_message("Ce rôle n'existe plus sur le serveur !", ephemeral=True)
            return

        if role in interaction.user.roles:
            await interaction.response.send_message("Tu possèdes déjà ce rôle !", ephemeral=True)
            return

        data   = charger_data()
        joueur = get_joueur(data, interaction.guild_id, interaction.user.id)

        if joueur["xp"] < prix:
            manque = prix - joueur["xp"]
            await interaction.response.send_message(
                f"Il te manque **{manque} XP** ! (tu as {joueur['xp']} XP)", ephemeral=True
            )
            return

        joueur["xp"] -= prix
        sauvegarder_data(data)
        await interaction.user.add_roles(role)

        embed = discord.Embed(
            title="✅ Achat réussi !",
            description=f"Tu as acheté le rôle **{nom_role}** pour **{prix} XP** !\nXP restant : **{joueur['xp']} XP**",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
        # ── /inventaire ────────────────────────────

    @app_commands.command(name="inventaire", description="Voir les rôles achetés au shop")
    @app_commands.describe(membre="Le membre à consulter (toi par défaut)")
    async def inventaire(self, interaction: discord.Interaction, membre: discord.Member = None):
        cible   = membre or interaction.user
        articles = get_shop(interaction.guild_id)

        if not articles:
            await interaction.response.send_message("La boutique est vide !", ephemeral=True)
            return

        # Vérifie quels rôles du shop le membre possède
        roles_possedes = []
        roles_manquants = []

        for nom_role, prix in sorted(articles.items(), key=lambda x: x[1]):
            role = discord.utils.get(interaction.guild.roles, name=nom_role)
            if role and role in cible.roles:
                roles_possedes.append(f"✅ **{nom_role}** ({prix} XP)")
            else:
                roles_manquants.append(f"❌ **{nom_role}** ({prix} XP)")

        embed = discord.Embed(
            title=f"🎒 Inventaire de {cible.display_name}",
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url=cible.display_avatar.url)

        if roles_possedes:
            embed.add_field(name="Rôles possédés", value="\n".join(roles_possedes), inline=False)
        else:
            embed.add_field(name="Rôles possédés", value="Aucun rôle acheté pour l'instant.", inline=False)

        if roles_manquants:
            embed.add_field(name="Rôles disponibles", value="\n".join(roles_manquants), inline=False)

        # XP actuel
        from config import charger_data, get_joueur
        data   = charger_data()
        joueur = get_joueur(data, interaction.guild_id, cible.id)
        embed.set_footer(text=f"XP actuel : {joueur['xp']} XP")

        await interaction.response.send_message(embed=embed)

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("Tu n'as pas la permission !", ephemeral=True)
        else:
            await interaction.response.send_message(f"Erreur : {error}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Shop(bot))