"""
cogs/configuration.py — Panneau de configuration complet
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime

from config import get_config, set_config, charger_config, sauvegarder_config


# ══════════════════════════════════════════════
# HELPERS SHOP
# ══════════════════════════════════════════════

def get_shop(guild_id):
    return get_config(guild_id).get("shop", {})

def set_shop(guild_id, shop):
    set_config(guild_id, "shop", shop)


# ══════════════════════════════════════════════
# MODALS
# ══════════════════════════════════════════════

class ModalSalonId(discord.ui.Modal):
    def __init__(self, cle, titre, label, valeur_actuelle):
        super().__init__(title=titre)
        self.cle = cle
        self.champ = discord.ui.TextInput(
            label=label,
            placeholder="Clic droit sur le salon → Copier l'identifiant",
            default=valeur_actuelle,
            required=False,
            max_length=20
        )
        self.add_item(self.champ)

    async def on_submit(self, interaction: discord.Interaction):
        val = self.champ.value.strip()
        if not val:
            set_config(interaction.guild_id, self.cle, None)
            await interaction.response.send_message("✅ Salon désactivé !", ephemeral=True)
            return
        try:
            canal = interaction.guild.get_channel(int(val))
            if not canal:
                await interaction.response.send_message("❌ Salon introuvable ! Vérifie l'ID.", ephemeral=True)
                return
            set_config(interaction.guild_id, self.cle, val)
            await interaction.response.send_message(f"✅ Mis à jour → {canal.mention}", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ ID invalide ! Entre uniquement des chiffres.", ephemeral=True)


class ModalNombre(discord.ui.Modal):
    def __init__(self, cle, titre, label, valeur_actuelle, minimum, maximum):
        super().__init__(title=titre)
        self.cle, self.minimum, self.maximum = cle, minimum, maximum
        self.champ = discord.ui.TextInput(
            label=label,
            default=valeur_actuelle,
            required=True,
            max_length=5
        )
        self.add_item(self.champ)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = int(self.champ.value.strip())
            if not (self.minimum <= val <= self.maximum):
                await interaction.response.send_message(
                    f"❌ La valeur doit être entre {self.minimum} et {self.maximum} !", ephemeral=True
                )
                return
            set_config(interaction.guild_id, self.cle, val)
            await interaction.response.send_message(f"✅ Mis à jour → **{val}**", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Entre un nombre valide !", ephemeral=True)


class ModalRoles(discord.ui.Modal, title="Rôles par niveau"):
    def __init__(self, roles_actuels):
        super().__init__()
        valeur = "\n".join(
            f"{n}={r}" for n, r in sorted(roles_actuels.items(), key=lambda x: int(x[0]))
        ) if roles_actuels else ""
        self.champ = discord.ui.TextInput(
            label="Format : niveau=NomDuRôle (un par ligne)",
            placeholder="5=Recrue\n10=Membre\n20=Veteran\n50=Legende",
            default=valeur,
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500
        )
        self.add_item(self.champ)

    async def on_submit(self, interaction: discord.Interaction):
        texte = self.champ.value.strip()
        roles, erreurs = {}, []
        for ligne in texte.splitlines():
            ligne = ligne.strip()
            if not ligne: continue
            if "=" not in ligne:
                erreurs.append(f"`{ligne}`")
                continue
            niv, nom = ligne.split("=", 1)
            try:
                roles[str(int(niv.strip()))] = nom.strip()
            except ValueError:
                erreurs.append(f"`{ligne}`")
        set_config(interaction.guild_id, "roles_niveaux", roles)
        msg = f"✅ **{len(roles)} association(s)** enregistrée(s)."
        if erreurs:
            msg += "\n⚠️ Lignes ignorées : " + ", ".join(erreurs)
        await interaction.response.send_message(msg, ephemeral=True)


class ModalShopAjouter(discord.ui.Modal, title="Ajouter un article au shop"):
    def __init__(self):
        super().__init__()
        self.nom  = discord.ui.TextInput(label="Nom exact du rôle", placeholder="ex: VIP", required=True, max_length=50)
        self.prix = discord.ui.TextInput(label="Prix en coins 💵",  placeholder="ex: 500",  required=True, max_length=6)
        self.add_item(self.nom)
        self.add_item(self.prix)

    async def on_submit(self, interaction: discord.Interaction):
        nom_role = self.nom.value.strip()
        try:
            prix = int(self.prix.value.strip())
            if prix <= 0:
                await interaction.response.send_message("❌ Le prix doit être supérieur à 0 !", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("❌ Prix invalide !", ephemeral=True)
            return
        role = discord.utils.get(interaction.guild.roles, name=nom_role)
        if not role:
            role = await interaction.guild.create_role(name=nom_role)
            await interaction.followup.send(f"✅ Rôle **{nom_role}** créé automatiquement !", ephemeral=True)
        shop = get_shop(interaction.guild_id)
        shop[nom_role] = prix
        set_shop(interaction.guild_id, shop)
        await interaction.response.send_message(f"✅ **{nom_role}** ajouté au shop pour **{prix} 💵** !", ephemeral=True)


class ModalShopSupprimer(discord.ui.Modal, title="Supprimer un article du shop"):
    def __init__(self, shop_actuel):
        super().__init__()
        articles  = "\n".join(f"{n} ({p} 💵)" for n, p in shop_actuel.items()) if shop_actuel else "Aucun article"
        self.champ = discord.ui.TextInput(label="Nom du rôle à supprimer", placeholder="ex: VIP", required=True, max_length=50)
        self.info  = discord.ui.TextInput(label="Articles actuels (lecture seule)", default=articles, required=False, style=discord.TextStyle.paragraph, max_length=500)
        self.add_item(self.champ)
        self.add_item(self.info)

    async def on_submit(self, interaction: discord.Interaction):
        nom_role = self.champ.value.strip()
        shop = get_shop(interaction.guild_id)
        if nom_role not in shop:
            await interaction.response.send_message(f"❌ **{nom_role}** n'est pas dans le shop !", ephemeral=True)
            return
        del shop[nom_role]
        set_shop(interaction.guild_id, shop)
        await interaction.response.send_message(f"✅ **{nom_role}** supprimé du shop !", ephemeral=True)


# ══════════════════════════════════════════════
# SOUS-MENU SHOP
# ══════════════════════════════════════════════

class SelectShop(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Ajouter un article",  emoji="➕", value="ajouter",  description="Ajouter un rôle au shop"),
            discord.SelectOption(label="Supprimer un article", emoji="➖", value="supprimer", description="Retirer un rôle du shop"),
            discord.SelectOption(label="Voir le shop actuel",  emoji="👁️", value="voir",     description="Afficher les articles"),
            discord.SelectOption(label="← Retour",             emoji="↩️", value="retour",   description="Retour au menu principal"),
        ]
        super().__init__(placeholder="🛒 Gérer le shop...", options=options)

    async def callback(self, interaction: discord.Interaction):
        choix = self.values[0]
        if choix == "ajouter":
            await interaction.response.send_modal(ModalShopAjouter())
        elif choix == "supprimer":
            await interaction.response.send_modal(ModalShopSupprimer(get_shop(interaction.guild_id)))
        elif choix == "voir":
            shop = get_shop(interaction.guild_id)
            if not shop:
                await interaction.response.send_message("❌ Le shop est vide !", ephemeral=True)
                return
            desc  = "\n".join(f"🎭 **{n}** — {p} 💵" for n, p in sorted(shop.items(), key=lambda x: x[1]))
            embed = discord.Embed(title="🛒 Shop actuel", description=desc, color=discord.Color.gold(), timestamp=datetime.utcnow())
            await interaction.response.send_message(embed=embed, ephemeral=True)
        elif choix == "retour":
            await interaction.response.edit_message(view=VueConfig())


class VueShop(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(SelectShop())

    @discord.ui.button(label="✖ Fermer", style=discord.ButtonStyle.danger, row=1)
    async def fermer(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.message.delete()


# ══════════════════════════════════════════════
# SOUS-MENU LOGS
# ══════════════════════════════════════════════

class SelectLogs(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Logs modération",  emoji="🛡️", value="logs_moderation", description="Ban, kick, warn..."),
            discord.SelectOption(label="Logs messages",    emoji="💬", value="logs_messages",   description="Édition et suppression"),
            discord.SelectOption(label="Logs membres",     emoji="👥", value="logs_membres",    description="Arrivées et départs"),
            discord.SelectOption(label="Logs vocal",       emoji="🎤", value="logs_vocal",      description="Connexions/déconnexions vocal"),
            discord.SelectOption(label="Logs rôles",       emoji="🎭", value="logs_roles",      description="Ajout/suppression de rôles"),
            discord.SelectOption(label="Logs salons",      emoji="📁", value="logs_salons",     description="Création/suppression de salons"),
            discord.SelectOption(label="Logs pseudos",     emoji="✏️", value="logs_pseudos",    description="Changements de pseudos"),
            discord.SelectOption(label="← Retour",         emoji="↩️", value="retour",          description="Retour au menu principal"),
        ]
        super().__init__(placeholder="📋 Configurer les logs...", options=options)

    async def callback(self, interaction: discord.Interaction):
        cfg   = get_config(interaction.guild_id)
        choix = self.values[0]
        if choix == "retour":
            await interaction.response.edit_message(view=VueConfig())
            return
        titres = {
            "logs_moderation": "Logs modération",
            "logs_messages":   "Logs messages",
            "logs_membres":    "Logs membres",
            "logs_vocal":      "Logs vocal",
            "logs_roles":      "Logs rôles",
            "logs_salons":     "Logs salons",
            "logs_pseudos":    "Logs pseudos",
        }
        await interaction.response.send_modal(
            ModalSalonId(choix, titres[choix], "ID du salon (vide pour désactiver)", cfg.get(choix) or "")
        )


class VueLogs(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(SelectLogs())

    @discord.ui.button(label="✖ Fermer", style=discord.ButtonStyle.danger, row=1)
    async def fermer(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.message.delete()


# ══════════════════════════════════════════════
# MENU PRINCIPAL
# ══════════════════════════════════════════════

class SelectCategorie(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Salon de bienvenue",   emoji="👋", value="bienvenue",    description="Définir le salon de bienvenue"),
            discord.SelectOption(label="Logs",                  emoji="📋", value="logs",         description="Configurer les salons de logs"),
            discord.SelectOption(label="Catégorie des tickets", emoji="🎫", value="tickets",      description="Définir la catégorie des tickets"),
            discord.SelectOption(label="Salon anniversaires",   emoji="🎂", value="anniversaire", description="Définir le salon des anniversaires"),
            discord.SelectOption(label="Salon suggestions",     emoji="💡", value="suggestions",  description="Définir le salon des suggestions"),
            discord.SelectOption(label="XP par message",        emoji="⭐", value="xp",           description="Modifier l'XP gagnée par message"),
            discord.SelectOption(label="Seuil anti-spam",       emoji="🚫", value="antispam",     description="Modifier le seuil anti-spam"),
            discord.SelectOption(label="Rôles par niveau",      emoji="🎭", value="roles",        description="Associer des rôles aux niveaux"),
            discord.SelectOption(label="Shop",                  emoji="🛒", value="shop",         description="Gérer la boutique de rôles"),
        ]
        super().__init__(placeholder="⚙️ Que veux-tu configurer ?", options=options)

    async def callback(self, interaction: discord.Interaction):
        cfg   = get_config(interaction.guild_id)
        choix = self.values[0]

        if choix == "bienvenue":
            await interaction.response.send_modal(ModalSalonId("salon_bienvenue",   "Salon de bienvenue",       "ID du salon",       cfg["salon_bienvenue"]   or ""))
        elif choix == "logs":
            await interaction.response.edit_message(view=VueLogs())
        elif choix == "tickets":
            await interaction.response.send_modal(ModalSalonId("categorie_tickets", "Catégorie des tickets",    "ID de la catégorie", cfg["categorie_tickets"] or ""))
        elif choix == "anniversaire":
            await interaction.response.send_modal(ModalSalonId("salon_anniversaire","Salon des anniversaires",  "ID du salon",        cfg.get("salon_anniversaire") or ""))
        elif choix == "suggestions":
            await interaction.response.send_modal(ModalSalonId("salon_suggestions", "Salon des suggestions",    "ID du salon",        cfg.get("salon_suggestions")  or ""))
        elif choix == "xp":
            await interaction.response.send_modal(ModalNombre("xp_par_message",   "XP par message",            "XP (entre 1 et 100)",               str(cfg["xp_par_message"]),   1,  100))
        elif choix == "antispam":
            await interaction.response.send_modal(ModalNombre("seuil_anti_spam",  "Seuil anti-spam",           "Messages max / 5 secondes (2-20)",  str(cfg["seuil_anti_spam"]),  2,  20))
        elif choix == "roles":
            await interaction.response.send_modal(ModalRoles(cfg["roles_niveaux"]))
        elif choix == "shop":
            await interaction.response.edit_message(view=VueShop())


class VueConfig(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(SelectCategorie())

    @discord.ui.button(label="✖ Fermer", style=discord.ButtonStyle.danger, row=1)
    async def fermer(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.message.delete()


# ══════════════════════════════════════════════
# MENU AIDE
# ══════════════════════════════════════════════

PAGES_HELP = {
    "moderation": {
        "titre": "🛡️ Modération",
        "desc":  "Commandes réservées aux modérateurs.",
        "color": discord.Color.red(),
        "cmds": [
            ("`/kick`",   "Expulser un membre"),
            ("`/ban`",    "Bannir un membre"),
            ("`/unban`",  "Débannir un membre"),
            ("`/warn`",   "Avertir un membre"),
            ("`/modlog`", "Historique des sanctions"),
            ("`/clear`",  "Supprimer des messages"),
            ("`/nick`",   "Changer le pseudo d'un membre"),
            ("`/dm`",     "Envoyer un DM à un membre"),
            ("`/mute`",   "Rendre muet un membre"),
            ("`/unmute`", "Retirer le mute"),
        ]
    },
    "niveaux": {
        "titre": "⭐ Niveaux & XP",
        "desc":  "Gagne de l'XP en chattant !",
        "color": discord.Color.gold(),
        "cmds": [
            ("`/niveau`",            "Voir ton niveau et ton XP"),
            ("`/top`",               "Classement des membres actifs"),
            ("`/leaderboard_vocal`", "Classement du temps en vocal"),
        ]
    },
    "economie": {
        "titre": "💵 Économie",
        "desc":  "Gagne et dépense des coins !",
        "color": discord.Color.green(),
        "cmds": [
            ("`/solde`",    "Voir ton solde (cash + banque)"),
            ("`/daily`",    "Récompense quotidienne"),
            ("`/weekly`",   "Récompense hebdomadaire"),
            ("`/work`",     "Travailler pour gagner des coins"),
            ("`/deposer`",  "Déposer en banque"),
            ("`/retirer`",  "Retirer de la banque"),
            ("`/payer`",    "Payer un membre"),
            ("`/gamble`",   "Jouer au casino"),
            ("`/coinflip`", "Pile ou face"),
            ("`/rob`",      "Tenter de voler un membre"),
            ("`/richesse`", "Classement des plus riches"),
        ]
    },
    "shop": {
        "titre": "🛒 Shop",
        "desc":  "Achète des rôles avec tes coins !",
        "color": discord.Color.orange(),
        "cmds": [
            ("`/shop`",       "Voir la boutique"),
            ("`/buy`",        "Acheter un rôle"),
            ("`/inventaire`", "Voir tes rôles achetés"),
        ]
    },
    "roles": {
        "titre": "🎭 Rôles",
        "desc":  "Panels de rôles cliquables.",
        "color": discord.Color.purple(),
        "cmds": [
            ("`/role-panel`",  "Créer un panel de rôles"),
            ("`/role-add`",    "Ajouter un bouton rôle"),
            ("`/role-remove`", "Retirer un bouton rôle"),
            ("`/role-list`",   "Lister les panels"),
        ]
    },
    "tickets": {
        "titre": "🎫 Tickets",
        "desc":  "Système de support.",
        "color": discord.Color.blurple(),
        "cmds": [
            ("`/ticket-panel`",  "Envoyer le panel d'ouverture"),
            ("`/ticket-add`",    "Ajouter un membre au ticket"),
            ("`/ticket-remove`", "Retirer un membre du ticket"),
        ]
    },
    "divers": {
        "titre": "🔧 Divers",
        "desc":  "Commandes utilitaires et autres.",
        "color": discord.Color.teal(),
        "cmds": [
            ("`/anniversaire_set`", "Enregistrer ton anniversaire"),
            ("`/anniversaire`",     "Voir l'anniversaire d'un membre"),
            ("`/anniversaires`",    "Liste des anniversaires du mois"),
            ("`/missions`",         "Voir tes missions"),
            ("`/missions_claim`",   "Réclamer une récompense de mission"),
            ("`/suggestion`",       "Faire une suggestion"),
            ("`/say`",              "Faire parler le bot"),
            ("`/announce`",         "Faire une annonce"),
            ("`/snipe`",            "Voir le dernier message supprimé"),
            ("`/stats_bot`",        "Statistiques du bot"),
        ]
    },
}


class SelectHelp(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="🛡️ Modération",  value="moderation", description="Kick, ban, warn, clear..."),
            discord.SelectOption(label="⭐ Niveaux & XP", value="niveaux",    description="Niveau, classement, vocal..."),
            discord.SelectOption(label="💵 Économie",     value="economie",   description="Daily, work, gamble, rob..."),
            discord.SelectOption(label="🛒 Shop",         value="shop",       description="Boutique de rôles"),
            discord.SelectOption(label="🎭 Rôles",        value="roles",      description="Panels de rôles cliquables"),
            discord.SelectOption(label="🎫 Tickets",      value="tickets",    description="Système de support"),
            discord.SelectOption(label="🔧 Divers",       value="divers",     description="Anniversaires, missions, utils..."),
        ]
        super().__init__(placeholder="📂 Choisir une catégorie...", options=options)

    async def callback(self, interaction: discord.Interaction):
        page  = PAGES_HELP[self.values[0]]
        embed = discord.Embed(
            title       = page["titre"],
            description = page["desc"],
            color       = page["color"],
            timestamp   = datetime.utcnow()
        )
        for cmd, desc in page["cmds"]:
            embed.add_field(name=cmd, value=desc, inline=True)
        embed.set_footer(text="KatsuBot • /help")
        await interaction.response.edit_message(embed=embed, view=VueHelp())


class VueHelp(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(SelectHelp())

    @discord.ui.button(label="✖ Fermer", style=discord.ButtonStyle.danger, row=1)
    async def fermer(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.message.delete()


# ══════════════════════════════════════════════
# COG
# ══════════════════════════════════════════════

class Configuration(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /config ────────────────────────────────

    @app_commands.command(name="config", description="Ouvre le panneau de configuration du bot")
    @app_commands.checks.has_permissions(administrator=True)
    async def config(self, interaction: discord.Interaction):
        cfg   = get_config(interaction.guild_id)
        guild = interaction.guild

        def nom_canal(id_):
            if not id_: return "❌ Non configuré"
            c = guild.get_channel(int(id_))
            return c.mention if c else "❌ Introuvable"

        shop      = get_shop(interaction.guild_id)
        roles     = cfg["roles_niveaux"]
        roles_txt = " | ".join(f"Niv.{n}→{r}" for n, r in sorted(roles.items(), key=lambda x: int(x[0]))) if roles else "Aucun"
        shop_txt  = " | ".join(f"{n} ({p} 💵)" for n, p in shop.items()) if shop else "Aucun article"

        logs_noms = {
            "logs_moderation": "🛡️ Modération",
            "logs_messages":   "💬 Messages",
            "logs_membres":    "👥 Membres",
            "logs_vocal":      "🎤 Vocal",
            "logs_roles":      "🎭 Rôles",
            "logs_salons":     "📁 Salons",
            "logs_pseudos":    "✏️ Pseudos",
        }
        logs_cfg = ""
        for cle, nom in logs_noms.items():
            val   = cfg.get(cle)
            canal = guild.get_channel(int(val)) if val else None
            logs_cfg += f"{nom} → {canal.mention if canal else '❌'}\n"

        embed = discord.Embed(
            title       = "⚙️ Configuration de KatsuBot",
            color       = discord.Color.blurple(),
            timestamp   = datetime.utcnow()
        )
        embed.set_author(name=guild.name, icon_url=guild.icon.url if guild.icon else None)
        embed.add_field(name="👋 Bienvenue",     value=nom_canal(cfg["salon_bienvenue"]),         inline=True)
        embed.add_field(name="🎫 Tickets",       value=nom_canal(cfg["categorie_tickets"]),       inline=True)
        embed.add_field(name="🎂 Anniversaires", value=nom_canal(cfg.get("salon_anniversaire")),  inline=True)
        embed.add_field(name="💡 Suggestions",   value=nom_canal(cfg.get("salon_suggestions")),   inline=True)
        embed.add_field(name="⭐ XP / message",  value=str(cfg["xp_par_message"]),                inline=True)
        embed.add_field(name="🚫 Anti-spam",     value=f"{cfg['seuil_anti_spam']} msg/5s",        inline=True)
        embed.add_field(name="🎭 Rôles / niv.",  value=roles_txt,                                 inline=False)
        embed.add_field(name="🛒 Shop",          value=shop_txt,                                  inline=False)
        embed.add_field(name="📋 Logs",          value=logs_cfg or "❌ Aucun configuré",           inline=False)
        embed.set_footer(text="Utilise le menu ci-dessous pour modifier les paramètres")

        await interaction.response.send_message(embed=embed, view=VueConfig(), ephemeral=True)

    # ── /help ──────────────────────────────────

    @app_commands.command(name="help", description="Affiche toutes les commandes disponibles")
    async def aide(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title       = "📖 Aide — KatsuBot",
            description = "Sélectionne une catégorie dans le menu ci-dessous pour voir les commandes !",
            color       = discord.Color.blurple(),
            timestamp   = datetime.utcnow()
        )
        embed.set_author(name=interaction.guild.name, icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
        embed.set_footer(text="Tu gagnes de l'XP en écrivant dans les salons !")
        await interaction.response.send_message(embed=embed, view=VueHelp())

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            message = "❌ Tu n'as pas la permission d'utiliser cette commande."
        else:
            message = f"⚠️ Une erreur est survenue : {error}"
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.NotFound:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Configuration(bot))