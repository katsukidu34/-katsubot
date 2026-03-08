"""
api.py — Serveur FastAPI pour KatsuBot Dashboard (JSON only)
Lance avec : python -m uvicorn api:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Any, Optional
import os, requests as req, json
from dotenv import load_dotenv

load_dotenv()

DISCORD_CLIENT_ID     = os.getenv("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
DISCORD_REDIRECT_URI  = os.getenv("DISCORD_REDIRECT_URI", "http://localhost:8000/callback")
DISCORD_API           = "https://discord.com/api/v10"

sessions: dict = {}

from config import (
    CONFIG_DEFAUT, get_config, set_config,
    ajouter_sanction, get_sanctions,
    charger_data, sauvegarder_data, get_joueur,
    charger_eco, get_compte, save_compte,
)

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

    bot_data     = lire_bot_data()
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
                "icon_url":    data.get("icon"),
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

@app.get("/sanctions/{guild_id}")
def get_toutes_sanctions(guild_id: str):
    bot_data = lire_bot_data()
    membres  = {m["id"]: m for m in bot_data.get(guild_id, {}).get("membres", [])}
    data     = charger_data()
    result   = []
    guild_data = data.get(guild_id, {})
    for uid, doc in guild_data.items():
        sanctions = doc.get("sanctions", [])
        if sanctions:
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

@app.get("/membres/{guild_id}")
def get_membres(guild_id: str, search: str = ""):
    bot_data = lire_bot_data()
    membres  = bot_data.get(guild_id, {}).get("membres", [])
    data     = charger_data()
    guild_data = data.get(guild_id, {})
    result   = []
    for m in membres:
        if search and search.lower() not in m["name"].lower():
            continue
        doc = guild_data.get(m["id"], {})
        result.append({
            **m,
            "xp":        doc.get("xp", 0),
            "niveau":    doc.get("niveau", 0),
            "warnings":  doc.get("warnings", 0),
            "sanctions": len(doc.get("sanctions", [])),
        })
    result.sort(key=lambda x: x["xp"], reverse=True)
    return result[:50]

@app.get("/stats/{guild_id}")
def get_stats(guild_id: str):
    data       = charger_data()
    guild_data = data.get(guild_id, {})
    joueurs    = [{"user_id": uid, "xp": d.get("xp",0), "niveau": d.get("niveau",0)} for uid, d in guild_data.items()]
    joueurs.sort(key=lambda x: x["xp"], reverse=True)
    total_sanctions = sum(len(d.get("sanctions",[])) for d in guild_data.values())
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