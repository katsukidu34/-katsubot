"""
cogs/missions.py — Système de missions journalières
=====================================================
Commandes : /missions, /reward_claim
Reset automatique à minuit via task.
Notification quand une mission est complétée.
Accès direct MongoDB (pas de charger_data global).
"""

import time
import random
import discord

from datetime        import date, time as dtime
from discord         import app_commands
from discord.ext     import commands, tasks
from config          import col_data, get_config


# ══════════════════════════════════════════════
# MISSIONS DISPONIBLES
# ══════════════════════════════════════════════

MISSIONS = [
    {"id": "messages_10",  "nom": "Bavard",          "description": "Envoie 10 messages",    "type": "messages",  "objectif": 10,   "recompense": 50},
    {"id": "messages_25",  "nom": "Grand bavard",    "description": "Envoie 25 messages",    "type": "messages",  "objectif": 25,   "recompense": 100},
    {"id": "messages_50",  "nom": "Inépuisable",     "description": "Envoie 50 messages",    "type": "messages",  "objectif": 50,   "recompense": 200},
    {"id": "vocal_5",      "nom": "Sociable",        "description": "Passe 5 min en vocal",  "type": "vocal",     "objectif": 300,  "recompense": 75},
    {"id": "vocal_15",     "nom": "Communicatif",    "description": "Passe 15 min en vocal", "type": "vocal",     "objectif": 900,  "recompense": 150},
    {"id": "vocal_30",     "nom": "Vocal addict",    "description": "Passe 30 min en vocal", "type": "vocal",     "objectif": 1800, "recompense": 300},
    {"id": "reactions_5",  "nom": "Expressif",       "description": "Ajoute 5 réactions",    "type": "reactions", "objectif": 5,    "recompense": 40},
    {"id": "reactions_10", "nom": "Très expressif",  "description": "Ajoute 10 réactions",   "type": "reactions", "objectif": 10,   "recompense": 80},
]

MISSIONS_INDEX = {m["id"]: m for m in MISSIONS}


# ══════════════════════════════════════════════
# HELPERS MONGODB DIRECTS
# ══════════════════════════════════════════════

def _get_doc(guild_id: int, user_id: int) -> dict:
    """Récupère le document d'un joueur depuis MongoDB."""
    gid, uid = str(guild_id), str(user_id)
    return col_data.find_one({"guild_id": gid, "user_id": uid}, {"_id": 0}) or {}


def _save_missions(guild_id: int, user_id: int, fields: dict):
    """Met à jour uniquement les champs missions en MongoDB."""
    gid, uid = str(guild_id), str(user_id)
    col_data.update_one(
        {"guild_id": gid, "user_id": uid},
        {"$set": {**fields, "guild_id": gid, "user_id": uid}},
        upsert=True
    )


def _ensure_missions(guild_id: int, user_id: int) -> dict:
    """
    Vérifie si les missions du joueur sont à jour.
    Si non (nouveau jour), génère 3 nouvelles missions.
    Retourne le doc mis à jour.
    """
    doc   = _get_doc(guild_id, user_id)
    today = str(date.today())

    if doc.get("missions_date") != today:
        choisies = random.sample(MISSIONS, 3)
        fields = {
            "missions_date":      today,
            "missions":           [m["id"] for m in choisies],
            "missions_progres":   {m["id"]: 0 for m in choisies},
            "missions_claimed":   [],
            "missions_notifiees": [],
        }
        _save_missions(guild_id, user_id, fields)
        doc.update(fields)

    return doc


def _progresser(guild_id: int, user_id: int, type_mission: str, valeur: int = 1) -> list[dict]:
    """
    Incrémente la progression d'un type de mission.
    Retourne la liste des missions nouvellement complétées.
    """
    doc = _ensure_missions(guild_id, user_id)

    missions_ids    = doc.get("missions", [])
    progres         = doc.get("missions_progres", {})
    claimed         = doc.get("missions_claimed", [])
    notifiees       = doc.get("missions_notifiees", [])
    completees      = []
    progres_updated = {}

    for mid in missions_ids:
        m = MISSIONS_INDEX.get(mid)
        if not m or m["type"] != type_mission:
            continue
        if mid in claimed or mid in notifiees:
            continue

        ancien  = progres.get(mid, 0)
        nouveau = min(ancien + valeur, m["objectif"])
        progres_updated[f"missions_progres.{mid}"] = nouveau

        if nouveau >= m["objectif"] and ancien < m["objectif"]:
            completees.append(m)
            notifiees.append(mid)

    if progres_updated:
        gid, uid = str(guild_id), str(user_id)
        update = {**progres_updated}
        if completees:
            update["missions_notifiees"] = notifiees
        col_data.update_one(
            {"guild_id": gid, "user_id": uid},
            {"$set": update},
            upsert=True
        )

    return completees


