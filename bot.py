"""
bot.py — Point d'entrée du bot
================================
C'est CE fichier que tu lances : python bot.py
"""
import discord
from discord.ext import commands
import asyncio
import os
import json
from config import TOKEN

# ══════════════════════════════════════════════
# CRÉATION DU BOT
# ══════════════════════════════════════════════

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)
bot.snipe_cache = {}

# ══════════════════════════════════════════════
# CHARGEMENT DES MODULES (COGS)
# ══════════════════════════════════════════════

async def charger_cogs():
    for fichier in os.listdir("./cogs"):
        if fichier.endswith(".py") and fichier != "__init__.py":
            nom = fichier[:-3]
            await bot.load_extension(f"cogs.{nom}")
            print(f"  ✅ Module chargé : cogs/{fichier}")

# ══════════════════════════════════════════════
# EXPOSITION DES DONNÉES POUR LE DASHBOARD
# ══════════════════════════════════════════════

def exporter_donnees_bot():
    data = {}
    for guild in bot.guilds:
        salons_texte = [
            {"id": str(c.id), "name": f"#{c.name}"}
            for c in sorted(guild.text_channels, key=lambda x: x.position)
        ]
        categories = [
            {"id": str(c.id), "name": f"📁 {c.name}"}
            for c in guild.categories
        ]
        roles = [
            {"id": str(r.id), "name": r.name}
            for r in reversed(guild.roles)
            if r.name != "@everyone"
        ]
        membres = [
            {
                "id":     str(m.id),
                "name":   m.display_name,
                "avatar": str(m.display_avatar.url),
                "roles":  [r.name for r in m.roles if r.name != "@everyone"],
                "joined": m.joined_at.strftime("%d/%m/%Y") if m.joined_at else "?"
            }
            for m in guild.members if not m.bot
        ]
        data[str(guild.id)] = {
            "name":       guild.name,
            "icon":       str(guild.icon) if guild.icon else None,
            "members":    guild.member_count,
            "salons":     salons_texte,
            "categories": categories,
            "roles":      roles,
            "membres":    membres,
        }
    with open("bot_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("✅ bot_data.json mis à jour !")

# ══════════════════════════════════════════════
# ÉVÉNEMENTS
# ══════════════════════════════════════════════

@bot.event
async def on_ready():
    synced = await bot.tree.sync()
    print(f"\n🤖 Bot connecté : {bot.user}")
    print(f"📋 {len(synced)} commandes slash synchronisées !\n")
    await bot.change_presence(activity=discord.Game(name="/help"))
    exporter_donnees_bot()

@bot.event
async def on_guild_join(guild):
    exporter_donnees_bot()

@bot.event
async def on_guild_remove(guild):
    exporter_donnees_bot()

@bot.event
async def on_member_join(member):
    exporter_donnees_bot()

@bot.event
async def on_member_remove(member):
    exporter_donnees_bot()

# ══════════════════════════════════════════════
# LANCEMENT
# ══════════════════════════════════════════════

async def main():
    async with bot:
        print("📦 Chargement des modules...")
        await charger_cogs()
        await bot.start(TOKEN)

asyncio.run(main())