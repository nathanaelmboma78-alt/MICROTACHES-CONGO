"""
╔══════════════════════════════════════════════════════════════╗
║     BOT TELEGRAM MICRO-TÂCHES - Paiement MTN MoMo           ║
║              Congo Brazzaville - Nathanaël                   ║
╚══════════════════════════════════════════════════════════════╝

COMMENT ÇA MARCHE :
-------------------
1. Tu publies des tâches dans le bot (cliquer, s'inscrire, regarder)
2. Les utilisateurs choisissent une tâche et la font
3. Ils envoient une preuve (capture d'écran)
4. TOI (admin) tu valides ou refuses la preuve
5. Si validé → tu paies manuellement via MTN MoMo
6. Le bot notifie automatiquement l'utilisateur

INSTALLATION :
--------------
pip install python-telegram-bot
python bot_microtaches_momo.py
"""

import logging
import json
import os
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

# ─────────────────────────────────────────────────────────────
#  ⚙️  CONFIGURATION — MODIFIE ICI
# ─────────────────────────────────────────────────────────────

import os
TOKEN        = os.environ.get("TOKEN", "TON_TOKEN_BOT")   # ← Token de @BotFather
ADMIN_ID     = int(os.environ.get("ADMIN_ID", "123456789"))          # ← Ton ID Telegram (@userinfobot)
FICHIER_DATA = "momo_data.json"   # ← Fichier de sauvegarde

# Ton numéro MTN MoMo (affiché aux utilisateurs pour te payer ou être payé)
NUMERO_MOMO  = "06X XXX XXXX"    # ← Ton vrai numéro MTN MoMo

# ─────────────────────────────────────────────────────────────
#  📋  TÂCHES DISPONIBLES (modifie selon tes besoins)
# ─────────────────────────────────────────────────────────────
#
#  Où trouver des tâches à payer ?
#  → Microworkers.com  (crée un compte travailleur)
#  → Picoworkers.com   (idem)
#  → Coinpayu.com      (voir des pubs)
#  → Timebucks.com     (tâches variées)
#  Tu acceptes une tâche sur ces sites → tu la redistribues ici
#  Tu gardes la différence comme commission !

TACHES = [
    {
        "id": "t1",
        "titre": "👍 Liker une page Facebook",
        "description": (
            "1️⃣ Va sur ce lien : facebook.com/exemple\n"
            "2️⃣ Like la page\n"
            "3️⃣ Fais une capture d'écran montrant le like\n"
            "4️⃣ Envoie la capture ici"
        ),
        "recompense": 200,   # en FCFA
        "places": 50,        # nombre de personnes pouvant faire cette tâche
        "actif": True,
    },
    {
        "id": "t2",
        "titre": "📺 Regarder une vidéo YouTube",
        "description": (
            "1️⃣ Va sur ce lien : youtube.com/exemple\n"
            "2️⃣ Regarde la vidéo jusqu'à la fin (3 minutes)\n"
            "3️⃣ Like la vidéo\n"
            "4️⃣ Fais une capture d'écran de la vidéo likée\n"
            "5️⃣ Envoie la capture ici"
        ),
        "recompense": 300,
        "places": 30,
        "actif": True,
    },
    {
        "id": "t3",
        "titre": "📝 S'inscrire sur un site",
        "description": (
            "1️⃣ Va sur ce lien : site-exemple.com\n"
            "2️⃣ Crée un compte gratuit\n"
            "3️⃣ Confirme ton email\n"
            "4️⃣ Fais une capture d'écran de ton profil créé\n"
            "5️⃣ Envoie la capture ici"
        ),
        "recompense": 500,
        "places": 20,
        "actif": True,
    },
    {
        "id": "t4",
        "titre": "📲 Installer une application",
        "description": (
            "1️⃣ Télécharge l'app : NomApp sur Play Store\n"
            "2️⃣ Ouvre l'application\n"
            "3️⃣ Crée un compte\n"
            "4️⃣ Fais une capture d'écran de l'app ouverte\n"
            "5️⃣ Envoie la capture ici"
        ),
        "recompense": 400,
        "places": 40,
        "actif": True,
    },
]

