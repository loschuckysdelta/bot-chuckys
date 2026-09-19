from telebot import types
from html import escape


# ============================================================
# CONFIGURACIÓN
# ============================================================

# PON AQUÍ TU ID PERSONAL DE TELEGRAM
ADMIN_ID = 8635600472


def registrar_reportes(bot):

    # ============================================================
    # /MIID
    # Sirve para saber tu ID personal de Telegram
    # ============================================================

    @bot.message_handler(commands=["miid"])
    def obtener_mi_id(message):

        bot.reply_to(
            message,
            "🆔 <b>Tu ID de Telegram es:</b>\n"
            f"<code>{message.from_user.id}</code>"
        )


    # ============================================================
    # /REPORTAR
    # ============================================================

    @bot.message_handler(commands=["reportar", "reporte"])
    def reportar(message):

        # --------------------------------------------------------
        # Tiene que responder al mensaje que quiere reportar
        # --------------------------------------------------------

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


        if not usuario_reportado:

            bot.reply_to(
                message,
                "❌ No pude identificar al usuario que envió ese contenido."
            )

            return


        # ========================================================
        # DATOS DEL REPORTE
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
                "⚠️ No puedes reportar tu propio contenido."
            )

            return


        # ========================================================
        # REENVIAR EL VIDEO / FOTO / MENSAJE A TU PRIVADO
        # ========================================================

        try:

            mensaje_reenviado = bot.forward_message(
                chat_id=ADMIN_ID,
                from_chat_id=chat_origen,
                message_id=mensaje_original_id
            )

        except Exception as error:

            print("")
            print("=====================================")
            print("❌ ERROR ENVIANDO REPORTE AL PRIVADO")
            print("ADMIN ID:", ADMIN_ID)
            print("CHAT ORIGEN:", chat_origen)
            print("MENSAJE:", mensaje_original_id)
            print("ERROR:", error)
            print("=====================================")
            print("")

            bot.reply_to(
                message,
                "❌ <b>No pude enviar el reporte al administrador.</b>\n\n"
                "El administrador debe iniciar primero el bot en privado."
            )

            return


        # ========================================================
        # BOTONERA
        # ========================================================

        markup = types.InlineKeyboardMarkup(row_width=2)


        boton_banear = types.InlineKeyboardButton(
            "🔨 Banear",
            callback_data=(
                f"rban:"
                f"{chat_origen}:"
                f"{usuario_reportado_id}:"
                f"{mensaje_original_id}"
            )
        )


        boton_mutear = types.InlineKeyboardButton(
            "🔇 Mutear",
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
        # INFORMACIÓN DEL REPORTADO
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
        # INFORMACIÓN DEL QUE REPORTA
        # ========================================================

        nombre_reportador = escape(
            message.from_user.first_name or "Sin nombre"
        )


        username_reportador = (
            f"@{escape(message.from_user.username)}"
            if message.from_user.username
            else "Sin username"
        )


        nombre_grupo = escape(
            message.chat.title or "Grupo"
        )


        # ========================================================
        # MENSAJE DE REPORTE
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
        # ENVIAR LA BOTONERA A TU PRIVADO
        # RESPONDIENDO AL VIDEO/FOTO REENVIADO
        # ========================================================

        try:

            bot.send_message(
                chat_id=ADMIN_ID,
                text=texto,
                reply_to_message_id=mensaje_reenviado.message_id,
                reply_markup=markup
            )

        except Exception as error:

            print(
                "❌ Error enviando información del reporte:",
                error
            )


        # ========================================================
        # CONFIRMAR AL USUARIO
        # ========================================================

        try:

            bot.reply_to(
                message,
                "✅ <b>Reporte enviado correctamente.</b>\n\n"
                "El administrador revisará el contenido."
            )

        except Exception:
            pass


        # ========================================================
        # BORRAR EL COMANDO /REPORTAR
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

        # Solo tú puedes usar el botón
        if call.from_user.id != ADMIN_ID:

            bot.answer_callback_query(
                call.id,
                "❌ No tienes permiso para hacer esto.",
                show_alert=True
            )

            return


        # ========================================================
        # LEER DATOS DEL BOTÓN
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
        # BANEAR AL USUARIO
        # ========================================================

        try:

            bot.ban_chat_member(
                chat_id=chat_origen,
                user_id=usuario_id
            )

        except Exception as error:

            print("❌ ERROR BANEANDO:", error)

            bot.answer_callback_query(
                call.id,
                f"❌ No pude banear: {str(error)[:120]}",
                show_alert=True
            )

            return


        # ========================================================
        # BORRAR EL VIDEO / FOTO / MENSAJE ORIGINAL
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
                "⚠️ Usuario baneado pero no pude borrar el contenido:",
                error
            )


        # ========================================================
        # QUITAR LOS BOTONES
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
        # RESULTADO
        # ========================================================

        if contenido_eliminado:

            bot.answer_callback_query(
                call.id,
                "🔨 Usuario baneado y contenido eliminado.",
                show_alert=True
            )


            bot.send_message(
                ADMIN_ID,
                "✅ <b>REPORTE RESUELTO</b>\n\n"
                f"👤 ID: <code>{usuario_id}</code>\n"
                "🔨 Estado: <b>BANEADO</b>\n"
                "🗑 Contenido: <b>ELIMINADO</b>"
            )

        else:

            bot.answer_callback_query(
                call.id,
                "🔨 Usuario baneado. No pude eliminar el contenido.",
                show_alert=True
            )


            bot.send_message(
                ADMIN_ID,
                "✅ <b>REPORTE RESUELTO</b>\n\n"
                f"👤 ID: <code>{usuario_id}</code>\n"
                "🔨 Estado: <b>BANEADO</b>\n"
                "⚠️ Contenido: <b>NO SE PUDO ELIMINAR</b>"
            )


    # ============================================================
    # 🔇 MUTEAR
    # ============================================================

    @bot.callback_query_handler(
        func=lambda call: call.data.startswith("rmute:")
    )
    def mutear_reportado(call):

        # Solo tú puedes usar el botón
        if call.from_user.id != ADMIN_ID:

            bot.answer_callback_query(
                call.id,
                "❌ No tienes permiso para hacer esto.",
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

            print("❌ ERROR MUTEANDO:", error)

            bot.answer_callback_query(
                call.id,
                f"❌ No pude mutear: {str(error)[:120]}",
                show_alert=True
            )

            return


        # ========================================================
        # AL MUTEAR NO BORRAMOS EL CONTENIDO
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
        # CONFIRMAR
        # ========================================================

        bot.answer_callback_query(
            call.id,
            "🔇 Usuario muteado correctamente.",
            show_alert=True
        )


        bot.send_message(
            ADMIN_ID,
            "✅ <b>REPORTE RESUELTO</b>\n\n"
            f"👤 ID: <code>{usuario_id}</code>\n"
            "🔇 Estado: <b>MUTEADO</b>\n"
            "📸 Contenido: <b>NO ELIMINADO</b>"
        )