import time
import threading
import requests

from telebot import types
from telebot.apihelper import ApiTelegramException


API_USUARIOS = "https://bot-apis-zkmk.vercel.app/api/users"

# ==========================================
# PON AQUÍ TU ID DE TELEGRAM
# ==========================================
ADMIN_IDS = [
   8635600472
]

# Configuración temporal de cada administrador
alertas = {}


# ==========================================
# CREAR DATOS POR DEFECTO
# ==========================================

def nueva_alerta():
    return {
        "texto": None,
        "multimedia": None,
        "botones": [],
        "fijar": False
    }


# ==========================================
# BARRA DE PROGRESO
# ==========================================

def crear_barra_progreso(actual, total, longitud=15):

    if total <= 0:
        return "░" * longitud

    porcentaje = min(actual / total, 1)

    llenos = int(porcentaje * longitud)

    return (
        "█" * llenos
        + "░" * (longitud - llenos)
    )


# ==========================================
# OBTENER TODOS LOS USUARIOS
# ==========================================

def obtener_usuarios():

    usuarios_totales = []

    pagina = 1

    try:

        while True:

            respuesta = requests.get(
                API_USUARIOS,
                params={
                    "page": pagina
                },
                timeout=20
            )

            respuesta.raise_for_status()

            data = respuesta.json()

            usuarios = data.get(
                "usuarios",
                []
            )

            paginas = data.get(
                "pages",
                1
            )

            for usuario in usuarios:

                telegram_id = usuario.get(
                    "telegramId"
                )

                bloqueado = usuario.get(
                    "botBloqueado",
                    False
                )

                if telegram_id and not bloqueado:

                    usuarios_totales.append(
                        usuario
                    )

            print(
                f"📥 Página {pagina}/{paginas}"
                f" | usuarios: {len(usuarios_totales)}"
            )

            if pagina >= paginas:
                break

            pagina += 1

        # Quitar duplicados
        unicos = {}

        for usuario in usuarios_totales:

            telegram_id = usuario.get(
                "telegramId"
            )

            unicos[telegram_id] = usuario

        return list(
            unicos.values()
        )

    except Exception as error:

        print(
            f"❌ Error obteniendo usuarios: {error}"
        )

        return []


# ==========================================
# PERSONALIZAR TEXTO
# ==========================================

def preparar_texto(texto, usuario):

    if not texto:
        return ""

    telegram_id = usuario.get(
        "telegramId"
    )

    nombre = (
        usuario.get("nombre")
        or "Usuario"
    )

    username = (
        usuario.get("username")
        or ""
    )

    mention = (
        f'<a href="tg://user?id={telegram_id}">'
        f'{nombre}'
        f'</a>'
    )

    username_final = (
        f"@{username}"
        if username
        else "Sin username"
    )

    texto = texto.replace(
        "%mention%",
        mention
    )

    texto = texto.replace(
        "%firstname%",
        nombre
    )

    texto = texto.replace(
        "%username%",
        username_final
    )

    return texto


# ==========================================
# CONSTRUIR BOTONES
# ==========================================

def crear_markup_botones(botones):

    if not botones:
        return None

    markup = types.InlineKeyboardMarkup()

    for boton in botones:

        texto = boton.get("texto")
        url = boton.get("url")

        if texto and url:

            markup.row(
                types.InlineKeyboardButton(
                    texto,
                    url=url
                )
            )

    return markup


# ==========================================
# ENVIAR CONTENIDO
# ==========================================

