import re
import requests
import telebot
from html import escape
from unicodedata import normalize, combining

# ============================================================
# CONFIGURACIÓN
# ============================================================
ID_GRUPO = -1004497451670
WEB_KEYS = "https://loschuckys.com/key"
API_CANJEAR = "https://bot-apis-zkmk.vercel.app/api/keys/canjear"
API_CONTACTOS = "https://bot-apis-zkmk.vercel.app/api/contactos"

# Este conjunto es temporal. La API de contactos conserva el registro.
usuarios_verificados = set()


def contacto_registrado(user_id):
    """Comprueba la memoria y, tras un reinicio, la API del proyecto."""
    if user_id in usuarios_verificados:
        return True

    try:
        from main.guardar import usuario_registrado_contactos
        if usuario_registrado_contactos(user_id) is True:
            usuarios_verificados.add(user_id)
            return True
    except Exception as error:
        print(f"⚠️ No se pudo consultar el contacto: {error}")

    return False


def _texto_normalizado(valor):
    texto = normalize("NFKD", str(valor).lower())
    return "".join(c for c in texto if not combining(c))


def interpretar_respuesta_canje(respuesta):
    """Devuelve (True, False o None, motivo).

    None significa que el resultado es incierto: NO se vuelve a canjear
    automáticamente porque el servidor pudo haber consumido la key.
    """
    codigo = respuesta.status_code
    print(f"📡 API keys: HTTP {codigo}")
    print("📦 Content-Type:", respuesta.headers.get("Content-Type", "desconocido"))

    # Algunos servidores confirman una operación con 204, sin cuerpo.
    if codigo == 204:
        return True, "HTTP 204: operación confirmada sin contenido"

    # 5xx, 408 y 429 no permiten asumir que la operación no ocurrió.
    if codigo >= 500 or codigo in (408, 429):
        return None, f"HTTP {codigo}: estado del canje incierto"

    if not respuesta.ok:
        return False, f"HTTP {codigo}: solicitud rechazada"

    cuerpo = (respuesta.text or "").strip()
    if not cuerpo:
        return None, "Respuesta exitosa, pero sin confirmación de canje"

    try:
        datos = respuesta.json()
    except ValueError:
        datos = cuerpo

    if isinstance(datos, bool):
        return datos, "Confirmación booleana de API"

    if isinstance(datos, dict):
        print("📋 Campos recibidos:", list(datos.keys()))

        error = datos.get("error")
        if error not in (None, False, "", 0):
            return False, "La API indicó un error"

        flags = ("success", "ok", "valida", "valid", "canjeada", "canjeado", "redeemed", "exito")
        for campo in flags:
            valor = datos.get(campo)
            if valor is False or (isinstance(valor, str) and valor.lower() == "false"):
                return False, f"{campo}=false"

        estado = _texto_normalizado(datos.get("status") or datos.get("estado") or "")
        if estado in ("error", "failed", "invalid", "expired", "used", "rechazado", "invalida", "vencida", "utilizada"):
            return False, f"Estado: {estado}"

        for campo in flags:
            valor = datos.get(campo)
            if valor is True or (isinstance(valor, str) and valor.lower() == "true"):
                return True, f"{campo}=true"

        if estado in ("success", "ok", "redeemed", "canjeada", "canjeado", "completado", "exitoso"):
            return True, f"Estado: {estado}"

        texto = _texto_normalizado(datos.get("message") or datos.get("mensaje") or "")
    elif isinstance(datos, str):
        texto = _texto_normalizado(datos)
    else:
        return None, "Formato de respuesta no reconocido"

    errores = (
        "key invalida", "clave invalida", "ya utilizada", "ya canjeada",
        "key vencida", "clave vencida", "no se pudo", "canje rechazado",
        "key no encontrada", "codigo invalido", "error al canjear"
    )
    if any(frase in texto for frase in errores):
        return False, "La respuesta indica que la key fue rechazada"

    exitos = (
        "key canjeada correctamente", "clave canjeada correctamente",
        "canjeada correctamente", "canjeado correctamente",
        "canje exitoso", "canje realizado", "codigo canjeado",
        "successfully redeemed"
    )
    if any(frase in texto for frase in exitos) or texto in ("ok", "true", "success", "canjeado", "canjeada"):
        return True, "La respuesta confirma el canje"

    return None, "La API respondió, pero no confirmó explícitamente el canje"


