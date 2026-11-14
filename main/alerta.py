import copy
import html
import threading
import time
from datetime import timedelta
from urllib.parse import urlparse

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

# Ritmo base (segundos entre envíos para evitar flood limits de Telegram)
PAUSA_ENTRE_ENVIOS = 0.06
ACTUALIZAR_PROGRESO_CADA = 25
INTERVALO_PROGRESO_SEGUNDOS = 3
MAX_BOTONES = 20        # Límite de botones configurado a 20
BOTONES_POR_FILA = 5    # Máximo de 5 botones por fila en la botonera
MAX_REINTENTOS = 3
TIMEOUT_API = 20

# Sesión HTTP reutilizable
HTTP = requests.Session()
HTTP.headers.update({"User-Agent": "LosChuckysBot/2.0"})

# Borradores por administrador
alertas = {}

# Estado de difusiones activas por administrador
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
        "ultimo_panel_pausa": 0,
    }


# ============================================================
# UTILIDADES Y DISEÑO
# ============================================================
def crear_barra_progreso(actual, total, longitud=12):
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
        bot.answer_callback_query(call.id, text=texto, show_alert=alerta)
    except Exception:
        pass


def editar_seguro(bot, texto, chat_id, message_id, **kwargs):
    try:
        return bot.edit_message_text(texto, chat_id, message_id, **kwargs)
    except Exception:
        return None


def es_admin(user_id):
    return user_id in ADMIN_IDS


# ============================================================
# API DE USUARIOS (CORREGIDA Y BLINDADA)
# ============================================================
def obtener_usuarios():
    """Obtiene TODAS las páginas de la API secuencialmente hasta agotar los registros."""
    unicos = {}
    pagina = 1
    try:
        while pagina <= 10000:  # Límite de seguridad amplio
            respuesta = HTTP.get(API_USUARIOS, params={"page": pagina}, timeout=TIMEOUT_API)
            respuesta.raise_for_status()
            data = respuesta.json()
            
            # Soportar diferentes estructuras de respuesta que pueda devolver la API
            if isinstance(data, list):
                usuarios = data
            elif isinstance(data, dict):
                usuarios = data.get("usuarios", data.get("users", data.get("data", [])))
            else:
                usuarios = []
            
            # Si la página actual no trae usuarios, significa que llegamos al final de la base de datos
            if not isinstance(usuarios, list) or len(usuarios) == 0:
                print(f"📥 Paginación completada. Total de páginas leídas: {pagina - 1}")
                break
            
            for usuario in usuarios:
                if not isinstance(usuario, dict) or usuario.get("botBloqueado", False):
                    continue
                try:
                    telegram_id = int(usuario.get("telegramId"))
                    if telegram_id > 0:
                        unicos[telegram_id] = dict(usuario, telegramId=telegram_id)
                except (ValueError, TypeError):
                    continue
            
            print(f"📥 Página {pagina} procesada | Usuarios únicos acumulados: {len(unicos)}")
            pagina += 1
            
        return list(unicos.values())
    except Exception as error:
        print(f"❌ Error obteniendo usuarios en la página {pagina}: {error}")
        # Devuelve lo que alcanzó a rescatar en lugar de dejar la lista vacía
        return list(unicos.values())


def marcar_usuario_bloqueado(telegram_id):
    try:
        HTTP.post(
            API_USUARIOS,
            json={"telegramId": telegram_id, "botBloqueado": True},
            timeout=10,
        )
    except Exception as error:
        print(f"⚠️ Error marcando bloqueado {telegram_id}: {error}")


# ============================================================
# PREPARACIÓN DE TEXTO Y CONTENIDO
# ============================================================
def preparar_texto(texto, usuario):
    if not texto:
        return ""

    telegram_id = usuario.get("telegramId")
    nombre = usuario.get("nombre") or "Usuario"
    username = usuario.get("username") or ""

    nombre_html = html.escape(str(nombre))
    username_html = html.escape(str(username))

    mention = f'<a href="tg://user?id={telegram_id}">{nombre_html}</a>'
    username_final = f"@{username_html}" if username else "Sin username"

    return (
        texto.replace("%mention%", mention)
        .replace("%firstname%", nombre_html)
        .replace("%username%", username_final)
    )


