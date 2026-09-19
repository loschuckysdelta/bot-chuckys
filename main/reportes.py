import requests

from telebot import types
from html import escape


# ============================================================
# CONFIGURACIÓN
# ============================================================

# TU ID PERSONAL DE TELEGRAM
# Usa /miid para saber cuál es
ADMIN_ID = 8635600472


# ============================================================
# APIs
# ============================================================

API_USERS = "https://bot-apis-zkmk.vercel.app/api/users"
API_BANEADOS = "https://bot-apis-zkmk.vercel.app/api/baneados"


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

        if response.status_code != 200:
            print(
                "❌ Error API users:",
                response.status_code,
                response.text
            )
            return None

        data = response.json()

        usuarios = data.get("usuarios", [])

        for usuario in usuarios:

            if str(usuario.get("telegramId")) == str(telegram_id):
                return usuario

        return None

    except Exception as error:

        print(
            "❌ Error buscando usuario en API:",
            error
        )

        return None


# ============================================================
# BANEAR EN API
# ============================================================

def banear_en_api(
    telegram_id,
    baneado_por="Reporte Telegram",
    motivo="Contenido reportado"
):

    try:

        payload = {
            "telegramId": telegram_id,
            "baneadoPor": baneado_por,
            "motivoBloqueo": motivo
        }

        response = requests.post(
            API_BANEADOS,
            json=payload,
            timeout=15
        )

        print("")
        print("==============================================")
        print("🚫 RESPUESTA API BANEADOS")
        print("STATUS:", response.status_code)
        print("BODY:", response.text)
        print("==============================================")
        print("")

        if response.status_code in [200, 201]:

            try:
                return True, response.json()
            except Exception:
                return True, {}

        return False, {
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
# REGISTRAR REPORTES
# ============================================================

def registrar_reportes(bot):

    # ========================================================
    # /MIID
    # ========================================================

    @bot.message_handler(commands=["miid"])
    def mi_id(message):

        bot.reply_to(
            message,
            "🆔 <b>Tu ID de Telegram:</b>\n\n"
            f"<code>{message.from_user.id}</code>"
        )


    # ========================================================
    # /REPORTAR
    # ========================================================

    @bot.message_handler(commands=["reportar", "reporte"])
    def reportar(message):

        # ====================================================
        # DEBE RESPONDER A OTRO MENSAJE
        # ====================================================

        if not message.reply_to_message:

            bot.reply_to(
                message,
                "⚠️ <b>Debes responder al contenido que quieres reportar.</b>\n\n"
                "Responde al video, foto, audio o mensaje y escribe:\n"
                "<code>/reportar</code>"
            )

            return


        mensaje_reportado = message.reply_to_message

        usuario_reportado = mensaje_reportado.from_user


        # ====================================================
        # VALIDAR USUARIO
        # ====================================================

        if not usuario_reportado:

            bot.reply_to(
                message,
                "❌ No pude identificar al usuario que envió ese contenido."
            )

            return


        # ====================================================
        # DATOS
        # ====================================================

        chat_origen = message.chat.id

        mensaje_original_id = mensaje_reportado.message_id

        usuario_reportado_id = usuario_reportado.id

        reportador_id = message.from_user.id


        # ====================================================
        # EVITAR AUTOREPORTE
        # ====================================================

        if usuario_reportado_id == reportador_id:

            bot.reply_to(
                message,
                "⚠️ No puedes reportar tu propio contenido."
            )

            return


        # ====================================================
        # REENVIAR VIDEO / FOTO / AUDIO / MENSAJE A TU PRIVADO
        # ====================================================

        try:

            mensaje_enviado = bot.forward_message(
                chat_id=ADMIN_ID,
                from_chat_id=chat_origen,
                message_id=mensaje_original_id
            )

        except Exception as error_forward:

            print(
                "⚠️ No se pudo reenviar. Intentando copiar:",
                error_forward
            )

            # Si Telegram no permite reenviarlo,
            # intentamos copiar el contenido.
            try:

                mensaje_enviado = bot.copy_message(
                    chat_id=ADMIN_ID,
                    from_chat_id=chat_origen,
                    message_id=mensaje_original_id
                )

            except Exception as error_copy:

                print("")
                print("==============================================")
                print("❌ ERROR ENVIANDO REPORTE")
                print("ADMIN ID:", ADMIN_ID)
                print("CHAT ORIGEN:", chat_origen)
                print("MESSAGE ID:", mensaje_original_id)
                print("FORWARD:", error_forward)
                print("COPY:", error_copy)
                print("==============================================")
                print("")

                bot.reply_to(
                    message,
                    "❌ <b>No pude enviar el contenido al administrador.</b>\n\n"
                    "Asegúrate de que el administrador haya iniciado "
                    "el bot en privado."
                )

                return


        # ====================================================
        # DATOS USUARIO REPORTADO
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


        # ====================================================
        # GRUPO
        # ====================================================

        nombre_grupo = escape(
            message.chat.title
            or "Grupo"
        )


        # ====================================================
        # BOTONERA
        # ====================================================

        markup = types.InlineKeyboardMarkup(
            row_width=2
        )


        boton_banear = types.InlineKeyboardButton(
            text="🔨 Banear",
            callback_data=(
                f"rban:"
                f"{chat_origen}:"
                f"{usuario_reportado_id}:"
                f"{mensaje_original_id}"
            )
        )


        boton_mutear = types.InlineKeyboardButton(
            text="🔇 Mutear",
            callback_data=(
                f"rmute:"
                f"{chat_origen}:"
                f"{usuario_reportado_id}:"
                f"{mensaje_original_id}"
            )
        )


        markup.add(
            boton_banear,
            boton_mutear
        )


        # ====================================================
        # INFORMACIÓN DEL REPORTE
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

            "🏠 <b>GRUPO DE ORIGEN</b>\n"
            f"├ Nombre: {nombre_grupo}\n"
            f"└ ID: <code>{chat_origen}</code>\n\n"

            "👇 <b>Selecciona una acción:</b>"
        )


        # ====================================================
        # ENVIAR INFO DEBAJO DEL VIDEO/FOTO
        # ====================================================

        try:

            bot.send_message(
                chat_id=ADMIN_ID,
                text=texto,
                reply_to_message_id=mensaje_enviado.message_id,
                reply_markup=markup
            )

        except Exception as error:

            print(
                "❌ Error enviando información:",
                error
            )

            return


        # ====================================================
        # CONFIRMAR REPORTE
        # ====================================================

        try:

            bot.reply_to(
                message,
                "✅ <b>Reporte enviado correctamente.</b>\n\n"
                "El administrador revisará el contenido."
            )

        except Exception:
            pass


        # ====================================================
        # BORRAR /REPORTAR
        # ====================================================

        try:

            bot.delete_message(
                chat_id=message.chat.id,
                message_id=message.message_id
            )

        except Exception:
            pass


    # ========================================================
    # 🔨 BANEAR
    # ========================================================

    @bot.callback_query_handler(
        func=lambda call: (
            call.data
            and call.data.startswith("rban:")
        )
    )
    def banear_reportado(call):

        # ====================================================
        # SOLO EL ADMIN
        # ====================================================

        if call.from_user.id != ADMIN_ID:

            bot.answer_callback_query(
                call.id,
                "❌ No tienes permiso para realizar esta acción.",
                show_alert=True
            )

            return


        # ====================================================
        # DATOS CALLBACK
        # ====================================================

        try:

            datos = call.data.split(":")

            chat_origen = int(datos[1])

            usuario_id = int(datos[2])

            mensaje_id = int(datos[3])

        except Exception as error:

            print(
                "❌ Error leyendo callback:",
                error
            )

            bot.answer_callback_query(
                call.id,
                "❌ Datos del reporte inválidos.",
                show_alert=True
            )

            return


        # ====================================================
        # BUSCAR USUARIO EN API
        # ====================================================

        usuario_api = buscar_usuario_api(
            usuario_id
        )


        if usuario_api:

            nombre_usuario = (
                usuario_api.get("nombre")
                or "Sin nombre"
            )

            username_usuario = (
                usuario_api.get("username")
                or ""
            )

        else:

            nombre_usuario = "Sin nombre"
            username_usuario = ""


        # ====================================================
        # 1. BANEAR DEL GRUPO DE TELEGRAM
        # ====================================================

        telegram_baneado = False

        error_telegram = ""


        try:

            bot.ban_chat_member(
                chat_id=chat_origen,
                user_id=usuario_id
            )

            telegram_baneado = True

        except Exception as error:

            error_telegram = str(error)

            print(
                "❌ ERROR BANEANDO EN TELEGRAM:",
                error
            )


        # ====================================================
        # SI NO SE PUDO BANEAR, DETENER
        # ====================================================

        if not telegram_baneado:

            bot.answer_callback_query(
                call.id,
                (
                    "❌ No pude banear al usuario.\n"
                    f"{error_telegram[:120]}"
                ),
                show_alert=True
            )

            return


        # ====================================================
        # 2. BORRAR FOTO / VIDEO / MENSAJE ORIGINAL
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
                "⚠️ Usuario baneado pero no pude borrar contenido:",
                error
            )


        # ====================================================
        # 3. NOMBRE DEL ADMINISTRADOR
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

            baneado_por = nombre_admin


        # ====================================================
        # 4. BANEAR EN API
        # ====================================================

        api_baneado, respuesta_api = banear_en_api(
            telegram_id=usuario_id,
            baneado_por=baneado_por,
            motivo="Contenido reportado"
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

        except Exception as error:

            print(
                "⚠️ No pude quitar botonera:",
                error
            )


        # ====================================================
        # ESTADOS
        # ====================================================

        if contenido_eliminado:

            estado_contenido = "✅ Eliminado"

        else:

            estado_contenido = "⚠️ No se pudo eliminar"


        if api_baneado:

            estado_api = "✅ Baneado"

        else:

            estado_api = "⚠️ Error"


        if username_usuario:

            username_texto = (
                f"@{escape(str(username_usuario))}"
            )

        else:

            username_texto = "Sin username"


        # ====================================================
        # AVISO
        # ====================================================

        resultado = (
            "🚫 <b>USUARIO BANEADO</b>\n\n"

            f"👤 <b>Nombre:</b> "
            f"{escape(str(nombre_usuario))}\n"

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


        if api_baneado:

            bot.answer_callback_query(
                call.id,
                "🚫 Usuario baneado correctamente.",
                show_alert=True
            )

        else:

            bot.answer_callback_query(
                call.id,
                "⚠️ Baneado de Telegram, pero hubo error en la API.",
                show_alert=True
            )


    # ========================================================
    # 🔇 MUTEAR
    # ========================================================

    @bot.callback_query_handler(
        func=lambda call: (
            call.data
            and call.data.startswith("rmute:")
        )
    )
    def mutear_reportado(call):

        # ====================================================
        # SOLO EL ADMIN
        # ====================================================

        if call.from_user.id != ADMIN_ID:

            bot.answer_callback_query(
                call.id,
                "❌ No tienes permiso para realizar esta acción.",
                show_alert=True
            )

            return


        # ====================================================
        # DATOS
        # ====================================================

        try:

            datos = call.data.split(":")

            chat_origen = int(datos[1])

            usuario_id = int(datos[2])

            mensaje_id = int(datos[3])

        except Exception:

            bot.answer_callback_query(
                call.id,
                "❌ Datos del reporte inválidos.",
                show_alert=True
            )

            return


        # ====================================================
        # PERMISOS MUTE
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
            can_add_web_page_previews=False
        )


        # ====================================================
        # MUTEAR
        # ====================================================

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
                    f"{str(error)[:120]}"
                ),
                show_alert=True
            )

            return


        # ====================================================
        # NO BORRAR CONTENIDO AL MUTEAR
        # ====================================================


        # ====================================================
        # QUITAR BOTONES
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
        # CONFIRMACIÓN
        # ====================================================

        bot.answer_callback_query(
            call.id,
            "🔇 Usuario muteado correctamente.",
            show_alert=True
        )


        bot.send_message(
            ADMIN_ID,
            (
                "🔇 <b>USUARIO MUTEADO</b>\n\n"
                f"👤 <b>ID:</b> "
                f"<code>{usuario_id}</code>\n\n"

                "🔇 <b>Estado:</b> Muteado\n"
                "📸 <b>Contenido:</b> No eliminado\n"
                "🌐 <b>API baneados:</b> No modificado"
            )
        )