# ─────────────────────────────────────────────────────────────
#  💾  GESTION DES DONNÉES
# ─────────────────────────────────────────────────────────────

def charger_data() -> dict:
    if os.path.exists(FICHIER_DATA):
        with open(FICHIER_DATA, "r") as f:
            return json.load(f)
    return {
        "utilisateurs": {},   # user_id → {nom, numero_momo, solde, taches_faites}
        "soumissions":  {},   # soumission_id → {user_id, tache_id, statut, ...}
        "compteur":     0,    # pour générer des IDs uniques
    }

def sauvegarder_data(data: dict):
    with open(FICHIER_DATA, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_user(user_id: int) -> dict:
    data = charger_data()
    return data["utilisateurs"].get(str(user_id))

def enregistrer_user(user_id: int, nom: str):
    data = charger_data()
    uid  = str(user_id)
    if uid not in data["utilisateurs"]:
        data["utilisateurs"][uid] = {
            "nom":          nom,
            "numero_momo":  None,
            "solde":        0,
            "taches_faites": [],
        }
        sauvegarder_data(data)

def set_numero_momo(user_id: int, numero: str):
    data = charger_data()
    uid  = str(user_id)
    if uid in data["utilisateurs"]:
        data["utilisateurs"][uid]["numero_momo"] = numero
        sauvegarder_data(data)

def a_deja_fait_tache(user_id: int, tache_id: str) -> bool:
    data = charger_data()
    uid  = str(user_id)
    user = data["utilisateurs"].get(uid, {})
    return tache_id in user.get("taches_faites", [])

def nouvelle_soumission(user_id: int, tache_id: str, file_id: str) -> str:
    data = charger_data()
    data["compteur"] += 1
    soumission_id = f"S{data['compteur']:04d}"
    tache = next((t for t in TACHES if t["id"] == tache_id), None)

    data["soumissions"][soumission_id] = {
        "user_id":    str(user_id),
        "tache_id":   tache_id,
        "tache_titre": tache["titre"] if tache else "?",
        "recompense": tache["recompense"] if tache else 0,
        "file_id":    file_id,
        "statut":     "en_attente",
        "date":       datetime.now().strftime("%d/%m/%Y %H:%M"),
    }
    sauvegarder_data(data)
    return soumission_id

def valider_soumission(soumission_id: str) -> dict:
    data = charger_data()
    s    = data["soumissions"].get(soumission_id)
    if not s:
        return None
    s["statut"] = "validé"
    uid  = s["user_id"]
    # Ajouter la tâche aux tâches faites
    if uid in data["utilisateurs"]:
        data["utilisateurs"][uid]["taches_faites"].append(s["tache_id"])
        data["utilisateurs"][uid]["solde"] += s["recompense"]
    sauvegarder_data(data)
    return s

def refuser_soumission(soumission_id: str) -> dict:
    data = charger_data()
    s    = data["soumissions"].get(soumission_id)
    if not s:
        return None
    s["statut"] = "refusé"
    sauvegarder_data(data)
    return s

def get_soumissions_en_attente() -> list:
    data = charger_data()
    return [
        {"id": sid, **s}
        for sid, s in data["soumissions"].items()
        if s["statut"] == "en_attente"
    ]

# États pour la conversation
ATTENTE_NUMERO, ATTENTE_PREUVE = range(2)
tache_en_cours = {}  # user_id → tache_id

# ─────────────────────────────────────────────────────────────
#  🤖  COMMANDES
# ─────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    enregistrer_user(user.id, user.first_name)
    u    = get_user(user.id)

    clavier = ReplyKeyboardMarkup(
        [
            ["📋 Voir les tâches disponibles", "💰 Mon solde"],
            ["📱 Mon numéro MoMo",             "📊 Mes statistiques"],
            ["❓ Comment ça marche",            "📞 Contacter l'admin"],
        ],
        resize_keyboard=True,
    )

    await update.message.reply_text(
        f"👋 Bienvenue *{user.first_name}* sur *MicroTâches Congo* !\n\n"
        "💵 Gagne de l'argent facilement depuis ton téléphone.\n"
        "✅ Fais des petites tâches → reçois ton paiement sur *MTN MoMo*\n\n"
        "📲 Utilise le menu pour commencer :",
        parse_mode="Markdown",
        reply_markup=clavier,
    )

    # Si pas encore de numéro MoMo, demander
    if u and not u.get("numero_momo"):
        await update.message.reply_text(
            "⚠️ *Action requise !*\n\n"
            "Pour recevoir tes paiements, enregistre ton numéro MTN MoMo.\n"
            "Tape : `/momo 06XXXXXXXX`",
            parse_mode="Markdown",
        )


async def voir_taches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Affiche la liste des tâches disponibles."""
    taches_actives = [t for t in TACHES if t["actif"]]

    if not taches_actives:
        await update.message.reply_text(
            "😔 Aucune tâche disponible pour le moment.\n"
            "Reviens plus tard, de nouvelles tâches arrivent bientôt !"
        )
        return

    texte = "📋 *Tâches disponibles*\n\n"
    boutons = []

    for t in taches_actives:
        deja_fait = a_deja_fait_tache(update.effective_user.id, t["id"])
        statut    = "✅ Déjà fait" if deja_fait else f"💵 {t['recompense']} FCFA"
        texte    += f"*{t['titre']}*\n💰 Récompense : {t['recompense']} FCFA\n\n"
        if not deja_fait:
            boutons.append([InlineKeyboardButton(
                f"{t['titre']} — {t['recompense']} FCFA",
                callback_data=f"tache_{t['id']}"
            )])

    if not boutons:
        texte += "_Tu as déjà fait toutes les tâches disponibles ! Reviens bientôt._"
        await update.message.reply_text(texte, parse_mode="Markdown")
        return

    clavier = InlineKeyboardMarkup(boutons)
    await update.message.reply_text(
        texte + "👇 *Choisis une tâche à faire :*",
        parse_mode="Markdown",
        reply_markup=clavier,
    )


async def tache_choisie_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Affiche le détail d'une tâche choisie."""
    query    = update.callback_query
    await query.answer()
    tache_id = query.data.replace("tache_", "")
    tache    = next((t for t in TACHES if t["id"] == tache_id), None)

    if not tache:
        await query.edit_message_text("❌ Tâche introuvable.")
        return

    # Vérifier si déjà fait
    if a_deja_fait_tache(query.from_user.id, tache_id):
        await query.edit_message_text("✅ Tu as déjà fait cette tâche !")
        return

    tache_en_cours[query.from_user.id] = tache_id

    clavier = InlineKeyboardMarkup([
        [InlineKeyboardButton("📸 J'ai fait la tâche, envoyer ma preuve", callback_data=f"preuve_{tache_id}")],
        [InlineKeyboardButton("⬅️ Retour aux tâches", callback_data="retour_taches")],
    ])

    await query.edit_message_text(
        f"📌 *{tache['titre']}*\n"
        f"💰 Récompense : *{tache['recompense']} FCFA*\n\n"
        f"*Instructions :*\n{tache['description']}\n\n"
        "⚠️ _Une fois la tâche faite, appuie sur le bouton ci-dessous._",
        parse_mode="Markdown",
        reply_markup=clavier,
    )


async def demander_preuve_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Demande à l'utilisateur d'envoyer sa preuve."""
    query    = update.callback_query
    await query.answer()
    tache_id = query.data.replace("preuve_", "")
    tache    = next((t for t in TACHES if t["id"] == tache_id), None)

    tache_en_cours[query.from_user.id] = tache_id
    context.user_data["attente_preuve"] = True

    await query.edit_message_text(
        f"📸 *Envoie ta capture d'écran*\n\n"
        f"Tâche : *{tache['titre']}*\n"
        f"Récompense : *{tache['recompense']} FCFA*\n\n"
        "📲 Envoie maintenant ta capture d'écran comme preuve.\n"
        "⚠️ _Sans preuve, la tâche ne peut pas être validée._",
        parse_mode="Markdown",
    )


async def recevoir_preuve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reçoit la capture d'écran et l'envoie à l'admin pour validation."""
    user     = update.effective_user
    tache_id = tache_en_cours.get(user.id)

    if not tache_id or not context.user_data.get("attente_preuve"):
        await update.message.reply_text(
            "⚠️ Choisis d'abord une tâche dans le menu.\nTape *📋 Voir les tâches disponibles*",
            parse_mode="Markdown",
        )
        return

    # Récupérer le file_id de la photo
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
    else:
        await update.message.reply_text(
            "❌ Envoie une *image* (capture d'écran) comme preuve, pas un fichier texte.",
            parse_mode="Markdown",
        )
        return

    tache         = next((t for t in TACHES if t["id"] == tache_id), None)
    soumission_id = nouvelle_soumission(user.id, tache_id, file_id)
    u             = get_user(user.id)

    context.user_data["attente_preuve"] = False
    tache_en_cours.pop(user.id, None)

    # Confirmer à l'utilisateur
    await update.message.reply_text(
        f"✅ *Preuve reçue !*\n\n"
        f"📌 Tâche : *{tache['titre']}*\n"
        f"🆔 Référence : `{soumission_id}`\n"
        f"💰 Récompense : *{tache['recompense']} FCFA*\n\n"
        "⏳ L'admin va vérifier ta preuve sous *24h*.\n"
        "Tu recevras une notification dès que c'est validé !",
        parse_mode="Markdown",
    )

    # Envoyer à l'admin pour validation
    clavier_admin = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ VALIDER", callback_data=f"valider_{soumission_id}"),
            InlineKeyboardButton("❌ REFUSER", callback_data=f"refuser_{soumission_id}"),
        ]
    ])

    numero = u.get("numero_momo") if u else "Non enregistré"

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=file_id,
        caption=(
            f"🔔 *Nouvelle soumission à valider*\n\n"
            f"🆔 Référence : `{soumission_id}`\n"
            f"👤 Utilisateur : {user.first_name} (ID: `{user.id}`)\n"
            f"📌 Tâche : *{tache['titre']}*\n"
            f"💰 À payer : *{tache['recompense']} FCFA*\n"
            f"📱 MoMo : `{numero}`\n\n"
            "👆 Valide ou refuse cette preuve :"
        ),
        parse_mode="Markdown",
        reply_markup=clavier_admin,
    )


