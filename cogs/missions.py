"""
cogs/missions.py — Système de missions journalières
=====================================================
Commandes : /missions, /missions_claim
Reset automatique à minuit via task.
Notification quand une mission est complétée.
"""

import time
import random
import discord
from datetime import date, time as dtime
from discord import app_commands
from discord.ext import commands
from discord.ext import tasks

from config import charger_data, sauvegarder_data, get_joueur


# ══════════════════════════════════════════════
# MISSIONS DISPONIBLES
# ══════════════════════════════════════════════

MISSIONS_POSSIBLES = [
    {"id": "messages_10",  "nom": "Bavard",         "description": "Envoie 10 messages",   "type": "messages",  "objectif": 10,   "recompense": 50},
    {"id": "messages_25",  "nom": "Grand bavard",   "description": "Envoie 25 messages",   "type": "messages",  "objectif": 25,   "recompense": 100},
    {"id": "messages_50",  "nom": "Inépuisable",    "description": "Envoie 50 messages",   "type": "messages",  "objectif": 50,   "recompense": 200},
    {"id": "vocal_5",      "nom": "Sociable",       "description": "Passe 5 min en vocal", "type": "vocal",     "objectif": 300,  "recompense": 75},
    {"id": "vocal_15",     "nom": "Communicatif",   "description": "Passe 15 min en vocal","type": "vocal",     "objectif": 900,  "recompense": 150},
    {"id": "vocal_30",     "nom": "Vocal addict",   "description": "Passe 30 min en vocal","type": "vocal",     "objectif": 1800, "recompense": 300},
    {"id": "reactions_5",  "nom": "Expressif",      "description": "Ajoute 5 réactions",   "type": "reactions", "objectif": 5,    "recompense": 40},
    {"id": "reactions_10", "nom": "Très expressif", "description": "Ajoute 10 réactions",  "type": "reactions", "objectif": 10,   "recompense": 80},
]


def get_missions_joueur(data, guild_id, user_id):
    joueur = get_joueur(data, guild_id, user_id)
    today  = str(date.today())
    if joueur.get("missions_date") != today:
        missions_choisies            = random.sample(MISSIONS_POSSIBLES, 3)
        joueur["missions_date"]      = today
        joueur["missions"]           = [m["id"] for m in missions_choisies]
        joueur["missions_progres"]   = {m["id"]: 0 for m in missions_choisies}
        joueur["missions_claimed"]   = []
        joueur["missions_notifiees"] = []
    return joueur


def progresser_mission(data, guild_id, user_id, type_mission, valeur=1):
    """Incrémente la progression. Retourne les missions nouvellement complétées."""
    joueur    = get_missions_joueur(data, guild_id, user_id)
    completees = []

    for mission_id in joueur.get("missions", []):
        mission = next((m for m in MISSIONS_POSSIBLES if m["id"] == mission_id), None)
        if not mission or mission["type"] != type_mission:
            continue
        if mission_id in joueur.get("missions_claimed", []):
            continue
        if mission_id in joueur.get("missions_notifiees", []):
            continue

        actuel  = joueur["missions_progres"].get(mission_id, 0)
        nouveau = min(actuel + valeur, mission["objectif"])
        joueur["missions_progres"][mission_id] = nouveau

        if nouveau >= mission["objectif"] and actuel < mission["objectif"]:
            completees.append(mission)
            joueur["missions_notifiees"].append(mission_id)

    return completees


# ══════════════════════════════════════════════
# COG
# ══════════════════════════════════════════════

