import requests

from telebot import types
from html import escape
from datetime import datetime, timezone


# ============================================================
# CONFIGURACIÓN
# ============================================================

# PON AQUÍ TU ID PERSONAL DE TELEGRAM
ADMIN_ID = 8635600472


API_USERS = "https://bot-apis-zkmk.vercel.app/api/users"
API_BANEADOS = "https://bot-apis-zkmk.vercel.app/api/baneados"


# ============================================================
# FECHA UTC
# ============================================================

def fecha_actual():

    return (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


# ============================================================
# BUSCAR USUARIO EN API
# ============================================================

def buscar_usuario_api(telegram_id):

    try:

        response = requests.get(
            API_USERS,
            params={
                "buscar": str(telegram_id)
            },
            timeout=15
        )

        print("")
        print("========== BUSCAR USUARIO ==========")
        print("STATUS:", response.status_code)
        print("BODY:", response.text[:1000])
        print("====================================")
        print("")

        if response.status_code != 200:
            return None

        data = response.json()

        usuarios = data.get("usuarios", [])

        for usuario in usuarios:

            if str(usuario.get("telegramId")) == str(telegram_id):
                return usuario

        return None

    except Exception as error:

        print(
            "❌ Error buscando usuario:",
            error
        )

        return None


# ============================================================
# REGISTRAR USUARIO SI NO EXISTE
# ============================================================

def registrar_usuario_api(
    telegram_id,
    nombre,
    username
):

    try:

        ahora = fecha_actual()

        payload = {
            "telegramId": int(telegram_id),
            "botBloqueado": False,
            "fechaBloqueo": None,
            "fechaRegistro": ahora,
            "nombre": nombre or "Sin nombre",
            "username": username or "",
            "ultimaActividad": ahora,
            "ultimaActualizacion": ahora
        }

        response = requests.post(
            API_USERS,
            json=payload,
            timeout=15
        )

        print("")
        print("========== REGISTRAR USUARIO ==========")
        print("STATUS:", response.status_code)
        print("BODY:", response.text[:1000])
        print("=======================================")
        print("")

        if response.status_code in [
            200,
            201
        ]:
            return True

        # Algunos endpoints responden conflicto si ya existe.
        # En ese caso seguimos con el proceso de ban.
        if response.status_code == 409:
            return True

        return False

    except Exception as error:

        print(
            "❌ Error registrando usuario:",
            error
        )

        return False


# ============================================================
# ASEGURAR QUE EXISTA EN /API/USERS
# ============================================================

def asegurar_usuario_api(
    telegram_id,
    nombre,
    username
):

    usuario = buscar_usuario_api(
        telegram_id
    )

    if usuario:
        return True

    return registrar_usuario_api(
        telegram_id=telegram_id,
        nombre=nombre,
        username=username
    )


# ============================================================
# BANEAR EN API
# ============================================================

def banear_usuario_api(
    telegram_id,
    baneado_por,
    motivo
):

    try:

        payload = {
            "telegramId": int(telegram_id),
            "baneadoPor": baneado_por,
            "motivoBloqueo": motivo
        }

        response = requests.post(
            API_BANEADOS,
            json=payload,
            timeout=15
        )

        print("")
        print("========================================")
        print("🚫 API BANEADOS")
        print("URL:", API_BANEADOS)
        print("PAYLOAD:", payload)
        print("STATUS:", response.status_code)
        print("BODY:", response.text)
        print("========================================")
        print("")

        if response.status_code in [
            200,
            201
        ]:

            try:
                return True, response.json()

            except Exception:
                return True, {}

        return False, {
            "status": response.status_code,
            "error": response.text
        }

    except Exception as error:

        print(
            "❌ ERROR API BANEADOS:",
            error
        )

        return False, {
            "error": str(error)
        }


# ============================================================
# REGISTRAR MÓDULO
# ============================================================

def registrar_reportes(bot):


    # ========================================================
    # /MIID
    # ========================================================

    @bot.message_handler(commands=["miid"])
    def comando_miid(message):

        bot.reply_to(
            message,
            "🆔 <b>Tu ID:</b>\n\n"
            f"<code>{message.from_user.id}</code>"
        )


    # ========================================================
    # /REPORTAR
    # ========================================================

    @bot.message_handler(
        commands=[
            "reportar",
            "reporte"
        ]
    )
    def comando_reportar(message):

        # ====================================================
        # TIENE QUE RESPONDER A ALGO
        # ====================================================

        if not message.reply_to_message:

            bot.reply_to(
                message,
                "⚠️ <b>Debes responder al contenido que quieres reportar.</b>\n\n"
                "Responde al video, foto, audio o mensaje y escribe:\n"
                "<code>/reportar</code>"
            )

            return


        # ====================================================
        # MENSAJE REPORTADO
        # ====================================================

        mensaje_reportado = (
            message.reply_to_message
        )

        usuario_reportado = (
            mensaje_reportado.from_user
        )


        if not usuario_reportado:

            bot.reply_to(
                message,
                "❌ No pude identificar quién envió ese contenido."
            )

            return


        # ====================================================
        # DATOS
        # ====================================================

        chat_origen = message.chat.id

        mensaje_original_id = (
            mensaje_reportado.message_id
        )

        usuario_reportado_id = (
            usuario_reportado.id
        )

        reportador_id = (
            message.from_user.id
        )


        # ====================================================
        # NO AUTOREPORTE
        # ====================================================

        if (
            usuario_reportado_id
            == reportador_id
        ):

            bot.reply_to(
                message,
                "⚠️ No puedes reportar tu propio contenido."
            )

            return


        # ====================================================
        # IMPORTANTE
        #
        # AQUÍ NO BORRAMOS NADA.
        #
        # EL VIDEO/FOTO/MENSAJE ORIGINAL
        # SIGUE EN EL GRUPO.
        # ====================================================


        # ====================================================
        # REENVIAR A TU PRIVADO
        # ====================================================

        try:

            contenido_privado = (
                bot.forward_message(
                    chat_id=ADMIN_ID,
                    from_chat_id=chat_origen,
                    message_id=mensaje_original_id
                )
            )

        except Exception as error_forward:

            print(
                "⚠️ Forward falló:",
                error_forward
            )


            # =================================================
            # SI ESTÁ PROTEGIDO, INTENTA COPIAR
            # =================================================

            try:

                contenido_privado = (
                    bot.copy_message(
                        chat_id=ADMIN_ID,
                        from_chat_id=chat_origen,
                        message_id=mensaje_original_id
                    )
                )

            except Exception as error_copy:

                print(
                    "❌ Copy también falló:",
                    error_copy
                )

                bot.reply_to(
                    message,
                    "❌ No pude enviar el contenido al administrador."
                )

                return


        # ====================================================
        # DATOS REPORTADO
        # ====================================================

        nombre_reportado = escape(
            usuario_reportado.first_name
            or "Sin nombre"
        )

        username_reportado = (
            f"@{escape(usuario_reportado.username)}"
            if usuario_reportado.username
            else "Sin username"
        )


        # ====================================================
        # DATOS REPORTADOR
        # ====================================================

        nombre_reportador = escape(
            message.from_user.first_name
            or "Sin nombre"
        )

        username_reportador = (
            f"@{escape(message.from_user.username)}"
            if message.from_user.username
            else "Sin username"
        )


        nombre_grupo = escape(
            message.chat.title
            or "Grupo"
        )


        # ====================================================
        # BOTONES
        # ====================================================

        markup = types.InlineKeyboardMarkup(
            row_width=2
        )


        btn_banear = (
            types.InlineKeyboardButton(
                "🔨 Banear",
                callback_data=(
                    f"rban:"
                    f"{chat_origen}:"
                    f"{usuario_reportado_id}:"
                    f"{mensaje_original_id}"
                )
            )
        )


        btn_mutear = (
            types.InlineKeyboardButton(
                "🔇 Mutear",
                callback_data=(
                    f"rmute:"
                    f"{chat_origen}:"
                    f"{usuario_reportado_id}:"
                    f"{mensaje_original_id}"
                )
            )
        )


        markup.add(
            btn_banear,
            btn_mutear
        )


        # ====================================================
        # INFORMACIÓN
        # ====================================================

        texto = (
            "🚨 <b>NUEVO REPORTE</b>\n\n"

            "👤 <b>USUARIO REPORTADO</b>\n"
            f"├ Nombre: {nombre_reportado}\n"
            f"├ Usuario: {username_reportado}\n"
            f"└ ID: <code>{usuario_reportado_id}</code>\n\n"

            "📢 <b>REPORTADO POR</b>\n"
            f"├ Nombre: {nombre_reportador}\n"
            f"├ Usuario: {username_reportador}\n"
            f"└ ID: <code>{reportador_id}</code>\n\n"

            "🏠 <b>GRUPO</b>\n"
            f"├ Nombre: {nombre_grupo}\n"
            f"└ ID: <code>{chat_origen}</code>\n\n"

            "⚠️ <b>El contenido todavía NO fue eliminado.</b>\n\n"

            "👇 Selecciona una acción:"
        )


        # ====================================================
        # BOTONERA EN TU PRIVADO
        # ====================================================

        bot.send_message(
            chat_id=ADMIN_ID,
            text=texto,
            reply_to_message_id=contenido_privado.message_id,
            reply_markup=markup
        )


        # ====================================================
        # CONFIRMAR AL REPORTADOR
        # ====================================================

        bot.reply_to(
            message,
            "✅ <b>Reporte enviado.</b>\n\n"
            "El administrador revisará el contenido."
        )


        # ====================================================
        # IMPORTANTE:
        #
        # NO BORRAMOS:
        #
        # - video
        # - foto
        # - audio
        # - texto
        # - comando /reportar
        #
        # NO SE BORRA NADA AQUÍ.
        # ====================================================


    # ========================================================
    # 🔨 BOTÓN BANEAR
    # ========================================================

    @bot.callback_query_handler(
        func=lambda call: (
            call.data
            and call.data.startswith("rban:")
        )
    )
    def callback_banear(call):


        # ====================================================
        # SOLO TÚ
        # ====================================================

        if call.from_user.id != ADMIN_ID:

            bot.answer_callback_query(
                call.id,
                "❌ No tienes permiso.",
                show_alert=True
            )

            return


        # ====================================================
        # DATOS
        # ====================================================

        try:

            partes = call.data.split(":")

            chat_origen = int(
                partes[1]
            )

            usuario_id = int(
                partes[2]
            )

            mensaje_id = int(
                partes[3]
            )

        except Exception:

            bot.answer_callback_query(
                call.id,
                "❌ Datos inválidos.",
                show_alert=True
            )

            return


        # ====================================================
        # OBTENER NOMBRE Y USERNAME ANTES DEL BAN
        # ====================================================

        nombre_usuario = "Sin nombre"
        username_usuario = ""


        try:

            miembro = bot.get_chat_member(
                chat_origen,
                usuario_id
            )

            usuario_telegram = miembro.user

            nombre_usuario = (
                usuario_telegram.first_name
                or "Sin nombre"
            )

            username_usuario = (
                usuario_telegram.username
                or ""
            )

        except Exception as error:

            print(
                "⚠️ No pude obtener datos Telegram:",
                error
            )


        # ====================================================
        # 1. BANEAR EN EL GRUPO
        # ====================================================

        try:

            bot.ban_chat_member(
                chat_id=chat_origen,
                user_id=usuario_id
            )

        except Exception as error:

            print(
                "❌ ERROR BANEANDO:",
                error
            )

            bot.answer_callback_query(
                call.id,
                (
                    "❌ No pude banear al usuario.\n"
                    f"{str(error)[:150]}"
                ),
                show_alert=True
            )

            return


        # ====================================================
        # 2. SOLO AHORA BORRAMOS EL CONTENIDO
        # ====================================================

        contenido_eliminado = False


        try:

            bot.delete_message(
                chat_id=chat_origen,
                message_id=mensaje_id
            )

            contenido_eliminado = True

        except Exception as error:

            print(
                "⚠️ Baneado, pero no pude borrar contenido:",
                error
            )


        # ====================================================
        # 3. ASEGURAR USUARIO EN /API/USERS
        # ====================================================

        usuario_api_ok = (
            asegurar_usuario_api(
                telegram_id=usuario_id,
                nombre=nombre_usuario,
                username=username_usuario
            )
        )


        # ====================================================
        # 4. API BANEADOS
        # ====================================================

        nombre_admin = (
            call.from_user.first_name
            or "Administrador"
        )


        if call.from_user.username:

            baneado_por = (
                f"{nombre_admin} "
                f"(@{call.from_user.username})"
            )

        else:

            baneado_por = (
                nombre_admin
            )


        api_baneado = False
        api_respuesta = {}


        if usuario_api_ok:

            (
                api_baneado,
                api_respuesta
            ) = banear_usuario_api(
                telegram_id=usuario_id,
                baneado_por=baneado_por,
                motivo="Contenido reportado"
            )

        else:

            print(
                "❌ No se pudo asegurar usuario en API USERS."
            )


        # ====================================================
        # 5. QUITAR BOTONES
        # ====================================================

        try:

            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=None
            )

        except Exception:
            pass


        # ====================================================
        # ESTADOS
        # ====================================================

        estado_contenido = (
            "✅ Eliminado"
            if contenido_eliminado
            else "⚠️ No eliminado"
        )


        estado_api = (
            "✅ Baneado"
            if api_baneado
            else "⚠️ Error"
        )


        username_texto = (
            f"@{escape(username_usuario)}"
            if username_usuario
            else "Sin username"
        )


        # ====================================================
        # RESULTADO PRIVADO
        # ====================================================

        resultado = (
            "🚫 <b>USUARIO BANEADO</b>\n\n"

            f"👤 <b>Nombre:</b> "
            f"{escape(nombre_usuario)}\n"

            f"📱 <b>Usuario:</b> "
            f"{username_texto}\n"

            f"🆔 <b>ID:</b> "
            f"<code>{usuario_id}</code>\n\n"

            "🔨 <b>Telegram:</b> ✅ Baneado\n"

            f"🗑 <b>Contenido:</b> "
            f"{estado_contenido}\n"

            f"🌐 <b>API baneados:</b> "
            f"{estado_api}\n\n"

            f"🛡 <b>Baneado por:</b> "
            f"{escape(baneado_por)}\n"

            "📝 <b>Motivo:</b> "
            "Contenido reportado"
        )


        bot.send_message(
            ADMIN_ID,
            resultado
        )


        # ====================================================
        # POPUP
        # ====================================================

        if api_baneado:

            bot.answer_callback_query(
                call.id,
                "✅ Usuario baneado correctamente.",
                show_alert=True
            )

        else:

            error_api = (
                api_respuesta.get("error", "")
                if isinstance(
                    api_respuesta,
                    dict
                )
                else ""
            )

            print(
                "❌ ERROR FINAL API:",
                error_api
            )

            bot.answer_callback_query(
                call.id,
                "⚠️ Baneado en Telegram, pero la API respondió con error.",
                show_alert=True
            )


    # ========================================================
    # 🔇 BOTÓN MUTEAR
    # ========================================================

    @bot.callback_query_handler(
        func=lambda call: (
            call.data
            and call.data.startswith("rmute:")
        )
    )
    def callback_mutear(call):


        # ====================================================
        # SOLO TÚ
        # ====================================================

        if call.from_user.id != ADMIN_ID:

            bot.answer_callback_query(
                call.id,
                "❌ No tienes permiso.",
                show_alert=True
            )

            return


        # ====================================================
        # DATOS
        # ====================================================

        try:

            partes = call.data.split(":")

            chat_origen = int(
                partes[1]
            )

            usuario_id = int(
                partes[2]
            )

        except Exception:

            bot.answer_callback_query(
                call.id,
                "❌ Datos inválidos.",
                show_alert=True
            )

            return


        # ====================================================
        # MUTE COMPLETO
        # ====================================================

        permisos = types.ChatPermissions(
            can_send_messages=False,
            can_send_audios=False,
            can_send_documents=False,
            can_send_photos=False,
            can_send_videos=False,
            can_send_video_notes=False,
            can_send_voice_notes=False,
            can_send_polls=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False,
            can_change_info=False,
            can_invite_users=False,
            can_pin_messages=False
        )


        try:

            bot.restrict_chat_member(
                chat_id=chat_origen,
                user_id=usuario_id,
                permissions=permisos
            )

        except Exception as error:

            print(
                "❌ ERROR MUTEANDO:",
                error
            )

            bot.answer_callback_query(
                call.id,
                (
                    "❌ No pude mutear.\n"
                    f"{str(error)[:140]}"
                ),
                show_alert=True
            )

            return


        # ====================================================
        # IMPORTANTE:
        #
        # AL MUTEAR:
        #
        # ❌ NO borrar mensaje
        # ❌ NO banear
        # ❌ NO tocar API baneados
        #
        # SOLO RESTRINGIR EN ESE GRUPO.
        # ====================================================


        try:

            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=None
            )

        except Exception:
            pass


        bot.answer_callback_query(
            call.id,
            "🔇 Usuario muteado en el grupo.",
            show_alert=True
        )


        bot.send_message(
            ADMIN_ID,
            (
                "🔇 <b>USUARIO MUTEADO</b>\n\n"

                f"👤 ID: "
                f"<code>{usuario_id}</code>\n\n"

                "✅ Ya no puede enviar mensajes "
                "ni contenido en el grupo.\n\n"

                "📸 El contenido reportado "
                "<b>NO fue eliminado</b>.\n"

                "🌐 La API de baneados "
                "<b>NO fue modificada</b>."
            )
        )