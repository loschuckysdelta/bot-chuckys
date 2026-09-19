from telebot import types
from html import escape


# ============================================================
# CONFIGURACIÓN
# ============================================================

GRUPO_REPORTES_ID = -1004452499126


def registrar_reportes(bot):

    # ============================================================
    # VERIFICAR ADMIN DEL GRUPO DE REPORTES
    # ============================================================

    def es_admin_reportes(user_id):
        try:
            miembro = bot.get_chat_member(
                GRUPO_REPORTES_ID,
                user_id
            )

            return miembro.status in [
                "administrator",
                "creator"
            ]

        except Exception as error:
            print("❌ Error verificando administrador:", error)
            return False


    # ============================================================
    # COMANDO /TESTREPORTE
    # ============================================================

    @bot.message_handler(commands=["testreporte"])
    def test_reporte(message):

        try:
            bot.send_message(
                GRUPO_REPORTES_ID,
                "✅ <b>GRUPO DE REPORTES CONECTADO</b>\n\n"
                "El bot puede enviar mensajes correctamente."
            )

            bot.reply_to(
                message,
                "✅ Grupo de reportes conectado correctamente."
            )

        except Exception as error:

            print("❌ ERROR TEST REPORTES:", error)

            bot.reply_to(
                message,
                "❌ <b>No puedo enviar mensajes al grupo de reportes.</b>\n\n"
                f"<code>{escape(str(error))}</code>"
            )


    # ============================================================
    # COMANDO /REPORTAR
    # ============================================================

    @bot.message_handler(commands=["reportar", "reporte"])
    def reportar(message):

        # ========================================================
        # DEBE RESPONDER A ALGO
        # ========================================================

        if not message.reply_to_message:

            bot.reply_to(
                message,
                "⚠️ <b>Debes responder al contenido que quieres reportar.</b>\n\n"
                "Ejemplo:\n"
                "Responde al video, foto o mensaje y escribe:\n"
                "<code>/reportar</code>"
            )

            return


        # ========================================================
        # MENSAJE REPORTADO
        # ========================================================

        mensaje_reportado = message.reply_to_message

        usuario_reportado = mensaje_reportado.from_user


        if not usuario_reportado:

            bot.reply_to(
                message,
                "❌ No pude identificar quién envió ese contenido."
            )

            return


        # ========================================================
        # DATOS
        # ========================================================

        chat_origen = message.chat.id

        mensaje_original_id = mensaje_reportado.message_id

        usuario_reportado_id = usuario_reportado.id

        reportador_id = message.from_user.id


        # ========================================================
        # EVITAR AUTOREPORTE
        # ========================================================

        if usuario_reportado_id == reportador_id:

            bot.reply_to(
                message,
                "⚠️ No puedes reportar tu propio contenido."
            )

            return


        # ========================================================
        # REENVIAR EXACTAMENTE EL VIDEO / FOTO / MENSAJE
        # ========================================================

        try:

            mensaje_reenviado = bot.forward_message(
                chat_id=GRUPO_REPORTES_ID,
                from_chat_id=chat_origen,
                message_id=mensaje_original_id
            )

        except Exception as error:

            print("")
            print("============================================")
            print("❌ ERROR REENVIANDO REPORTE")
            print("GRUPO REPORTES:", GRUPO_REPORTES_ID)
            print("GRUPO ORIGEN:", chat_origen)
            print("MENSAJE ID:", mensaje_original_id)
            print("ERROR:", error)
            print("============================================")
            print("")

            bot.reply_to(
                message,
                "❌ <b>No pude enviar el contenido al grupo de reportes.</b>\n\n"
                f"<code>{escape(str(error))}</code>"
            )

            return


        # ========================================================
        # BOTONES
        # ========================================================

        markup = types.InlineKeyboardMarkup(
            row_width=2
        )


        btn_banear = types.InlineKeyboardButton(
            "🔨 Banear",
            callback_data=(
                f"rban:"
                f"{chat_origen}:"
                f"{usuario_reportado_id}:"
                f"{mensaje_original_id}"
            )
        )


        btn_mutear = types.InlineKeyboardButton(
            "🔇 Mutear",
            callback_data=(
                f"rmute:"
                f"{chat_origen}:"
                f"{usuario_reportado_id}:"
                f"{mensaje_original_id}"
            )
        )


        markup.add(
            btn_banear,
            btn_mutear
        )


        # ========================================================
        # DATOS DEL REPORTADO
        # ========================================================

        nombre_reportado = escape(
            usuario_reportado.first_name or "Sin nombre"
        )


        if usuario_reportado.username:

            username_reportado = (
                f"@{escape(usuario_reportado.username)}"
            )

        else:

            username_reportado = "Sin username"


        # ========================================================
        # DATOS DEL QUE REPORTA
        # ========================================================

        nombre_reportador = escape(
            message.from_user.first_name or "Sin nombre"
        )


        if message.from_user.username:

            username_reportador = (
                f"@{escape(message.from_user.username)}"
            )

        else:

            username_reportador = "Sin username"


        # ========================================================
        # GRUPO ORIGEN
        # ========================================================

        nombre_grupo = escape(
            message.chat.title or "Grupo"
        )


        # ========================================================
        # MENSAJE DE INFORMACIÓN
        # ========================================================

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

            "👇 <b>Selecciona qué deseas hacer:</b>"
        )


        # ========================================================
        # ENVIAR INFO RESPONDIENDO AL VIDEO/FOTO
        # ========================================================

        try:

            bot.send_message(
                chat_id=GRUPO_REPORTES_ID,
                text=texto,
                reply_to_message_id=mensaje_reenviado.message_id,
                reply_markup=markup
            )

        except Exception as error:

            print("❌ Error enviando botonera:", error)


        # ========================================================
        # CONFIRMAR AL QUE REPORTÓ
        # ========================================================

        try:

            bot.reply_to(
                message,
                "✅ <b>Reporte enviado correctamente.</b>\n\n"
                "Los administradores revisarán el contenido."
            )

        except Exception:
            pass


        # ========================================================
        # BORRAR /REPORTAR DEL GRUPO
        # ========================================================

        try:

            bot.delete_message(
                message.chat.id,
                message.message_id
            )

        except Exception:
            pass


    # ============================================================
    # 🔨 BANEAR
    # ============================================================

    @bot.callback_query_handler(
        func=lambda call: call.data.startswith("rban:")
    )
    def banear_reportado(call):

        # ========================================================
        # SOLO ADMINS DEL GRUPO DE REPORTES
        # ========================================================

        if not es_admin_reportes(call.from_user.id):

            bot.answer_callback_query(
                call.id,
                "❌ Solo los administradores pueden usar este botón.",
                show_alert=True
            )

            return


        # ========================================================
        # LEER DATOS
        # ========================================================

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


        # ========================================================
        # BANEAR USUARIO
        # ========================================================

        try:

            bot.ban_chat_member(
                chat_id=chat_origen,
                user_id=usuario_id
            )

        except Exception as error:

            print("❌ Error baneando usuario:", error)

            bot.answer_callback_query(
                call.id,
                f"❌ No pude banear:\n{str(error)[:150]}",
                show_alert=True
            )

            return


        # ========================================================
        # ELIMINAR VIDEO/FOTO/MENSAJE ORIGINAL
        # ========================================================

        contenido_eliminado = True

        try:

            bot.delete_message(
                chat_id=chat_origen,
                message_id=mensaje_id
            )

        except Exception as error:

            contenido_eliminado = False

            print(
                "⚠️ Usuario baneado, pero no pude borrar contenido:",
                error
            )


        # ========================================================
        # QUITAR BOTONERA
        # ========================================================

        try:

            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=None
            )

        except Exception:
            pass


        # ========================================================
        # AVISO
        # ========================================================

        if contenido_eliminado:

            bot.answer_callback_query(
                call.id,
                "🔨 Usuario baneado y contenido eliminado.",
                show_alert=True
            )

        else:

            bot.answer_callback_query(
                call.id,
                "🔨 Usuario baneado, pero no pude borrar el contenido.",
                show_alert=True
            )


        # ========================================================
        # MODERADOR
        # ========================================================

        nombre_admin = escape(
            call.from_user.first_name or "Administrador"
        )


        estado_contenido = (
            "🗑 Eliminado"
            if contenido_eliminado
            else "⚠️ No eliminado"
        )


        bot.send_message(
            GRUPO_REPORTES_ID,

            "✅ <b>REPORTE RESUELTO</b>\n\n"

            f"👤 Usuario: <code>{usuario_id}</code>\n"
            "🔨 Acción: <b>BANEADO</b>\n"
            f"📸 Contenido: <b>{estado_contenido}</b>\n\n"

            f"🛡 Moderador: "
            f"<a href='tg://user?id={call.from_user.id}'>"
            f"{nombre_admin}"
            "</a>"
        )


    # ============================================================
    # 🔇 MUTEAR
    # ============================================================

    @bot.callback_query_handler(
        func=lambda call: call.data.startswith("rmute:")
    )
    def mutear_reportado(call):

        # ========================================================
        # SOLO ADMINS
        # ========================================================

        if not es_admin_reportes(call.from_user.id):

            bot.answer_callback_query(
                call.id,
                "❌ Solo los administradores pueden usar este botón.",
                show_alert=True
            )

            return


        # ========================================================
        # LEER DATOS
        # ========================================================

        try:

            datos = call.data.split(":")

            chat_origen = int(datos[1])

            usuario_id = int(datos[2])

            mensaje_id = int(datos[3])

        except Exception:

            bot.answer_callback_query(
                call.id,
                "❌ Datos inválidos.",
                show_alert=True
            )

            return


        # ========================================================
        # PERMISOS DEL MUTE
        # ========================================================

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


        # ========================================================
        # MUTEAR
        # ========================================================

        try:

            bot.restrict_chat_member(
                chat_id=chat_origen,
                user_id=usuario_id,
                permissions=permisos
            )

        except Exception as error:

            print("❌ Error muteando:", error)

            bot.answer_callback_query(
                call.id,
                f"❌ No pude mutear:\n{str(error)[:150]}",
                show_alert=True
            )

            return


        # ========================================================
        # IMPORTANTE:
        # MUTEAR NO BORRA EL VIDEO/FOTO
        # ========================================================


        # ========================================================
        # QUITAR BOTONERA
        # ========================================================

        try:

            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=None
            )

        except Exception:
            pass


        # ========================================================
        # CONFIRMAR
        # ========================================================

        bot.answer_callback_query(
            call.id,
            "🔇 Usuario muteado correctamente.",
            show_alert=True
        )


        nombre_admin = escape(
            call.from_user.first_name or "Administrador"
        )


        bot.send_message(
            GRUPO_REPORTES_ID,

            "✅ <b>REPORTE RESUELTO</b>\n\n"

            f"👤 Usuario: <code>{usuario_id}</code>\n"
            "🔇 Acción: <b>MUTEADO</b>\n"
            "📸 Contenido: <b>NO eliminado</b>\n\n"

            f"🛡 Moderador: "
            f"<a href='tg://user?id={call.from_user.id}'>"
            f"{nombre_admin}"
            "</a>"
        )