# ============================================================
# BOTONES DE GENERACIÓN Y CANJE
# ============================================================
def mostrar_menu_keys(bot, user_id):
    usuarios_verificados.add(user_id)

    teclado = telebot.types.InlineKeyboardMarkup(row_width=1)
    teclado.add(
        telebot.types.InlineKeyboardButton("🔑 GENERAR MI KEY", url=WEB_KEYS),
        telebot.types.InlineKeyboardButton("✅ CANJEAR MI KEY", callback_data="free_canjear_key")
    )

    bot.send_message(
        user_id,
        "✅ <b>CONTACTO REGISTRADO</b>\n\n"
        "👥 <b>ACCESO AL GRUPO FREE</b>\n\n"
        "1️⃣ Presiona GENERAR MI KEY.\n"
        "2️⃣ Genera una key de 6 dígitos en la página.\n"
        "3️⃣ Regresa a este bot.\n"
        "4️⃣ Presiona CANJEAR MI KEY.\n"
        "5️⃣ Recibe tu enlace del grupo.\n\n"
        "⚠️ Cada key solo se puede canjear una vez.",
        parse_mode="HTML",
        reply_markup=teclado
    )


def registrar_canje_free(bot):
    """Llamar UNA vez desde main.py antes de iniciar el polling."""

    @bot.callback_query_handler(func=lambda call: call.data == "free_canjear_key")
    def solicitar_key(call):
        try:
            bot.answer_callback_query(call.id)
        except Exception as error:
            print("⚠️ Error respondiendo callback:", error)

        user_id = call.from_user.id
        if call.message.chat.type != "private":
            return

        if not contacto_registrado(user_id):
            bot.send_message(user_id, "⚠️ Primero comparte tu número desde GRUPO FREE.")
            return

        try:
            miembro = bot.get_chat_member(ID_GRUPO, user_id)
            if miembro.status in ("member", "administrator", "creator"):
                bot.send_message(user_id, "✅ Ya perteneces al Grupo FREE.")
                return
        except Exception as error:
            # Para usuarios que todavía no están en el grupo esto puede ser normal.
            print("⚠️ No se pudo comprobar membresía:", error)

        mensaje = bot.send_message(
            user_id,
            "🔑 <b>CANJEAR KEY</b>\n\n"
            "Envía tu código de 6 dígitos.\n\n"
            "Ejemplo: <code>583291</code>",
            parse_mode="HTML"
        )
        bot.register_next_step_handler(mensaje, lambda msg: verificar_key(bot, msg, user_id))


