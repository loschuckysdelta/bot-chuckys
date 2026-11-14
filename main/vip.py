import logging
import html
import threading
import time
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

import requests
from telebot import types

CHAT_ID = -1004361223083
ADMIN_IDS = {7219427873, 8635600472}
API_BASE = "https://bot-apis-zkmk.vercel.app"
VIP_IMAGE = "https://i.postimg.cc/bvFhRtHQ/image.png"
PLANS = {
    "7": ("S/5 • 7 días", 7, False),
    "30": ("S/20 • 30 días", 30, False),
    "60": ("S/35 • 2 meses (60 días)", 60, False),
    "permanent": ("S/50 • Pago único (sin vencimiento)", None, True),
}

log = logging.getLogger(__name__)
_EXPIRY_WORKERS = set()
_WORKERS_LOCK = threading.Lock()
_PERU = timezone(timedelta(hours=-5))


def format_member(member):
    """Presentación segura de datos devueltos por la API."""
    if not isinstance(member, dict):
        return "⚠️ La API no devolvió una membresía válida."
    uid = html.escape(str(member.get("telegramUserId") or "No disponible"))
    return f"👤 <b>ID:</b> <code>{uid}</code>\n{descripcion_vencimiento(member)}"


def is_vip_admin(message):
    return message.chat.type == "private" and message.from_user and message.from_user.id in ADMIN_IDS


def api(method, path, payload=None):
    try:
        response = requests.request(method, API_BASE + path, json=payload, timeout=20)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict) or data.get("success") is not True:
            raise ValueError(f"Respuesta inesperada de API en {path}: {data}")
        return data
    except requests.RequestException as e:
        log.error("Error de conexión con la API en %s: %s", path, e)
        raise


def date_value(value):
    if not isinstance(value, str):
        raise ValueError("Fecha inválida")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result


def descripcion_vencimiento(membership):
    """Informa la vigencia REAL que devuelve el backend, no una fecha inventada."""
    if not isinstance(membership, dict):
        return "Consulta tu fecha de vencimiento con el administrador."
    if membership.get("permanent"):
        return "♾️ Acceso permanente, sin vencimiento."
    expiry = membership.get("expiresAt")
    if not expiry:
        return "Consulta tu fecha de vencimiento con el administrador."
    try:
        fecha = date_value(expiry).astimezone(_PERU)
        return f"📅 Vence: {fecha:%d/%m/%Y a las %H:%M} (Perú)."
    except (ValueError, TypeError, OverflowError):
        return "Consulta tu fecha de vencimiento con el administrador."


