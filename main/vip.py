"""VIP Telegram: no SQLite; enlaces y membresías persistidos por API."""
import logging
import threading
import time
from datetime import datetime, timezone
from urllib.parse import quote

import requests
from telebot import types

CHAT_ID = -1004361223083
ADMIN_IDS = {7219427873, 8635600472}
API_BASE = "https://bot-apis-zkmk.vercel.app"
PLANS = {
    "7": ("S/5 • 7 días", 7, False),
    "30": ("S/20 • 30 días", 30, False),
    "60": ("S/35 • 2 meses (60 días)", 60, False),
    "permanent": ("S/50 • Permanente", None, True),
}
log = logging.getLogger(__name__)


def api(method, path, payload=None):
    response = requests.request(method, API_BASE + path, json=payload, timeout=20)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict) or data.get("success") is not True:
        raise ValueError(f"Respuesta inesperada de API en {path}: {data}")
    return data


def date_value(value):
    if not isinstance(value, str):
        raise ValueError("Fecha inválida")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result


def register_vip(bot):
    @bot.message_handler(commands=["vip"])
    def vip_menu(message):
        if message.from_user.id not in ADMIN_IDS or message.chat.type != "private":
            return
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        for code, (label, _, _) in PLANS.items():
            keyboard.add(types.InlineKeyboardButton(label, callback_data=f"vipplan:{code}"))
        bot.send_message(message.chat.id, "👑 <b>MEMBRESÍAS VIP</b>\nSelecciona un plan:", reply_markup=keyboard)

    @bot.callback_query_handler(func=lambda call: bool(call.data and call.data.startswith("vipplan:")))
    def create_link(call):
        if call.from_user.id not in ADMIN_IDS or call.message.chat.type != "private":
            bot.answer_callback_query(call.id, "Solo administradores", show_alert=True)
            return
        code = call.data.split(":", 1)[1]
        if code not in PLANS:
            bot.answer_callback_query(call.id, "Plan inválido", show_alert=True)
            return
        invite = None
        try:
            # Valida acceso antes de intentar crear el enlace.
            bot.get_chat(CHAT_ID)
            invite = bot.create_chat_invite_link(
                CHAT_ID, name=f"VIP-{code}",
                expire_date=int(time.time()) + 86400, member_limit=1
            )
            # El backend DEBE implementar este endpoint y almacenar el enlace.
            api("POST", "/api/vip/links", {
                "invite_link": invite.invite_link,
                "plan": code,
                "used": False,
                "chat_id": CHAT_ID,
            })
            bot.answer_callback_query(call.id, "Enlace generado")
            bot.send_message(call.from_user.id,
                f"👑 <b>{PLANS[code][0]}</b>\n"
                f"🔗 {invite.invite_link}\n\n"
                "Enlace de un uso, válido por 24 horas si no se utiliza.")
        except Exception as error:
            log.exception("No se pudo crear o registrar el enlace VIP")
            if invite is not None:
                try:
                    bot.revoke_chat_invite_link(CHAT_ID, invite.invite_link)
                except Exception:
                    log.exception("No se pudo revocar el enlace no registrado")
            description = str(error).lower()
            if "chat not found" in description:
                msg = "❌ Grupo VIP no encontrado. Comprueba el ID y que el bot esté dentro del grupo."
            elif "not enough rights" in description or "not administrator" in description:
                msg = "❌ El bot necesita permisos para crear enlaces de invitación."
            elif isinstance(error, requests.HTTPError) and error.response is not None and error.response.status_code == 404:
                msg = "❌ La API todavía no tiene /api/vip/links. Debes agregar ese endpoint en tu backend."
            else:
                msg = "❌ No se pudo generar el enlace. Revisa la consola y la conexión con la API."
            try:
                bot.answer_callback_query(call.id, "Operación fallida", show_alert=True)
            except Exception:
                pass
            bot.send_message(call.from_user.id, msg)

    @bot.chat_member_handler(func=lambda update: update.chat.id == CHAT_ID)
    def on_join(update):
        before = update.old_chat_member.status
        after = update.new_chat_member.status
        if before in ("member", "administrator", "creator") or after not in ("member", "administrator"):
            return
        invite = getattr(update, "invite_link", None)
        if not invite:
            return
        user = update.new_chat_member.user
        try:
            # Activación atómica: la API conoce el plan por el enlace guardado.
            # Evita duplicar membresías si Telegram repite el evento.
            result = api("POST", "/api/vip/activate", {
                "inviteLink": invite.invite_link,
                "telegramUserId": str(user.id),
                "username": user.username or "",
            })
            # La membresía se registra primero; después se inutiliza el enlace.
            # Aunque el usuario abandone el grupo, no podrá reutilizarlo.
            try:
                bot.revoke_chat_invite_link(CHAT_ID, invite.invite_link)
                log.info("Enlace VIP de un solo ingreso revocado para %s", user.id)
            except Exception:
                log.exception("VIP activado para %s, pero no se pudo revocar el enlace", user.id)
            try:
                bot.send_message(user.id, "👑 Tu membresía VIP está activa.")
            except Exception:
                log.info("Usuario %s no inició chat privado con el bot", user.id)
        except Exception:
            log.exception("Error al registrar ingreso VIP de %s", user.id)

    def check_expired():
        data = api("GET", "/api/vip")
        memberships = data.get("memberships")
        if not isinstance(memberships, list):
            raise ValueError("API GET /api/vip no devolvió memberships como lista")
        for member in memberships:
            try:
                uid = member.get("telegramUserId")
                expiry = member.get("expiresAt")
                if not uid or not expiry or member.get("permanent"):
                    continue
                if date_value(expiry) > datetime.now(timezone.utc):
                    continue
                # Comprobación fresca antes de expulsar: respeta renovaciones.
                fresh = api("GET", "/api/vip/" + quote(str(uid), safe="")).get("membership")
                if not isinstance(fresh, dict):
                    continue
                fresh_expiry = fresh.get("expiresAt")
                if (fresh.get("permanent") or not fresh_expiry or
                        date_value(fresh_expiry) > datetime.now(timezone.utc) or
                        fresh_expiry != expiry):
                    continue
                bot.ban_chat_member(CHAT_ID, int(uid))
                bot.unban_chat_member(CHAT_ID, int(uid), only_if_banned=True)
                log.info("Membresía VIP vencida, usuario retirado: %s", uid)
            except Exception:
                log.exception("Error revisando vencimiento del usuario %s", member.get("telegramUserId"))

    def expiry_loop():
        while True:
            try:
                check_expired()
            except Exception:
                log.exception("No se pudo revisar la API VIP; no se expulsó en este ciclo")
            time.sleep(300)

    threading.Thread(target=expiry_loop, name="vip-expiry", daemon=True).start()
