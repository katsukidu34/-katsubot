"""
cogs/economie.py — Système d'économie (JSON only)
"""

import discord
import random
from discord import app_commands
from discord.ext import commands
from datetime import datetime

from config import get_compte, save_compte, charger_eco

SYMBOLE = "💵"

def fmt(montant: int) -> str:
    return f"{montant:,} {SYMBOLE}".replace(",", " ")

def embed_base(title: str, color=discord.Color.gold()) -> discord.Embed:
    return discord.Embed(title=title, color=color, timestamp=datetime.utcnow())


class VueCoinflip(discord.ui.View):
    def __init__(self, user_id: int, mise: int, guild_id: int):
        super().__init__(timeout=30)
        self.user_id  = user_id
        self.mise     = mise
        self.guild_id = guild_id

    @discord.ui.button(label="🪙 Pile", style=discord.ButtonStyle.primary)
    async def pile(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.jouer(interaction, "pile")

    @discord.ui.button(label="🪙 Face", style=discord.ButtonStyle.secondary)
    async def face(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.jouer(interaction, "face")

    async def jouer(self, interaction: discord.Interaction, choix: str):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Ce n'est pas ton jeu !", ephemeral=True)
            return
        compte = get_compte(self.guild_id, self.user_id)
        if compte["cash"] < self.mise:
            await interaction.response.send_message("❌ Plus assez de cash !", ephemeral=True)
            return
        resultat = random.choice(["pile", "face"])
        gagne    = choix == resultat
        if gagne:
            compte["cash"] += self.mise
            titre = "🎉 Tu as gagné !"
            color = discord.Color.green()
            desc  = f"Résultat : **{resultat}** — tu avais choisi **{choix}** !\n\n+{fmt(self.mise)}"
        else:
            compte["cash"] -= self.mise
            titre = "😢 Tu as perdu !"
            color = discord.Color.red()
            desc  = f"Résultat : **{resultat}** — tu avais choisi **{choix}** !\n\n-{fmt(self.mise)}"
        save_compte(self.guild_id, self.user_id, compte)
        for item in self.children:
            item.disabled = True
        embed = embed_base(titre, color)
        embed.description = desc
        embed.set_footer(text=f"Solde : {fmt(compte['cash'])}")
        await interaction.response.edit_message(embed=embed, view=self)


class Economie(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="solde", description="Affiche ton solde")
    @app_commands.describe(membre="Le membre à consulter (toi par défaut)")
    async def solde(self, interaction: discord.Interaction, membre: discord.Member = None):
        cible  = membre or interaction.user
        compte = get_compte(interaction.guild_id, cible.id)
        total  = compte["cash"] + compte["banque"]
        embed  = embed_base(f"💰 Solde de {cible.display_name}")
        embed.set_thumbnail(url=cible.display_avatar.url)
        embed.add_field(name="👛 Cash",   value=fmt(compte["cash"]),   inline=True)
        embed.add_field(name="🏦 Banque", value=fmt(compte["banque"]), inline=True)
        embed.add_field(name="💎 Total",  value=fmt(total),            inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="daily", description="Récupère ta récompense quotidienne")
    async def daily(self, interaction: discord.Interaction):
        compte = get_compte(interaction.guild_id, interaction.user.id)
        now    = datetime.utcnow().timestamp()
        if now - compte["daily_last"] < 86400:
            restant = 86400 - (now - compte["daily_last"])
            h, m    = int(restant // 3600), int((restant % 3600) // 60)
            embed   = embed_base("⏰ Daily déjà récupéré", discord.Color.orange())
            embed.description = f"Disponible dans **{h}h {m}min** !"
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        gain = random.randint(100, 500)
        compte["cash"]      += gain
        compte["daily_last"] = now
        save_compte(interaction.guild_id, interaction.user.id, compte)
        embed = embed_base("🎁 Daily récupéré !", discord.Color.green())
        embed.description = f"Tu as reçu **{fmt(gain)}** !\n💰 Nouveau solde : {fmt(compte['cash'])}"
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="weekly", description="Récupère ta récompense hebdomadaire")
    async def weekly(self, interaction: discord.Interaction):
        compte = get_compte(interaction.guild_id, interaction.user.id)
        now    = datetime.utcnow().timestamp()
        if now - compte["weekly_last"] < 604800:
            restant = 604800 - (now - compte["weekly_last"])
            j, h    = int(restant // 86400), int((restant % 86400) // 3600)
            embed   = embed_base("⏰ Weekly déjà récupéré", discord.Color.orange())
            embed.description = f"Disponible dans **{j}j {h}h** !"
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        gain = random.randint(1000, 3000)
        compte["cash"]       += gain
        compte["weekly_last"] = now
        save_compte(interaction.guild_id, interaction.user.id, compte)
        embed = embed_base("🎁 Weekly récupéré !", discord.Color.green())
        embed.description = f"Tu as reçu **{fmt(gain)}** !\n💰 Nouveau solde : {fmt(compte['cash'])}"
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="work", description="Travailler pour gagner de l'argent (cooldown 1h)")
    async def work(self, interaction: discord.Interaction):
        compte = get_compte(interaction.guild_id, interaction.user.id)
        now    = datetime.utcnow().timestamp()
        if now - compte["work_last"] < 3600:
            minutes = int((3600 - (now - compte["work_last"])) // 60)
            embed   = embed_base("⏰ Déjà au travail !", discord.Color.orange())
            embed.description = f"Disponible dans **{minutes} minutes** !"
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        metiers = [
            ("🍕 Livreur de pizza", 50, 150), ("💻 Développeur", 200, 500),
            ("🎮 Joueur pro", 100, 300),       ("🎵 DJ", 80, 250),
            ("🚗 Chauffeur Uber", 60, 180),    ("🍔 Cuisinier", 40, 120),
        ]
        metier, min_g, max_g = random.choice(metiers)
        gain = random.randint(min_g, max_g)
        compte["cash"]     += gain
        compte["work_last"] = now
        save_compte(interaction.guild_id, interaction.user.id, compte)
        embed = embed_base("💼 Travail effectué !", discord.Color.green())
        embed.description = f"{metier}\nTu as gagné **{fmt(gain)}** !\n💰 Solde : {fmt(compte['cash'])}"
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="deposer", description="Déposer de l'argent en banque")
    @app_commands.describe(montant="Montant à déposer (ou 'tout')")
    async def deposer(self, interaction: discord.Interaction, montant: str):
        compte = get_compte(interaction.guild_id, interaction.user.id)
        somme  = compte["cash"] if montant.lower() in ("tout", "all", "max") else int(montant) if montant.isdigit() else -1
        if somme <= 0 or somme > compte["cash"]:
            await interaction.response.send_message("❌ Montant invalide !", ephemeral=True)
            return
        compte["cash"]   -= somme
        compte["banque"] += somme
        save_compte(interaction.guild_id, interaction.user.id, compte)
        embed = embed_base("🏦 Dépôt effectué !", discord.Color.green())
        embed.add_field(name="💸 Déposé", value=fmt(somme),            inline=True)
        embed.add_field(name="👛 Cash",   value=fmt(compte["cash"]),   inline=True)
        embed.add_field(name="🏦 Banque", value=fmt(compte["banque"]), inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="retirer", description="Retirer de l'argent de la banque")
    @app_commands.describe(montant="Montant à retirer (ou 'tout')")
    async def retirer(self, interaction: discord.Interaction, montant: str):
        compte = get_compte(interaction.guild_id, interaction.user.id)
        somme  = compte["banque"] if montant.lower() in ("tout", "all", "max") else int(montant) if montant.isdigit() else -1
        if somme <= 0 or somme > compte["banque"]:
            await interaction.response.send_message("❌ Montant invalide !", ephemeral=True)
            return
        compte["banque"] -= somme
        compte["cash"]   += somme
        save_compte(interaction.guild_id, interaction.user.id, compte)
        embed = embed_base("🏦 Retrait effectué !", discord.Color.green())
        embed.add_field(name="💸 Retiré", value=fmt(somme),            inline=True)
        embed.add_field(name="👛 Cash",   value=fmt(compte["cash"]),   inline=True)
        embed.add_field(name="🏦 Banque", value=fmt(compte["banque"]), inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="payer", description="Payer un membre")
    @app_commands.describe(membre="Le membre à payer", montant="Le montant")
    async def payer(self, interaction: discord.Interaction, membre: discord.Member, montant: int):
        if membre.id == interaction.user.id or membre.bot or montant <= 0:
            await interaction.response.send_message("❌ Paiement invalide !", ephemeral=True)
            return
        payeur = get_compte(interaction.guild_id, interaction.user.id)
        if payeur["cash"] < montant:
            await interaction.response.send_message(f"❌ Tu n'as que {fmt(payeur['cash'])} en cash !", ephemeral=True)
            return
        receveur = get_compte(interaction.guild_id, membre.id)
        payeur["cash"]   -= montant
        receveur["cash"] += montant
        save_compte(interaction.guild_id, interaction.user.id, payeur)
        save_compte(interaction.guild_id, membre.id, receveur)
        embed = embed_base("💸 Paiement effectué !", discord.Color.green())
        embed.description = f"{interaction.user.mention} a envoyé **{fmt(montant)}** à {membre.mention} !"
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="gamble", description="Jouer au casino (50% de chance de doubler)")
    @app_commands.describe(montant="Montant à miser")
    async def gamble(self, interaction: discord.Interaction, montant: int):
        compte = get_compte(interaction.guild_id, interaction.user.id)
        if montant <= 0 or montant > compte["cash"]:
            await interaction.response.send_message("❌ Mise invalide !", ephemeral=True)
            return
        gagne = random.random() < 0.5
        if gagne:
            compte["cash"] += montant
            embed = embed_base("🎰 JACKPOT !", discord.Color.green())
            embed.description = f"Tu as **gagné** {fmt(montant)} !\n💰 Solde : {fmt(compte['cash'])}"
        else:
            compte["cash"] -= montant
            embed = embed_base("🎰 Perdu !", discord.Color.red())
            embed.description = f"Tu as **perdu** {fmt(montant)} !\n💰 Solde : {fmt(compte['cash'])}"
        save_compte(interaction.guild_id, interaction.user.id, compte)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="coinflip", description="Pile ou face — double ou rien !")
    @app_commands.describe(montant="Montant à miser")
    async def coinflip(self, interaction: discord.Interaction, montant: int):
        compte = get_compte(interaction.guild_id, interaction.user.id)
        if montant <= 0 or montant > compte["cash"]:
            await interaction.response.send_message("❌ Mise invalide !", ephemeral=True)
            return
        embed = embed_base("🪙 Coinflip — Choisis !", discord.Color.gold())
        embed.description = f"Mise : **{fmt(montant)}**\nChoisis **Pile** ou **Face** !"
        await interaction.response.send_message(embed=embed, view=VueCoinflip(interaction.user.id, montant, interaction.guild_id))

    @app_commands.command(name="rob", description="Tenter de voler un membre (risqué !)")
    @app_commands.describe(membre="Le membre à voler")
    async def rob(self, interaction: discord.Interaction, membre: discord.Member):
        if membre.id == interaction.user.id or membre.bot:
            await interaction.response.send_message("❌ Impossible !", ephemeral=True)
            return
        voleur  = get_compte(interaction.guild_id, interaction.user.id)
        victime = get_compte(interaction.guild_id, membre.id)
        now     = datetime.utcnow().timestamp()
        if now - voleur["rob_last"] < 3600:
            minutes = int((3600 - (now - voleur["rob_last"])) // 60)
            await interaction.response.send_message(f"❌ Attends encore **{minutes} minutes** !", ephemeral=True)
            return
        if victime["cash"] < 100:
            await interaction.response.send_message(f"❌ {membre.display_name} n'a pas assez de cash !", ephemeral=True)
            return
        voleur["rob_last"] = now
        if random.random() < 0.4:
            vol = random.randint(50, min(500, victime["cash"] // 2))
            victime["cash"] -= vol
            voleur["cash"]  += vol
            save_compte(interaction.guild_id, interaction.user.id, voleur)
            save_compte(interaction.guild_id, membre.id, victime)
            embed = embed_base("🦹 Vol réussi !", discord.Color.green())
            embed.description = f"Tu as volé **{fmt(vol)}** à {membre.mention} !\n💰 Ton solde : {fmt(voleur['cash'])}"
        else:
            amende = random.randint(100, 300)
            voleur["cash"] = max(0, voleur["cash"] - amende)
            save_compte(interaction.guild_id, interaction.user.id, voleur)
            embed = embed_base("🚔 Vol échoué !", discord.Color.red())
            embed.description = f"Tu paies une amende de **{fmt(amende)}** !\n💰 Ton solde : {fmt(voleur['cash'])}"
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="richesse", description="Classement des membres les plus riches")
    async def richesse(self, interaction: discord.Interaction):
        await interaction.response.defer()
        eco  = charger_eco()
        gid  = str(interaction.guild_id)
        docs = eco.get(gid, {})
        if not docs:
            await interaction.followup.send("Personne n'a encore d'argent !")
            return
        classement = sorted(docs.items(), key=lambda x: x[1]["cash"] + x[1].get("banque", 0), reverse=True)[:10]
        embed = embed_base("🏆 Classement des plus riches", discord.Color.gold())
        medailles = ["🥇", "🥈", "🥉"]
        desc = ""
        for i, (uid, data) in enumerate(classement):
            try:
                user = await self.bot.fetch_user(int(uid))
                nom  = user.display_name
            except Exception:
                nom = "Utilisateur inconnu"
            total    = data["cash"] + data.get("banque", 0)
            medaille = medailles[i] if i < 3 else f"**{i+1}.**"
            desc    += f"{medaille} {nom} — {fmt(total)}\n"
        embed.description = desc
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="add-money", description="Ajouter de l'argent à un membre (admin)")
    @app_commands.describe(membre="Le membre", montant="Montant à ajouter")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_money(self, interaction: discord.Interaction, membre: discord.Member, montant: int):
        compte = get_compte(interaction.guild_id, membre.id)
        compte["cash"] += montant
        save_compte(interaction.guild_id, membre.id, compte)
        embed = embed_base("✅ Argent ajouté", discord.Color.green())
        embed.description = f"**+{fmt(montant)}** ajouté à {membre.mention}\n💰 Nouveau solde : {fmt(compte['cash'])}"
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="remove-money", description="Retirer de l'argent à un membre (admin)")
    @app_commands.describe(membre="Le membre", montant="Montant à retirer")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_money(self, interaction: discord.Interaction, membre: discord.Member, montant: int):
        compte = get_compte(interaction.guild_id, membre.id)
        compte["cash"] = max(0, compte["cash"] - montant)
        save_compte(interaction.guild_id, membre.id, compte)
        embed = embed_base("✅ Argent retiré", discord.Color.orange())
        embed.description = f"**-{fmt(montant)}** retiré à {membre.mention}\n💰 Nouveau solde : {fmt(compte['cash'])}"
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="reset-money", description="Réinitialiser l'économie d'un membre (admin)")
    @app_commands.describe(membre="Le membre à reset")
    @app_commands.checks.has_permissions(administrator=True)
    async def reset_money(self, interaction: discord.Interaction, membre: discord.Member):
        compte = get_compte(interaction.guild_id, membre.id)
        compte["cash"] = 0
        compte["banque"] = 0
        save_compte(interaction.guild_id, membre.id, compte)
        embed = embed_base("🔄 Économie réinitialisée", discord.Color.red())
        embed.description = f"L'économie de {membre.mention} a été remise à zéro."
        await interaction.response.send_message(embed=embed)

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ Tu n'as pas la permission !", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Erreur : {error}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Economie(bot))