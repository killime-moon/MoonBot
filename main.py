import os
import discord
from discord.ext import commands
import requests
import asyncio
import threading
import random
import re
from flask import Flask

# --- KEEP-ALIVE (optionnel) ---
app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is alive!"
def start():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
threading.Thread(target=start).start()
# -------------------------------

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

bot_frozen = False  # État du gel

PECHEURS_ROLE = "Pécheurs"
PECHE_S_CAPITAUX = [
    "Luxure", "Colère", "Envie", "Paresse", "Orgueil", "Gourmandise", "Avarice"
]
JEUX_ROLES = ["Valorant", "Genshin Impact", "Resident evil", "Minecraft", "Red Dead", "Roblox", "Jeux indépendants"]

def find_role_by_name(guild, name):
    return discord.utils.find(lambda r: r.name.lower() == name.lower(), guild.roles)

async def fetch_annonces_messages():
    await bot.wait_until_ready()
    if not bot.guilds:
        return []
    guild = bot.guilds[0]
    channel = discord.utils.get(guild.text_channels, name="「📆」annonces")
    if not channel:
        return []
    messages_data = []
    async for msg in channel.history(limit=3):
        try:
            avatar = msg.author.display_avatar.url
        except Exception:
            avatar = msg.author.avatar.url if msg.author.avatar else msg.author.default_avatar.url
        attachments = [a.url for a in msg.attachments] if msg.attachments else []
        messages_data.append({
            "author_name": msg.author.display_name,
            "author_avatar": avatar,
            "content": msg.content,
            "attachments": attachments
        })
    return messages_data

async def build_players(guild):
    role_pecheurs = find_role_by_name(guild, PECHEURS_ROLE)
    players = {}
    for peche in PECHE_S_CAPITAUX:
        role_peche = find_role_by_name(guild, peche)
        if not role_peche:
            players[peche] = {"name": "Place vacante", "avatar": None}
            continue
        joueur = None
        for member in guild.members:
            if role_pecheurs in member.roles and role_peche in member.roles:
                joueur = member
                break
        if not joueur:
            try:
                async for member in guild.fetch_members(limit=None):
                    if role_pecheurs in member.roles and role_peche in member.roles:
                        joueur = member
                        break
            except Exception as e:
                print(f"[build_players] Erreur fetch_members: {e}")
        if joueur:
            try:
                avatar = joueur.display_avatar.url
            except Exception:
                avatar = joueur.avatar.url if joueur.avatar else joueur.default_avatar.url
            players[peche] = {"name": joueur.display_name, "avatar": avatar}
        else:
            players[peche] = {"name": "Place vacante", "avatar": None}
    return players

async def build_apotres(guild):
    role_apotre = find_role_by_name(guild, "Apotre")
    if not role_apotre:
        return {peche: [] for peche in PECHE_S_CAPITAUX}
    apotres = {peche: [] for peche in PECHE_S_CAPITAUX}
    for peche in PECHE_S_CAPITAUX:
        role_peche = find_role_by_name(guild, peche)
        if not role_peche:
            continue
        for member in guild.members:
            if role_apotre in member.roles and role_peche in member.roles:
                try:
                    avatar = member.display_avatar.url
                except Exception:
                    avatar = member.avatar.url if member.avatar else member.default_avatar.url
                apotres[peche].append({"name": member.display_name, "avatar": avatar})
    return apotres

async def build_membres(guild):
    role_membres = find_role_by_name(guild, "Membres")
    if not role_membres:
        return []
    membres_list = []
    for member in guild.members:
        if role_membres in member.roles:
            try:
                avatar = member.display_avatar.url
            except Exception:
                avatar = member.avatar.url if member.avatar else member.default_avatar.url
            roles = [r.name for r in member.roles if r.name != "@everyone"]
            membres_list.append({
                "name": member.display_name,
                "realname": member.name,
                "avatar": avatar,
                "roles": roles
            })
    return membres_list

