import requests
import telebot

ID_GRUPO = -1004375169075
API_CONTACTOS = "https://bot-apis-zkmk.vercel.app/api/contactos"
TIMEOUT = (4, 8)


def _es_miembro_grupo(bot, uid):
    try:
        estado = bot.get_chat_member(ID_GRUPO, uid).status
        return estado in ("member", "administrator", "creator")
    except Exception:
        return False


def _puede_invitar_usuarios(bot):
    try:
        admin = bot.get_chat_member(ID_GRUPO, bot.get_me().id)
        return admin.status == "creator" or (
            admin.status == "administrator" and admin.can_invite_users is True
        )
    except Exception as exc:
        print(f"❌ Error al verificar permisos del bot: {type(exc).__name__}")
        return False


def _entregar_enlace_invitacion(bot, uid):
    try:
        if _es_miembro_grupo(bot, uid):
            bot.send_message(
                uid,
                "ℹ️ **Ya te encuentras dentro** del GRUPO FREE.",
                parse_mode="Markdown",
                reply_markup=telebot.types.ReplyKeyboardRemove()
            )
            return

        if not _puede_invitar_usuarios(bot):
            bot.send_message(
                uid,
                "⚠️ El bot no cuenta con los permisos de administrador necesarios para generar invitaciones.",
                parse_mode="Markdown",
                reply_markup=telebot.types.ReplyKeyboardRemove()
            )
            return

        import time
        tiempo_actual = int(time.time())
        expiracion = tiempo_actual + 86400  # 24 horas

        invitacion = bot.create_chat_invite_link(
            ID_GRUPO,
            member_limit=1,
            expire_date=expiracion,
            name=f"FREE-{uid}"[:32],
        )
        enlace = invitacion.invite_link

        mensaje_exito = (
            "✅ **¡NÚMERO VERIFICADO CON ÉXITO!**\n\n"
            "👥 Aquí tienes tu enlace de invitación personal para el **GRUPO FREE**:\n\n"
            f"🔗 `{enlace}`\n\n"
            "⏳ *Aviso: Este enlace es válido por 24 horas y de un solo uso.*"
        )
        bot.send_message(
            uid,
            mensaje_exito,
            parse_mode="Markdown",
            reply_markup=telebot.types.ReplyKeyboardRemove(),
            disable_web_page_preview=True,
        )
    except Exception as exc:
        print(f"❌ Error al entregar enlace de invitación: {type(exc).__name__} - {exc}")
        try:
            bot.send_message(
                uid,
                "⚠️ Ocurrió un error al generar tu invitación. Por favor, vuelve a tocar **GRUPO FREE**.",
                parse_mode="Markdown",
                reply_markup=telebot.types.ReplyKeyboardRemove()
            )
        except Exception:
            pass


def registrar_verificacion_free(bot):
    """Función de compatibilidad para main.py."""
    pass


def mostrar_menu_verificacion(bot, usuario):
    uid = usuario.id
    if _es_miembro_grupo(bot, uid):
        bot.send_message(usuario.id, "ℹ️ Ya eres miembro del GRUPO FREE.", parse_mode="Markdown")
        return
    if not _puede_invitar_usuarios(bot):
        bot.send_message(usuario.id, "⚠️ El bot necesita permisos de administrador para gestionar accesos.", parse_mode="Markdown")
        return
    
    _solicitar_contacto_usuario(bot, usuario)


def mostrar_menu_keys(bot, uid):
    """Alias de compatibilidad con main.py."""
    try:
        user = bot.get_chat(uid)
        mostrar_menu_verificacion(bot, user)
    except Exception as exc:
        print(f"⚠️ Error en menú alternativo: {type(exc).__name__}")
        bot.send_message(uid, "Por favor, toca **GRUPO FREE** nuevamente.", parse_mode="Markdown")


def registrar_canje_free(bot):
    """Nombre antiguo conservado para compatibilidad."""
    pass


def _solicitar_contacto_usuario(bot, usuario):
    uid = usuario.id
    teclado = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    teclado.add(telebot.types.KeyboardButton("📱 Compartir mi número", request_contact=True))
    bot.clear_step_handler_by_chat_id(uid)
    
    texto_solicitud = (
        "👥 **GRUPO FREE — VERIFICACIÓN**\n\n"
        "Para continuar de forma segura y registrarte en nuestro sistema, "
        "por favor comparte tu número de Telegram utilizando el botón inferior."
    )
    msg = bot.send_message(
        uid,
        texto_solicitud,
        parse_mode="Markdown",
        reply_markup=teclado,
    )
    bot.register_next_step_handler(msg, lambda m: _procesar_contacto_recibido(bot, m, usuario))


def _procesar_contacto_recibido(bot, message, usuario_original):
    uid = usuario_original.id
    if message.chat.type != "private" or message.from_user.id != uid:
        return
    
    contacto = message.contact
    if not contacto or contacto.user_id != uid:
        bot.send_message(
            uid,
            "⚠️ Debes compartir **tu propio contacto** utilizando el botón oficial proporcionado.",
            parse_mode="Markdown"
        )
        _solicitar_contacto_usuario(bot, usuario_original)
        return
    
    usuario = message.from_user
    datos = {
        "telegramId": uid,
        "username": usuario.username or "",
        "nombre": " ".join(x for x in [usuario.first_name, usuario.last_name] if x),
        "telefono": (contacto.phone_number or "").replace(" ", "").replace("-", "").lstrip("+"),
    }
    
    try:
        respuesta = requests.post(API_CONTACTOS, json=datos, timeout=TIMEOUT)
        datos_respuesta = respuesta.json() if respuesta.ok else {}
        api_aceptada = respuesta.ok and (not isinstance(datos_respuesta, dict) or (
            datos_respuesta.get("success") is not False and not datos_respuesta.get("error")))
    except (requests.RequestException, ValueError) as exc:
        print(f"❌ Error en API de contactos: {type(exc).__name__}")
        api_aceptada = False

    if not api_aceptada:
        bot.send_message(
            uid,
            "❌ No se pudo registrar tu número en la API. Por favor, presiona **GRUPO FREE** e inténtalo de nuevo.",
            parse_mode="Markdown",
            reply_markup=telebot.types.ReplyKeyboardRemove()
        )
        return

    _entregar_enlace_invitacion(bot, uid)


def ejecutar_grupo_free(bot, call):
    """Callback principal disparado por el botón GRUPO FREE."""
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    
    if not call.message or call.message.chat.type != "private":
        return
        
    usuario = call.from_user
    if _es_miembro_grupo(bot, usuario.id):
        bot.send_message(usuario.id, "ℹ️ Ya eres miembro del GRUPO FREE.", parse_mode="Markdown")
        return
    
    _solicitar_contacto_usuario(bot, usuario)