def crear_markup_botones(botones):
    if not botones:
        return None

    markup = types.InlineKeyboardMarkup(row_width=BOTONES_POR_FILA)
    fila = []

    for boton in botones:
        texto = boton.get("texto")
        url = boton.get("url")
        if not texto or not url:
            continue
        fila.append(types.InlineKeyboardButton(texto, url=url))
        if len(fila) == BOTONES_POR_FILA:
            markup.row(*fila)
            fila = []

    if fila:
        markup.row(*fila)
    return markup


def enviar_contenido(bot, chat_id, datos, usuario=None):
    texto = datos.get("texto") or ""
    foto = datos.get("foto")
    video = datos.get("video")
    markup = crear_markup_botones(datos.get("botones", []))

    if usuario:
        texto = preparar_texto(texto, usuario)

    if foto or video:
        medio = foto or video
        enviar = bot.send_photo if foto else bot.send_video
        kwargs = {"parse_mode": "HTML"}
        if video:
            kwargs["supports_streaming"] = True
        
        if len(texto) <= 1024:
            return enviar(chat_id, medio, caption=texto or None, reply_markup=markup, **kwargs)
        
        resultado = enviar(chat_id, medio, **kwargs)
        bot.send_message(chat_id, texto, parse_mode="HTML", reply_markup=markup)
        return resultado

    if texto:
        return bot.send_message(
            chat_id, texto, parse_mode="HTML", reply_markup=markup, disable_web_page_preview=False
        )
    return None


def url_boton_valida(url):
    if url.startswith("tg://"):
        return bool(urlparse(url).netloc)
    if url.startswith(("https://", "http://")):
        return bool(urlparse(url).netloc)
    return False


# ============================================================
# REINTENTOS Y ENVÍO SEGURO
# ============================================================
def enviar_con_reintentos(bot, telegram_id, datos, usuario):
    intento = 0
    while intento < MAX_REINTENTOS:
        intento += 1
        try:
            mensaje = enviar_contenido(bot, telegram_id, datos, usuario)
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
                time.sleep(espera + 1)
                continue

            bloqueado = any(
                f in texto_error
                for f in (
                    "blocked by the user",
                    "bot was blocked",
                    "chat not found",
                    "user is deactivated",
                    "forbidden",
                )
            )
            if bloqueado:
                return False, None, True

            return False, None, False
        except Exception:
            return False, None, False

    return False, None, False


# ============================================================
# PANELES Y CONTROLES VISUALES
# ============================================================
def markup_control_difusion(admin_id):
    estado = difusiones.get(admin_id)
    if not estado:
        return None

    markup = types.InlineKeyboardMarkup(row_width=2)
    if estado.get("pausada"):
        markup.row(
            types.InlineKeyboardButton("▶️ Reanudar", callback_data="alerta_continuar"),
            types.InlineKeyboardButton("⏹ Cancelar", callback_data="alerta_cancelar_envio"),
        )
    else:
        markup.row(
            types.InlineKeyboardButton("⏸ Pausar", callback_data="alerta_pausar"),
            types.InlineKeyboardButton("⏹ Cancelar", callback_data="alerta_cancelar_envio"),
        )
    return markup