async def retour_taches_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tache_en_cours.pop(query.from_user.id, None)
    context.user_data["attente_preuve"] = False
    await query.edit_message_text("↩️ Retour au menu. Tape *📋 Voir les tâches disponibles*", parse_mode="Markdown")


# ─────────────────────────────────────────────────────────────
#  👮  VALIDATION PAR L'ADMIN
# ─────────────────────────────────────────────────────────────

async def admin_valider_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """L'admin valide une soumission."""
    query         = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        await query.answer("⛔ Accès refusé.", show_alert=True)
        return

    soumission_id = query.data.replace("valider_", "")
    s             = valider_soumission(soumission_id)

    if not s:
        await query.edit_message_caption("❌ Soumission introuvable.")
        return

    u = get_user(int(s["user_id"]))
    numero = u.get("numero_momo") if u else "Non enregistré"

    # Mettre à jour le message admin
    await query.edit_message_caption(
        f"✅ *VALIDÉ — {soumission_id}*\n\n"
        f"👤 Utilisateur ID : `{s['user_id']}`\n"
        f"📌 Tâche : {s['tache_titre']}\n"
        f"💰 À payer : *{s['recompense']} FCFA*\n"
        f"📱 Numéro MoMo : `{numero}`\n\n"
        f"⚠️ *N'oublie pas d'envoyer {s['recompense']} FCFA sur MTN MoMo au `{numero}` !*",
        parse_mode="Markdown",
    )

    # Notifier l'utilisateur
    await context.bot.send_message(
        chat_id=int(s["user_id"]),
        text=(
            f"🎉 *Félicitations ! Ta tâche a été validée !*\n\n"
            f"📌 Tâche : *{s['tache_titre']}*\n"
            f"💰 Récompense : *{s['recompense']} FCFA*\n\n"
            f"📱 Le paiement MTN MoMo sera envoyé sur ton numéro *{numero}* sous peu.\n\n"
            "Merci pour ton travail ! Continue pour gagner plus 💪"
        ),
        parse_mode="Markdown",
    )