def verificar_key(bot, message, user_id):
    if message.chat.type != "private" or message.from_user.id != user_id:
        return

    key = (message.text or "").strip()
    if not re.fullmatch(r"[0-9]{6}", key):
        bot.send_message(
            user_id,
            "❌ <b>KEY INVÁLIDA</b>\n\n"
            "Ingresa exactamente 6 números y vuelve a tocar CANJEAR MI KEY.",
            parse_mode="HTML"
        )
        return

    if not contacto_registrado(user_id):
        bot.send_message(user_id, "⚠️ Primero registra tu contacto en GRUPO FREE.")
        return

    # Verificar permisos ANTES de consumir la key.
    try:
        info_bot = bot.get_me()
        admin = bot.get_chat_member(ID_GRUPO, info_bot.id)
        if admin.status not in ("administrator", "creator"):
            raise RuntimeError("El bot no es administrador")
        if admin.status == "administrator" and admin.can_invite_users is not True:
            raise RuntimeError("Falta permiso para invitar usuarios")
    except Exception as error:
        print("❌ Error de permisos:", error)
        bot.send_message(user_id, "❌ El grupo no está disponible. Tu key aún no fue canjeada.")
        return

    payload = {"key": key, "usuarioId": str(user_id)}
    print("🔑 Solicitando canje a la API (sin registrar key ni teléfono)...")

    # No reintentar POST automáticamente: podría consumir dos veces la key.
    try:
        respuesta = requests.post(
            API_CANJEAR,
            json=payload,
            headers={"Accept": "application/json"},
            timeout=(5, 35)
        )
        valido, detalle = interpretar_respuesta_canje(respuesta)
        print("📋 Evaluación del canje:", detalle)
    except requests.exceptions.Timeout as error:
        print("❌ Timeout API keys:", type(error).__name__)
        bot.send_message(
            user_id,
            "⚠️ <b>CANJE NO CONFIRMADO</b>\n\n"
            "La API tardó demasiado en responder. Es posible que haya consumido la key. "
            "Consulta su estado antes de reintentar.",
            parse_mode="HTML"
        )
        return
    except requests.exceptions.RequestException as error:
        print("❌ Error conexión API keys:", type(error).__name__, error)
        bot.send_message(
            user_id,
            "⚠️ No se pudo confirmar el canje con el servidor. "
            "Comprueba el estado de la key antes de reintentar."
        )
        return

    if valido is False:
        bot.send_message(
            user_id,
            "❌ <b>KEY RECHAZADA</b>\n\n"
            "La API no aceptó el canje. Verifica que tu key sea correcta, "
            "vigente y no haya sido utilizada.",
            parse_mode="HTML"
        )
        return

    if valido is None:
        bot.send_message(
            user_id,
            "⚠️ <b>CANJE NO CONFIRMADO</b>\n\n"
            "El servidor respondió, pero no confirmó explícitamente que la key se canjeó. "
            "Consulta su estado antes de intentarlo otra vez.",
            parse_mode="HTML"
        )
        return

    # Solo conceder acceso cuando la API confirma el canje.
    try:
        invitacion = bot.create_chat_invite_link(
            chat_id=ID_GRUPO,
            member_limit=1,
            name=f"FREE-{user_id}"
        )
        bot.send_message(
            user_id,
            "✅ <b>KEY CANJEADA CORRECTAMENTE</b>\n\n"
            "🎉 <b>ACCESO AL GRUPO FREE</b>\n\n"
            f"🔗 {invitacion.invite_link}\n\n"
            "⚠️ Enlace limitado a un miembro.",
            parse_mode="HTML"
        )
        usuarios_verificados.discard(user_id)
        print("✅ Invitación creada y enviada al usuario")
    except Exception as error:
        print("❌ Error entregando invitación:", error)
        bot.send_message(
            user_id,
            "⚠️ <b>KEY CANJEADA</b>\n\n"
            "La API aceptó tu key, pero no se pudo entregar el enlace. "
            "Contacta al administrador para recuperar el acceso.",
            parse_mode="HTML"
        )