def enviar_contenido(
    bot,
    chat_id,
    datos,
    usuario=None
):

    texto = datos.get(
        "texto"
    )

    multimedia = datos.get(
        "multimedia"
    )

    botones = datos.get(
        "botones",
        []
    )

    if usuario:

        texto = preparar_texto(
            texto,
            usuario
        )

    markup = crear_markup_botones(
        botones
    )

    # FOTO
    if multimedia and multimedia["tipo"] == "foto":

        return bot.send_photo(
            chat_id,
            multimedia["file_id"],
            caption=texto or None,
            parse_mode="HTML",
            reply_markup=markup
        )

    # VIDEO
    elif multimedia and multimedia["tipo"] == "video":

        return bot.send_video(
            chat_id,
            multimedia["file_id"],
            caption=texto or None,
            parse_mode="HTML",
            reply_markup=markup
        )

    # GIF
    elif multimedia and multimedia["tipo"] == "gif":

        return bot.send_animation(
            chat_id,
            multimedia["file_id"],
            caption=texto or None,
            parse_mode="HTML",
            reply_markup=markup
        )

    # DOCUMENTO
    elif multimedia and multimedia["tipo"] == "documento":

        return bot.send_document(
            chat_id,
            multimedia["file_id"],
            caption=texto or None,
            parse_mode="HTML",
            reply_markup=markup
        )

    # AUDIO
    elif multimedia and multimedia["tipo"] == "audio":

        return bot.send_audio(
            chat_id,
            multimedia["file_id"],
            caption=texto or None,
            parse_mode="HTML",
            reply_markup=markup
        )

    # VOZ
    elif multimedia and multimedia["tipo"] == "voz":

        mensaje = bot.send_voice(
            chat_id,
            multimedia["file_id"]
        )

        if texto:

            bot.send_message(
                chat_id,
                texto,
                parse_mode="HTML",
                reply_markup=markup
            )

        return mensaje

    # VIDEO NOTE
    elif multimedia and multimedia["tipo"] == "video_note":

        mensaje = bot.send_video_note(
            chat_id,
            multimedia["file_id"]
        )

        if texto:

            bot.send_message(
                chat_id,
                texto,
                parse_mode="HTML",
                reply_markup=markup
            )

        return mensaje

    # STICKER
    elif multimedia and multimedia["tipo"] == "sticker":

        mensaje = bot.send_sticker(
            chat_id,
            multimedia["file_id"]
        )

        if texto:

            bot.send_message(
                chat_id,
                texto,
                parse_mode="HTML",
                reply_markup=markup
            )

        return mensaje

    # SOLO TEXTO
    elif texto:

        return bot.send_message(
            chat_id,
            texto,
            parse_mode="HTML",
            reply_markup=markup,
            disable_web_page_preview=False
        )

    return None


# ==========================================
# REGISTRAR MÓDULO
# ==========================================