async def admin_refuser_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """L'admin refuse une soumission."""
    query         = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        await query.answer("⛔ Accès refusé.", show_alert=True)
        return

    soumission_id = query.data.replace("refuser_", "")
    s             = refuser_soumission(soumission_id)

    if not s:
        await query.edit_message_caption("❌ Soumission introuvable.")
        return

    await query.edit_message_caption(
        f"❌ *REFUSÉ — {soumission_id}*\n\n"
        f"📌 Tâche : {s['tache_titre']}\n"
        f"👤 Utilisateur ID : `{s['user_id']}`",
        parse_mode="Markdown",
    )

    # Notifier l'utilisateur
    await context.bot.send_message(
        chat_id=int(s["user_id"]),
        text=(
            f"😔 *Ta soumission a été refusée.*\n\n"
            f"📌 Tâche : *{s['tache_titre']}*\n\n"
            "❓ *Raisons possibles :*\n"
            "• La capture d'écran n'est pas claire\n"
            "• La tâche n'a pas été complétée correctement\n"
            "• L'image ne montre pas la bonne preuve\n\n"
            "💡 Refais la tâche correctement et renvoie une meilleure preuve !\n"
            "Contacte l'admin si tu penses que c'est une erreur."
        ),
        parse_mode="Markdown",
    )


