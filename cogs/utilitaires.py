"""
cogs/utilitaires.py — Commandes utilitaires
=============================================
Commandes : /profil, /daily, /serveur, /say, /snipe
"""

import time
import discord
from discord import app_commands
from discord.ext import commands

from config import (
    charger_data, sauvegarder_data,
    get_joueur, get_config, xp_pour_niveau
)

DAILY_XP = 100


class Utilitaires(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

   

    # ── /profil ────────────────────────────────

    @app_commands.command(name="profil", description="Affiche la carte de profil d'un membre")
    @app_commands.describe(membre="Le membre à consulter (toi par défaut)")
    async def profil(self, interaction: discord.Interaction, membre: discord.Member = None):
        cible  = membre or interaction.user
        data   = charger_data()
        joueur = get_joueur(data, interaction.guild_id, cible.id)
        cfg    = get_config(interaction.guild_id)

        niv       = joueur["niveau"]
        xp        = joueur["xp"]
        xp_requis = xp_pour_niveau(niv)
        warnings  = joueur["warnings"]

        remplissage = int((xp / xp_requis) * 20)
        barre = "█" * remplissage + "░" * (20 - remplissage)

        roles_niveaux = cfg["roles_niveaux"]
        role_actuel   = "Aucun"
        for n in sorted(roles_niveaux.keys(), key=int, reverse=True):
            if niv >= int(n):
                role_actuel = roles_niveaux[n]
                break

        prochain_role     = "Aucun"
        prochain_role_niv = None
        for n in sorted(roles_niveaux.keys(), key=int):
            if int(n) > niv:
                prochain_role     = roles_niveaux[n]
                prochain_role_niv = int(n)
                break

        if niv >= 50:   couleur = discord.Color.gold()
        elif niv >= 20: couleur = discord.Color.purple()
        elif niv >= 10: couleur = discord.Color.blurple()
        elif niv >= 5:  couleur = discord.Color.green()
        else:           couleur = discord.Color.greyple()

        embed = discord.Embed(title=f"Profil de {cible.display_name}", color=couleur)
        embed.set_thumbnail(url=cible.display_avatar.url)
        embed.add_field(name="🏅 Niveau",         value=str(niv),              inline=True)
        embed.add_field(name="⭐ XP",             value=f"{xp} / {xp_requis}", inline=True)
        embed.add_field(name="⚠️ Avertissements", value=str(warnings),         inline=True)
        embed.add_field(name="📊 Progression",    value=f"`{barre}` {int((xp/xp_requis)*100)}%", inline=False)
        embed.add_field(name="🎭 Rôle actuel",    value=role_actuel,           inline=True)

        if prochain_role_niv:
            niveaux_restants = prochain_role_niv - niv
            embed.add_field(name="🎯 Prochain rôle", value=f"{prochain_role} (dans {niveaux_restants} niveau(x))", inline=True)

        if cible.joined_at:
            embed.add_field(name="📅 Membre depuis", value=cible.joined_at.strftime("%d/%m/%Y"), inline=True)

        embed.set_footer(text=f"ID : {cible.id}")
        await interaction.response.send_message(embed=embed)

    # ── /daily ─────────────────────────────────

    @app_commands.command(name="daily", description="Récupère ta récompense XP quotidienne")
    async def daily(self, interaction: discord.Interaction):
        data   = charger_data()
        joueur = get_joueur(data, interaction.guild_id, interaction.user.id)
        now    = time.time()

        derniere_recup = joueur.get("derniere_daily", 0)
        temps_restant  = (derniere_recup + 86400) - now

        if temps_restant > 0:
            heures  = int(temps_restant // 3600)
            minutes = int((temps_restant % 3600) // 60)
            embed = discord.Embed(
                title="⏳ Daily déjà récupéré !",
                description=f"Reviens dans **{heures}h {minutes}min**.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        joueur["xp"]           += DAILY_XP
        joueur["derniere_daily"] = now
        cfg = get_config(interaction.guild_id)
        messages_niveau = []

        while joueur["xp"] >= xp_pour_niveau(joueur["niveau"]):
            joueur["xp"] -= xp_pour_niveau(joueur["niveau"])
            joueur["niveau"] += 1
            nv = joueur["niveau"]
            messages_niveau.append(f"🎉 Tu passes au **niveau {nv}** !")
            if str(nv) in cfg["roles_niveaux"]:
                role = discord.utils.get(interaction.guild.roles, name=cfg["roles_niveaux"][str(nv)])
                if role:
                    await interaction.user.add_roles(role)
                    messages_niveau.append(f"🎭 Tu obtiens le rôle **{role.name}** !")

        sauvegarder_data(data)

        embed = discord.Embed(
            title="🎁 Récompense quotidienne !",
            description=f"Tu as reçu **{DAILY_XP} XP** !\n" + "\n".join(messages_niveau),
            color=discord.Color.green()
        )
        embed.add_field(name="⭐ XP total", value=f"{joueur['xp']} / {xp_pour_niveau(joueur['niveau'])}", inline=True)
        embed.add_field(name="🏅 Niveau",   value=str(joueur["niveau"]),                                  inline=True)
        embed.set_footer(text="Reviens dans 24h pour ta prochaine récompense !")
        await interaction.response.send_message(embed=embed)

    # ── /serveur ───────────────────────────────

    @app_commands.command(name="serveur", description="Affiche les statistiques du serveur")
    async def serveur(self, interaction: discord.Interaction):
        guild    = interaction.guild
        bots     = sum(1 for m in guild.members if m.bot)
        en_ligne = sum(1 for m in guild.members if m.status != discord.Status.offline and not m.bot)

        niveaux_verif = {
            discord.VerificationLevel.none:    "Aucun",
            discord.VerificationLevel.low:     "Faible",
            discord.VerificationLevel.medium:  "Moyen",
            discord.VerificationLevel.high:    "Élevé",
            discord.VerificationLevel.highest: "Maximum",
        }

        embed = discord.Embed(title=f"📊 Statistiques de {guild.name}", color=discord.Color.blurple())
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        embed.add_field(name="👑 Propriétaire",  value=guild.owner.mention,                              inline=True)
        embed.add_field(name="📅 Créé le",       value=guild.created_at.strftime("%d/%m/%Y"),            inline=True)
        embed.add_field(name="👥 Membres",       value=str(guild.member_count),                          inline=True)
        embed.add_field(name="🟢 En ligne",      value=str(en_ligne),                                    inline=True)
        embed.add_field(name="🤖 Bots",          value=str(bots),                                        inline=True)
        embed.add_field(name="💬 Salons texte",  value=str(len(guild.text_channels)),                    inline=True)
        embed.add_field(name="🔊 Salons vocaux", value=str(len(guild.voice_channels)),                   inline=True)
        embed.add_field(name="🎭 Rôles",         value=str(len(guild.roles) - 1),                        inline=True)
        embed.add_field(name="😀 Emojis",        value=str(len(guild.emojis)),                           inline=True)
        embed.set_footer(text=f"ID : {guild.id}")
        await interaction.response.send_message(embed=embed)
    # ── /mute ──────────────────────────────────

    @app_commands.command(name="mute", description="Rend muet un membre")
    @app_commands.describe(membre="Le membre à muter", duree="Durée en minutes", raison="La raison")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def mute(self, interaction: discord.Interaction, membre: discord.Member, duree: int = 10, raison: str = "Aucune raison donnée"):
        import datetime
        until = discord.utils.utcnow() + datetime.timedelta(minutes=duree)
        await membre.timeout(until, reason=raison)
        embed = discord.Embed(title="🔇 Membre muté", color=discord.Color.orange())
        embed.add_field(name="Membre", value=membre.mention,   inline=True)
        embed.add_field(name="Durée",  value=f"{duree} min",   inline=True)
        embed.add_field(name="Raison", value=raison,           inline=False)
        await interaction.response.send_message(embed=embed)

    # ── /unmute ────────────────────────────────

    @app_commands.command(name="unmute", description="Retire le mute d'un membre")
    @app_commands.describe(membre="Le membre à démuter")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def unmute(self, interaction: discord.Interaction, membre: discord.Member):
        await membre.timeout(None)
        await interaction.response.send_message(f"🔊 {membre.mention} n'est plus muté !")

    # ── /rapport ───────────────────────────────

    @app_commands.command(name="rapport", description="Signale un membre aux modérateurs")
    @app_commands.describe(membre="Le membre à signaler", raison="La raison du signalement")
    async def rapport(self, interaction: discord.Interaction, membre: discord.Member, raison: str):
        cfg = get_config(interaction.guild_id)
        if cfg["salon_logs"]:
            canal = interaction.guild.get_channel(int(cfg["salon_logs"]))
            if canal:
                embed = discord.Embed(title="🚨 Signalement", color=discord.Color.red())
                embed.add_field(name="Membre signalé", value=membre.mention,           inline=True)
                embed.add_field(name="Signalé par",    value=interaction.user.mention, inline=True)
                embed.add_field(name="Raison",         value=raison,                   inline=False)
                embed.set_footer(text=f"ID du membre : {membre.id}")
                await canal.send(embed=embed)
                await interaction.response.send_message("✅ Signalement envoyé aux modérateurs !", ephemeral=True)
                return
        await interaction.response.send_message("⚠️ Aucun salon de logs configuré !", ephemeral=True)
        # ── /stats_bot ─────────────────────────────

    @app_commands.command(name="stats_bot", description="Affiche les statistiques du bot")
    async def stats_bot(self, interaction: discord.Interaction):
        import datetime
        import platform

        embed = discord.Embed(title="🤖 Statistiques du bot", color=discord.Color.blurple())

        # Infos générales
        embed.add_field(name="📛 Nom",          value=str(self.bot.user),                        inline=True)
        embed.add_field(name="🆔 ID",           value=str(self.bot.user.id),                     inline=True)
        embed.add_field(name="🏓 Latence",      value=f"{round(self.bot.latency * 1000)}ms",     inline=True)

        # Serveurs et membres
        total_membres = sum(g.member_count for g in self.bot.guilds)
        embed.add_field(name="🌍 Serveurs",     value=str(len(self.bot.guilds)),                 inline=True)
        embed.add_field(name="👥 Membres",      value=str(total_membres),                        inline=True)
        embed.add_field(name="💬 Commandes",    value=str(len(self.bot.tree.get_commands())),    inline=True)

        

        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text="Bot développé avec discord.py")
        await interaction.response.send_message(embed=embed)

    # ── /announce ──────────────────────────────

    @app_commands.command(name="announce", description="Fait une annonce stylée dans un salon")
    @app_commands.describe(
        titre="Le titre de l'annonce",
        message="Le contenu de l'annonce",
        salon="Le salon cible (optionnel, salon actuel par défaut)",
        couleur="La couleur de l'embed : rouge, vert, bleu, or, violet"
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def announce(self, interaction: discord.Interaction, titre: str, message: str, salon: discord.TextChannel = None, couleur: str = "bleu"):
        cible = salon or interaction.channel

        couleurs = {
            "rouge":  discord.Color.red(),
            "vert":   discord.Color.green(),
            "bleu":   discord.Color.blurple(),
            "or":     discord.Color.gold(),
            "violet": discord.Color.purple(),
        }
        color = couleurs.get(couleur.lower(), discord.Color.blurple())

        embed = discord.Embed(title=f"📢 {titre}", description=message, color=color)
        embed.set_footer(text=f"Annonce par {interaction.user.display_name}")

        await cible.send(embed=embed)
        await interaction.response.send_message(f"✅ Annonce envoyée dans {cible.mention} !", ephemeral=True)

 

    # ── Gestion des erreurs ────────────────────

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await interaction.response.send_message(f"Erreur : {error}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Utilitaires(bot))