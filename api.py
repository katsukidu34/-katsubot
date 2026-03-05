"""
api.py — Serveur FastAPI complet pour KatsuBot Dashboard
Lance avec : python -m uvicorn api:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Any, Optional
import json, os, requests as req
from datetime import datetime

# ══════════════════════════════════════════════
# CONSTANTES
# ══════════════════════════════════════════════

DISCORD_CLIENT_ID     = "1479239529197076691"
DISCORD_CLIENT_SECRET = "rOM-Mr4uIHIKBtM_fXcjZIh_rQOwgYUW"
DISCORD_REDIRECT_URI  = "http://localhost:8000/callback"
DISCORD_API           = "https://discord.com/api/v10"
FICHIER_CONFIG        = "config.json"
FICHIER_DATA          = "data.json"
FICHIER_BOT_DATA      = "bot_data.json"
FICHIER_LOGS          = "logs.json"
FICHIER_MISSIONS      = "missions.json"

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

sessions: dict = {}

# ══════════════════════════════════════════════
# FONCTIONS INTERNES
# ══════════════════════════════════════════════

def lire_json(fichier, defaut=None):
    if defaut is None: defaut = {}
    if os.path.exists(fichier):
        with open(fichier, "r", encoding="utf-8") as f:
            return json.load(f)
    return defaut

def ecrire_json(fichier, data):
    with open(fichier, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_guild_config(guild_id: str) -> dict:
    config = lire_json(FICHIER_CONFIG)
    if guild_id not in config:
        config[guild_id] = CONFIG_DEFAUT.copy()
        ecrire_json(FICHIER_CONFIG, config)
    for cle, valeur in CONFIG_DEFAUT.items():
        if cle not in config[guild_id]:
            config[guild_id][cle] = valeur
    return config[guild_id]

def get_user_from_token(request: Request):
    token = request.cookies.get("token") or request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token or token not in sessions:
        return None
    return sessions[token]

# ══════════════════════════════════════════════
# MODÈLES
# ══════════════════════════════════════════════

class ConfigUpdate(BaseModel):
    cle: str
    valeur: Any

class ShopItem(BaseModel):
    nom: str
    prix: int

class RoleNiveau(BaseModel):
    niveau: str
    role: str

class ReactionRole(BaseModel):
    message_id: str
    emoji: str
    role: str

class Mission(BaseModel):
    id: Optional[str] = None
    titre: str
    description: str
    type: str        # "messages", "xp", "invitations"
    objectif: int
    recompense_xp: int
    recompense_role: Optional[str] = None

class SanctionDelete(BaseModel):
    user_id: str
    index: int

# ══════════════════════════════════════════════
# APP
# ══════════════════════════════════════════════

app = FastAPI(title="KatsuBot Dashboard", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# ══════════════════════════════════════════════
# OAUTH2
# ══════════════════════════════════════════════

@app.get("/login")
def login():
    url = (
        f"https://discord.com/oauth2/authorize"
        f"?client_id={DISCORD_CLIENT_ID}"
        f"&redirect_uri={DISCORD_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify+guilds"
    )
    return RedirectResponse(url)

@app.get("/callback")
def callback(code: str):
    token_res = req.post("https://discord.com/api/oauth2/token", data={
        "client_id":     DISCORD_CLIENT_ID,
        "client_secret": DISCORD_CLIENT_SECRET,
        "grant_type":    "authorization_code",
        "code":          code,
        "redirect_uri":  DISCORD_REDIRECT_URI,
    }, headers={"Content-Type": "application/x-www-form-urlencoded"})

    if token_res.status_code != 200:
        return HTMLResponse("<h2>Erreur d'authentification</h2>", status_code=400)

    access_token = token_res.json()["access_token"]

    user   = req.get(f"{DISCORD_API}/users/@me",       headers={"Authorization": f"Bearer {access_token}"}).json()
    guilds = req.get(f"{DISCORD_API}/users/@me/guilds", headers={"Authorization": f"Bearer {access_token}"}).json()

    bot_data     = lire_json(FICHIER_BOT_DATA)
    admin_guilds = [g for g in guilds if (int(g["permissions"]) & 0x8) == 0x8 and str(g["id"]) in bot_data]

    sessions[access_token] = {"user": user, "guilds": admin_guilds}

    response = RedirectResponse(url=f"/dashboard.html?token={access_token}")
    response.set_cookie("token", access_token, httponly=False, max_age=604800)
    return response

@app.get("/logout")
def logout(request: Request):
    token = request.cookies.get("token")
    if token and token in sessions:
        del sessions[token]
    response = RedirectResponse(url="/dashboard.html")
    response.delete_cookie("token")
    return response

@app.get("/me")
def get_me(request: Request):
    user_data = get_user_from_token(request)
    if not user_data:
        raise HTTPException(status_code=401, detail="Non connecté")
    return user_data

# ══════════════════════════════════════════════
# BOT DATA
# ══════════════════════════════════════════════

@app.get("/bot/{guild_id}")
def get_bot_data(guild_id: str):
    bot_data = lire_json(FICHIER_BOT_DATA)
    if guild_id not in bot_data:
        raise HTTPException(status_code=404, detail="Serveur introuvable")
    return bot_data[guild_id]

# ══════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════

@app.get("/config/{guild_id}")
def lire_config(guild_id: str):
    return get_guild_config(guild_id)

@app.patch("/config/{guild_id}")
def modifier_config(guild_id: str, body: ConfigUpdate):
    if body.cle not in CONFIG_DEFAUT:
        raise HTTPException(status_code=400, detail=f"Clé inconnue : {body.cle}")
    config = lire_json(FICHIER_CONFIG)
    if guild_id not in config:
        config[guild_id] = CONFIG_DEFAUT.copy()
    config[guild_id][body.cle] = body.valeur
    ecrire_json(FICHIER_CONFIG, config)
    return {"ok": True}

# ══════════════════════════════════════════════
# SHOP
# ══════════════════════════════════════════════

@app.post("/config/{guild_id}/shop")
def ajouter_article(guild_id: str, item: ShopItem):
    if item.prix <= 0:
        raise HTTPException(status_code=400, detail="Prix invalide")
    config = lire_json(FICHIER_CONFIG)
    if guild_id not in config: config[guild_id] = CONFIG_DEFAUT.copy()
    config[guild_id].setdefault("shop", {})[item.nom] = item.prix
    ecrire_json(FICHIER_CONFIG, config)
    return {"ok": True}

@app.delete("/config/{guild_id}/shop/{nom}")
def supprimer_article(guild_id: str, nom: str):
    config = lire_json(FICHIER_CONFIG)
    if nom not in config.get(guild_id, {}).get("shop", {}):
        raise HTTPException(status_code=404, detail="Article introuvable")
    del config[guild_id]["shop"][nom]
    ecrire_json(FICHIER_CONFIG, config)
    return {"ok": True}

# ══════════════════════════════════════════════
# RÔLES PAR NIVEAU
# ══════════════════════════════════════════════

@app.post("/config/{guild_id}/roles")
def ajouter_role(guild_id: str, item: RoleNiveau):
    config = lire_json(FICHIER_CONFIG)
    if guild_id not in config: config[guild_id] = CONFIG_DEFAUT.copy()
    config[guild_id].setdefault("roles_niveaux", {})[item.niveau] = item.role
    ecrire_json(FICHIER_CONFIG, config)
    return {"ok": True}

@app.delete("/config/{guild_id}/roles/{niveau}")
def supprimer_role(guild_id: str, niveau: str):
    config = lire_json(FICHIER_CONFIG)
    if niveau not in config.get(guild_id, {}).get("roles_niveaux", {}):
        raise HTTPException(status_code=404, detail="Niveau introuvable")
    del config[guild_id]["roles_niveaux"][niveau]
    ecrire_json(FICHIER_CONFIG, config)
    return {"ok": True}

# ══════════════════════════════════════════════
# REACTION ROLES
# ══════════════════════════════════════════════

@app.get("/config/{guild_id}/reaction_roles")
def lire_reaction_roles(guild_id: str):
    cfg = get_guild_config(guild_id)
    return cfg.get("reaction_roles", {})

@app.post("/config/{guild_id}/reaction_roles")
def ajouter_reaction_role(guild_id: str, item: ReactionRole):
    config = lire_json(FICHIER_CONFIG)
    if guild_id not in config: config[guild_id] = CONFIG_DEFAUT.copy()
    rr = config[guild_id].setdefault("reaction_roles", {})
    rr.setdefault(item.message_id, {})[item.emoji] = item.role
    ecrire_json(FICHIER_CONFIG, config)
    return {"ok": True}

@app.delete("/config/{guild_id}/reaction_roles/{message_id}/{emoji}")
def supprimer_reaction_role(guild_id: str, message_id: str, emoji: str):
    config = lire_json(FICHIER_CONFIG)
    rr = config.get(guild_id, {}).get("reaction_roles", {})
    if message_id not in rr or emoji not in rr[message_id]:
        raise HTTPException(status_code=404, detail="Reaction role introuvable")
    del config[guild_id]["reaction_roles"][message_id][emoji]
    if not config[guild_id]["reaction_roles"][message_id]:
        del config[guild_id]["reaction_roles"][message_id]
    ecrire_json(FICHIER_CONFIG, config)
    return {"ok": True}

# ══════════════════════════════════════════════
# SANCTIONS
# ══════════════════════════════════════════════

@app.get("/sanctions/{guild_id}")
def get_toutes_sanctions(guild_id: str):
    data       = lire_json(FICHIER_DATA)
    guild_data = data.get(guild_id, {})
    bot_data   = lire_json(FICHIER_BOT_DATA)
    membres    = {m["id"]: m for m in bot_data.get(guild_id, {}).get("membres", [])}
    result = []
    for uid, d in guild_data.items():
        sanctions = d.get("sanctions", [])
        if sanctions:
            membre = membres.get(uid, {})
            result.append({
                "user_id":  uid,
                "name":     membre.get("name", f"User {uid}"),
                "avatar":   membre.get("avatar", ""),
                "sanctions": sanctions,
                "total":    len(sanctions),
            })
    result.sort(key=lambda x: x["total"], reverse=True)
    return result

@app.get("/sanctions/{guild_id}/{user_id}")
def get_sanctions_membre(guild_id: str, user_id: str):
    data   = lire_json(FICHIER_DATA)
    joueur = data.get(guild_id, {}).get(user_id, {})
    return joueur.get("sanctions", [])

@app.delete("/sanctions/{guild_id}/{user_id}/{index}")
def supprimer_sanction(guild_id: str, user_id: str, index: int):
    data = lire_json(FICHIER_DATA)
    sanctions = data.get(guild_id, {}).get(user_id, {}).get("sanctions", [])
    if index >= len(sanctions):
        raise HTTPException(status_code=404, detail="Sanction introuvable")
    del data[guild_id][user_id]["sanctions"][index]
    ecrire_json(FICHIER_DATA, data)
    return {"ok": True}

# ══════════════════════════════════════════════
# MEMBRES / PROFILS
# ══════════════════════════════════════════════

@app.get("/membres/{guild_id}")
def get_membres(guild_id: str, search: str = ""):
    bot_data = lire_json(FICHIER_BOT_DATA)
    data     = lire_json(FICHIER_DATA)
    membres  = bot_data.get(guild_id, {}).get("membres", [])
    guild_xp = data.get(guild_id, {})
    result   = []
    for m in membres:
        if search and search.lower() not in m["name"].lower():
            continue
        xp_data = guild_xp.get(m["id"], {})
        result.append({
            **m,
            "xp":       xp_data.get("xp", 0),
            "niveau":   xp_data.get("niveau", 0),
            "warnings": xp_data.get("warnings", 0),
            "sanctions": len(xp_data.get("sanctions", [])),
        })
    result.sort(key=lambda x: x["xp"], reverse=True)
    return result[:50]

@app.get("/profil/{guild_id}/{user_id}")
def get_profil(guild_id: str, user_id: str):
    bot_data = lire_json(FICHIER_BOT_DATA)
    data     = lire_json(FICHIER_DATA)
    membres  = {m["id"]: m for m in bot_data.get(guild_id, {}).get("membres", [])}
    membre   = membres.get(user_id, {"name": f"User {user_id}", "avatar": "", "roles": [], "joined": "?"})
    xp_data  = data.get(guild_id, {}).get(user_id, {})
    return {
        **membre,
        "xp":        xp_data.get("xp", 0),
        "niveau":    xp_data.get("niveau", 0),
        "warnings":  xp_data.get("warnings", 0),
        "sanctions": xp_data.get("sanctions", []),
    }

# ══════════════════════════════════════════════
# MISSIONS
# ══════════════════════════════════════════════

@app.get("/missions/{guild_id}")
def get_missions(guild_id: str):
    missions = lire_json(FICHIER_MISSIONS)
    return missions.get(guild_id, [])

@app.post("/missions/{guild_id}")
def ajouter_mission(guild_id: str, mission: Mission):
    missions = lire_json(FICHIER_MISSIONS)
    guild_missions = missions.setdefault(guild_id, [])
    import uuid
    mission_dict = mission.dict()
    mission_dict["id"] = str(uuid.uuid4())[:8]
    guild_missions.append(mission_dict)
    ecrire_json(FICHIER_MISSIONS, missions)
    return {"ok": True, "mission": mission_dict}

@app.delete("/missions/{guild_id}/{mission_id}")
def supprimer_mission(guild_id: str, mission_id: str):
    missions = lire_json(FICHIER_MISSIONS)
    guild_missions = missions.get(guild_id, [])
    nouvelle_liste = [m for m in guild_missions if m["id"] != mission_id]
    if len(nouvelle_liste) == len(guild_missions):
        raise HTTPException(status_code=404, detail="Mission introuvable")
    missions[guild_id] = nouvelle_liste
    ecrire_json(FICHIER_MISSIONS, missions)
    return {"ok": True}

# ══════════════════════════════════════════════
# LOGS
# ══════════════════════════════════════════════

@app.get("/logs/{guild_id}")
def get_logs(guild_id: str, limit: int = 50):
    logs       = lire_json(FICHIER_LOGS)
    guild_logs = logs.get(guild_id, [])
    return guild_logs[-limit:][::-1]

# ══════════════════════════════════════════════
# STATS
# ══════════════════════════════════════════════

@app.get("/stats/{guild_id}")
def get_stats(guild_id: str):
    data       = lire_json(FICHIER_DATA)
    guild_data = data.get(guild_id, {})
    joueurs    = [
        {"user_id": uid, "xp": d.get("xp", 0), "niveau": d.get("niveau", 0), "warnings": d.get("warnings", 0)}
        for uid, d in guild_data.items()
    ]
    joueurs.sort(key=lambda x: x["xp"], reverse=True)
    total_sanctions = sum(len(d.get("sanctions", [])) for d in guild_data.values())
    return {
        "total_membres":   len(joueurs),
        "top10":           joueurs[:10],
        "total_xp":        sum(j["xp"] for j in joueurs),
        "total_sanctions": total_sanctions,
    }

# ══════════════════════════════════════════════
# SANTÉ
# ══════════════════════════════════════════════

@app.get("/health")
def sante():
    return {"status": "ok", "bot": "KatsuBot", "version": "3.0.0"}

# ══════════════════════════════════════════════
# FICHIERS STATIQUES — EN DERNIER !
# ══════════════════════════════════════════════

app.mount("/", StaticFiles(directory=".", html=True), name="static")