# ─────────────────────────────────────────────────────────────
#  👤  PROFIL UTILISATEUR
# ─────────────────────────────────────────────────────────────

async def mon_solde(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    if not u:
        await update.message.reply_text("Tape /start d'abord.")
        return

    data         = charger_data()
    uid          = str(update.effective_user.id)
    soumissions  = [s for s in data["soumissions"].values() if s["user_id"] == uid]
    en_attente   = sum(s["recompense"] for s in soumissions if s["statut"] == "en_attente")
    total_gagné  = u.get("solde", 0)
    nb_taches    = len(u.get("taches_faites", []))

    await update.message.reply_text(
        f"💰 *Ton solde*\n\n"
        f"✅ Total gagné : *{total_gagné} FCFA*\n"
        f"⏳ En attente de validation : *{en_attente} FCFA*\n"
        f"📋 Tâches complétées : *{nb_taches}*\n"
        f"📱 Numéro MoMo : `{u.get('numero_momo') or 'Non enregistré'}`\n\n"
        "💡 Les paiements sont envoyés après validation par l'admin.",
        parse_mode="Markdown",
    )


async def mes_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u    = get_user(update.effective_user.id)
    user = update.effective_user
    if not u:
        await update.message.reply_text("Tape /start d'abord.")
        return

    data        = charger_data()
    uid         = str(user.id)
    soumissions = [s for s in data["soumissions"].values() if s["user_id"] == uid]
    validees    = [s for s in soumissions if s["statut"] == "validé"]
    refusees    = [s for s in soumissions if s["statut"] == "refusé"]
    en_attente  = [s for s in soumissions if s["statut"] == "en_attente"]

    await update.message.reply_text(
        f"📊 *Tes statistiques*\n\n"
        f"👤 Nom : *{user.first_name}*\n"
        f"📱 MoMo : `{u.get('numero_momo') or 'Non enregistré'}`\n\n"
        f"✅ Tâches validées : *{len(validees)}*\n"
        f"⏳ En attente : *{len(en_attente)}*\n"
        f"❌ Refusées : *{len(refusees)}*\n\n"
        f"💵 Total gagné : *{u.get('solde', 0)} FCFA*",
        parse_mode="Markdown",
    )


async def enregistrer_momo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enregistre le numéro MTN MoMo de l'utilisateur via /momo NUMERO."""
    if not context.args:
        await update.message.reply_text(
            "Usage : `/momo 06XXXXXXXX`\nExemple : `/momo 0612345678`",
            parse_mode="Markdown",
        )
        return

    numero = context.args[0].strip()
    if not numero.startswith("06") or len(numero) < 9:
        await update.message.reply_text(
            "❌ Numéro invalide. Format : `06XXXXXXXX`\nExemple : `/momo 0612345678`",
            parse_mode="Markdown",
        )
        return

    set_numero_momo(update.effective_user.id, numero)
    await update.message.reply_text(
        f"✅ *Numéro MTN MoMo enregistré !*\n\n"
        f"📱 Numéro : `{numero}`\n\n"
        "Tu recevras tes paiements sur ce numéro après validation de tes tâches.\n"
        "Pour changer le numéro, retape `/momo NOUVEAU_NUMERO`",
        parse_mode="Markdown",
    )


async def contacter_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📞 *Contacter l'admin*\n\n"
        f"Pour toute question ou problème, envoie un message direct à l'admin.\n\n"
        f"📱 MTN MoMo admin : `{NUMERO_MOMO}`\n\n"
        "Utilise la commande `/support Ton message` pour envoyer un message à l'admin.",
        parse_mode="Markdown",
    )


