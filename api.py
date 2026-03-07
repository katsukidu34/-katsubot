"""
api.py — Serveur FastAPI pour KatsuBot Dashboard
Lance avec : python -m uvicorn api:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Any, Optional
import os, requests as req
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DISCORD_CLIENT_ID     = os.getenv("DISCORD_CLIENT_ID", "1479239529197076691")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
DISCORD_REDIRECT_URI  = "http://localhost:8000/callback"
DISCORD_API           = "https://discord.com/api/v10"

sessions: dict = {}

from config import (
    col_data, col_config, col_logs, col_missions,
    CONFIG_DEFAUT, get_config, set_config,
    ajouter_sanction, get_sanctions
)
import json, os

def lire_bot_data():
    if os.path.exists("bot_data.json"):
        with open("bot_data.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

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
    type: str
    objectif: int
    recompense_xp: int
    recompense_role: Optional[str] = None

app = FastAPI(title="KatsuBot Dashboard", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

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
        print("Discord OAuth error:", token_res.text)
        return HTMLResponse(f"<h2>Erreur d'authentification</h2><pre>{token_res.text}</pre>", status_code=400)

    access_token = token_res.json()["access_token"]
    user   = req.get(f"{DISCORD_API}/users/@me",        headers={"Authorization": f"Bearer {access_token}"}).json()
    guilds = req.get(f"{DISCORD_API}/users/@me/guilds", headers={"Authorization": f"Bearer {access_token}"}).json()

    bot_data = lire_bot_data()

    # ✅ Uniquement les serveurs admin ET où le bot est présent, avec infos enrichies
    admin_guilds = []
    for g in guilds:
        is_admin    = (int(g["permissions"]) & 0x8) == 0x8
        bot_present = str(g["id"]) in bot_data
        if is_admin and bot_present:
            data = bot_data[str(g["id"])]
            admin_guilds.append({
                **g,
                "bot_present": True,
                "members":     data.get("members", 0),
                "icon_url":    data.get("icon"),  # URL complète depuis bot_data
            })

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
    token = request.cookies.get("token") or request.headers.get("Authorization","").replace("Bearer ","")
    if not token or token not in sessions:
        raise HTTPException(status_code=401, detail="Non connecté")
    return sessions[token]

@app.get("/bot/{guild_id}")
def get_bot_data(guild_id: str):
    bot_data = lire_bot_data()
    return bot_data.get(guild_id, {"salons": [], "categories": [], "roles": [], "membres": []})

@app.get("/config/{guild_id}")
def lire_config(guild_id: str):
    return get_config(int(guild_id))

@app.patch("/config/{guild_id}")
def modifier_config(guild_id: str, body: ConfigUpdate):
    if body.cle not in CONFIG_DEFAUT:
        raise HTTPException(status_code=400, detail=f"Clé inconnue : {body.cle}")
    set_config(int(guild_id), body.cle, body.valeur)
    return {"ok": True}

@app.post("/config/{guild_id}/shop")
def ajouter_article(guild_id: str, item: ShopItem):
    if item.prix <= 0:
        raise HTTPException(status_code=400, detail="Prix invalide")
    cfg = get_config(int(guild_id))
    cfg.setdefault("shop", {})[item.nom] = item.prix
    set_config(int(guild_id), "shop", cfg["shop"])
    return {"ok": True}

@app.delete("/config/{guild_id}/shop/{nom}")
def supprimer_article(guild_id: str, nom: str):
    cfg = get_config(int(guild_id))
    if nom not in cfg.get("shop", {}):
        raise HTTPException(status_code=404, detail="Article introuvable")
    del cfg["shop"][nom]
    set_config(int(guild_id), "shop", cfg["shop"])
    return {"ok": True}

@app.post("/config/{guild_id}/roles")
def ajouter_role(guild_id: str, item: RoleNiveau):
    cfg = get_config(int(guild_id))
    cfg.setdefault("roles_niveaux", {})[item.niveau] = item.role
    set_config(int(guild_id), "roles_niveaux", cfg["roles_niveaux"])
    return {"ok": True}

@app.delete("/config/{guild_id}/roles/{niveau}")
def supprimer_role(guild_id: str, niveau: str):
    cfg = get_config(int(guild_id))
    if niveau not in cfg.get("roles_niveaux", {}):
        raise HTTPException(status_code=404, detail="Niveau introuvable")
    del cfg["roles_niveaux"][niveau]
    set_config(int(guild_id), "roles_niveaux", cfg["roles_niveaux"])
    return {"ok": True}

@app.post("/config/{guild_id}/reaction_roles")
def ajouter_reaction_role(guild_id: str, item: ReactionRole):
    cfg = get_config(int(guild_id))
    rr  = cfg.setdefault("reaction_roles", {})
    rr.setdefault(item.message_id, {})[item.emoji] = item.role
    set_config(int(guild_id), "reaction_roles", rr)
    return {"ok": True}

@app.delete("/config/{guild_id}/reaction_roles/{message_id}/{emoji}")
def supprimer_reaction_role(guild_id: str, message_id: str, emoji: str):
    cfg = get_config(int(guild_id))
    rr  = cfg.get("reaction_roles", {})
    if message_id not in rr or emoji not in rr[message_id]:
        raise HTTPException(status_code=404, detail="Reaction role introuvable")
    del rr[message_id][emoji]
    if not rr[message_id]:
        del rr[message_id]
    set_config(int(guild_id), "reaction_roles", rr)
    return {"ok": True}

@app.get("/sanctions/{guild_id}")
def get_toutes_sanctions(guild_id: str):
    bot_data = lire_bot_data()
    membres  = {m["id"]: m for m in bot_data.get(guild_id, {}).get("membres", [])}
    result   = []
    for doc in col_data.find({"guild_id": guild_id}, {"_id": 0}):
        sanctions = doc.get("sanctions", [])
        if sanctions:
            uid    = doc.get("user_id")
            membre = membres.get(uid, {})
            result.append({
                "user_id":   uid,
                "name":      membre.get("name", f"User {uid}"),
                "avatar":    membre.get("avatar", ""),
                "sanctions": sanctions,
                "total":     len(sanctions),
            })
    result.sort(key=lambda x: x["total"], reverse=True)
    return result

@app.delete("/sanctions/{guild_id}/{user_id}/{index}")
def supprimer_sanction(guild_id: str, user_id: str, index: int):
    doc = col_data.find_one({"guild_id": guild_id, "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Membre introuvable")
    sanctions = doc.get("sanctions", [])
    if index >= len(sanctions):
        raise HTTPException(status_code=404, detail="Sanction introuvable")
    del sanctions[index]
    col_data.update_one({"guild_id": guild_id, "user_id": user_id}, {"$set": {"sanctions": sanctions}})
    return {"ok": True}

@app.get("/membres/{guild_id}")
def get_membres(guild_id: str, search: str = ""):
    bot_data = lire_bot_data()
    membres  = bot_data.get(guild_id, {}).get("membres", [])
    result   = []
    for m in membres:
        if search and search.lower() not in m["name"].lower():
            continue
        doc = col_data.find_one({"guild_id": guild_id, "user_id": m["id"]}, {"_id": 0}) or {}
        result.append({
            **m,
            "xp":        doc.get("xp", 0),
            "niveau":    doc.get("niveau", 0),
            "warnings":  doc.get("warnings", 0),
            "sanctions": len(doc.get("sanctions", [])),
        })
    result.sort(key=lambda x: x["xp"], reverse=True)
    return result[:50]

@app.get("/profil/{guild_id}/{user_id}")
def get_profil(guild_id: str, user_id: str):
    bot_data = lire_bot_data()
    membres  = {m["id"]: m for m in bot_data.get(guild_id, {}).get("membres", [])}
    membre   = membres.get(user_id, {"name": f"User {user_id}", "avatar": "", "roles": [], "joined": "?"})
    doc      = col_data.find_one({"guild_id": guild_id, "user_id": user_id}, {"_id": 0}) or {}
    return {
        **membre,
        "xp":        doc.get("xp", 0),
        "niveau":    doc.get("niveau", 0),
        "warnings":  doc.get("warnings", 0),
        "sanctions": doc.get("sanctions", []),
    }

@app.get("/missions/{guild_id}")
def get_missions(guild_id: str):
    return list(col_missions.find({"guild_id": guild_id}, {"_id": 0}))

@app.post("/missions/{guild_id}")
def ajouter_mission(guild_id: str, mission: Mission):
    import uuid
    d = mission.dict()
    d["id"]       = str(uuid.uuid4())[:8]
    d["guild_id"] = guild_id
    col_missions.insert_one(d)
    d.pop("_id", None)
    return {"ok": True, "mission": d}

@app.delete("/missions/{guild_id}/{mission_id}")
def supprimer_mission(guild_id: str, mission_id: str):
    r = col_missions.delete_one({"guild_id": guild_id, "id": mission_id})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Mission introuvable")
    return {"ok": True}

@app.get("/logs/{guild_id}")
def get_logs(guild_id: str, limit: int = 50):
    logs = list(col_logs.find({"guild_id": guild_id}, {"_id": 0}).sort("_id", -1).limit(limit))
    return logs

@app.get("/stats/{guild_id}")
def get_stats(guild_id: str):
    docs    = list(col_data.find({"guild_id": guild_id}, {"_id": 0}))
    joueurs = [{"user_id": d["user_id"], "xp": d.get("xp",0), "niveau": d.get("niveau",0)} for d in docs]
    joueurs.sort(key=lambda x: x["xp"], reverse=True)
    total_sanctions = sum(len(d.get("sanctions",[])) for d in docs)
    return {
        "total_membres":   len(joueurs),
        "top10":           joueurs[:10],
        "total_xp":        sum(j["xp"] for j in joueurs),
        "total_sanctions": total_sanctions,
    }

@app.get("/health")
def sante():
    return {"status": "ok", "bot": "KatsuBot", "version": "3.0.0"}

app.mount("/", StaticFiles(directory=".", html=True), name="static")