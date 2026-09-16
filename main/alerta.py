import copy
import html
import threading
import time
from datetime import timedelta

import requests
from telebot import types
from telebot.apihelper import ApiTelegramException


# ============================================================
# CONFIGURACIÓN
# ============================================================
API_USUARIOS = "https://bot-apis-zkmk.vercel.app/api/users"

ADMIN_IDS = [
    8635600472,
]

# Ritmo base. Telegram puede pedir más espera mediante retry_after.
PAUSA_ENTRE_ENVIOS = 0.06
ACTUALIZAR_PROGRESO_CADA = 25
MAX_REINTENTOS = 3
TIMEOUT_API = 20

# Sesión HTTP reutilizable
HTTP = requests.Session()
HTTP.headers.update({"User-Agent": "LosChuckysBot/1.0"})

# Borradores por administrador
alertas = {}

# Estado de difusiones activas por administrador
# {
#   admin_id: {
#       "pausada": bool,
#       "cancelada": bool,
#       "activa": bool,
#       "lock": threading.Lock(),
#   }
# }
difusiones = {}


# ============================================================
# DATOS POR DEFECTO
# ============================================================
def nueva_alerta():
    return {
        "texto": None,
        "foto": None,
        "video": None,
        "botones": [],
        "fijar": False,
    }


def nuevo_estado_difusion():
    return {
        "pausada": False,
        "cancelada": False,
        "activa": True,
        "lock": threading.Lock(),
    }


# ============================================================
# UTILIDADES
# ============================================================
def crear_barra_progreso(actual, total, longitud=15):
    if total <= 0:
        return "░" * longitud

    porcentaje = min(max(actual / total, 0), 1)
    llenos = int(porcentaje * longitud)
    return "█" * llenos + "░" * (longitud - llenos)


def formatear_tiempo(segundos):
    segundos = max(int(segundos), 0)
    return str(timedelta(seconds=segundos))


def responder_callback(bot, call, texto=None, alerta=False):
    try:
        bot.answer_callback_query(
            call.id,
            text=texto,
            show_alert=alerta,
        )
    except Exception:
        pass


def editar_seguro(bot, texto, chat_id, message_id, **kwargs):
    try:
        return bot.edit_message_text(
            texto,
            chat_id,
            message_id,
            **kwargs,
        )
    except Exception:
        return None


def es_admin(user_id):
    return user_id in ADMIN_IDS


# ============================================================
# API DE USUARIOS
# ============================================================
def obtener_usuarios():
    usuarios_totales = []
    pagina = 1

    try:
        while True:
            respuesta = HTTP.get(
                API_USUARIOS,
                params={"page": pagina},
                timeout=TIMEOUT_API,
            )
            respuesta.raise_for_status()
            data = respuesta.json()

            usuarios = data.get("usuarios", [])
            paginas = data.get("pages", 1)

            for usuario in usuarios:
                telegram_id = usuario.get("telegramId")
                bloqueado = usuario.get("botBloqueado", False)

                if telegram_id and not bloqueado:
                    usuarios_totales.append(usuario)

            print(
                f"📥 Página {pagina}/{paginas}"
                f" | usuarios acumulados: {len(usuarios_totales)}"
            )

            if pagina >= paginas:
                break

            pagina += 1

        # Eliminar duplicados por telegramId
        unicos = {}
        for usuario in usuarios_totales:
            telegram_id = usuario.get("telegramId")
            if telegram_id:
                unicos[str(telegram_id)] = usuario

        return list(unicos.values())

    except Exception as error:
        print(f"❌ Error obteniendo usuarios: {error}")
        return []


def marcar_usuario_bloqueado(telegram_id):
    """
    Tu API ya usa POST /api/users para registrar/actualizar usuarios.
    Se intenta marcar botBloqueado=True sin detener la difusión si falla.
    """
    try:
        respuesta = HTTP.post(
            API_USUARIOS,
            json={
                "telegramId": telegram_id,
                "botBloqueado": True,
            },
            timeout=10,
        )

        if respuesta.status_code >= 400:
            print(
                f"⚠️ No se pudo marcar bloqueado {telegram_id}: "
                f"HTTP {respuesta.status_code}"
            )
    except Exception as error:
        print(f"⚠️ Error marcando bloqueado {telegram_id}: {error}")


