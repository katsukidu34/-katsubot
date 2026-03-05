"""
config.py — Constantes et gestion de la configuration
"""

import json
import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ══════════════════════════════════════════════
# TOKEN
# ══════════════════════════════════════════════

TOKEN = os.getenv('TOKEN')

# ══════════════════════════════════════════════
# API
# ══════════════════════════════════════════════

API = "http://127.0.0.1:8000"

# ══════════════════════════════════════════════
# FICHIERS DE DONNÉES
# ══════════════════════════════════════════════

FICHIER_DATA   = "data.json"
FICHIER_CONFIG = "config.json"

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
# FONCTIONS — DONNÉES
# ══════════════════════════════════════════════

def charger_data() -> dict:
    if os.path.exists(FICHIER_DATA):
        with open(FICHIER_DATA, "r") as f:
            return json.load(f)
    return {}

def sauvegarder_data(data: dict):
    with open(FICHIER_DATA, "w") as f:
        json.dump(data, f, indent=4)

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
    sauvegarder_data(data)
    return joueur.get("sanctions", [])

# ══════════════════════════════════════════════
# FONCTIONS — CONFIGURATION
# ══════════════════════════════════════════════

def charger_config() -> dict:
    if os.path.exists(FICHIER_CONFIG):
        with open(FICHIER_CONFIG, "r") as f:
            return json.load(f)
    return {}

def sauvegarder_config(config: dict):
    with open(FICHIER_CONFIG, "w") as f:
        json.dump(config, f, indent=4)

def get_config(guild_id: int) -> dict:
    try:
        res = requests.get(f"{API}/config/{guild_id}", timeout=2)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
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
    try:
        res = requests.patch(
            f"{API}/config/{guild_id}",
            json={"cle": cle, "valeur": valeur},
            timeout=2
        )
        if res.status_code == 200:
            return
    except Exception:
        pass
    config = charger_config()
    gid    = str(guild_id)
    if gid not in config:
        config[gid] = CONFIG_DEFAUT.copy()
    config[gid][cle] = valeur
    sauvegarder_config(config)

# ══════════════════════════════════════════════
# FONCTION UTILITAIRE XP
# ══════════════════════════════════════════════

def xp_pour_niveau(niveau: int) -> int:
    return 100 * (niveau + 1)