def texto_progreso(titulo, total, procesados, enviados, fallidos, bloqueados, inicio, pausada=False):
    porcentaje = round((procesados / total) * 100, 1) if total else 0
    barra = crear_barra_progreso(procesados, total)
    transcurrido = max(time.time() - inicio, 0.001)
    velocidad = procesados / transcurrido if procesados else 0
    restantes = max(total - procesados, 0)
    segundos_restantes = restantes / velocidad if velocidad > 0 else 0

    estado_extra = "\n\n⏸ <b>ESTADO: PAUSADO</b>" if pausada else ""

    return (
        f"╭━━━ <b>{titulo}</b> ━━━╮{estado_extra}\n\n"
        f"👥 <b>Total audiencia:</b> <code>{total}</code>\n"
        f"✅ <b>Enviados con éxito:</b> <code>{enviados}</code>\n"
        f"❌ <b>Fallidos:</b> <code>{fallidos}</code>\n"
        f"🚫 <b>Bloqueos detectados:</b> <code>{bloqueados}</code>\n\n"
        f"📊 <b>Progreso general:</b>\n"
        f"<code>{barra}</code> <b>{porcentaje}%</b>\n"
        f"📌 <i>Procesados: {procesados} / {total}</i>\n\n"
        f"⚡ <b>Velocidad:</b> <code>{velocidad:.1f} msg/s</code>\n"
        f"⏱️ <b>Tiempo transcurrido:</b> <code>{formatear_tiempo(transcurrido)}</code>\n"
        f"⏳ <b>Tiempo restante:</b> <code>{formatear_tiempo(segundos_restantes)}</code>\n"
        f"╰━━━━━━━━━━━━━━━━━━━━╯"
    )