# ============================================================
# PERSONALIZAR TEXTO
# ============================================================
def preparar_texto(texto, usuario):
    if not texto:
        return ""

    telegram_id = usuario.get("telegramId")
    nombre = usuario.get("nombre") or "Usuario"
    username = usuario.get("username") or ""

    # Escapar los datos que vienen de la API para no romper HTML.
    nombre_html = html.escape(str(nombre))
    username_html = html.escape(str(username))

    mention = (
        f'<a href="tg://user?id={telegram_id}">'
        f"{nombre_html}"
        f"</a>"
    )

    username_final = f"@{username_html}" if username else "Sin username"

    return (
        texto.replace("%mention%", mention)
        .replace("%firstname%", nombre_html)
        .replace("%username%", username_final)
    )


# ============================================================
# BOTONES
# ============================================================
def crear_markup_botones(botones):
    if not botones:
        return None

    markup = types.InlineKeyboardMarkup(row_width=2)
    fila = []

    for boton in botones:
        texto = boton.get("texto")
        url = boton.get("url")

        if not texto or not url:
            continue

        fila.append(types.InlineKeyboardButton(texto, url=url))

        # Dos botones por fila
        if len(fila) == 2:
            markup.row(*fila)
            fila = []

    if fila:
        markup.row(*fila)

    return markup


# ============================================================
# ENVIAR CONTENIDO
# FOTO O VIDEO + TEXTO + BOTONES
# ============================================================
def enviar_contenido(bot, chat_id, datos, usuario=None):
    texto = datos.get("texto")
    foto = datos.get("foto")
    video = datos.get("video")
    botones = datos.get("botones", [])

    if usuario:
        texto = preparar_texto(texto, usuario)

    markup = crear_markup_botones(botones)

    if foto:
        return bot.send_photo(
            chat_id,
            foto,
            caption=texto or None,
            parse_mode="HTML",
            reply_markup=markup,
        )

    if video:
        return bot.send_video(
            chat_id,
            video,
            caption=texto or None,
            parse_mode="HTML",
            reply_markup=markup,
            supports_streaming=True,
        )

    if texto:
        return bot.send_message(
            chat_id,
            texto,
            parse_mode="HTML",
            reply_markup=markup,
            disable_web_page_preview=False,
        )

    return None


# ============================================================
# REINTENTOS DE ENVÍO
# ============================================================
def enviar_con_reintentos(bot, telegram_id, datos, usuario):
    """
    Devuelve:
      (True, mensaje, False)  -> enviado
      (False, None, True)     -> usuario bloqueó / chat inválido
      (False, None, False)    -> otro error
    """
    intento = 0

    while intento < MAX_REINTENTOS:
        intento += 1

        try:
            mensaje = enviar_contenido(
                bot,
                telegram_id,
                datos,
                usuario,
            )
            return True, mensaje, False

        except ApiTelegramException as error:
            texto_error = str(error).lower()

            if "too many requests" in texto_error:
                espera = 3

                try:
                    resultado = error.result_json or {}
                    parametros = resultado.get("parameters", {})
                    espera = int(parametros.get("retry_after", 3))
                except Exception:
                    pass

                print(
                    f"⏳ Rate limit para {telegram_id}. "
                    f"Esperando {espera}s. Intento {intento}/{MAX_REINTENTOS}"
                )
                time.sleep(espera + 1)
                continue

            bloqueado = any(
                fragmento in texto_error
                for fragmento in (
                    "blocked by the user",
                    "bot was blocked by the user",
                    "chat not found",
                    "user is deactivated",
                    "forbidden",
                )
            )

            if bloqueado:
                return False, None, True

            print(f"❌ Telegram {telegram_id}: {error}")
            return False, None, False

        except Exception as error:
            print(f"❌ Error usuario {telegram_id}: {error}")
            return False, None, False

    return False, None, False


# ============================================================
# PANEL DE PROGRESO
# ============================================================
def markup_control_difusion(admin_id):
    estado = difusiones.get(admin_id)
    if not estado:
        return None

    markup = types.InlineKeyboardMarkup(row_width=2)

    if estado.get("pausada"):
        markup.row(
            types.InlineKeyboardButton(
                "▶️ Continuar",
                callback_data="alerta_continuar",
            ),
            types.InlineKeyboardButton(
                "⏹ Cancelar",
                callback_data="alerta_cancelar_envio",
            ),
        )
    else:
        markup.row(
            types.InlineKeyboardButton(
                "⏸ Pausar",
                callback_data="alerta_pausar",
            ),
            types.InlineKeyboardButton(
                "⏹ Cancelar",
                callback_data="alerta_cancelar_envio",
            ),
        )

    return markup