async def build_classement(guild):
    classement = []
    for peche in PECHE_S_CAPITAUX:
        role_peche = find_role_by_name(guild, peche)
        if not role_peche:
            classement.append({"peche": peche, "count": 0})
            continue
        count = len(role_peche.members)
        if count == 0:
            try:
                async for m in guild.fetch_members(limit=None):
                    if role_peche in m.roles:
                        count += 1
            except Exception as e:
                print(f"[build_classement] fetch_members erreur: {e}")
        classement.append({"peche": peche, "count": count})
    classement.sort(key=lambda x: x["count"], reverse=True)
    return classement

async def build_classement_jeux(guild):
    classement = []
    for jeu in JEUX_ROLES:
        role_jeu = find_role_by_name(guild, jeu)
        if not role_jeu:
            classement.append({"jeu": jeu, "count": 0})
            continue
        count = len(role_jeu.members)
        if count == 0:
            try:
                async for m in guild.fetch_members(limit=None):
                    if role_jeu in m.roles:
                        count += 1
            except Exception as e:
                print(f"[build_classement_jeux] fetch_members erreur: {e}")
        classement.append({"jeu": jeu, "count": count})
    classement.sort(key=lambda x: x["count"], reverse=True)
    return classement

async def periodic_task():
    await bot.wait_until_ready()
    print("[Bot] Tâche périodique démarrée")
    while not bot.is_closed():
        try:
            if bot_frozen:
                await asyncio.sleep(60)
                continue
            if not bot.is_ready():
                await asyncio.sleep(10)
                continue
            if not bot.guilds:
                await asyncio.sleep(30)
                continue

            app_info = await bot.application_info()
            owner_name = app_info.owner.name
            guild = bot.guilds[0]
            players = await build_players(guild)
            annonces = await fetch_annonces_messages()
            classement = await build_classement(guild)
            classement_jeux = await build_classement_jeux(guild)
            apotres = await build_apotres(guild)
            membres = await build_membres(guild)

            payload = {
                "owner": owner_name,
                "players": players,
                "apotres": apotres,
                "annonces": annonces,
                "ClassementPeche": classement,
                "ClassementJeux": classement_jeux,
                "membres": membres,
            }

            url = os.environ.get("API_URL", "https://siteapi-2.onrender.com/update")
            try:
                response = requests.post(url, json=payload, timeout=10)
                if response.status_code == 200:
                    print("[API] ✅ Données envoyées (avec annonces)")
                else:
                    print(f"[API] ⚠️ Code {response.status_code} : {response.text}")
            except Exception as e:
                print(f"[API] ❌ Erreur envoi annonces : {e}")

        except Exception as e:
            print(f"[Erreur] tâche périodique : {e}")

        await asyncio.sleep(300)

@bot.event
async def on_ready():
    print(f"Bot connecté en tant que {bot.user}")
    print(f"Connecté à {len(bot.guilds)} serveur(s)")
    bot.loop.create_task(periodic_task())

@bot.command(name="stop")
@commands.is_owner()
async def stop(ctx):
    global bot_frozen
    bot_frozen = True
    await ctx.send("🔒 Bot gelé. Il ignore tout jusqu'au prochain redémarrage.")

@bot.command(name="classement")
async def classement(ctx):
    guild = ctx.guild
    classement = []
    for peche in PECHE_S_CAPITAUX:
        role_peche = find_role_by_name(guild, peche)
        if not role_peche:
            classement.append((peche, 0))
            continue
        count = len(role_peche.members)
        if count == 0:
            count = 0
            try:
                async for m in guild.fetch_members(limit=None):
                    if role_peche in m.roles:
                        count += 1
            except Exception as e:
                print(f"[classement] fetch_members erreur: {e}")
        classement.append((peche, count))
    classement.sort(key=lambda x: x[1], reverse=True)
    msg = "**Classement des péchés capitaux (par nombre de membres) :**\n"
    for i, (peche, count) in enumerate(classement, 1):
        msg += f"**{i}. {peche}** — {count} membre(s)\n"
    await ctx.send(msg)

@bot.command(name="classement-jeux")
async def classement_jeux(ctx):
    guild = ctx.guild
    classement = await build_classement_jeux(guild)
    msg = "**Classement des jeux (par nombre de membres) :**\n"
    for i, entry in enumerate(classement, 1):
        msg += f"**{i}. {entry['jeu']}** — {entry['count']} membre(s)\n"
    await ctx.send(msg)

