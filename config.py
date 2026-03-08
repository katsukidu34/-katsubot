"""
config.py — Constantes et gestion de la configuration avec JSON
"""

import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ══════════════════════════════════════════════
# TOKEN
# ══════════════════════════════════════════════
TOKEN = os.getenv("TOKEN")

# ══════════════════════════════════════════════
# FICHIERS DE DONNÉES
# ══════════════════════════════════════════════
DATA_FILE   = "xp_data.json"       # XP, niveaux, sanctions
CONFIG_FILE = "config_data.json"   # Config par serveur
ECO_FILE    = "eco_data.json"      # Économie

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
# FONCTIONS UTILITAIRES JSON
# ══════════════════════════════════════════════
def lire_json(fichier: str) -> dict:
    if not os.path.exists(fichier):
        return {}
    with open(fichier, "r", encoding="utf-8") as f:
        return json.load(f)

def ecrire_json(fichier: str, data: dict):
    with open(fichier, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# ══════════════════════════════════════════════
# FONCTIONS — DONNÉES XP
# ══════════════════════════════════════════════
def charger_data() -> dict:
    return lire_json(DATA_FILE)

def sauvegarder_data(data: dict):
    ecrire_json(DATA_FILE, data)

def get_joueur(data: dict, guild_id: int, user_id: int) -> dict:
    gid, uid = str(guild_id), str(user_id)
    if gid not in data:
        data[gid] = {}
    if uid not in data[gid]:
        data[gid][uid] = {
            "xp": 0, "niveau": 0, "warnings": 0,
            "derniere_xp": 0, "sanctions": []
        }
    if "sanctions" not in data[gid][uid]:
        data[gid][uid]["sanctions"] = []
    return data[gid][uid]

def sauvegarder_joueur(data: dict, guild_id: int, user_id: int):
    sauvegarder_data(data)

# ══════════════════════════════════════════════
# FONCTIONS — SANCTIONS
# ══════════════════════════════════════════════
def ajouter_sanction(guild_id: int, user_id: int, action: str, moderateur_id: int, moderateur_nom: str, raison: str):
    data   = charger_data()
    joueur = get_joueur(data, guild_id, user_id)
    joueur["sanctions"].append({
        "action":         action,
        "moderateur_id":  str(moderateur_id),
        "moderateur_nom": moderateur_nom,
        "raison":         raison,
        "date":           datetime.now().strftime("%d/%m/%Y à %Hh%M")
    })
    sauvegarder_data(data)

def get_sanctions(guild_id: int, user_id: int) -> list:
    data   = charger_data()
    joueur = get_joueur(data, guild_id, user_id)
    return joueur.get("sanctions", [])

def get_warnings(guild_id: int, user_id: int) -> int:
    data   = charger_data()
    joueur = get_joueur(data, guild_id, user_id)
    return joueur.get("warnings", 0)

def increment_warning(guild_id: int, user_id: int) -> int:
    data   = charger_data()
    joueur = get_joueur(data, guild_id, user_id)
    joueur["warnings"] = joueur.get("warnings", 0) + 1
    sauvegarder_data(data)
    return joueur["warnings"]

# ══════════════════════════════════════════════
# FONCTIONS — CONFIGURATION (autonomes)
# ══════════════════════════════════════════════
def charger_config() -> dict:
    cfg = lire_json(CONFIG_FILE)
    for gid, c in cfg.items():
        for k, v in CONFIG_DEFAUT.items():
            if k not in c:
                c[k] = v
    return cfg

def sauvegarder_config(config: dict):
    ecrire_json(CONFIG_FILE, config)

def get_config(guild_id: int) -> dict:
    """Charge et retourne la config d'un serveur. Autonome."""
    config = charger_config()
    gid    = str(guild_id)
    if gid not in config:
        config[gid] = CONFIG_DEFAUT.copy()
        sauvegarder_config(config)
    for cle, valeur in CONFIG_DEFAUT.items():
        if cle not in config[gid]:
            config[gid][cle] = valeur
    return config[gid]

def set_config(guild_id: int, cle: str, valeur):
    """Modifie une clé de config d'un serveur. Autonome."""
    config = charger_config()
    gid    = str(guild_id)
    if gid not in config:
        config[gid] = CONFIG_DEFAUT.copy()
    config[gid][cle] = valeur
    sauvegarder_config(config)

# ══════════════════════════════════════════════
# FONCTIONS — ÉCONOMIE
# ══════════════════════════════════════════════
def charger_eco() -> dict:
    return lire_json(ECO_FILE)

def sauvegarder_eco(data: dict):
    ecrire_json(ECO_FILE, data)

def get_compte(guild_id: int, user_id: int) -> dict:
    data = charger_eco()
    gid, uid = str(guild_id), str(user_id)
    if gid not in data:
        data[gid] = {}
    if uid not in data[gid]:
        data[gid][uid] = {
            "cash": 0, "banque": 0,
            "daily_last": 0, "weekly_last": 0,
            "work_last": 0, "rob_last": 0,
        }
    return data[gid][uid]

def save_compte(guild_id: int, user_id: int, compte: dict):
    data = charger_eco()
    gid, uid = str(guild_id), str(user_id)
    if gid not in data:
        data[gid] = {}
    data[gid][uid] = compte
    sauvegarder_eco(data)

# ══════════════════════════════════════════════
# FONCTION UTILITAIRE XP
# ══════════════════════════════════════════════
def xp_pour_niveau(niveau: int) -> int:
    return 100 * (niveau + 1)