async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envoie un message de support à l'admin."""
    if not context.args:
        await update.message.reply_text(
            "Usage : `/support Ton message ici`",
            parse_mode="Markdown",
        )
        return

    user    = update.effective_user
    message = " ".join(context.args)

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"📩 *Message de support*\n\n"
            f"👤 De : {user.first_name} (ID: `{user.id}`)\n\n"
            f"💬 Message : {message}"
        ),
        parse_mode="Markdown",
    )

    await update.message.reply_text(
        "✅ Ton message a été envoyé à l'admin.\nTu recevras une réponse bientôt !"
    )


# ─────────────────────────────────────────────────────────────
#  👮  COMMANDES ADMIN
# ─────────────────────────────────────────────────────────────

async def admin_en_attente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Affiche toutes les soumissions en attente."""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Accès refusé.")
        return

    soumissions = get_soumissions_en_attente()
    if not soumissions:
        await update.message.reply_text("✅ Aucune soumission en attente !")
        return

    await update.message.reply_text(
        f"⏳ *{len(soumissions)} soumission(s) en attente*\n\n"
        "Les preuves ont été envoyées au-dessus dans ta messagerie.",
        parse_mode="Markdown",
    )


async def admin_stats_global(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stats globales pour l'admin."""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Accès refusé.")
        return

    data        = charger_data()
    total_u     = len(data["utilisateurs"])
    soumissions = list(data["soumissions"].values())
    validees    = [s for s in soumissions if s["statut"] == "validé"]
    en_attente  = [s for s in soumissions if s["statut"] == "en_attente"]
    total_paye  = sum(s["recompense"] for s in validees)

    await update.message.reply_text(
        f"📊 *Stats Admin*\n\n"
        f"👥 Utilisateurs : *{total_u}*\n"
        f"📋 Total soumissions : *{len(soumissions)}*\n"
        f"✅ Validées : *{len(validees)}*\n"
        f"⏳ En attente : *{len(en_attente)}*\n"
        f"💰 Total payé : *{total_paye} FCFA*",
        parse_mode="Markdown",
    )