class Missions(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._vocal_join: dict[int, float] = {}  # {user_id: timestamp d'entrée en vocal}
        self.reset_missions.start()

    def cog_unload(self):
        self.reset_missions.cancel()

    # ── Task reset à minuit ────────────────────

    @tasks.loop(time=dtime(hour=0, minute=0, second=0))
    async def reset_missions(self):
        """Reset les missions de tout le monde à minuit."""
        data    = charger_data()
        today   = str(date.today())
        modifie = False

        for guild_id in data:
            for user_id in data[guild_id]:
                joueur = data[guild_id][user_id]
                if joueur.get("missions_date") != today:
                    missions_choisies            = random.sample(MISSIONS_POSSIBLES, 3)
                    joueur["missions_date"]      = today
                    joueur["missions"]           = [m["id"] for m in missions_choisies]
                    joueur["missions_progres"]   = {m["id"]: 0 for m in missions_choisies}
                    joueur["missions_claimed"]   = []
                    joueur["missions_notifiees"] = []
                    modifie = True

        if modifie:
            sauvegarder_data(data)

        for guild in self.bot.guilds:
            from config import get_config
            cfg      = get_config(guild.id)
            salon_id = cfg.get("salon_bienvenue") or cfg.get("salon_logs")
            if not salon_id:
                continue
            canal = guild.get_channel(int(salon_id))
            if not canal:
                continue
            embed = discord.Embed(
                title="🌅 Nouvelles missions disponibles !",
                description="Les missions journalières ont été renouvelées !\nTape `/missions` pour voir tes nouvelles missions du jour.",
                color=discord.Color.blurple()
            )
            embed.set_footer(text="Les missions se renouvellent chaque jour à minuit !")
            await canal.send(embed=embed)

    @reset_missions.before_loop
    async def before_reset(self):
        await self.bot.wait_until_ready()

    # ── Listeners de progression ───────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        data       = charger_data()
        completees = progresser_mission(data, message.guild.id, message.author.id, "messages")
        sauvegarder_data(data)

        for mission in completees:
            embed = discord.Embed(
                title="🎯 Mission complétée !",
                description=f"Tu as complété la mission **{mission['nom']}** !\nTape `/missions_claim` pour récupérer **+{mission['recompense']} XP** !",
                color=discord.Color.green()
            )
            await message.channel.send(content=message.author.mention, embed=embed, delete_after=10)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        if user.bot or not reaction.message.guild:
            return
        data       = charger_data()
        completees = progresser_mission(data, reaction.message.guild.id, user.id, "reactions")
        sauvegarder_data(data)

        for mission in completees:
            embed = discord.Embed(
                title="🎯 Mission complétée !",
                description=f"Tu as complété la mission **{mission['nom']}** !\nTape `/missions_claim` pour récupérer **+{mission['recompense']} XP** !",
                color=discord.Color.green()
            )
            try:
                await user.send(embed=embed)
            except discord.Forbidden:
                pass

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Track le temps passé en vocal pour les missions."""
        if member.bot:
            return

        # Membre rejoint un salon vocal
        if before.channel is None and after.channel is not None:
            self._vocal_join[member.id] = time.time()

        # Membre quitte un salon vocal
        elif before.channel is not None and after.channel is None:
            join_time = self._vocal_join.pop(member.id, None)
            if join_time is None:
                return

            duree = int(time.time() - join_time)  # secondes passées en vocal

            data       = charger_data()
            completees = progresser_mission(data, member.guild.id, member.id, "vocal", duree)
            sauvegarder_data(data)

            for mission in completees:
                embed = discord.Embed(
                    title="🎯 Mission complétée !",
                    description=f"Tu as complété la mission **{mission['nom']}** !\nTape `/missions_claim` pour récupérer **+{mission['recompense']} XP** !",
                    color=discord.Color.green()
                )
                try:
                    await member.send(embed=embed)
                except discord.Forbidden:
                    pass

    # ── /missions ──────────────────────────────

    @app_commands.command(name="missions", description="Affiche tes missions journalières")
    async def missions(self, interaction: discord.Interaction):
        data   = charger_data()
        joueur = get_missions_joueur(data, interaction.guild_id, interaction.user.id)
        sauvegarder_data(data)

        embed = discord.Embed(
            title="📋 Missions du jour",
            description="Complète tes missions pour gagner de l'XP bonus !",
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)

        for mission_id in joueur["missions"]:
            mission = next((m for m in MISSIONS_POSSIBLES if m["id"] == mission_id), None)
            if not mission:
                continue

            progres  = joueur["missions_progres"].get(mission_id, 0)
            objectif = mission["objectif"]
            claimed  = mission_id in joueur.get("missions_claimed", [])

            pct         = min(progres / objectif, 1.0)
            remplissage = int(pct * 10)
            barre       = "█" * remplissage + "░" * (10 - remplissage)

            if claimed:
                statut = "✅ Réclamée"
            elif progres >= objectif:
                statut = "🎁 Prête à réclamer !"
            else:
                statut = f"`{barre}` {progres}/{objectif}"

            embed.add_field(
                name=f"{'✅' if claimed else '🎯'} {mission['nom']} — {mission['recompense']} XP",
                value=f"{mission['description']}\n{statut}",
                inline=False
            )

        embed.set_footer(text="Les missions se renouvellent chaque jour à minuit !")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /missions_claim ────────────────────────

    @app_commands.command(name="missions_claim", description="Réclame les XP de tes missions complétées")
    async def missions_claim(self, interaction: discord.Interaction):
        data   = charger_data()
        joueur = get_missions_joueur(data, interaction.guild_id, interaction.user.id)

        xp_total  = 0
        reclamees = []

        for mission_id in joueur["missions"]:
            mission = next((m for m in MISSIONS_POSSIBLES if m["id"] == mission_id), None)
            if not mission:
                continue
            if mission_id in joueur.get("missions_claimed", []):
                continue
            if joueur["missions_progres"].get(mission_id, 0) >= mission["objectif"]:
                joueur["missions_claimed"].append(mission_id)
                joueur["xp"]  += mission["recompense"]
                xp_total      += mission["recompense"]
                reclamees.append(f"✅ **{mission['nom']}** — +{mission['recompense']} XP")

        sauvegarder_data(data)

        if not reclamees:
            await interaction.response.send_message(
                "Aucune mission complétée à réclamer pour l'instant !", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🎁 Missions réclamées !",
            description="\n".join(reclamees),
            color=discord.Color.green()
        )
        embed.add_field(name="💰 Total gagné", value=f"**+{xp_total} XP**", inline=False)
        embed.set_footer(text="Continue comme ça !")
        await interaction.response.send_message(embed=embed)

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await interaction.response.send_message(f"Erreur : {error}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Missions(bot))