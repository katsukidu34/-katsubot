"""
utils.py — Fonctions utilitaires partagées
============================================
Contient :
  - L'anti-spam
  - Les logs de modération avancés
"""

import discord
import datetime
import time
from collections import defaultdict

from config import get_config

# ══════════════════════════════════════════════
# ANTI-SPAM
# ══════════════════════════════════════════════

_messages_recents: dict = defaultdict(list)

def est_spam(user_id: int, seuil: int) -> bool:
    now = time.time()
    _messages_recents[user_id] = [t for t in _messages_recents[user_id] if now - t < 5]
    _messages_recents[user_id].append(now)
    return len(_messages_recents[user_id]) > seuil

# ══════════════════════════════════════════════
# LOGS DE MODÉRATION
# ══════════════════════════════════════════════

COULEURS_LOG = {
    "Kick":             discord.Color.orange(),
    "Ban":              discord.Color.red(),
    "Warn":             discord.Color.yellow(),
    "Unban":            discord.Color.green(),
    "Message supprimé": discord.Color.red(),
    "Message édité":    discord.Color.yellow(),
    "Membre parti":     discord.Color.orange(),
    "Membre arrivé":    discord.Color.green(),
    "Salon créé":       discord.Color.blurple(),
    "Salon supprimé":   discord.Color.dark_red(),
    "Rôle ajouté":      discord.Color.green(),
    "Rôle retiré":      discord.Color.orange(),
}

async def envoyer_log(guild: discord.Guild, action: str, moderateur=None, cible=None, raison: str = None, extra: dict = None):
    """
    Envoie un embed de log dans le salon configuré.
    extra = champs supplémentaires {nom: valeur}
    """
    cfg = get_config(guild.id)
    if not cfg["salon_logs"]:
        return

    canal = guild.get_channel(int(cfg["salon_logs"]))
    if not canal:
        return

    embed = discord.Embed(
        title=f"📋 {action}",
        color=COULEURS_LOG.get(action, discord.Color.blurple()),
        timestamp=datetime.datetime.utcnow()
    )

    if cible:
        embed.add_field(name="Membre", value=cible.mention if hasattr(cible, 'mention') else str(cible), inline=True)
    if moderateur:
        embed.add_field(name="Modérateur", value=moderateur.mention, inline=True)
    if raison:
        embed.add_field(name="Raison", value=raison, inline=False)
    if extra:
        for nom, valeur in extra.items():
            embed.add_field(name=nom, value=valeur, inline=False)

    await canal.send(embed=embed)