def texto_progreso(
    titulo,
    total,
    procesados,
    enviados,
    fallidos,
    bloqueados,
    inicio,
    pausada=False,
):
    porcentaje = round((procesados / total) * 100, 1) if total else 0
    barra = crear_barra_progreso(procesados, total)

    transcurrido = max(time.time() - inicio, 0.001)
    velocidad = procesados / transcurrido if procesados else 0

    restantes = max(total - procesados, 0)
    segundos_restantes = restantes / velocidad if velocidad > 0 else 0

    estado_extra = "\n⏸ <b>PAUSADA</b>" if pausada else ""

    return (
        f"{titulo}{estado_extra}\n\n"
        f"👥 Total: <b>{total}</b>\n"
        f"✅ Enviados: <b>{enviados}</b>\n"
        f"❌ Fallidos: <b>{fallidos}</b>\n"
        f"🚫 Bloquearon bot: <b>{bloqueados}</b>\n\n"
        f"📊 <b>Progreso</b>\n"
        f"<code>{barra}</code>\n"
        f"<b>{porcentaje}%</b> • {procesados}/{total}\n\n"
        f"⚡ Velocidad: <b>{velocidad:.1f} usuarios/s</b>\n"
        f"⏱️ Tiempo: <b>{formatear_tiempo(transcurrido)}</b>\n"
        f"⏳ Restante aprox.: <b>{formatear_tiempo(segundos_restantes)}</b>"
    )