# ============================================================
# GRUPO FREE: REGISTRO DE CONTACTO ANTES DEL CANJE
# ============================================================
def ejecutar_grupo_free(bot, call):
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    user_id = call.from_user.id
    if call.message.chat.type != "private":
        bot.send_message(
            call.message.chat.id,
            "🔒 Abre el chat privado del bot y toca GRUPO FREE para compartir tu número."
        )
        return

    try:
        miembro = bot.get_chat_member(chat_id=ID_GRUPO, user_id=user_id)
        if miembro.status in ("member", "administrator", "creator"):
            bot.send_message(
                user_id,
                "⚠️ <b>Ya eres miembro de este grupo.</b>\n\nNo necesitas otro enlace.",
                parse_mode="HTML"
            )
            return
    except Exception as error:
        print("⚠️ No fue posible comprobar membresía:", error)

    if contacto_registrado(user_id):
        mostrar_menu_keys(bot, user_id)
        return

    markup = telebot.types.ReplyKeyboardMarkup(
        one_time_keyboard=True,
        resize_keyboard=True,
        input_field_placeholder="Presiona el botón de abajo 👇"
    )
    markup.add(
        telebot.types.KeyboardButton(
            text="📱 Compartir mi número telefónico",
            request_contact=True
        )
    )

    def procesar_contacto(message):
        if message.chat.type != "private" or message.from_user.id != user_id:
            return

        quitar_teclado = telebot.types.ReplyKeyboardRemove()
        if not message.contact:
            bot.send_message(
                user_id,
                "❌ Debes presionar <b>📱 Compartir mi número telefónico</b>.\n\n"
                "Toca GRUPO FREE para reintentar.",
                parse_mode="HTML",
                reply_markup=quitar_teclado
            )
            return

        if message.contact.user_id != user_id:
            bot.send_message(
                user_id,
                "❌ Comparte <b>tu propio número</b> utilizando el botón de Telegram.\n\n"
                "Toca GRUPO FREE para reintentar.",
                parse_mode="HTML",
                reply_markup=quitar_teclado
            )
            return

        nombre = message.from_user.first_name or ""
        apellido = message.from_user.last_name or ""
        nombre_completo = f"{nombre} {apellido}".strip()
        username = message.from_user.username or ""
        telefono = (message.contact.phone_number or "").replace(" ", "").replace("-", "")
        if telefono.startswith("+"):
            telefono = telefono[1:]

        if not telefono:
            bot.send_message(
                user_id,
                "❌ No se recibió un teléfono válido. Toca GRUPO FREE para reintentar.",
                reply_markup=quitar_teclado
            )
            return

        payload = {
            "telegramId": user_id,
            "username": username,
            "nombre": nombre_completo,
            "telefono": telefono
        }

        try:
            respuesta = requests.post(API_CONTACTOS, json=payload, timeout=(5, 15))
            print("📡 API contactos: HTTP", respuesta.status_code)

            registrado = respuesta.ok
            try:
                datos = respuesta.json()
                if isinstance(datos, dict):
                    if datos.get("success") is False or datos.get("ok") is False or datos.get("error"):
                        registrado = False
            except ValueError:
                pass

            if not registrado:
                bot.send_message(
                    user_id,
                    "❌ <b>No se pudo registrar tu contacto.</b>\n\n"
                    f"Servidor: HTTP {respuesta.status_code}. Inténtalo nuevamente.",
                    parse_mode="HTML",
                    reply_markup=quitar_teclado
                )
                return
        except requests.exceptions.Timeout:
            bot.send_message(
                user_id,
                "⚠️ El servidor de contactos tardó demasiado. "
                "Consulta tu registro antes de volver a enviarlo.",
                reply_markup=quitar_teclado
            )
            return
        except requests.exceptions.RequestException as error:
            print("❌ Error API contactos:", type(error).__name__)
            bot.send_message(
                user_id,
                "❌ No se pudo conectar con el servidor de contactos. Inténtalo nuevamente.",
                reply_markup=quitar_teclado
            )
            return

        bot.send_message(
            user_id,
            "✅ <b>NÚMERO REGISTRADO CORRECTAMENTE</b>\n\n"
            f"👤 <b>Usuario:</b> {escape(nombre_completo)}\n"
            f"📱 <b>Teléfono:</b> {escape(telefono)}\n\n"
            "🔑 Ahora genera y canjea tu key para recibir acceso al grupo.",
            parse_mode="HTML",
            reply_markup=quitar_teclado
        )
        mostrar_menu_keys(bot, user_id)

    try:
        mensaje = bot.send_message(
            user_id,
            "👥 <b>UNIRSE AL GRUPO FREE</b>\n\n"
            "Para obtener el enlace, puedes compartir tu número vinculado a Telegram. "
            "Se guardará en la API de contactos para gestionar tu acceso.\n\n"
            "👇 Presiona el botón si aceptas compartirlo.",
            parse_mode="HTML",
            reply_markup=markup
        )
        bot.register_next_step_handler(mensaje, procesar_contacto)
    except Exception as error:
        print(f"❌ No se pudo solicitar el contacto: {error}")
