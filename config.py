"""
config.py — Constantes et gestion de la configuration avec MongoDB
"""

import os
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

# ══════════════════════════════════════════════
# TOKEN & MONGODB
# ══════════════════════════════════════════════

TOKEN       = os.getenv("TOKEN")
MONGODB_URI = os.getenv("MONGODB_URI")

# Connexion MongoDB
client = MongoClient(
    MONGODB_URI,
    tls=True,
    tlsAllowInvalidCertificates=True,
    serverSelectionTimeoutMS=30000
)
db     = client["katsubot"]

# Collections
col_data    = db["data"]
col_config  = db["config"]
col_logs    = db["logs"]
col_missions= db["missions"]

# ══════════════════════════════════════════════
# CONFIGURATION PAR DÉFAUT
# ══════════════════════════════════════════════

CONFIG_DEFAUT = {
    "salon_bienvenue":    None,
    "salon_logs":         None,
    "categorie_tickets":  None,
    "seuil_anti_spam":    5,
    "xp_par_message":     10,
    "roles_niveaux":      {},
    "salon_anniversaire": None,
    "logs_moderation":    None,
    "logs_messages":      None,
    "logs_membres":       None,
    "logs_vocal":         None,
    "logs_roles":         None,
    "logs_salons":        None,
    "logs_pseudos":       None,
    "salon_suggestions":  None,
    "reaction_roles":     {},
    "shop":               {},
}

# ══════════════════════════════════════════════
# FONCTIONS — DONNÉES XP
# ══════════════════════════════════════════════

def charger_data() -> dict:
    """Charge toutes les données XP depuis MongoDB."""
    result = {}
    for doc in col_data.find({}, {"_id": 0}):
        guild_id = doc.get("guild_id")
        user_id  = doc.get("user_id")
        if guild_id and user_id:
            if guild_id not in result:
                result[guild_id] = {}
            result[guild_id][user_id] = {
                "xp":          doc.get("xp", 0),
                "niveau":      doc.get("niveau", 0),
                "warnings":    doc.get("warnings", 0),
                "derniere_xp": doc.get("derniere_xp", 0),
                "sanctions":   doc.get("sanctions", []),
            }
    return result

def sauvegarder_data(data: dict):
    """Sauvegarde toutes les données XP dans MongoDB."""
    for guild_id, membres in data.items():
        for user_id, d in membres.items():
            col_data.update_one(
                {"guild_id": guild_id, "user_id": user_id},
                {"$set": {**d, "guild_id": guild_id, "user_id": user_id}},
                upsert=True
            )

def get_joueur(data: dict, guild_id: int, user_id: int) -> dict:
    gid, uid = str(guild_id), str(user_id)
    if gid not in data: data[gid] = {}
    if uid not in data[gid]:
        data[gid][uid] = {
            "xp": 0, "niveau": 0, "warnings": 0,
            "derniere_xp": 0, "sanctions": []
        }
    if "sanctions" not in data[gid][uid]:
        data[gid][uid]["sanctions"] = []
    return data[gid][uid]

def get_joueur_direct(guild_id: int, user_id: int) -> dict:
    """Récupère un joueur directement depuis MongoDB."""
    gid, uid = str(guild_id), str(user_id)
    doc = col_data.find_one({"guild_id": gid, "user_id": uid}, {"_id": 0})
    if not doc:
        doc = {"xp": 0, "niveau": 0, "warnings": 0, "derniere_xp": 0, "sanctions": []}
    return doc

def sauvegarder_joueur(guild_id: int, user_id: int, joueur: dict):
    """Sauvegarde un joueur directement dans MongoDB."""
    gid, uid = str(guild_id), str(user_id)
    col_data.update_one(
        {"guild_id": gid, "user_id": uid},
        {"$set": {**joueur, "guild_id": gid, "user_id": uid}},
        upsert=True
    )

# ══════════════════════════════════════════════
# FONCTIONS — SANCTIONS
# ══════════════════════════════════════════════

def ajouter_sanction(guild_id: int, user_id: int, action: str, moderateur_id: int, moderateur_nom: str, raison: str):
    gid, uid = str(guild_id), str(user_id)
    sanction = {
        "action":         action,
        "moderateur_id":  str(moderateur_id),
        "moderateur_nom": moderateur_nom,
        "raison":         raison,
        "date":           datetime.now().strftime("%d/%m/%Y à %Hh%M")
    }
    col_data.update_one(
        {"guild_id": gid, "user_id": uid},
        {"$push": {"sanctions": sanction}, "$setOnInsert": {"xp": 0, "niveau": 0, "warnings": 0}},
        upsert=True
    )

def get_sanctions(guild_id: int, user_id: int) -> list:
    gid, uid = str(guild_id), str(user_id)
    doc = col_data.find_one({"guild_id": gid, "user_id": uid}, {"_id": 0})
    return doc.get("sanctions", []) if doc else []

# ══════════════════════════════════════════════
# FONCTIONS — CONFIGURATION
# ══════════════════════════════════════════════

def charger_config() -> dict:
    result = {}
    for doc in col_config.find({}, {"_id": 0}):
        gid = doc.pop("guild_id", None)
        if gid:
            result[gid] = doc
    return result

def sauvegarder_config(config: dict):
    for guild_id, cfg in config.items():
        col_config.update_one(
            {"guild_id": guild_id},
            {"$set": {**cfg, "guild_id": guild_id}},
            upsert=True
        )

def get_config(guild_id: int) -> dict:
    gid = str(guild_id)
    doc = col_config.find_one({"guild_id": gid}, {"_id": 0, "guild_id": 0})
    if not doc:
        doc = CONFIG_DEFAUT.copy()
        col_config.update_one(
            {"guild_id": gid},
            {"$set": {**doc, "guild_id": gid}},
            upsert=True
        )
    for cle, valeur in CONFIG_DEFAUT.items():
        if cle not in doc:
            doc[cle] = valeur
    return doc

def set_config(guild_id: int, cle: str, valeur):
    gid = str(guild_id)
    col_config.update_one(
        {"guild_id": gid},
        {"$set": {cle: valeur, "guild_id": gid}},
        upsert=True
    )

# ══════════════════════════════════════════════
# FONCTION UTILITAIRE XP
# ══════════════════════════════════════════════

def xp_pour_niveau(niveau: int) -> int:
    return 100 * (niveau + 1)