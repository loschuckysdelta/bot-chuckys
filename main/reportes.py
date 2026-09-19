from telebot import types
from html import escape


# ============================================================
# CONFIGURACIÓN
# ============================================================

# CAMBIA ESTO POR EL ID DE TU GRUPO DE REPORTES
GRUPO_REPORTES_ID = -1004452499126


def registrar_reportes(bot):

    # ============================================================
    # VERIFICAR SI ES ADMIN DEL GRUPO DE REPORTES
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
            print("Error verificando admin:", error)
            return False


    # ============================================================
    # COMANDO /REPORTAR
    # ============================================================

    @bot.message_handler(commands=["reportar", "reporte"])
    def reportar(message):

        # ========================================================
        # DEBE RESPONDER A UN MENSAJE
        # ========================================================

        if not message.reply_to_message:

            bot.reply_to(
                message,
                "⚠️ <b>Debes responder al contenido que quieres reportar.</b>\n\n"
                "Por ejemplo:\n"
                "1️⃣ Responde al video, foto o mensaje.\n"
                "2️⃣ Escribe <code>/reportar</code>"
            )

            return


        # ========================================================
        # MENSAJE QUE ESTÁ REPORTANDO
        # ========================================================

        mensaje_reportado = message.reply_to_message

        usuario_reportado = mensaje_reportado.from_user


        if not usuario_reportado:

            bot.reply_to(
                message,
                "❌ No pude identificar al usuario que envió ese contenido."
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
        # EVITAR QUE SE REPORTE A SÍ MISMO
        # ========================================================

        if usuario_reportado_id == reportador_id:

            bot.reply_to(
                message,
                "⚠️ No puedes reportar tu propio mensaje."
            )

            return


        # ========================================================
        # REENVIAR EL VIDEO / FOTO / MENSAJE AL GRUPO DE REPORTES
        # ========================================================

        try:

            mensaje_reenviado = bot.forward_message(
                chat_id=GRUPO_REPORTES_ID,
                from_chat_id=chat_origen,
                message_id=mensaje_original_id
            )

        except Exception as error:

            print("Error reenviando reporte:", error)

            bot.reply_to(
                message,
                "❌ No pude enviar el contenido al grupo de reportes."
            )

            return


        # ========================================================
        # BOTONES
        # ========================================================

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


        # ========================================================
        # DATOS DEL USUARIO REPORTADO
        # ========================================================

        nombre_reportado = escape(
            usuario_reportado.first_name or "Sin nombre"
        )


        username_reportado = (
            f"@{escape(usuario_reportado.username)}"
            if usuario_reportado.username
            else "Sin username"
        )


        # ========================================================
        # DATOS DEL QUE REPORTÓ
        # ========================================================

        nombre_reportador = escape(
            message.from_user.first_name or "Sin nombre"
        )


        username_reportador = (
            f"@{escape(message.from_user.username)}"
            if message.from_user.username
            else "Sin username"
        )


        # ========================================================
        # NOMBRE DEL GRUPO
        # ========================================================

        nombre_grupo = escape(
            message.chat.title or "Grupo"
        )


        # ========================================================
        # INFORMACIÓN DEL REPORTE
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

            "🏠 <b>GRUPO</b>\n"
            f"├ Nombre: {nombre_grupo}\n"
            f"└ ID: <code>{chat_origen}</code>\n\n"

            "👇 <b>Selecciona una acción:</b>"
        )


        # ========================================================
        # ENVIAR BOTONERA DEBAJO DEL VIDEO/FOTO
        # ========================================================

        try:

            bot.send_message(
                chat_id=GRUPO_REPORTES_ID,
                text=texto,
                reply_to_message_id=mensaje_reenviado.message_id,
                reply_markup=markup
            )

        except Exception as error:

            print("Error enviando botonera:", error)


        # ========================================================
        # CONFIRMAR AL USUARIO
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
        # BORRAR EL /REPORTAR DEL GRUPO
        # ========================================================

        try:

            bot.delete_message(
                chat_id=message.chat.id,
                message_id=message.message_id
            )

        except Exception:
            pass


    # ============================================================
    # CALLBACK BANEAR
    # ============================================================

    @bot.callback_query_handler(
        func=lambda call: call.data.startswith("rban:")
    )
    def callback_banear(call):

        # ========================================================
        # SOLO ADMINS DEL GRUPO DE REPORTES
        # ========================================================

        if not es_admin_reportes(call.from_user.id):

            bot.answer_callback_query(
                call.id,
                "❌ Solo los administradores pueden hacer esto.",
                show_alert=True
            )

            return


        # ========================================================
        # OBTENER DATOS
        # ========================================================

        try:

            datos = call.data.split(":")

            chat_origen = int(datos[1])

            usuario_id = int(datos[2])

            mensaje_id = int(datos[3])

        except Exception:

            bot.answer_callback_query(
                call.id,
                "❌ Error leyendo los datos del reporte.",
                show_alert=True
            )

            return


        # ========================================================
        # BANEAR
        # ========================================================

        try:

            bot.ban_chat_member(
                chat_id=chat_origen,
                user_id=usuario_id
            )

        except Exception as error:

            bot.answer_callback_query(
                call.id,
                f"❌ No pude banear: {str(error)[:120]}",
                show_alert=True
            )

            return


        # ========================================================
        # ELIMINAR VIDEO / FOTO / MENSAJE ORIGINAL
        # ========================================================

        eliminado = True

        try:

            bot.delete_message(
                chat_id=chat_origen,
                message_id=mensaje_id
            )

        except Exception as error:

            eliminado = False

            print(
                "Usuario baneado pero no se pudo eliminar mensaje:",
                error
            )


        # ========================================================
        # QUITAR BOTONES
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
        # RESPUESTA
        # ========================================================

        if eliminado:

            respuesta = (
                "🔨 Usuario baneado.\n"
                "🗑 Contenido eliminado."
            )

        else:

            respuesta = (
                "🔨 Usuario baneado.\n"
                "⚠️ No pude eliminar el contenido."
            )


        bot.answer_callback_query(
            call.id,
            respuesta,
            show_alert=True
        )


        # ========================================================
        # MOSTRAR QUIÉN REALIZÓ LA ACCIÓN
        # ========================================================

        admin_nombre = escape(
            call.from_user.first_name or "Administrador"
        )


        estado_contenido = (
            "🗑 Eliminado"
            if eliminado
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
            f"{admin_nombre}"
            "</a>"
        )


    # ============================================================
    # CALLBACK MUTEAR
    # ============================================================

    @bot.callback_query_handler(
        func=lambda call: call.data.startswith("rmute:")
    )
    def callback_mutear(call):

        # ========================================================
        # SOLO ADMINS
        # ========================================================

        if not es_admin_reportes(call.from_user.id):

            bot.answer_callback_query(
                call.id,
                "❌ Solo los administradores pueden hacer esto.",
                show_alert=True
            )

            return


        # ========================================================
        # OBTENER DATOS
        # ========================================================

        try:

            datos = call.data.split(":")

            chat_origen = int(datos[1])

            usuario_id = int(datos[2])

            mensaje_id = int(datos[3])

        except Exception:

            bot.answer_callback_query(
                call.id,
                "❌ Error leyendo los datos.",
                show_alert=True
            )

            return


        # ========================================================
        # PERMISOS PARA MUTE
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
        # MUTEAR USUARIO
        # ========================================================

        try:

            bot.restrict_chat_member(
                chat_id=chat_origen,
                user_id=usuario_id,
                permissions=permisos
            )

        except Exception as error:

            bot.answer_callback_query(
                call.id,
                f"❌ No pude mutear: {str(error)[:120]}",
                show_alert=True
            )

            return


        # ========================================================
        # IMPORTANTE:
        # AL MUTEAR NO BORRAMOS EL VIDEO / FOTO
        # ========================================================


        # ========================================================
        # QUITAR BOTONES
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
        # CONFIRMACIÓN
        # ========================================================

        bot.answer_callback_query(
            call.id,
            "🔇 Usuario muteado correctamente.",
            show_alert=True
        )


        admin_nombre = escape(
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
            f"{admin_nombre}"
            "</a>"
        )