async def repondre_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin répond à un utilisateur : /repondre USER_ID message"""
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Usage : `/repondre USER_ID Ton message`", parse_mode="Markdown")
        return

    try:
        dest_id = int(context.args[0])
        message = " ".join(context.args[1:])
        await context.bot.send_message(
            chat_id=dest_id,
            text=f"📩 *Réponse de l'admin :*\n\n{message}",
            parse_mode="Markdown",
        )
        await update.message.reply_text("✅ Message envoyé !")
    except Exception as e:
        await update.message.reply_text(f"❌ Erreur : {e}")


async def message_inconnu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("attente_preuve"):
        await update.message.reply_text(
            "📸 J'attends ta *capture d'écran* (image) comme preuve de la tâche.\n"
            "Envoie une photo !",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            "🤖 Utilise le menu en bas.\nTape /start pour revoir le menu."
        )


# ─────────────────────────────────────────────────────────────
#  🚀  LANCEMENT
# ─────────────────────────────────────────────────────────────

def main():
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )

    app = Application.builder().token(TOKEN).build()

    # Commandes utilisateur
    app.add_handler(CommandHandler("start",   start))
    app.add_handler(CommandHandler("momo",    enregistrer_momo))
    app.add_handler(CommandHandler("support", support))

    # Commandes admin
    app.add_handler(CommandHandler("attente",    admin_en_attente))
    app.add_handler(CommandHandler("adminstats", admin_stats_global))
    app.add_handler(CommandHandler("repondre",   repondre_support))

    # Boutons menu
    app.add_handler(MessageHandler(filters.Regex("📋 Voir les tâches disponibles"), voir_taches))
    app.add_handler(MessageHandler(filters.Regex("💰 Mon solde"),                   mon_solde))
    app.add_handler(MessageHandler(filters.Regex("📱 Mon numéro MoMo"),             contacter_admin))
    app.add_handler(MessageHandler(filters.Regex("📊 Mes statistiques"),            mes_stats))
    app.add_handler(MessageHandler(filters.Regex("❓ Comment ça marche"),           comment_ca_marche))
    app.add_handler(MessageHandler(filters.Regex("📞 Contacter l'admin"),           contacter_admin))

    # Callbacks inline
    app.add_handler(CallbackQueryHandler(tache_choisie_callback,   pattern=r"^tache_"))
    app.add_handler(CallbackQueryHandler(demander_preuve_callback,  pattern=r"^preuve_"))
    app.add_handler(CallbackQueryHandler(retour_taches_callback,    pattern="retour_taches"))
    app.add_handler(CallbackQueryHandler(admin_valider_callback,    pattern=r"^valider_"))
    app.add_handler(CallbackQueryHandler(admin_refuser_callback,    pattern=r"^refuser_"))

    # Réception des photos (preuves)
    app.add_handler(MessageHandler(filters.PHOTO, recevoir_preuve))

    # Messages non reconnus
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_inconnu))

    print("✅ Bot MicroTâches MoMo démarré !")
    print("📋 Les tâches sont configurées dans le fichier")
    print("👮 Commandes admin : /attente /adminstats /repondre")
    app.run_polling()


async def comment_ca_marche(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ *Comment gagner de l'argent ici ?*\n\n"
        "C'est simple en 4 étapes :\n\n"
        "1️⃣ *Enregistre ton numéro MTN MoMo*\n"
        "   → Tape `/momo 06XXXXXXXX`\n\n"
        "2️⃣ *Choisis une tâche*\n"
        "   → Menu *📋 Voir les tâches disponibles*\n\n"
        "3️⃣ *Fais la tâche et envoie ta preuve*\n"
        "   → Capture d'écran obligatoire\n\n"
        "4️⃣ *Reçois ton paiement MTN MoMo*\n"
        "   → Après validation par l'admin (sous 24h)\n\n"
        "💡 Plus tu fais de tâches, plus tu gagnes !\n"
        "📋 Nouvelles tâches ajoutées régulièrement.",
        parse_mode="Markdown",
    )


if __name__ == "__main__":
    main()