def registrar_alerta(bot):

    # ======================================
    # MOSTRAR PANEL PRINCIPAL
    # ======================================

    def mostrar_panel(
        chat_id,
        user_id,
        message_id=None
    ):

        datos = alertas.get(
            user_id,
            nueva_alerta()
        )

        multimedia_estado = (
            "✅ Ver"
            if datos.get("multimedia")
            else "👀 Ver"
        )

        texto_estado = (
            "✅ Ver"
            if datos.get("texto")
            else "👀 Ver"
        )

        botones_estado = (
            "✅ Ver"
            if datos.get("botones")
            else "👀 Ver"
        )

        fijar_estado = (
            "✅ SÍ"
            if datos.get("fijar")
            else "❌ NO"
        )

        markup = types.InlineKeyboardMarkup()

        markup.row(
            types.InlineKeyboardButton(
                "🖼️ Medio multimedia",
                callback_data="alerta_multimedia"
            ),
            types.InlineKeyboardButton(
                multimedia_estado,
                callback_data="alerta_ver_multimedia"
            )
        )

        markup.row(
            types.InlineKeyboardButton(
                "🔤 Texto",
                callback_data="alerta_texto"
            ),
            types.InlineKeyboardButton(
                texto_estado,
                callback_data="alerta_ver_texto"
            )
        )

        markup.row(
            types.InlineKeyboardButton(
                "⌨️ Botones",
                callback_data="alerta_botones"
            ),
            types.InlineKeyboardButton(
                botones_estado,
                callback_data="alerta_ver_botones"
            )
        )

        markup.row(
            types.InlineKeyboardButton(
                "📌 Fijar",
                callback_data="alerta_fijar"
            ),
            types.InlineKeyboardButton(
                fijar_estado,
                callback_data="alerta_fijar"
            )
        )

        markup.row(
            types.InlineKeyboardButton(
                "👀 Vista previa completa",
                callback_data="alerta_preview"
            )
        )

        markup.row(
            types.InlineKeyboardButton(
                "⬅️ Volver",
                callback_data="alerta_cancelar"
            ),
            types.InlineKeyboardButton(
                "Siguiente ➡️",
                callback_data="alerta_siguiente"
            )
        )

        texto_panel = (
            "📢 <b>Difusión · Guía</b>\n"
            "<i>Envía un mensaje simultáneamente a todos "
            "los usuarios que iniciaron el bot.</i>"
        )

        if message_id:

            try:

                bot.edit_message_text(
                    texto_panel,
                    chat_id,
                    message_id,
                    reply_markup=markup,
                    parse_mode="HTML"
                )

                return

            except Exception:
                pass

        bot.send_message(
            chat_id,
            texto_panel,
            reply_markup=markup,
            parse_mode="HTML"
        )


    # ======================================
    # /alerta
    # ======================================

    @bot.message_handler(
        commands=["alerta"]
    )
    def comando_alerta(message):

        user_id = message.from_user.id

        if user_id not in ADMIN_IDS:

            bot.reply_to(
                message,
                "⛔ <b>No tienes permiso para usar /alerta.</b>"
            )

            return

        alertas[user_id] = nueva_alerta()

        mostrar_panel(
            message.chat.id,
            user_id
        )


    # ======================================
    # MULTIMEDIA
    # ======================================

    @bot.callback_query_handler(
        func=lambda call:
        call.data == "alerta_multimedia"
    )
    def alerta_multimedia(call):

        user_id = call.from_user.id

        if user_id not in ADMIN_IDS:
            return

        bot.answer_callback_query(
            call.id
        )

        markup = types.InlineKeyboardMarkup()

        markup.row(
            types.InlineKeyboardButton(
                "⬅️ Volver",
                callback_data="alerta_regresar"
            )
        )

        bot.edit_message_text(
            "🖼️ <b>Envía una nueva multimedia al post</b>\n\n"
            "💣 <i>Multimedia permitida: fotos, videos, "
            "archivos, stickers, GIFs, audio, mensajes "
            "de voz y videomensajes</i>",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )

        bot.register_next_step_handler_by_chat_id(
            call.message.chat.id,
            guardar_multimedia
        )


    def guardar_multimedia(message):

        user_id = message.from_user.id

        if user_id not in ADMIN_IDS:
            return

        if user_id not in alertas:
            return

        multimedia = None

        if message.photo:

            multimedia = {
                "tipo": "foto",
                "file_id": message.photo[-1].file_id
            }

        elif message.video:

            multimedia = {
                "tipo": "video",
                "file_id": message.video.file_id
            }

        elif message.document:

            multimedia = {
                "tipo": "documento",
                "file_id": message.document.file_id
            }

        elif message.animation:

            multimedia = {
                "tipo": "gif",
                "file_id": message.animation.file_id
            }

        elif message.audio:

            multimedia = {
                "tipo": "audio",
                "file_id": message.audio.file_id
            }

        elif message.voice:

            multimedia = {
                "tipo": "voz",
                "file_id": message.voice.file_id
            }

        elif message.video_note:

            multimedia = {
                "tipo": "video_note",
                "file_id": message.video_note.file_id
            }

        elif message.sticker:

            multimedia = {
                "tipo": "sticker",
                "file_id": message.sticker.file_id
            }

        else:

            bot.send_message(
                message.chat.id,
                "❌ <b>Multimedia no compatible.</b>"
            )

            return

        alertas[user_id][
            "multimedia"
        ] = multimedia

        bot.send_message(
            message.chat.id,
            "✅ <b>Multimedia guardada.</b>"
        )

        mostrar_panel(
            message.chat.id,
            user_id
        )


    # ======================================
    # VER MULTIMEDIA
    # ======================================

    @bot.callback_query_handler(
        func=lambda call:
        call.data == "alerta_ver_multimedia"
    )
    def ver_multimedia(call):

        datos = alertas.get(
            call.from_user.id,
            {}
        )

        multimedia = datos.get(
            "multimedia"
        )

        if not multimedia:

            bot.answer_callback_query(
                call.id,
                "❌ No agregaste multimedia.",
                show_alert=True
            )

            return

        bot.answer_callback_query(
            call.id
        )

        datos_preview = datos.copy()

        datos_preview["texto"] = None
        datos_preview["botones"] = []

        enviar_contenido(
            bot,
            call.message.chat.id,
            datos_preview
        )


    # ======================================
    # TEXTO
    # ======================================

    @bot.callback_query_handler(
        func=lambda call:
        call.data == "alerta_texto"
    )
    def alerta_texto(call):

        user_id = call.from_user.id

        if user_id not in ADMIN_IDS:
            return

        bot.answer_callback_query(
            call.id
        )

        markup = types.InlineKeyboardMarkup()

        markup.row(
            types.InlineKeyboardButton(
                "⬅️ Volver",
                callback_data="alerta_regresar"
            )
        )

        bot.edit_message_text(
            "📄 <b>Envía el texto del mensaje</b>\n\n"
            "<i>Las siguientes palabras clave se pueden agregar "
            "en el texto y se reemplazarán con datos del usuario:</i>\n\n"
            "• <b>Menciona al usuario:</b> "
            "<code>%mention%</code>\n"
            "• <b>Nombre del usuario:</b> "
            "<code>%firstname%</code>\n"
            "• <b>Username del usuario:</b> "
            "<code>%username%</code>",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )

        bot.register_next_step_handler_by_chat_id(
            call.message.chat.id,
            guardar_texto
        )


    def guardar_texto(message):

        user_id = message.from_user.id

        if user_id not in ADMIN_IDS:
            return

        if user_id not in alertas:
            return

        if not message.text:

            bot.send_message(
                message.chat.id,
                "❌ Debes enviar un texto."
            )

            return

        alertas[user_id][
            "texto"
        ] = message.text

        bot.send_message(
            message.chat.id,
            "✅ <b>Texto guardado.</b>"
        )

        mostrar_panel(
            message.chat.id,
            user_id
        )


    # ======================================
    # VER TEXTO
    # ======================================

    @bot.callback_query_handler(
        func=lambda call:
        call.data == "alerta_ver_texto"
    )
    def ver_texto(call):

        datos = alertas.get(
            call.from_user.id,
            {}
        )

        texto = datos.get(
            "texto"
        )

        if not texto:

            bot.answer_callback_query(
                call.id,
                "❌ No agregaste texto.",
                show_alert=True
            )

            return

        bot.answer_callback_query(
            call.id
        )

        bot.send_message(
            call.message.chat.id,
            "📄 <b>Texto actual:</b>\n\n"
            + texto,
            parse_mode="HTML"
        )


    # ======================================
    # BOTONES
    # Formato:
    # Texto | https://sitio.com
    # ======================================

    @bot.callback_query_handler(
        func=lambda call:
        call.data == "alerta_botones"
    )
    def alerta_botones(call):

        user_id = call.from_user.id

        if user_id not in ADMIN_IDS:
            return

        bot.answer_callback_query(
            call.id
        )

        markup = types.InlineKeyboardMarkup()

        markup.row(
            types.InlineKeyboardButton(
                "🗑 Quitar botones",
                callback_data="alerta_quitar_botones"
            )
        )

        markup.row(
            types.InlineKeyboardButton(
                "⬅️ Volver",
                callback_data="alerta_regresar"
            )
        )

        bot.edit_message_text(
            "⌨️ <b>Agregar botones</b>\n\n"
            "Envía cada botón en una línea usando:\n\n"
            "<code>Texto | https://enlace.com</code>\n\n"
            "Ejemplo:\n"
            "<code>🌐 Página web | https://loschuckys.com</code>\n"
            "<code>📢 Telegram | https://t.me/LosChuckysXBot</code>",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=markup
        )

        bot.register_next_step_handler_by_chat_id(
            call.message.chat.id,
            guardar_botones
        )


    def guardar_botones(message):

        user_id = message.from_user.id

        if user_id not in ADMIN_IDS:
            return

        if not message.text:
            return

        botones = []

        lineas = message.text.splitlines()

        for linea in lineas:

            if "|" not in linea:
                continue

            partes = linea.split(
                "|",
                1
            )

            texto = partes[0].strip()
            url = partes[1].strip()

            if (
                texto
                and url.startswith(
                    ("http://", "https://", "tg://")
                )
            ):

                botones.append({
                    "texto": texto,
                    "url": url
                })

        if not botones:

            bot.send_message(
                message.chat.id,
                "❌ <b>No encontré botones válidos.</b>\n\n"
                "Ejemplo:\n"
                "<code>Web | https://loschuckys.com</code>"
            )

            return

        alertas[user_id][
            "botones"
        ] = botones

        bot.send_message(
            message.chat.id,
            f"✅ <b>{len(botones)} botón(es) guardado(s).</b>"
        )

        mostrar_panel(
            message.chat.id,
            user_id
        )


    # ======================================
    # VER BOTONES
    # ======================================

    @bot.callback_query_handler(
        func=lambda call:
        call.data == "alerta_ver_botones"
    )
    def ver_botones(call):

        datos = alertas.get(
            call.from_user.id,
            {}
        )

        botones = datos.get(
            "botones",
            []
        )

        if not botones:

            bot.answer_callback_query(
                call.id,
                "❌ No agregaste botones.",
                show_alert=True
            )

            return

        bot.answer_callback_query(
            call.id
        )

        markup = crear_markup_botones(
            botones
        )

        bot.send_message(
            call.message.chat.id,
            "⌨️ <b>Vista previa de botones</b>",
            reply_markup=markup
        )


    # ======================================
    # QUITAR BOTONES
    # ======================================

    @bot.callback_query_handler(
        func=lambda call:
        call.data == "alerta_quitar_botones"
    )
    def quitar_botones(call):

        user_id = call.from_user.id

        if user_id in alertas:

            alertas[user_id][
                "botones"
            ] = []

        bot.answer_callback_query(
            call.id,
            "✅ Botones eliminados."
        )

        mostrar_panel(
            call.message.chat.id,
            user_id,
            call.message.message_id
        )


    # ======================================
    # FIJAR
    # ======================================

    @bot.callback_query_handler(
        func=lambda call:
        call.data == "alerta_fijar"
    )
    def alerta_fijar(call):

        user_id = call.from_user.id

        if user_id not in alertas:
            return

        actual = alertas[
            user_id
        ].get(
            "fijar",
            False
        )

        alertas[
            user_id
        ]["fijar"] = not actual

        bot.answer_callback_query(
            call.id,
            "📌 Fijar activado."
            if not actual
            else "📌 Fijar desactivado."
        )

        mostrar_panel(
            call.message.chat.id,
            user_id,
            call.message.message_id
        )


    # ======================================
    # VISTA PREVIA
    # ======================================

    @bot.callback_query_handler(
        func=lambda call:
        call.data == "alerta_preview"
    )
    def alerta_preview(call):

        user_id = call.from_user.id

        datos = alertas.get(
            user_id,
            {}
        )

        if (
            not datos.get("texto")
            and not datos.get("multimedia")
        ):

            bot.answer_callback_query(
                call.id,
                "❌ Agrega texto o multimedia.",
                show_alert=True
            )

            return

        bot.answer_callback_query(
            call.id
        )

        usuario_preview = {
            "telegramId": user_id,
            "nombre": call.from_user.first_name or "Usuario",
            "username": call.from_user.username or ""
        }

        enviar_contenido(
            bot,
            call.message.chat.id,
            datos,
            usuario_preview
        )


    # ======================================
    # SIGUIENTE
    # ======================================

    @bot.callback_query_handler(
        func=lambda call:
        call.data == "alerta_siguiente"
    )
    def alerta_siguiente(call):

        user_id = call.from_user.id

        datos = alertas.get(
            user_id,
            {}
        )

        if (
            not datos.get("texto")
            and not datos.get("multimedia")
        ):

            bot.answer_callback_query(
                call.id,
                "❌ Primero agrega contenido.",
                show_alert=True
            )

            return

        bot.answer_callback_query(
            call.id
        )

        markup = types.InlineKeyboardMarkup()

        markup.row(
            types.InlineKeyboardButton(
                "🚀 ENVIAR DIFUSIÓN",
                callback_data="alerta_enviar"
            )
        )

        markup.row(
            types.InlineKeyboardButton(
                "⬅️ Volver",
                callback_data="alerta_regresar"
            ),
            types.InlineKeyboardButton(
                "❌ Cancelar",
                callback_data="alerta_cancelar"
            )
        )

        bot.edit_message_text(
            "🚨 <b>CONFIRMAR DIFUSIÓN</b>\n\n"
            "El mensaje será enviado a los usuarios "
            "registrados y activos.\n\n"
            "⚠️ Confirma para comenzar.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )


    # ======================================
    # REGRESAR
    # ======================================

    @bot.callback_query_handler(
        func=lambda call:
        call.data == "alerta_regresar"
    )
    def alerta_regresar(call):

        bot.clear_step_handler_by_chat_id(
            call.message.chat.id
        )

        bot.answer_callback_query(
            call.id
        )

        mostrar_panel(
            call.message.chat.id,
            call.from_user.id,
            call.message.message_id
        )


    # ======================================
    # CANCELAR
    # ======================================

    @bot.callback_query_handler(
        func=lambda call:
        call.data == "alerta_cancelar"
    )
    def alerta_cancelar(call):

        user_id = call.from_user.id

        alertas.pop(
            user_id,
            None
        )

        bot.clear_step_handler_by_chat_id(
            call.message.chat.id
        )

        bot.answer_callback_query(
            call.id,
            "Difusión cancelada."
        )

        try:

            bot.edit_message_text(
                "❌ <b>Difusión cancelada.</b>",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="HTML"
            )

        except Exception:
            pass


    # ======================================
    # INICIAR DIFUSIÓN
    # ======================================

    @bot.callback_query_handler(
        func=lambda call:
        call.data == "alerta_enviar"
    )
    def alerta_enviar(call):

        user_id = call.from_user.id

        if user_id not in ADMIN_IDS:
            return

        datos = alertas.get(
            user_id
        )

        if not datos:
            return

        bot.answer_callback_query(
            call.id,
            "🚀 Iniciando difusión..."
        )

        try:

            bot.edit_message_text(
                "⏳ <b>Cargando usuarios...</b>\n\n"
                "Consultando la base de datos.",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="HTML"
            )

        except Exception:
            pass

        # Se ejecuta en segundo plano
        hilo = threading.Thread(
            target=ejecutar_difusion,
            args=(
                bot,
                call.message.chat.id,
                call.message.message_id,
                user_id,
                datos.copy()
            ),
            daemon=True
        )

        hilo.start()


    # ======================================
    # PROCESAR DIFUSIÓN
    # ======================================

    def ejecutar_difusion(
        bot,
        chat_admin,
        mensaje_estado,
        admin_id,
        datos
    ):

        usuarios = obtener_usuarios()

        if not usuarios:

            try:

                bot.edit_message_text(
                    "❌ <b>No se pudieron cargar usuarios.</b>",
                    chat_admin,
                    mensaje_estado,
                    parse_mode="HTML"
                )

            except Exception:
                pass

            return

        total = len(
            usuarios
        )

        enviados = 0
        fallidos = 0
        bloqueados = 0

        try:

            bot.edit_message_text(
                "🚀 <b>DIFUSIÓN INICIADA</b>\n\n"
                f"👥 Total: <b>{total}</b>\n"
                "📤 Enviados: <b>0</b>\n"
                "❌ Fallidos: <b>0</b>\n"
                "🚫 Bloquearon bot: <b>0</b>\n\n"
                "📊 Progreso\n"
                "<code>░░░░░░░░░░░░░░░</code>\n"
                "<b>0%</b>",
                chat_admin,
                mensaje_estado,
                parse_mode="HTML"
            )

        except Exception:
            pass

        for indice, usuario in enumerate(
            usuarios,
            start=1
        ):

            telegram_id = usuario.get(
                "telegramId"
            )

            try:

                mensaje_enviado = enviar_contenido(
                    bot,
                    telegram_id,
                    datos,
                    usuario
                )

                enviados += 1

                # Intentar fijar
                if (
                    datos.get("fijar")
                    and mensaje_enviado
                ):

                    try:

                        bot.pin_chat_message(
                            telegram_id,
                            mensaje_enviado.message_id,
                            disable_notification=True
                        )

                    except Exception:
                        pass

            except ApiTelegramException as error:

                texto_error = str(
                    error
                ).lower()

                # RATE LIMIT
                if "too many requests" in texto_error:

                    espera = 3

                    try:

                        resultado = error.result_json

                        parametros = resultado.get(
                            "parameters",
                            {}
                        )

                        espera = parametros.get(
                            "retry_after",
                            3
                        )

                    except Exception:
                        pass

                    print(
                        f"⏳ Telegram pidió esperar "
                        f"{espera} segundos."
                    )

                    time.sleep(
                        espera + 1
                    )

                    try:

                        mensaje_enviado = enviar_contenido(
                            bot,
                            telegram_id,
                            datos,
                            usuario
                        )

                        enviados += 1

                    except Exception:

                        fallidos += 1

                elif (
                    "blocked by the user" in texto_error
                    or "bot was blocked by the user" in texto_error
                    or "chat not found" in texto_error
                    or "user is deactivated" in texto_error
                ):

                    fallidos += 1
                    bloqueados += 1

                else:

                    fallidos += 1

                    print(
                        f"❌ Telegram {telegram_id}: "
                        f"{error}"
                    )

            except Exception as error:

                fallidos += 1

                print(
                    f"❌ Error usuario "
                    f"{telegram_id}: {error}"
                )

            # No mandar todos de golpe
            time.sleep(
                0.06
            )

            # Actualizar progreso
            if (
                indice % 25 == 0
                or indice == total
            ):

                porcentaje = round(
                    (indice / total) * 100,
                    1
                )

                barra = crear_barra_progreso(
                    indice,
                    total
                )

                try:

                    bot.edit_message_text(
                        "🚀 <b>DIFUSIÓN EN PROCESO</b>\n\n"
                        f"👥 Total: <b>{total}</b>\n"
                        f"📤 Enviados: <b>{enviados}</b>\n"
                        f"❌ Fallidos: <b>{fallidos}</b>\n"
                        f"🚫 Bloquearon bot: "
                        f"<b>{bloqueados}</b>\n\n"
                        "📊 <b>Progreso</b>\n"
                        f"<code>{barra}</code>\n"
                        f"<b>{porcentaje}%</b> "
                        f"• {indice}/{total}",
                        chat_admin,
                        mensaje_estado,
                        parse_mode="HTML"
                    )

                except Exception:
                    pass

        # ==================================
        # FINAL
        # ==================================

        try:

            bot.edit_message_text(
                "✅ <b>DIFUSIÓN FINALIZADA</b>\n\n"
                f"👥 Total: <b>{total}</b>\n"
                f"📤 Enviados: <b>{enviados}</b>\n"
                f"❌ Fallidos: <b>{fallidos}</b>\n"
                f"🚫 Bloquearon bot: "
                f"<b>{bloqueados}</b>\n\n"
                "📊 <b>Progreso</b>\n"
                "<code>███████████████</code>\n"
                "<b>100%</b>",
                chat_admin,
                mensaje_estado,
                parse_mode="HTML"
            )

        except Exception as error:

            print(
                f"Error terminando difusión: {error}"
            )

        alertas.pop(
            admin_id,
            None
        )