# ============================================================
# REGISTRO DEL MÓDULO DE DIFUSIÓN
# ============================================================
def registrar_alerta(bot):

    def mostrar_panel(chat_id, user_id, message_id=None):
        if not es_admin(user_id):
            return
        datos = alertas.get(user_id, nueva_alerta())

        f_estado = "🟢 Configurado" if datos.get("foto") else "⚪ Vacío"
        v_estado = "🟢 Configurado" if datos.get("video") else "⚪ Vacío"
        t_estado = "🟢 Configurado" if datos.get("texto") else "⚪ Vacío"
        b_estado = f"🟢 ({len(datos.get('botones', []))})" if datos.get("botones") else "⚪ Vacío"
        p_estado = "✅ SÍ" if datos.get("fijar") else "❌ NO"

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.row(
            types.InlineKeyboardButton("🖼 Imagen", callback_data="alerta_foto"),
            types.InlineKeyboardButton(f_estado, callback_data="alerta_ver_foto"),
        )
        markup.row(
            types.InlineKeyboardButton("🎬 Video", callback_data="alerta_video"),
            types.InlineKeyboardButton(v_estado, callback_data="alerta_ver_video"),
        )
        markup.row(
            types.InlineKeyboardButton("🔤 Texto", callback_data="alerta_texto"),
            types.InlineKeyboardButton(t_estado, callback_data="alerta_ver_texto"),
        )
        markup.row(
            types.InlineKeyboardButton("⌨️ Botones", callback_data="alerta_botones"),
            types.InlineKeyboardButton(b_estado, callback_data="alerta_ver_botones"),
        )
        markup.row(
            types.InlineKeyboardButton("📌 Fijar Mensaje", callback_data="alerta_fijar"),
            types.InlineKeyboardButton(p_estado, callback_data="alerta_fijar"),
        )
        markup.row(
            types.InlineKeyboardButton("👁️ Vista Previa", callback_data="alerta_preview"),
        )
        markup.row(
            types.InlineKeyboardButton("❌ Cancelar", callback_data="alerta_cancelar"),
            types.InlineKeyboardButton("Siguiente ➡️", callback_data="alerta_siguiente"),
        )

        texto_panel = (
            "📢 <b>CENTRAL DE DIFUSIONES · LOSCHUCKYS</b>\n\n"
            "<i>Configura los elementos de tu campaña y envíalos de forma masiva y segura a todos los usuarios registrados.</i>\n\n"
            "👇 <b>Selecciona una opción para editar:</b>"
        )

        if message_id:
            resultado = editar_seguro(
                bot, texto_panel, chat_id, message_id, reply_markup=markup, parse_mode="HTML"
            )
            if resultado:
                return

        bot.send_message(chat_id, texto_panel, reply_markup=markup, parse_mode="HTML")

    @bot.message_handler(commands=["alerta"])
    def comando_alerta(message):
        user_id = message.from_user.id
        if not es_admin(user_id):
            bot.reply_to(message, "⛔ <b>No tienes permisos para usar este comando.</b>", parse_mode="HTML")
            return

        estado = difusiones.get(user_id)
        if estado and estado.get("activa"):
            bot.reply_to(message, "⚠️ <b>Ya tienes una difusión activa en este momento.</b>", parse_mode="HTML")
            return

        alertas[user_id] = nueva_alerta()
        mostrar_panel(message.chat.id, user_id)

    # ==================== FOTO ====================
    @bot.callback_query_handler(func=lambda call: call.data == "alerta_foto")
    def alerta_foto(call):
        if not es_admin(call.from_user.id):
            return
        responder_callback(bot, call)
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("🗑 Quitar Imagen", callback_data="alerta_quitar_foto"))
        markup.row(types.InlineKeyboardButton("⬅️ Volver al Panel", callback_data="alerta_regresar"))

        editar_seguro(
            bot,
            "🖼 <b>Envía la imagen para tu difusión</b>\n\nCualquier foto enviada aquí se establecerá como imagen principal (reemplazará al video si existía).",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML",
        )
        bot.clear_step_handler_by_chat_id(call.message.chat.id)
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, guardar_foto)

    def guardar_foto(message):
        user_id = message.from_user.id
        if not es_admin(user_id) or user_id not in alertas:
            return
        if not message.photo:
            bot.send_message(message.chat.id, "❌ <b>Debes enviar una imagen válida.</b>", parse_mode="HTML")
            return
        alertas[user_id]["foto"] = message.photo[-1].file_id
        alertas[user_id]["video"] = None
        bot.send_message(message.chat.id, "✅ <b>Imagen guardada correctamente.</b>", parse_mode="HTML")
        mostrar_panel(message.chat.id, user_id)

    @bot.callback_query_handler(func=lambda call: call.data == "alerta_ver_foto")
    def ver_foto(call):
        if not es_admin(call.from_user.id):
            return
        foto = alertas.get(call.from_user.id, {}).get("foto")
        if not foto:
            responder_callback(bot, call, "❌ No hay imagen configurada.", True)
            return
        responder_callback(bot, call)
        bot.send_photo(call.message.chat.id, foto)

    @bot.callback_query_handler(func=lambda call: call.data == "alerta_quitar_foto")
    def quitar_foto(call):
        if not es_admin(call.from_user.id):
            return
        user_id = call.from_user.id
        if user_id in alertas:
            alertas[user_id]["foto"] = None
        responder_callback(bot, call, "✅ Imagen eliminada.")
        mostrar_panel(call.message.chat.id, user_id, call.message.message_id)

    # ==================== VIDEO ====================
    @bot.callback_query_handler(func=lambda call: call.data == "alerta_video")
    def alerta_video(call):
        if not es_admin(call.from_user.id):
            return
        responder_callback(bot, call)
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("🗑 Quitar Video", callback_data="alerta_quitar_video"))
        markup.row(types.InlineKeyboardButton("⬅️ Volver al Panel", callback_data="alerta_regresar"))

        editar_seguro(
            bot,
            "🎬 <b>Envía el video para tu difusión</b>\n\nEl video reemplazará cualquier imagen configurada previamente.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML",
        )
        bot.clear_step_handler_by_chat_id(call.message.chat.id)
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, guardar_video)

    def guardar_video(message):
        user_id = message.from_user.id
        if not es_admin(user_id) or user_id not in alertas:
            return
        if not message.video:
            bot.send_message(message.chat.id, "❌ <b>Debes enviar un video válido.</b>", parse_mode="HTML")
            return
        alertas[user_id]["video"] = message.video.file_id
        alertas[user_id]["foto"] = None
        bot.send_message(message.chat.id, "✅ <b>Video guardado correctamente.</b>", parse_mode="HTML")
        mostrar_panel(message.chat.id, user_id)

    @bot.callback_query_handler(func=lambda call: call.data == "alerta_ver_video")
    def ver_video(call):
        if not es_admin(call.from_user.id):
            return
        video = alertas.get(call.from_user.id, {}).get("video")
        if not video:
            responder_callback(bot, call, "❌ No hay video configurado.", True)
            return
        responder_callback(bot, call)
        bot.send_video(call.message.chat.id, video, supports_streaming=True)

    @bot.callback_query_handler(func=lambda call: call.data == "alerta_quitar_video")
    def quitar_video(call):
        if not es_admin(call.from_user.id):
            return
        user_id = call.from_user.id
        if user_id in alertas:
            alertas[user_id]["video"] = None
        responder_callback(bot, call, "✅ Video eliminado.")
        mostrar_panel(call.message.chat.id, user_id, call.message.message_id)

    # ==================== TEXTO ====================
    @bot.callback_query_handler(func=lambda call: call.data == "alerta_texto")
    def alerta_texto(call):
        if not es_admin(call.from_user.id):
            return
        responder_callback(bot, call)
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("🗑 Quitar Texto", callback_data="alerta_quitar_texto"))
        markup.row(types.InlineKeyboardButton("⬅️ Volver al Panel", callback_data="alerta_regresar"))

        editar_seguro(
            bot,
            "🔤 <b>Envía el texto de la difusión</b>\n\n"
            "Variables dinámicas permitidas:\n"
            "• <code>%mention%</code> -> Mención con enlace al usuario\n"
            "• <code>%firstname%</code> -> Nombre del usuario\n"
            "• <code>%username%</code> -> Alias del usuario (@username)",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML",
        )
        bot.clear_step_handler_by_chat_id(call.message.chat.id)
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, guardar_texto)

    def guardar_texto(message):
        user_id = message.from_user.id
        if not es_admin(user_id) or user_id not in alertas:
            return
        if not message.text:
            bot.send_message(message.chat.id, "❌ Debes enviar un texto válido.")
            return
        if len(message.text) > 4096:
            bot.send_message(message.chat.id, "❌ El texto excede el límite de 4096 caracteres.")
            return
        alertas[user_id]["texto"] = message.text
        bot.send_message(message.chat.id, "✅ <b>Texto guardado exitosamente.</b>", parse_mode="HTML")
        mostrar_panel(message.chat.id, user_id)

    @bot.callback_query_handler(func=lambda call: call.data == "alerta_ver_texto")
    def ver_texto(call):
        if not es_admin(call.from_user.id):
            return
        texto = alertas.get(call.from_user.id, {}).get("texto")
        if not texto:
            responder_callback(bot, call, "❌ No hay texto configurado.", True)
            return
        responder_callback(bot, call)
        bot.send_message(call.message.chat.id, f"📄 <b>Texto actual:</b>\n\n{texto}", parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "alerta_quitar_texto")
    def quitar_texto(call):
        if not es_admin(call.from_user.id):
            return
        user_id = call.from_user.id
        if user_id in alertas:
            alertas[user_id]["texto"] = None
        responder_callback(bot, call, "✅ Texto eliminado.")
        mostrar_panel(call.message.chat.id, user_id, call.message.message_id)

    # ==================== BOTONES ====================
    @bot.callback_query_handler(func=lambda call: call.data == "alerta_botones")
    def alerta_botones(call):
        if not es_admin(call.from_user.id):
            return
        responder_callback(bot, call)
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("🗑 Quitar Botones", callback_data="alerta_quitar_botones"))
        markup.row(types.InlineKeyboardButton("⬅️ Volver al Panel", callback_data="alerta_regresar"))

        editar_seguro(
            bot,
            "⌨️ <b>Configurar Botones Inline</b>\n\n"
            f"Envía múltiples botones (hasta {MAX_BOTONES}), uno por línea:\n"
            "<code>Texto | https://enlace.com</code>\n\n"
            f"<i>Se acomodarán automáticamente hasta {BOTONES_POR_FILA} botones por fila.</i>\n\n"
            "Ejemplo:\n"
            "<code>🌐 Web | https://loschuckys.com</code>",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML",
        )
        bot.clear_step_handler_by_chat_id(call.message.chat.id)
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, guardar_botones)

    def guardar_botones(message):
        user_id = message.from_user.id
        if not es_admin(user_id) or user_id not in alertas:
            return
        if not message.text:
            bot.send_message(message.chat.id, "❌ Debes enviar contenido válido.")
            return

        botones = []
        for linea in message.text.splitlines():
            if "|" not in linea:
                continue
            t_boton, url = linea.split("|", 1)
            t_boton = t_boton.strip()
            url = url.strip()
            if t_boton and len(t_boton) <= 64 and url_boton_valida(url):
                botones.append({"texto": t_boton, "url": url})

        if not botones:
            bot.send_message(message.chat.id, "❌ <b>No se encontraron botones válidos.</b> Revisa el formato.", parse_mode="HTML")
            return

        alertas[user_id]["botones"] = botones[:MAX_BOTONES]
        bot.send_message(message.chat.id, f"✅ <b>{min(len(botones), MAX_BOTONES)} botón(es) guardado(s).</b>", parse_mode="HTML")
        mostrar_panel(message.chat.id, user_id)

    @bot.callback_query_handler(func=lambda call: call.data == "alerta_ver_botones")
    def ver_botones(call):
        if not es_admin(call.from_user.id):
            return
        botones = alertas.get(call.from_user.id, {}).get("botones", [])
        if not botones:
            responder_callback(bot, call, "❌ No hay botones configurados.", True)
            return
        responder_callback(bot, call)
        bot.send_message(call.message.chat.id, "⌨️ <b>Vista previa de botones:</b>", reply_markup=crear_markup_botones(botones), parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "alerta_quitar_botones")
    def quitar_botones(call):
        if not es_admin(call.from_user.id):
            return
        user_id = call.from_user.id
        if user_id in alertas:
            alertas[user_id]["botones"] = []
        responder_callback(bot, call, "✅ Botones eliminados.")
        mostrar_panel(call.message.chat.id, user_id, call.message.message_id)

    # ==================== FIJAR ====================
    @bot.callback_query_handler(func=lambda call: call.data == "alerta_fijar")
    def alerta_fijar(call):
        if not es_admin(call.from_user.id):
            return
        user_id = call.from_user.id
        if user_id not in alertas:
            return
        actual = alertas[user_id].get("fijar", False)
        alertas[user_id]["fijar"] = not actual
        responder_callback(bot, call, "📌 Fijado activado." if not actual else "📌 Fijado desactivado.")
        mostrar_panel(call.message.chat.id, user_id, call.message.message_id)

    # ==================== PREVIEW ====================
    @bot.callback_query_handler(func=lambda call: call.data == "alerta_preview")
    def alerta_preview(call):
        if not es_admin(call.from_user.id):
            return
        datos = alertas.get(call.from_user.id, {})
        if not datos.get("texto") and not datos.get("foto") and not datos.get("video"):
            responder_callback(bot, call, "❌ Agrega contenido antes de ver la vista previa.", True)
            return
        responder_callback(bot, call)
        usuario_preview = {
            "telegramId": call.from_user.id,
            "nombre": call.from_user.first_name or "Administrador",
            "username": call.from_user.username or "",
        }
        try:
            enviar_contenido(bot, call.message.chat.id, datos, usuario_preview)
        except Exception as error:
            bot.send_message(call.message.chat.id, f"❌ <b>Error en la vista previa:</b>\n<code>{html.escape(str(error))}</code>", parse_mode="HTML")

    # ==================== SIGUIENTE / CONFIRMACIÓN ====================
    @bot.callback_query_handler(func=lambda call: call.data == "alerta_siguiente")
    def alerta_siguiente(call):
        if not es_admin(call.from_user.id):
            return
        user_id = call.from_user.id
        datos = alertas.get(user_id, {})
        if not datos.get("texto") and not datos.get("foto") and not datos.get("video"):
            responder_callback(bot, call, "❌ Debes configurar al menos texto, foto o video.", True)
            return

        estado = difusiones.get(user_id)
        if estado and estado.get("activa"):
            responder_callback(bot, call, "⚠️ Ya hay una difusión en proceso.", True)
            return

        responder_callback(bot, call)
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("🚀 INICIAR ENVÍO MASIVO", callback_data="alerta_enviar"))
        markup.row(
            types.InlineKeyboardButton("⬅️ Volver", callback_data="alerta_regresar"),
            types.InlineKeyboardButton("❌ Cancelar", callback_data="alerta_cancelar"),
        )

        resumen = (
            "🚨 <b>CONFIRMACIÓN DE DIFUSIÓN</b>\n\n"
            f"🖼 <b>Imagen:</b> {'SÍ' if datos.get('foto') else 'NO'}\n"
            f"🎬 <b>Video:</b> {'SÍ' if datos.get('video') else 'NO'}\n"
            f"🔤 <b>Texto:</b> {'SÍ' if datos.get('texto') else 'NO'}\n"
            f"⌨️ <b>Botones:</b> {len(datos.get('botones', []))}\n"
            f"📌 <b>Fijar mensaje:</b> {'SÍ' if datos.get('fijar') else 'NO'}\n\n"
            "⚠️ <i>Estás a punto de enviar este mensaje a todos los usuarios activos. Verifica que todo esté correcto.</i>"
        )
        editar_seguro(bot, resumen, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == "alerta_regresar")
    def alerta_regresar(call):
        if not es_admin(call.from_user.id):
            return
        bot.clear_step_handler_by_chat_id(call.message.chat.id)
        responder_callback(bot, call)
        mostrar_panel(call.message.chat.id, call.from_user.id, call.message.message_id)

    @bot.callback_query_handler(func=lambda call: call.data == "alerta_cancelar")
    def alerta_cancelar(call):
        if not es_admin(call.from_user.id):
            return
        user_id = call.from_user.id
        alertas.pop(user_id, None)
        bot.clear_step_handler_by_chat_id(call.message.chat.id)
        responder_callback(bot, call, "Difusión cancelada.")
        editar_seguro(bot, "❌ <b>Difusión cancelada por el administrador.</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML")

    # ==================== ENVIAR DIFUSIÓN ====================
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
            responder_callback(bot, call, "⚠️ Ya existe una difusión en proceso.", True)
            return

        difusiones[user_id] = nuevo_estado_difusion()
        responder_callback(bot, call, "🚀 ¡Iniciando difusión masiva!")

        editar_seguro(
            bot,
            "⏳ <b>Conectando con la base de datos...</b>\nObteniendo lista de usuarios activos.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=markup_control_difusion(user_id),
        )

        hilo = threading.Thread(
            target=ejecutar_difusion,
            args=(bot, call.message.chat.id, call.message.message_id, user_id, copy.deepcopy(datos)),
            daemon=True,
        )
        hilo.start()

    @bot.callback_query_handler(func=lambda call: call.data == "alerta_pausar")
    def alerta_pausar(call):
        if not es_admin(call.from_user.id):
            return
        estado = difusiones.get(call.from_user.id)
        if estado:
            with estado["lock"]:
                estado["pausada"] = True
        responder_callback(bot, call, "⏸ Difusión pausada.")

    @bot.callback_query_handler(func=lambda call: call.data == "alerta_continuar")
    def alerta_continuar(call):
        if not es_admin(call.from_user.id):
            return
        estado = difusiones.get(call.from_user.id)
        if estado:
            with estado["lock"]:
                estado["pausada"] = False
        responder_callback(bot, call, "▶️ Difusión reanudada.")

    @bot.callback_query_handler(func=lambda call: call.data == "alerta_cancelar_envio")
    def alerta_cancelar_envio(call):
        if not es_admin(call.from_user.id):
            return
        estado = difusiones.get(call.from_user.id)
        if estado:
            with estado["lock"]:
                estado["cancelada"] = True
                estado["pausada"] = False
        responder_callback(bot, call, "⏹ Cancelando envío...")

    def ejecutar_difusion(bot, chat_admin, mensaje_estado, admin_id, datos):
        inicio = time.time()
        usuarios = obtener_usuarios()
        estado = difusiones.get(admin_id)

        if not usuarios:
            editar_seguro(bot, "❌ <b>No se pudieron cargar usuarios de la API.</b>", chat_admin, mensaje_estado, parse_mode="HTML")
            if estado:
                estado["activa"] = False
            return

        total = len(usuarios)
        enviados, fallidos, bloqueados, procesados = 0, 0, 0, 0

        editar_seguro(
            bot,
            texto_progreso("DIFUSIÓN EN CURSO", total, 0, 0, 0, 0, inicio),
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

            with estado["lock"]:
                if estado.get("cancelada"):
                    cancelada = True
                    break

            while True:
                estado = difusiones.get(admin_id)
                if not estado:
                    cancelada = True
                    break
                with estado["lock"]:
                    if estado.get("cancelada"):
                        cancelada = True
                        break
                    if not estado.get("pausada"):
                        break

                if time.monotonic() - estado.get("ultimo_panel_pausa", 0) >= INTERVALO_PROGRESO_SEGUNDOS:
                    estado["ultimo_panel_pausa"] = time.monotonic()
                    editar_seguro(
                        bot,
                        texto_progreso("DIFUSIÓN PAUSADA", total, procesados, enviados, fallidos, bloqueados, inicio, pausada=True),
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

            ok, mensaje_enviado, usuario_bloqueado = enviar_con_reintentos(bot, telegram_id, datos, usuario)
            procesados += 1

            if ok:
                enviados += 1
                if datos.get("fijar") and mensaje_enviado:
                    try:
                        bot.pin_chat_message(telegram_id, mensaje_enviado.message_id, disable_notification=True)
                    except Exception:
                        pass
            else:
                fallidos += 1
                if usuario_bloqueado:
                    bloqueados += 1
                    marcar_usuario_bloqueado(telegram_id)

            time.sleep(PAUSA_ENTRE_ENVIOS)

            if procesados % ACTUALIZAR_PROGRESO_CADA == 0 or procesados == total:
                editar_seguro(
                    bot,
                    texto_progreso("DIFUSIÓN EN CURSO", total, procesados, enviados, fallidos, bloqueados, inicio),
                    chat_admin,
                    mensaje_estado,
                    parse_mode="HTML",
                    reply_markup=markup_control_difusion(admin_id),
                )

        estado = difusiones.get(admin_id)
        if estado:
            with estado["lock"]:
                estado["activa"] = False
                estado["pausada"] = False

        duracion = time.time() - inicio

        if cancelada:
            texto_final = (
                f"⏹ <b>DIFUSIÓN CANCELADA</b>\n\n"
                f"👥 Procesados: <code>{procesados}/{total}</code>\n"
                f"✅ Enviados: <code>{enviados}</code>\n"
                f"❌ Fallidos: <code>{fallidos}</code>\n"
                f"⏱️ Tiempo: <code>{formatear_tiempo(duracion)}</code>"
            )
        else:
            texto_final = (
                f"✅ <b>DIFUSIÓN COMPLETADA CON ÉXITO</b>\n\n"
                f"👥 Total audiencia: <code>{total}</code>\n"
                f"✅ Enviados: <code>{enviados}</code>\n"
                f"❌ Fallidos: <code>{fallidos}</code>\n"
                f"🚫 Bloqueos detectados: <code>{bloqueados}</code>\n\n"
                f"📊 <b>Progreso:</b> <code>100%</code>\n"
                f"⏱️ Tiempo total: <code>{formatear_tiempo(duracion)}</code>"
            )

        editar_seguro(bot, texto_final, chat_admin, mensaje_estado, parse_mode="HTML")
        alertas.pop(admin_id, None)
        difusiones.pop(admin_id, None)