# ============================================================
# REGISTRAR MÓDULO
# ============================================================
def registrar_alerta(bot):

    # ========================================================
    # PANEL PRINCIPAL
    # ========================================================
    def mostrar_panel(chat_id, user_id, message_id=None):
        datos = alertas.get(user_id, nueva_alerta())

        foto_estado = "✅ Ver" if datos.get("foto") else "👀 Ver"
        video_estado = "✅ Ver" if datos.get("video") else "👀 Ver"
        texto_estado = "✅ Ver" if datos.get("texto") else "👀 Ver"
        botones_estado = "✅ Ver" if datos.get("botones") else "👀 Ver"
        fijar_estado = "✅ SÍ" if datos.get("fijar") else "❌ NO"

        markup = types.InlineKeyboardMarkup()

        markup.row(
            types.InlineKeyboardButton(
                "🖼 Imagen",
                callback_data="alerta_foto",
            ),
            types.InlineKeyboardButton(
                foto_estado,
                callback_data="alerta_ver_foto",
            ),
        )

        markup.row(
            types.InlineKeyboardButton(
                "🎬 Video",
                callback_data="alerta_video",
            ),
            types.InlineKeyboardButton(
                video_estado,
                callback_data="alerta_ver_video",
            ),
        )

        markup.row(
            types.InlineKeyboardButton(
                "🔤 Texto",
                callback_data="alerta_texto",
            ),
            types.InlineKeyboardButton(
                texto_estado,
                callback_data="alerta_ver_texto",
            ),
        )

        markup.row(
            types.InlineKeyboardButton(
                "⌨️ Botones",
                callback_data="alerta_botones",
            ),
            types.InlineKeyboardButton(
                botones_estado,
                callback_data="alerta_ver_botones",
            ),
        )

        markup.row(
            types.InlineKeyboardButton(
                "📌 Fijar",
                callback_data="alerta_fijar",
            ),
            types.InlineKeyboardButton(
                fijar_estado,
                callback_data="alerta_fijar",
            ),
        )

        markup.row(
            types.InlineKeyboardButton(
                "👀 Vista previa completa",
                callback_data="alerta_preview",
            )
        )

        markup.row(
            types.InlineKeyboardButton(
                "❌ Cancelar",
                callback_data="alerta_cancelar",
            ),
            types.InlineKeyboardButton(
                "Siguiente ➡️",
                callback_data="alerta_siguiente",
            ),
        )

        texto_panel = (
            "📢 <b>Difusión · Los Chuckys</b>\n\n"
            "Configura tu difusión con:\n"
            "🖼 Imagen o 🎬 Video\n"
            "🔤 Texto\n"
            "⌨️ Botones\n\n"
            "Luego usa la vista previa antes de enviar."
        )

        if message_id:
            resultado = editar_seguro(
                bot,
                texto_panel,
                chat_id,
                message_id,
                reply_markup=markup,
                parse_mode="HTML",
            )
            if resultado:
                return

        bot.send_message(
            chat_id,
            texto_panel,
            reply_markup=markup,
            parse_mode="HTML",
        )

    # ========================================================
    # /alerta
    # ========================================================
    @bot.message_handler(commands=["alerta"])
    def comando_alerta(message):
        user_id = message.from_user.id

        if not es_admin(user_id):
            bot.reply_to(
                message,
                "⛔ <b>No tienes permiso para usar /alerta.</b>",
                parse_mode="HTML",
            )
            return

        estado = difusiones.get(user_id)
        if estado and estado.get("activa"):
            bot.reply_to(
                message,
                "⚠️ <b>Ya tienes una difusión en proceso.</b>\n\n"
                "Primero termínala o cancélala.",
                parse_mode="HTML",
            )
            return

        alertas[user_id] = nueva_alerta()
        mostrar_panel(message.chat.id, user_id)

    # ========================================================
    # FOTO / IMAGEN
    # ========================================================
    @bot.callback_query_handler(func=lambda call: call.data == "alerta_foto")
    def alerta_foto(call):
        user_id = call.from_user.id
        if not es_admin(user_id):
            return

        responder_callback(bot, call)

        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton(
                "🗑 Quitar imagen",
                callback_data="alerta_quitar_foto",
            )
        )
        markup.row(
            types.InlineKeyboardButton(
                "⬅️ Volver",
                callback_data="alerta_regresar",
            )
        )

        editar_seguro(
            bot,
            "🖼 <b>Envía la imagen para la difusión</b>\n\n"
            "Envía la foto directamente desde Telegram.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML",
        )

        bot.register_next_step_handler_by_chat_id(
            call.message.chat.id,
            guardar_foto,
        )

    def guardar_foto(message):
        user_id = message.from_user.id

        if not es_admin(user_id) or user_id not in alertas:
            return

        if not message.photo:
            bot.send_message(
                message.chat.id,
                "❌ <b>Debes enviar una imagen/foto.</b>",
                parse_mode="HTML",
            )
            return

        # Telegram entrega varias resoluciones; la última suele ser la mayor.
        alertas[user_id]["foto"] = message.photo[-1].file_id

        # Solo un medio por difusión: una foto reemplaza al video.
        alertas[user_id]["video"] = None

        bot.send_message(
            message.chat.id,
            "✅ <b>Imagen guardada.</b>",
            parse_mode="HTML",
        )
        mostrar_panel(message.chat.id, user_id)

    @bot.callback_query_handler(func=lambda call: call.data == "alerta_ver_foto")
    def ver_foto(call):
        datos = alertas.get(call.from_user.id, {})
        foto = datos.get("foto")

        if not foto:
            responder_callback(
                bot,
                call,
                "❌ No agregaste una imagen.",
                True,
            )
            return

        responder_callback(bot, call)
        bot.send_photo(call.message.chat.id, foto)

    @bot.callback_query_handler(func=lambda call: call.data == "alerta_quitar_foto")
    def quitar_foto(call):
        user_id = call.from_user.id

        if user_id in alertas:
            alertas[user_id]["foto"] = None

        bot.clear_step_handler_by_chat_id(call.message.chat.id)
        responder_callback(bot, call, "✅ Imagen eliminada.")
        mostrar_panel(
            call.message.chat.id,
            user_id,
            call.message.message_id,
        )

    # ========================================================
    # VIDEO
    # ========================================================
    @bot.callback_query_handler(func=lambda call: call.data == "alerta_video")
    def alerta_video(call):
        user_id = call.from_user.id
        if not es_admin(user_id):
            return

        responder_callback(bot, call)

        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton(
                "🗑 Quitar video",
                callback_data="alerta_quitar_video",
            )
        )
        markup.row(
            types.InlineKeyboardButton(
                "⬅️ Volver",
                callback_data="alerta_regresar",
            )
        )

        editar_seguro(
            bot,
            "🎬 <b>Envía el video para la difusión</b>\n\n"
            "Si ya habías elegido una imagen, el video la reemplazará.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML",
        )

        bot.register_next_step_handler_by_chat_id(
            call.message.chat.id,
            guardar_video,
        )

    def guardar_video(message):
        user_id = message.from_user.id

        if not es_admin(user_id) or user_id not in alertas:
            return

        if not message.video:
            bot.send_message(
                message.chat.id,
                "❌ <b>Debes enviar un video.</b>",
                parse_mode="HTML",
            )
            return

        alertas[user_id]["video"] = message.video.file_id

        # Solo un medio por difusión: un video reemplaza a la foto.
        alertas[user_id]["foto"] = None

        bot.send_message(
            message.chat.id,
            "✅ <b>Video guardado.</b>",
            parse_mode="HTML",
        )
        mostrar_panel(message.chat.id, user_id)

    @bot.callback_query_handler(func=lambda call: call.data == "alerta_ver_video")
    def ver_video(call):
        datos = alertas.get(call.from_user.id, {})
        video = datos.get("video")

        if not video:
            responder_callback(
                bot,
                call,
                "❌ No agregaste un video.",
                True,
            )
            return

        responder_callback(bot, call)
        bot.send_video(call.message.chat.id, video, supports_streaming=True)

    @bot.callback_query_handler(func=lambda call: call.data == "alerta_quitar_video")
    def quitar_video(call):
        user_id = call.from_user.id

        if user_id in alertas:
            alertas[user_id]["video"] = None

        bot.clear_step_handler_by_chat_id(call.message.chat.id)
        responder_callback(bot, call, "✅ Video eliminado.")
        mostrar_panel(
            call.message.chat.id,
            user_id,
            call.message.message_id,
        )

    # ========================================================
    # TEXTO
    # ========================================================
    @bot.callback_query_handler(func=lambda call: call.data == "alerta_texto")
    def alerta_texto(call):
        user_id = call.from_user.id
        if not es_admin(user_id):
            return

        responder_callback(bot, call)

        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton(
                "🗑 Quitar texto",
                callback_data="alerta_quitar_texto",
            )
        )
        markup.row(
            types.InlineKeyboardButton(
                "⬅️ Volver",
                callback_data="alerta_regresar",
            )
        )

        editar_seguro(
            bot,
            "📄 <b>Envía el texto del mensaje</b>\n\n"
            "Variables disponibles:\n\n"
            "• <code>%mention%</code> → menciona al usuario\n"
            "• <code>%firstname%</code> → nombre\n"
            "• <code>%username%</code> → username",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML",
        )

        bot.register_next_step_handler_by_chat_id(
            call.message.chat.id,
            guardar_texto,
        )

    def guardar_texto(message):
        user_id = message.from_user.id

        if not es_admin(user_id) or user_id not in alertas:
            return

        if not message.text:
            bot.send_message(
                message.chat.id,
                "❌ Debes enviar un texto.",
            )
            return

        alertas[user_id]["texto"] = message.text

        bot.send_message(
            message.chat.id,
            "✅ <b>Texto guardado.</b>",
            parse_mode="HTML",
        )
        mostrar_panel(message.chat.id, user_id)

    @bot.callback_query_handler(func=lambda call: call.data == "alerta_ver_texto")
    def ver_texto(call):
        datos = alertas.get(call.from_user.id, {})
        texto = datos.get("texto")

        if not texto:
            responder_callback(bot, call, "❌ No agregaste texto.", True)
            return

        responder_callback(bot, call)
        bot.send_message(
            call.message.chat.id,
            "📄 <b>Texto actual:</b>\n\n" + texto,
            parse_mode="HTML",
        )

    @bot.callback_query_handler(func=lambda call: call.data == "alerta_quitar_texto")
    def quitar_texto(call):
        user_id = call.from_user.id

        if user_id in alertas:
            alertas[user_id]["texto"] = None

        bot.clear_step_handler_by_chat_id(call.message.chat.id)
        responder_callback(bot, call, "✅ Texto eliminado.")
        mostrar_panel(
            call.message.chat.id,
            user_id,
            call.message.message_id,
        )

    # ========================================================
    # BOTONES
    # ========================================================
    @bot.callback_query_handler(func=lambda call: call.data == "alerta_botones")
    def alerta_botones(call):
        user_id = call.from_user.id
        if not es_admin(user_id):
            return

        responder_callback(bot, call)

        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton(
                "🗑 Quitar botones",
                callback_data="alerta_quitar_botones",
            )
        )
        markup.row(
            types.InlineKeyboardButton(
                "⬅️ Volver",
                callback_data="alerta_regresar",
            )
        )

        editar_seguro(
            bot,
            "⌨️ <b>Agregar botones</b>\n\n"
            "Envía un botón por línea:\n\n"
            "<code>Texto | https://enlace.com</code>\n\n"
            "Ejemplo:\n"
            "<code>🌐 Página web | https://loschuckys.com</code>\n"
            "<code>🤖 Abrir bot | https://t.me/LosChuckysXBot</code>\n\n"
            "Se mostrarán hasta 2 botones por fila.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=markup,
        )

        bot.register_next_step_handler_by_chat_id(
            call.message.chat.id,
            guardar_botones,
        )

    def guardar_botones(message):
        user_id = message.from_user.id

        if not es_admin(user_id) or user_id not in alertas:
            return

        if not message.text:
            bot.send_message(message.chat.id, "❌ Debes enviar texto.")
            return

        botones = []

        for linea in message.text.splitlines():
            if "|" not in linea:
                continue

            texto_boton, url = linea.split("|", 1)
            texto_boton = texto_boton.strip()
            url = url.strip()

            if (
                texto_boton
                and url.startswith(("http://", "https://", "tg://"))
            ):
                botones.append({
                    "texto": texto_boton,
                    "url": url,
                })

        if not botones:
            bot.send_message(
                message.chat.id,
                "❌ <b>No encontré botones válidos.</b>\n\n"
                "Ejemplo:\n"
                "<code>Web | https://loschuckys.com</code>",
                parse_mode="HTML",
            )
            return

        alertas[user_id]["botones"] = botones

        bot.send_message(
            message.chat.id,
            f"✅ <b>{len(botones)} botón(es) guardado(s).</b>",
            parse_mode="HTML",
        )
        mostrar_panel(message.chat.id, user_id)

    @bot.callback_query_handler(func=lambda call: call.data == "alerta_ver_botones")
    def ver_botones(call):
        datos = alertas.get(call.from_user.id, {})
        botones = datos.get("botones", [])

        if not botones:
            responder_callback(bot, call, "❌ No agregaste botones.", True)
            return

        responder_callback(bot, call)
        bot.send_message(
            call.message.chat.id,
            "⌨️ <b>Vista previa de botones</b>",
            reply_markup=crear_markup_botones(botones),
            parse_mode="HTML",
        )

    @bot.callback_query_handler(func=lambda call: call.data == "alerta_quitar_botones")
    def quitar_botones(call):
        user_id = call.from_user.id

        if user_id in alertas:
            alertas[user_id]["botones"] = []

        bot.clear_step_handler_by_chat_id(call.message.chat.id)
        responder_callback(bot, call, "✅ Botones eliminados.")
        mostrar_panel(
            call.message.chat.id,
            user_id,
            call.message.message_id,
        )

    # ========================================================
    # FIJAR
    # ========================================================
    @bot.callback_query_handler(func=lambda call: call.data == "alerta_fijar")
    def alerta_fijar(call):
        user_id = call.from_user.id

        if user_id not in alertas:
            return

        actual = alertas[user_id].get("fijar", False)
        alertas[user_id]["fijar"] = not actual

        responder_callback(
            bot,
            call,
            "📌 Fijar activado." if not actual else "📌 Fijar desactivado.",
        )

        mostrar_panel(
            call.message.chat.id,
            user_id,
            call.message.message_id,
        )

    # ========================================================
    # VISTA PREVIA
    # ========================================================
    @bot.callback_query_handler(func=lambda call: call.data == "alerta_preview")
    def alerta_preview(call):
        user_id = call.from_user.id
        datos = alertas.get(user_id, {})

        if (
            not datos.get("texto")
            and not datos.get("foto")
            and not datos.get("video")
        ):
            responder_callback(
                bot,
                call,
                "❌ Agrega texto, imagen o video.",
                True,
            )
            return

        responder_callback(bot, call)

        usuario_preview = {
            "telegramId": user_id,
            "nombre": call.from_user.first_name or "Usuario",
            "username": call.from_user.username or "",
        }

        try:
            enviar_contenido(
                bot,
                call.message.chat.id,
                datos,
                usuario_preview,
            )
        except Exception as error:
            bot.send_message(
                call.message.chat.id,
                "❌ <b>No pude generar la vista previa.</b>\n\n"
                f"<code>{html.escape(str(error))}</code>\n\n"
                "Revisa el HTML del texto.",
                parse_mode="HTML",
            )

    # ========================================================
    # SIGUIENTE / CONFIRMACIÓN
    # ========================================================
    @bot.callback_query_handler(func=lambda call: call.data == "alerta_siguiente")
    def alerta_siguiente(call):
        user_id = call.from_user.id
        datos = alertas.get(user_id, {})

        if (
            not datos.get("texto")
            and not datos.get("foto")
            and not datos.get("video")
        ):
            responder_callback(
                bot,
                call,
                "❌ Primero agrega contenido.",
                True,
            )
            return

        estado = difusiones.get(user_id)
        if estado and estado.get("activa"):
            responder_callback(
                bot,
                call,
                "⚠️ Ya hay una difusión activa.",
                True,
            )
            return

        responder_callback(bot, call)

        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton(
                "🚀 ENVIAR DIFUSIÓN",
                callback_data="alerta_enviar",
            )
        )
        markup.row(
            types.InlineKeyboardButton(
                "⬅️ Volver",
                callback_data="alerta_regresar",
            ),
            types.InlineKeyboardButton(
                "❌ Cancelar",
                callback_data="alerta_cancelar",
            ),
        )

        resumen = (
            "🚨 <b>CONFIRMAR DIFUSIÓN</b>\n\n"
            f"🖼 Imagen: <b>{'SÍ' if datos.get('foto') else 'NO'}</b>\n"
            f"🎬 Video: <b>{'SÍ' if datos.get('video') else 'NO'}</b>\n"
            f"🔤 Texto: <b>{'SÍ' if datos.get('texto') else 'NO'}</b>\n"
            f"⌨️ Botones: <b>{len(datos.get('botones', []))}</b>\n"
            f"📌 Fijar: <b>{'SÍ' if datos.get('fijar') else 'NO'}</b>\n\n"
            "El mensaje se enviará a todos los usuarios activos.\n\n"
            "⚠️ Confirma para comenzar."
        )

        editar_seguro(
            bot,
            resumen,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML",
        )

    # ========================================================
    # REGRESAR / CANCELAR BORRADOR
    # ========================================================
    @bot.callback_query_handler(func=lambda call: call.data == "alerta_regresar")
    def alerta_regresar(call):
        bot.clear_step_handler_by_chat_id(call.message.chat.id)
        responder_callback(bot, call)
        mostrar_panel(
            call.message.chat.id,
            call.from_user.id,
            call.message.message_id,
        )

    @bot.callback_query_handler(func=lambda call: call.data == "alerta_cancelar")
    def alerta_cancelar(call):
        user_id = call.from_user.id

        alertas.pop(user_id, None)
        bot.clear_step_handler_by_chat_id(call.message.chat.id)
        responder_callback(bot, call, "Difusión cancelada.")

        editar_seguro(
            bot,
            "❌ <b>Difusión cancelada.</b>",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
        )

    # ========================================================
    # INICIAR DIFUSIÓN
    # ========================================================
    @bot.callback_query_handler(func=lambda call: call.data == "alerta_enviar")
    def alerta_enviar(call):
        user_id = call.from_user.id

        if not es_admin(user_id):
            return

        datos = alertas.get(user_id)
        if not datos:
            responder_callback(bot, call, "❌ No hay difusión preparada.", True)
            return

        estado_actual = difusiones.get(user_id)
        if estado_actual and estado_actual.get("activa"):
            responder_callback(
                bot,
                call,
                "⚠️ Ya existe una difusión en proceso.",
                True,
            )
            return

        # Marcar activa ANTES de iniciar el hilo para evitar doble clic.
        difusiones[user_id] = nuevo_estado_difusion()

        responder_callback(bot, call, "🚀 Iniciando difusión...")

        editar_seguro(
            bot,
            "⏳ <b>Cargando usuarios...</b>\n\n"
            "Consultando la base de datos.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=markup_control_difusion(user_id),
        )

        hilo = threading.Thread(
            target=ejecutar_difusion,
            args=(
                bot,
                call.message.chat.id,
                call.message.message_id,
                user_id,
                copy.deepcopy(datos),
            ),
            daemon=True,
        )
        hilo.start()

    # ========================================================
    # PAUSAR / CONTINUAR / CANCELAR ENVÍO
    # ========================================================
    @bot.callback_query_handler(func=lambda call: call.data == "alerta_pausar")
    def alerta_pausar(call):
        user_id = call.from_user.id
        estado = difusiones.get(user_id)

        if not estado or not estado.get("activa"):
            responder_callback(bot, call, "No hay difusión activa.", True)
            return

        with estado["lock"]:
            estado["pausada"] = True

        responder_callback(bot, call, "⏸ Difusión pausada.")

    @bot.callback_query_handler(func=lambda call: call.data == "alerta_continuar")
    def alerta_continuar(call):
        user_id = call.from_user.id
        estado = difusiones.get(user_id)

        if not estado or not estado.get("activa"):
            responder_callback(bot, call, "No hay difusión activa.", True)
            return

        with estado["lock"]:
            estado["pausada"] = False

        responder_callback(bot, call, "▶️ Difusión continuada.")

    @bot.callback_query_handler(func=lambda call: call.data == "alerta_cancelar_envio")
    def alerta_cancelar_envio(call):
        user_id = call.from_user.id
        estado = difusiones.get(user_id)

        if not estado or not estado.get("activa"):
            responder_callback(bot, call, "No hay difusión activa.", True)
            return

        with estado["lock"]:
            estado["cancelada"] = True
            estado["pausada"] = False

        responder_callback(bot, call, "⏹ Cancelando difusión...")

    # ========================================================
    # PROCESAR DIFUSIÓN
    # ========================================================
    def ejecutar_difusion(
        bot,
        chat_admin,
        mensaje_estado,
        admin_id,
        datos,
    ):
        inicio = time.time()
        usuarios = obtener_usuarios()
        estado = difusiones.get(admin_id)

        if not usuarios:
            editar_seguro(
                bot,
                "❌ <b>No se pudieron cargar usuarios.</b>",
                chat_admin,
                mensaje_estado,
                parse_mode="HTML",
            )
            if estado:
                estado["activa"] = False
            return

        total = len(usuarios)
        enviados = 0
        fallidos = 0
        bloqueados = 0
        procesados = 0

        editar_seguro(
            bot,
            texto_progreso(
                "🚀 <b>DIFUSIÓN INICIADA</b>",
                total,
                0,
                0,
                0,
                0,
                inicio,
            ),
            chat_admin,
            mensaje_estado,
            parse_mode="HTML",
            reply_markup=markup_control_difusion(admin_id),
        )

        cancelada = False

        for usuario in usuarios:
            estado = difusiones.get(admin_id)
            if not estado:
                cancelada = True
                break

            # Cancelación
            with estado["lock"]:
                if estado.get("cancelada"):
                    cancelada = True
                    break

            # Pausa
            while True:
                estado = difusiones.get(admin_id)
                if not estado:
                    cancelada = True
                    break

                with estado["lock"]:
                    esta_cancelada = estado.get("cancelada")
                    esta_pausada = estado.get("pausada")

                if esta_cancelada:
                    cancelada = True
                    break

                if not esta_pausada:
                    break

                editar_seguro(
                    bot,
                    texto_progreso(
                        "⏸ <b>DIFUSIÓN EN PAUSA</b>",
                        total,
                        procesados,
                        enviados,
                        fallidos,
                        bloqueados,
                        inicio,
                        pausada=True,
                    ),
                    chat_admin,
                    mensaje_estado,
                    parse_mode="HTML",
                    reply_markup=markup_control_difusion(admin_id),
                )
                time.sleep(0.5)

            if cancelada:
                break

            telegram_id = usuario.get("telegramId")

            if not telegram_id:
                procesados += 1
                fallidos += 1
                continue

            ok, mensaje_enviado, usuario_bloqueado = enviar_con_reintentos(
                bot,
                telegram_id,
                datos,
                usuario,
            )

            procesados += 1

            if ok:
                enviados += 1

                if datos.get("fijar") and mensaje_enviado:
                    try:
                        bot.pin_chat_message(
                            telegram_id,
                            mensaje_enviado.message_id,
                            disable_notification=True,
                        )
                    except Exception:
                        pass
            else:
                fallidos += 1

                if usuario_bloqueado:
                    bloqueados += 1
                    marcar_usuario_bloqueado(telegram_id)

            time.sleep(PAUSA_ENTRE_ENVIOS)

            if (
                procesados % ACTUALIZAR_PROGRESO_CADA == 0
                or procesados == total
            ):
                editar_seguro(
                    bot,
                    texto_progreso(
                        "🚀 <b>DIFUSIÓN EN PROCESO</b>",
                        total,
                        procesados,
                        enviados,
                        fallidos,
                        bloqueados,
                        inicio,
                    ),
                    chat_admin,
                    mensaje_estado,
                    parse_mode="HTML",
                    reply_markup=markup_control_difusion(admin_id),
                )

        # ====================================================
        # FINAL
        # ====================================================
        estado = difusiones.get(admin_id)
        if estado:
            with estado["lock"]:
                estado["activa"] = False
                estado["pausada"] = False

        duracion = time.time() - inicio

        if cancelada:
            porcentaje = round((procesados / total) * 100, 1) if total else 0
            barra = crear_barra_progreso(procesados, total)

            texto_final = (
                "⏹ <b>DIFUSIÓN CANCELADA</b>\n\n"
                f"👥 Total: <b>{total}</b>\n"
                f"✅ Enviados: <b>{enviados}</b>\n"
                f"❌ Fallidos: <b>{fallidos}</b>\n"
                f"🚫 Bloquearon bot: <b>{bloqueados}</b>\n\n"
                f"📊 <code>{barra}</code>\n"
                f"<b>{porcentaje}%</b> • {procesados}/{total}\n\n"
                f"⏱️ Tiempo: <b>{formatear_tiempo(duracion)}</b>"
            )
        else:
            texto_final = (
                "✅ <b>DIFUSIÓN FINALIZADA</b>\n\n"
                f"👥 Total: <b>{total}</b>\n"
                f"✅ Enviados: <b>{enviados}</b>\n"
                f"❌ Fallidos: <b>{fallidos}</b>\n"
                f"🚫 Bloquearon bot: <b>{bloqueados}</b>\n\n"
                "📊 <b>Progreso</b>\n"
                "<code>███████████████</code>\n"
                "<b>100%</b>\n\n"
                f"⏱️ Tiempo total: <b>{formatear_tiempo(duracion)}</b>"
            )

        editar_seguro(
            bot,
            texto_final,
            chat_admin,
            mensaje_estado,
            parse_mode="HTML",
        )

        alertas.pop(admin_id, None)
        difusiones.pop(admin_id, None)