@bot.command(name="tg")
async def tg(ctx):
    msg = "**tg avec ton goumin de con tfaçon c'est qu'une pute**\n"
    await ctx.send(msg)

@bot.command(name="phoebe")
async def phoebe(ctx):
    msg = "https://tenor.com/view/want-demand-gif-12030398"
    await ctx.send(msg)

@bot.command(name="love")
async def love(ctx, member: discord.Member):
    pourcentage = random.randint(0, 100)
    await ctx.send(f"💖 Test d'amour entre **{ctx.author.display_name}** et **{member.display_name}** : {pourcentage}% 💖")

@bot.command(name="moon.update")
@commands.is_owner()
async def force_update(ctx):
    await ctx.send("Envoi manuel en cours...")
    guild = ctx.guild or (bot.guilds[0] if bot.guilds else None)
    if not guild:
        await ctx.send("Aucun serveur disponible.")
        return
    app_info = await bot.application_info()
    owner_name = app_info.owner.name
    players = await build_players(guild)
    annonces = await fetch_annonces_messages()
    classement = await build_classement(guild)
    classement_jeux = await build_classement_jeux(guild)
    apotres = await build_apotres(guild)
    membres = await build_membres(guild)
    payload = {
        "owner": owner_name,
        "players": players,
        "apotres": apotres,
        "annonces": annonces,
        "ClassementPeche": classement,
        "ClassementJeux": classement_jeux,
        "membres": membres,
    }
    url = os.environ.get("API_URL", "https://siteapi-2.onrender.com/update")
    try:
        r = requests.post(url, json=payload, timeout=10)
        await ctx.send(f"API status: {r.status_code}")
    except Exception as e:
        await ctx.send(f"Erreur envoi: {e}")

def ressemble_bonjour(texte):
    texte = texte.lower()
    texte = re.sub(r'(.)\1+', r'\1', texte)
    return "bonjour" in texte

@bot.event
async def on_message(message):
    if bot_frozen:
        return  # Ignore absolument tout

    if message.author == bot.user:
        return

    if bot.user.mentioned_in(message) or ressemble_bonjour(message.content):
        reponses = [
            "Tg gros con",
            "T'as cru t'avais des potes ?",
            "Franchement ferme là",
            "ok.",
        ]
        await message.channel.send(random.choice(reponses))

    await bot.process_commands(message)

@bot.event
async def on_member_remove(member):
    channel = discord.utils.get(member.guild.text_channels, name="「💬」général")
    if channel:
        await channel.send(f"👋 **{member.display_name}** vient de quitter le serveur. Bon débarras (ou pas) !")

@bot.command(name="sentence")
@commands.has_permissions(kick_members=True)
async def sentence(ctx, member: discord.Member):
    sanctions = ["rien", "kick", "ban"]
    choix = random.choice(sanctions)
    if choix == "rien":
        await ctx.send(f"⚖️ {member.mention} est jugé... **innocent** ! Aucune sanction cette fois. 🍀")
    elif choix == "kick":
        await member.kick(reason="Sentence aléatoire !")
        await ctx.send(f"👢 {member.mention} a été **kick** ! Le destin en a décidé ainsi.")
    elif choix == "ban":
        duree_jours = random.choice([1, 3, 7, 14, 30])
        await ctx.send(f"🔨 {member.mention} a été **banni pour {duree_jours} jour(s)** ! La justice est aveugle.")
        await member.ban(reason=f"Sentence aléatoire ({duree_jours}j)")
        await asyncio.sleep(duree_jours * 86400)
        await ctx.guild.unban(member)

@sentence.error
async def sentence_error(ctx, error):
    if isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Membre introuvable. Mentionne quelqu'un du serveur.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("🚫 T'as pas les droits pour ça.")

token = os.environ.get('TOKEN')
if not token:
    print("Erreur : variable d'environnement TOKEN absente ou vide.")
    exit(1)
bot.run(token)