def register_vip(bot):
    @bot.message_handler(commands=["vip"])
    def vip_menu(message):
        if not is_vip_admin(message):
            return
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(types.InlineKeyboardButton("🔗 Generar enlace VIP", callback_data="vipadmin:generar"))
        keyboard.add(types.InlineKeyboardButton("👥 Miembros VIP", callback_data="viplist:0"))
        keyboard.add(types.InlineKeyboardButton("📊 Estado de membresías", callback_data="vipadmin:estado"))
        keyboard.add(types.InlineKeyboardButton("ℹ️ Ayuda", callback_data="vipadmin:ayuda"))
        panel_text = (
            "👑 <b>PANEL DE MEMBRESÍAS VIP</b>\n\n"
            "🔗 El enlace de invitación vale <b>24 horas</b> y permite una entrada.\n"
            "📅 La membresía comienza cuando la API confirma el ingreso.\n\n"
            "Elige una opción del panel para continuar:"
        )
        try:
            bot.send_photo(message.chat.id, VIP_IMAGE, caption=panel_text,
                           reply_markup=keyboard, parse_mode="HTML")
        except Exception:
            log.exception("No se pudo cargar la imagen VIP; se enviará texto")
            bot.send_message(message.chat.id, panel_text, reply_markup=keyboard, parse_mode="HTML")

    @bot.message_handler(commands=["vip_lista", "vip_miembros"])
    def vip_lista(message):
        if not is_vip_admin(message):
            return
        enviar_lista(message.chat.id, 0)

    def leer_miembros():
        members = api("GET", "/api/vip").get("memberships")
        if not isinstance(members, list):
            raise ValueError("La API no devolvió una lista en 'memberships'")
        return [m for m in members if isinstance(m, dict)]

    def id_miembro(member):
        uid = str(member.get("telegramUserId") or "")
        return uid if uid.isdecimal() and len(uid) <= 20 else None

    def dias_restantes(member):
        if member.get("permanent"):
            return "♾️ Permanente"
        expiry = member.get("expiresAt")
        if not expiry:
            return "❔ Sin fecha de vencimiento"
        try:
            delta = date_value(expiry) - datetime.now(timezone.utc)
            if delta.total_seconds() <= 0:
                return "⌛ Vencido"
            dias = delta.days
            horas = delta.seconds // 3600
            return f"⏳ {dias} d y {horas} h restantes"
        except (TypeError, ValueError, OverflowError):
            return "❔ Fecha inválida"

    def enviar_lista(chat_id, pagina=0, message_id=None):
        try:
            members = leer_miembros()
            members.sort(key=lambda m: str(m.get("telegramUserId") or ""))
            page_size = 6
            last_page = max(0, (len(members) - 1) // page_size)
            pagina = max(0, min(pagina, last_page))
            start = pagina * page_size
            shown = members[start:start + page_size]
            lines = [f"👑 <b>MIEMBROS VIP</b> ({len(members)})",
                     f"📄 Página {pagina + 1}/{last_page + 1}", ""]
            keyboard = types.InlineKeyboardMarkup(row_width=1)
            for index, member in enumerate(shown, start + 1):
                uid = id_miembro(member)
                name = html.escape(str(member.get("username") or "Sin usuario").lstrip("@")[:35])
                lines.append(f"{index}. 👤 @{name} · <code>{html.escape(uid or 'ID no disponible')}</code>")
                lines.append(dias_restantes(member))
                if uid:
                    keyboard.add(types.InlineKeyboardButton(
                        f"👁 Ver / retirar · {uid}", callback_data=f"vipdetail:{uid}:{pagina}"))
            if not shown:
                lines.append("Todavía no hay membresías registradas.")
            nav = []
            if pagina > 0:
                nav.append(types.InlineKeyboardButton("⬅️ Anterior", callback_data=f"viplist:{pagina - 1}"))
            if pagina < last_page:
                nav.append(types.InlineKeyboardButton("Siguiente ➡️", callback_data=f"viplist:{pagina + 1}"))
            if nav:
                keyboard.row(*nav)
            keyboard.add(types.InlineKeyboardButton("🔄 Actualizar", callback_data=f"viplist:{pagina}"))
            text = "\n".join(lines)
            if message_id is not None:
                try:
                    bot.edit_message_text(text, chat_id, message_id, reply_markup=keyboard, parse_mode="HTML")
                    return
                except Exception as error:
                    if "message is not modified" in str(error).lower():
                        return
                    log.warning("No se pudo editar lista VIP: %s", error)
            bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode="HTML")
        except Exception:
            log.exception("No se pudo cargar la lista VIP")
            bot.send_message(chat_id, "⚠️ No pude cargar la lista VIP. La API debe devolver 'memberships' como lista.")

    @bot.callback_query_handler(func=lambda c: bool(c.data and c.data.startswith(("viplist:", "vipdetail:", "vipremove:", "vipconfirm:"))))
    def miembros_callbacks(call):
        if not call.from_user or call.from_user.id not in ADMIN_IDS or call.message.chat.type != "private":
            bot.answer_callback_query(call.id, "Solo administradores", show_alert=True)
            return
        parts = call.data.split(":")
        bot.answer_callback_query(call.id)
        if parts[0] == "viplist":
            try:
                pagina = int(parts[1])
            except (IndexError, ValueError):
                pagina = 0
            enviar_lista(call.message.chat.id, pagina, call.message.message_id)
            return
        if len(parts) != 3 or not parts[1].isdecimal() or not parts[2].isdigit():
            bot.answer_callback_query(call.id, "⚠️ Acción inválida.", show_alert=True)
            return
        uid, pagina = parts[1], int(parts[2])
        if parts[0] == "vipdetail":
            try:
                member = next((m for m in leer_miembros() if id_miembro(m) == uid), None)
                if member is None:
                    bot.answer_callback_query(call.id, "⚠️ Usuario no encontrado en /api/vip.", show_alert=True)
                    return
                keyboard = types.InlineKeyboardMarkup()
                keyboard.add(types.InlineKeyboardButton("🚫 Retirar del grupo", callback_data=f"vipremove:{uid}:{pagina}"))
                keyboard.add(types.InlineKeyboardButton("⬅️ Volver a miembros", callback_data=f"viplist:{pagina}"))
                bot.edit_message_text(
                    "👑 <b>MEMBRESÍA VIP</b>\n\n" + format_member(member) +
                    "\n" + dias_restantes(member),
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            except Exception:
                log.exception("No se pudo consultar miembro VIP %s", uid)
                bot.answer_callback_query(call.id, "⚠️ Error consultando la membresía.", show_alert=True)
        elif parts[0] == "vipremove":
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton("✅ Sí, retirar", callback_data=f"vipconfirm:{uid}:{pagina}"))
            keyboard.add(types.InlineKeyboardButton("❌ Cancelar", callback_data=f"viplist:{pagina}"))
            try:
                bot.edit_message_text(
                    f"⚠️ ¿Retirar del grupo VIP al usuario <code>{uid}</code>?\nEsta acción no se puede deshacer automáticamente.",
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            except Exception:
                pass
        elif parts[0] == "vipconfirm":
            if int(uid) in ADMIN_IDS:
                bot.answer_callback_query(call.id, "⛔ No se puede retirar a un administrador configurado.", show_alert=True)
                return
            try:
                bot.ban_chat_member(CHAT_ID, int(uid))
                bot.unban_chat_member(CHAT_ID, int(uid), only_if_banned=True)
                bot.answer_callback_query(call.id, f"✅ Usuario {uid} retirado del grupo.", show_alert=True)
                enviar_lista(call.message.chat.id, pagina, call.message.message_id)
            except Exception:
                log.exception("Fallo al retirar usuario VIP %s", uid)
                bot.answer_callback_query(call.id, "❌ No se pudo retirar al usuario. Verifica permisos.", show_alert=True)

    @bot.message_handler(commands=["vip_estado"])
    def vip_estado(message):
        if not is_vip_admin(message):
            return
        try:
            memberships = api("GET", "/api/vip").get("memberships")
            if not isinstance(memberships, list):
                raise ValueError("Respuesta sin lista memberships")
            now = datetime.now(timezone.utc)
            activos = vencidos = permanentes = 0
            for member in memberships:
                if not isinstance(member, dict):
                    continue
                if member.get("permanent"):
                    permanentes += 1
                elif member.get("expiresAt"):
                    try:
                        if date_value(member["expiresAt"]) > now:
                            activos += 1
                        else:
                            vencidos += 1
                    except (ValueError, TypeError, OverflowError):
                        pass
            bot.reply_to(message, "📊 <b>ESTADO VIP</b>\n\n"
                f"✅ Vigentes: <b>{activos}</b>\n"
                f"♾️ Permanentes: <b>{permanentes}</b>\n"
                f"⌛ Vencidas: <b>{vencidos}</b>\n\n"
                "Usa <code>/vip_usuario ID</code> para consultar una membresía.", parse_mode="HTML")
        except Exception:
            log.exception("No se pudo consultar resumen VIP")
            bot.reply_to(message, "⚠️ No pude consultar el estado VIP. Verifica la API y su conexión.")

    @bot.message_handler(commands=["vip_usuario"])
    def vip_usuario(message):
        if not is_vip_admin(message):
            return
        args = message.text.split(maxsplit=1)
        if len(args) != 2 or not args[1].strip().isdigit():
            bot.reply_to(message, "ℹ️ Uso: /vip_usuario 123456789")
            return
        uid = args[1].strip()
        try:
            result = api("GET", "/api/vip/" + quote(uid, safe=""))
            bot.reply_to(message, "👑 <b>CONSULTA VIP</b>\n\n" + format_member(result.get("membership")), parse_mode="HTML")
        except Exception:
            log.exception("Fallo consultando membresía %s", uid)
            bot.reply_to(message, "⚠️ No se pudo consultar esta membresía en la API.")

    @bot.callback_query_handler(func=lambda call: bool(call.data and call.data.startswith("vipadmin:")))
    def vip_admin_actions(call):
        if call.from_user.id not in ADMIN_IDS or call.message.chat.type != "private":
            bot.answer_callback_query(call.id, "Solo administradores", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        action = call.data.split(":", 1)[1]
        
        if action == "generar":
            kb = types.InlineKeyboardMarkup(row_width=2)
            for code, (label, _, _) in PLANS.items():
                kb.add(types.InlineKeyboardButton(label, callback_data=f"vipplan:{code}"))
            kb.add(types.InlineKeyboardButton("⬅️ Volver al panel", callback_data="vipadmin:volver"))
            
            text_generar = (
                "🔗 <b>GENERAR ENLACE VIP</b>\n\n"
                "Elige el plan. Se creará un enlace de un solo uso, válido 24 horas.\n"
                "Los días del plan se cuentan desde la activación registrada en la API."
            )
            try:
                bot.edit_message_caption(text_generar, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
            except Exception:
                try:
                    bot.edit_message_text(text_generar, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
                except Exception:
                    pass
                
        elif action == "volver":
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(types.InlineKeyboardButton("🔗 Generar enlace VIP", callback_data="vipadmin:generar"))
            kb.add(types.InlineKeyboardButton("👥 Miembros VIP", callback_data="viplist:0"))
            kb.add(types.InlineKeyboardButton("📊 Estado VIP", callback_data="vipadmin:estado"))
            kb.add(types.InlineKeyboardButton("ℹ️ Ayuda", callback_data="vipadmin:ayuda"))
            
            panel_text = "👑 <b>LOSCHUCKYS | PANEL VIP</b>\nSelecciona una opción:"
            try:
                bot.edit_message_caption(panel_text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
            except Exception:
                try:
                    bot.edit_message_text(panel_text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
                except Exception:
                    pass
                
        elif action == "estado":
            send_status_callback(call)
        elif action == "ayuda":
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("⬅️ Volver al panel", callback_data="vipadmin:volver"))
            ayuda_text = (
                "ℹ️ <b>AYUDA VIP</b>\n\n"
                "• /vip — generar enlaces por plan\n"
                "• /vip_estado — resumen de membresías\n"
                "• /vip_lista — lista, días restantes y retirar del grupo\n"
                "• /vip_usuario ID — consultar vencimiento\n\n"
                "⚠️ Los endpoints /api/vip deben existir en tu API."
            )
            try:
                bot.edit_message_text(ayuda_text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
            except Exception:
                pass

    def send_status_callback(call):
        try:
            memberships = api("GET", "/api/vip").get("memberships")
            if not isinstance(memberships, list):
                raise ValueError("Lista de membresías ausente")
            now = datetime.now(timezone.utc)
            permanent = sum(1 for m in memberships if isinstance(m, dict) and m.get("permanent"))
            active = 0
            for m in memberships:
                if isinstance(m, dict) and not m.get("permanent") and m.get("expiresAt"):
                    try:
                        active += date_value(m["expiresAt"]) > now
                    except (ValueError, TypeError, OverflowError):
                        pass
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("⬅️ Volver al panel", callback_data="vipadmin:volver"))
            
            status_text = f"📊 <b>ESTADO VIP</b>\n\n✅ Vigentes: {active}\n♾️ Permanentes: {permanent}"
            bot.edit_message_text(status_text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
        except Exception:
            log.exception("Error resumen VIP")
            bot.answer_callback_query(call.id, "⚠️ No se pudo cargar el estado VIP.", show_alert=True)

    @bot.callback_query_handler(func=lambda call: bool(call.data and call.data.startswith("vipplan:")))
    def create_link(call):
        if call.from_user.id not in ADMIN_IDS or call.message.chat.type != "private":
            bot.answer_callback_query(call.id, "Solo administradores", show_alert=True)
            return
        code = call.data.split(":", 1)[1]
        if code not in PLANS:
            bot.answer_callback_query(call.id, "Plan inválido", show_alert=True)
            return

        try:
            bot.answer_callback_query(call.id, "⏳ Generando enlace...")
        except Exception:
            pass

        invite = None
        try:
            # 1. Crear enlace de invitación en Telegram
            invite = bot.create_chat_invite_link(
                CHAT_ID, name=f"VIP-{code}",
                expire_date=int(time.time()) + 86400, member_limit=1
            )
            
            # 2. Registrar el enlace en la API de Vercel
            api("POST", "/api/vip/links", {
                "invite_link": invite.invite_link,
                "plan": code,
                "used": False,
                "chat_id": CHAT_ID,
            })
            
            bot.answer_callback_query(call.id, "¡Enlace generado!")
            
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("⬅️ Volver al panel", callback_data="vipadmin:volver"))
            
            result_text = (
                f"👑 <b>{PLANS[code][0]}</b>\n\n"
                f"🔗 <code>{html.escape(invite.invite_link)}</code>\n\n"
                "✅ Enlace de una sola entrada.\n"
                "⏳ Válido por 24 horas (si no se utiliza).\n"
                "📆 Los días del plan comienzan tras activar el ingreso en la API."
            )
            
            # 3. Como el mensaje original tiene foto, usamos edit_message_caption de manera segura
            try:
                bot.edit_message_caption(result_text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
            except Exception:
                try:
                    bot.edit_message_text(result_text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
                except Exception:
                    bot.send_message(call.message.chat.id, result_text, reply_markup=kb, parse_mode="HTML")
            
        except Exception as error:
            log.exception("No se pudo crear o registrar el enlace VIP")
            if invite is not None:
                try:
                    bot.revoke_chat_invite_link(CHAT_ID, invite.invite_link)
                except Exception:
                    pass
            
            description = str(error).lower()
            if "chat not found" in description or "peer_id_invalid" in description:
                msg = "❌ <b>Error:</b> Grupo VIP no encontrado.\nVerifica que el <code>CHAT_ID</code> sea correcto y que el bot sea administrador en el grupo."
            elif "not enough rights" in description or "not administrator" in description:
                msg = "❌ <b>Error:</b> El bot necesita permisos de administrador en el grupo para crear enlaces de invitación."
            elif isinstance(error, requests.HTTPError) and error.response is not None and error.response.status_code == 404:
                msg = "❌ <b>Error:</b> La API en Vercel no tiene configurado el endpoint <code>/api/vip/links</code>."
            else:
                msg = f"❌ <b>No se pudo generar el enlace.</b>\nDetalle: <code>{html.escape(str(error))}</code>"
            
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("⬅️ Volver al panel", callback_data="vipadmin:volver"))
            
            try:
                bot.edit_message_caption(msg, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
            except Exception:
                try:
                    bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
                except Exception:
                    bot.send_message(call.message.chat.id, msg, reply_markup=kb, parse_mode="HTML")

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
            result = api("POST", "/api/vip/activate", {
                "inviteLink": invite.invite_link,
                "telegramUserId": str(user.id),
                "username": user.username or "",
            })
            try:
                bot.revoke_chat_invite_link(CHAT_ID, invite.invite_link)
                log.info("Enlace VIP de un solo ingreso revocado para %s", user.id)
            except Exception:
                log.exception("VIP activado para %s, pero no se pudo revocar el enlace", user.id)
            membership = result.get("membership")
            try:
                bot.send_message(
                    user.id,
                    "👑 Tu membresía VIP está activa.\n" + descripcion_vencimiento(membership)
                )
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
            if not isinstance(member, dict):
                log.warning("Membresía mal formada recibida de API: %r", member)
                continue
            try:
                uid = member.get("telegramUserId")
                expiry = member.get("expiresAt")
                if not uid or not expiry or member.get("permanent"):
                    continue
                if date_value(expiry) > datetime.now(timezone.utc):
                    continue
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

    with _WORKERS_LOCK:
        bot_key = id(bot)
        if bot_key not in _EXPIRY_WORKERS:
            _EXPIRY_WORKERS.add(bot_key)
            threading.Thread(target=expiry_loop, name="vip-expiry", daemon=True).start()
