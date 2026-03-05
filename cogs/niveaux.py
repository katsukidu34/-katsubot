"""
cogs/niveaux.py — Système de niveaux & XP
"""

import time
import random
import discord
from discord import app_commands
from discord.ext import commands

from config import charger_data, sauvegarder_data, get_joueur, get_config, xp_pour_niveau
from utils import est_spam


class Niveaux(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.vocal_sessions = {}

    def get_canal(self, guild, cle):
        """Retourne le salon de logs pour une clé donnée."""
        cfg      = get_config(guild.id)
        salon_id = cfg.get(cle)
        if not salon_id:
            return None
        return guild.get_channel(int(salon_id))

    # ── Listener vocal ─────────────────────────

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot:
            return

        canal = self.get_canal(member.guild, "logs_vocal")

        if before.channel is None and after.channel is not None:
            self.vocal_sessions[member.id] = time.time()
            if canal:
                embed = discord.Embed(
                    description=f"{member.mention} vient de rejoindre {after.channel.mention} 🎤",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )
                embed.set_author(name=f"Connexion — {member.display_name}", icon_url=member.display_avatar.url)
                embed.set_footer(text=member.guild.name, icon_url=member.guild.icon.url if member.guild.icon else None)
                await canal.send(embed=embed)

        elif before.channel is not None and after.channel is None:
            duree, heures, minutes, secondes = 0, 0, 0, 0
            if member.id in self.vocal_sessions:
                duree    = int(time.time() - self.vocal_sessions.pop(member.id))
                heures   = duree // 3600
                minutes  = (duree % 3600) // 60
                secondes = duree % 60
                data     = charger_data()
                joueur   = get_joueur(data, member.guild.id, member.id)
                joueur["temps_vocal"]         = joueur.get("temps_vocal", 0) + duree
                joueur["temps_vocal_semaine"] = joueur.get("temps_vocal_semaine", 0) + duree
                joueur["temps_vocal_mois"]    = joueur.get("temps_vocal_mois", 0) + duree
                if duree > joueur.get("temps_vocal_record", 0):
                    joueur["temps_vocal_record"] = duree
                sauvegarder_data(data)
            if canal:
                embed = discord.Embed(
                    description=f"{member.mention} vient de quitter {before.channel.mention} 🔊",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow()
                )
                embed.set_author(name=f"Déconnexion — {member.display_name}", icon_url=member.display_avatar.url)
                if duree > 0:
                    embed.add_field(name="⏱️ Temps passé", value=f"{heures}h {minutes}min {secondes}s", inline=True)
                embed.set_footer(text=member.guild.name, icon_url=member.guild.icon.url if member.guild.icon else None)
                await canal.send(embed=embed)

        elif before.channel is not None and after.channel is not None and before.channel != after.channel:
            if canal:
                embed = discord.Embed(
                    description=f"{member.mention} a changé de salon : {before.channel.mention} → {after.channel.mention}",
                    color=discord.Color.yellow(),
                    timestamp=discord.utils.utcnow()
                )
                embed.set_author(name=f"Changement — {member.display_name}", icon_url=member.display_avatar.url)
                embed.set_footer(text=member.guild.name, icon_url=member.guild.icon.url if member.guild.icon else None)
                await canal.send(embed=embed)

    # ── Logs messages ──────────────────────────

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or not before.guild:
            return
        if before.content == after.content:
            return
        canal = self.get_canal(before.guild, "logs_messages")
        if not canal:
            return
        embed = discord.Embed(
            description=f"{before.author.mention} a édité un message dans {before.channel.mention}",
            color=discord.Color.yellow(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=f"Message édité — {before.author.display_name}", icon_url=before.author.display_avatar.url)
        embed.add_field(name="Avant", value=before.content[:1024] or "*vide*", inline=False)
        embed.add_field(name="Après", value=after.content[:1024]  or "*vide*", inline=False)
        embed.set_footer(text=before.guild.name, icon_url=before.guild.icon.url if before.guild.icon else None)
        await canal.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        self.bot.snipe_cache[message.channel.id] = {
            "contenu": message.content,
            "auteur":  str(message.author),
            "avatar":  message.author.display_avatar.url,
            "date":    message.created_at
        }
        canal = self.get_canal(message.guild, "logs_messages")
        if not canal:
            return
        embed = discord.Embed(
            description=f"{message.author.mention} a eu un message supprimé dans {message.channel.mention}",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=f"Message supprimé — {message.author.display_name}", icon_url=message.author.display_avatar.url)
        embed.add_field(name="Contenu", value=message.content[:1024] or "*vide*", inline=False)
        embed.set_footer(text=message.guild.name, icon_url=message.guild.icon.url if message.guild.icon else None)
        await canal.send(embed=embed)

    # ── Logs membres ───────────────────────────

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        canal = self.get_canal(member.guild, "logs_membres")
        if not canal:
            return
        embed = discord.Embed(
            description=f"{member.mention} a quitté le serveur 👋",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=f"Départ — {member.display_name}", icon_url=member.display_avatar.url)
        embed.add_field(name="📅 Compte créé le", value=member.created_at.strftime("%d/%m/%Y"), inline=True)
        embed.add_field(name="🏷️ ID",             value=str(member.id),                         inline=True)
        embed.set_footer(text=member.guild.name, icon_url=member.guild.icon.url if member.guild.icon else None)
        await canal.send(embed=embed)

    # ── Logs rôles ─────────────────────────────

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.roles == after.roles:
            return
        canal = self.get_canal(after.guild, "logs_roles")
        if not canal:
            return
        roles_ajoutes = [r for r in after.roles  if r not in before.roles]
        roles_retires = [r for r in before.roles if r not in after.roles]
        if roles_ajoutes:
            embed = discord.Embed(
                description=f"{after.mention} a reçu un rôle 🎭",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            embed.set_author(name=f"Rôle ajouté — {after.display_name}", icon_url=after.display_avatar.url)
            embed.add_field(name="Rôle", value=" ".join(r.mention for r in roles_ajoutes), inline=True)
            embed.set_footer(text=after.guild.name, icon_url=after.guild.icon.url if after.guild.icon else None)
            await canal.send(embed=embed)
        if roles_retires:
            embed = discord.Embed(
                description=f"{after.mention} a perdu un rôle 🎭",
                color=discord.Color.orange(),
                timestamp=discord.utils.utcnow()
            )
            embed.set_author(name=f"Rôle retiré — {after.display_name}", icon_url=after.display_avatar.url)
            embed.add_field(name="Rôle", value=" ".join(r.mention for r in roles_retires), inline=True)
            embed.set_footer(text=after.guild.name, icon_url=after.guild.icon.url if after.guild.icon else None)
            await canal.send(embed=embed)

    # ── Listener messages ──────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        cfg = get_config(message.guild.id)
        if est_spam(message.author.id, cfg["seuil_anti_spam"]):
            await message.delete()
            try:
                await message.author.send("Tu envoies des messages trop rapidement ! Ralentis.")
            except discord.Forbidden:
                pass
            return
        data   = charger_data()
        joueur = get_joueur(data, message.guild.id, message.author.id)
        now    = time.time()
        if now - joueur["derniere_xp"] >= 30:
            joueur["xp"] += cfg["xp_par_message"]
            joueur["derniere_xp"] = now
            while joueur["xp"] >= xp_pour_niveau(joueur["niveau"]):
                joueur["xp"] -= xp_pour_niveau(joueur["niveau"])
                joueur["niveau"] += 1
                nv = joueur["niveau"]
                await message.channel.send(
                    f"🎉 Félicitations {message.author.mention} ! Tu passes au **niveau {nv}** !"
                )
                if str(nv) in cfg["roles_niveaux"]:
                    role = discord.utils.get(message.guild.roles, name=cfg["roles_niveaux"][str(nv)])
                    if role:
                        await message.author.add_roles(role)
                        await message.channel.send(f"🎭 Tu as obtenu le rôle **{role.name}** !")
            sauvegarder_data(data)


async def setup(bot: commands.Bot):
    await bot.add_cog(Niveaux(bot))
    # ── Listener bienvenue ─────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        cfg = get_config(member.guild.id)
        if not cfg["salon_bienvenue"]:
            return
        canal = member.guild.get_channel(int(cfg["salon_bienvenue"]))
        if not canal:
            return
        couleurs = [discord.Color.green(), discord.Color.blurple(), discord.Color.gold(), discord.Color.purple()]
        embed = discord.Embed(
            title="👋 Nouveau membre !",
            description=f"Bienvenue {member.mention} sur **{member.guild.name}** !\n\n"
                        f"Tu es le **{member.guild.member_count}e membre** du serveur.\n"
                        f"N'oublie pas de lire les règles et tape `/help` pour voir les commandes !",
            color=random.choice(couleurs)
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Compte créé le {member.created_at.strftime('%d/%m/%Y')}")
        embed.add_field(name="📅 Arrivée", value=member.joined_at.strftime("%d/%m/%Y à %H:%M"), inline=True)
        embed.add_field(name="🏷️ ID",     value=str(member.id),                                 inline=True)
        await canal.send(content=f"Bienvenue {member.mention} !", embed=embed)

        # Log arrivée
        canal_log = self.get_canal(member.guild, "logs_membres")
        if canal_log:
            embed_log = discord.Embed(
                description=f"{member.mention} a rejoint le serveur 🎉",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            embed_log.set_author(name=f"Arrivée — {member.display_name}", icon_url=member.display_avatar.url)
            embed_log.add_field(name="📅 Compte créé le", value=member.created_at.strftime("%d/%m/%Y"), inline=True)
            embed_log.add_field(name="🏷️ ID",             value=str(member.id),                         inline=True)
            embed_log.set_footer(text=member.guild.name, icon_url=member.guild.icon.url if member.guild.icon else None)
            await canal_log.send(embed=embed_log)

    # ── /niveau ───────────────────────────────

    @app_commands.command(name="niveau", description="Affiche ton niveau et ton XP")
    @app_commands.describe(membre="Le membre à consulter (optionnel, toi par défaut)")
    async def niveau(self, interaction: discord.Interaction, membre: discord.Member = None):
        cible  = membre or interaction.user
        data   = charger_data()
        joueur = get_joueur(data, interaction.guild_id, cible.id)
        xp, niv     = joueur["xp"], joueur["niveau"]
        xp_requis   = xp_pour_niveau(niv)
        remplissage = int((xp / xp_requis) * 20)
        barre       = "█" * remplissage + "░" * (20 - remplissage)
        embed = discord.Embed(title=f"Profil de {cible.display_name}", color=discord.Color.blurple())
        embed.set_thumbnail(url=cible.display_avatar.url)
        embed.add_field(name="Niveau",      value=str(niv),              inline=True)
        embed.add_field(name="XP",          value=f"{xp} / {xp_requis}", inline=True)
        embed.add_field(name="Progression", value=f"`{barre}`",           inline=False)
        await interaction.response.send_message(embed=embed)

    # ── /top ───────────────────────────────────

    @app_commands.command(name="top", description="Classement des membres les plus actifs")
    async def top(self, interaction: discord.Interaction):
        data = charger_data()
        gid  = str(interaction.guild_id)
        if gid not in data or not data[gid]:
            await interaction.response.send_message("Pas encore de données pour ce serveur !")
            return
        classement = sorted(
            data[gid].items(),
            key=lambda x: (x[1]["niveau"], x[1]["xp"]),
            reverse=True
        )[:10]
        embed = discord.Embed(title="🏆 Classement des membres", color=discord.Color.gold())
        desc  = ""
        for i, (uid, stats) in enumerate(classement, 1):
            try:
                user = await self.bot.fetch_user(int(uid))
                nom  = user.display_name
            except Exception:
                nom = "Utilisateur inconnu"
            desc += f"**{i}.** {nom} — Niveau {stats['niveau']} ({stats['xp']} XP)\n"
        embed.description = desc
        await interaction.response.send_message(embed=embed)

    # ── /leaderboard_vocal ─────────────────────

    @app_commands.command(name="leaderboard_vocal", description="Classement du temps passé en vocal")
    async def leaderboard_vocal(self, interaction: discord.Interaction):
        data = charger_data()
        gid  = str(interaction.guild_id)
        if gid not in data or not data[gid]:
            await interaction.response.send_message("Pas encore de données pour ce serveur !")
            return
        classement = [
            (uid, stats) for uid, stats in data[gid].items()
            if stats.get("temps_vocal", 0) > 0
        ]
        classement = sorted(classement, key=lambda x: x[1].get("temps_vocal", 0), reverse=True)[:10]
        if not classement:
            await interaction.response.send_message("Personne n'a encore passé de temps en vocal !")
            return
        embed = discord.Embed(title="🎤 Classement vocal", color=discord.Color.purple())
        desc  = ""
        for i, (uid, stats) in enumerate(classement, 1):
            try:
                user = await self.bot.fetch_user(int(uid))
                nom  = user.display_name
            except Exception:
                nom = "Utilisateur inconnu"
            secondes = stats.get("temps_vocal", 0)
            heures   = secondes // 3600
            minutes  = (secondes % 3600) // 60
            desc += f"**{i}.** {nom} — {heures}h {minutes}min\n"
        embed.description = desc
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Niveaux(bot))