def _embed_completee(mission: dict, user: discord.User | discord.Member) -> discord.Embed:
    embed = discord.Embed(
        title="🎯 Mission complétée !",
        description=(
            f"**{user.display_name}** a complété **{mission['nom']}** !\n"
            f"Tape `/reward_claim` pour récupérer **+{mission['recompense']} XP** 🎁"
        ),
        color=discord.Color.green()
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    return embed


# ══════════════════════════════════════════════
# COG
# ══════════════════════════════════════════════

class Missions(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._vocal_join: dict[int, float] = {}
        self.reset_missions.start()

    def cog_unload(self):
        self.reset_missions.cancel()

    # ── Task reset à minuit ────────────────────

    @tasks.loop(time=dtime(hour=0, minute=0, second=0))
    async def reset_missions(self):
        """Reset les missions de tout le monde à minuit et envoie une notif."""
        today   = str(date.today())
        choisies = random.sample(MISSIONS, 3)
        nouveau  = {
            "missions_date":      today,
            "missions":           [m["id"] for m in choisies],
            "missions_progres":   {m["id"]: 0 for m in choisies},
            "missions_claimed":   [],
            "missions_notifiees": [],
        }
        # Reset uniquement les docs qui ne sont pas encore à jour
        col_data.update_many(
            {"missions_date": {"$ne": today}},
            {"$set": nouveau}
        )

        embed = discord.Embed(
            title="🌅 Nouvelles missions disponibles !",
            description="Les missions journalières ont été renouvelées !\nTape `/missions` pour voir tes nouvelles missions du jour.",
            color=discord.Color.blurple()
        )
        embed.set_footer(text="Reset quotidien à minuit !")

        for guild in self.bot.guilds:
            cfg      = get_config(guild.id)
            salon_id = cfg.get("salon_bienvenue") or cfg.get("salon_logs")
            if not salon_id:
                continue
            canal = guild.get_channel(int(salon_id))
            if canal:
                try:
                    await canal.send(embed=embed)
                except discord.Forbidden:
                    pass

    @reset_missions.before_loop
    async def before_reset(self):
        await self.bot.wait_until_ready()

    # ── Listeners ─────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        completees = _progresser(message.guild.id, message.author.id, "messages")
        for m in completees:
            await message.channel.send(
                content=message.author.mention,
                embed=_embed_completee(m, message.author),
                delete_after=12
            )

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        if user.bot or not reaction.message.guild:
            return
        completees = _progresser(reaction.message.guild.id, user.id, "reactions")
        for m in completees:
            try:
                await user.send(embed=_embed_completee(m, user))
            except discord.Forbidden:
                pass

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot:
            return
        if before.channel is None and after.channel is not None:
            self._vocal_join[member.id] = time.time()
        elif before.channel is not None and after.channel is None:
            join_time = self._vocal_join.pop(member.id, None)
            if join_time is None:
                return
            duree     = int(time.time() - join_time)
            completees = _progresser(member.guild.id, member.id, "vocal", duree)
            for m in completees:
                try:
                    await member.send(embed=_embed_completee(m, member))
                except discord.Forbidden:
                    pass

    # ── /missions ──────────────────────────────

    @app_commands.command(name="missions", description="Affiche tes missions journalières")
    async def missions(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        doc = _ensure_missions(interaction.guild_id, interaction.user.id)

        embed = discord.Embed(
            title="📋 Missions du jour",
            description="Complète tes missions pour gagner de l'XP bonus !",
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)

        for mid in doc.get("missions", []):
            m = MISSIONS_INDEX.get(mid)
            if not m:
                continue

            progres  = doc.get("missions_progres", {}).get(mid, 0)
            objectif = m["objectif"]
            claimed  = mid in doc.get("missions_claimed", [])

            pct      = min(progres / objectif, 1.0)
            barre    = "█" * int(pct * 10) + "░" * (10 - int(pct * 10))

            if claimed:
                statut = "✅ Réclamée"
            elif progres >= objectif:
                statut = "🎁 Prête à réclamer — `/reward_claim`"
            else:
                statut = f"`{barre}` {progres}/{objectif}"

            emoji = "✅" if claimed else ("🎁" if progres >= objectif else "🎯")
            embed.add_field(
                name=f"{emoji} {m['nom']} — {m['recompense']} XP",
                value=f"{m['description']}\n{statut}",
                inline=False
            )

        embed.set_footer(text="Les missions se renouvellent chaque jour à minuit !")
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── /reward_claim ──────────────────────────

    @app_commands.command(name="reward_claim", description="Réclame les XP de tes missions complétées")
    async def reward_claim(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        doc      = _ensure_missions(interaction.guild_id, interaction.user.id)
        gid, uid = str(interaction.guild_id), str(interaction.user.id)

        xp_total  = 0
        reclamees = []
        claimed   = list(doc.get("missions_claimed", []))

        for mid in doc.get("missions", []):
            m = MISSIONS_INDEX.get(mid)
            if not m or mid in claimed:
                continue
            if doc.get("missions_progres", {}).get(mid, 0) >= m["objectif"]:
                claimed.append(mid)
                xp_total += m["recompense"]
                reclamees.append(f"✅ **{m['nom']}** — +{m['recompense']} XP")

        if not reclamees:
            await interaction.followup.send(
                "❌ Aucune mission complétée à réclamer pour l'instant !", ephemeral=True
            )
            return

        # Sauvegarde XP + missions_claimed en une seule opération
        col_data.update_one(
            {"guild_id": gid, "user_id": uid},
            {
                "$set":  {"missions_claimed": claimed},
                "$inc":  {"xp": xp_total},
            },
            upsert=True
        )

        embed = discord.Embed(
            title="🎁 Récompenses réclamées !",
            description="\n".join(reclamees),
            color=discord.Color.green()
        )
        embed.add_field(name="💰 Total gagné", value=f"**+{xp_total} XP**", inline=False)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text="Continue comme ça !")
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── Erreurs ────────────────────────────────

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        msg = f"❌ Erreur : {error}"
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Missions(bot))