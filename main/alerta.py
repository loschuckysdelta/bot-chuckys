import time
import requests
from telebot import types
from telebot.apihelper import ApiTelegramException


API_USUARIOS = "https://bot-apis-zkmk.vercel.app/api/users"

# IMPORTANTE:
# Pon aquí solamente los IDs que pueden usar /alerta
ADMIN_IDS = [
    8635600472
]

alertas = {}


# =====================================================
# OBTENER TODOS LOS USUARIOS DE LA API
# =====================================================

def obtener_usuarios():
    usuarios_totales = []

    try:
        pagina = 1

        while True:

            response = requests.get(
                API_USUARIOS,
                params={"page": pagina},
                timeout=15
            )

            response.raise_for_status()

            data = response.json()

            usuarios = data.get("usuarios", [])
            paginas = data.get("pages", 1)

            for usuario in usuarios:

                telegram_id = usuario.get("telegramId")
                bloqueado = usuario.get("botBloqueado", False)

                if telegram_id and not bloqueado:
                    usuarios_totales.append(telegram_id)

            print(
                f"📥 Página {pagina}/{paginas} | "
                f"Usuarios cargados: {len(usuarios_totales)}"
            )

            if pagina >= paginas:
                break

            pagina += 1

        # Evita IDs duplicados
        usuarios_totales = list(dict.fromkeys(usuarios_totales))

        return usuarios_totales

    except Exception as e:

        print(f"❌ Error obteniendo usuarios: {e}")

        return []


# =====================================================
# REGISTRAR ALERTA
# =====================================================

def registrar_alerta(bot):

    # =====================================================
    # /alerta
    # =====================================================

    @bot.message_handler(commands=["alerta"])
    def comando_alerta(message):

        user_id = message.from_user.id

        # Seguridad
        if user_id not in ADMIN_IDS:

            bot.reply_to(
                message,
                "⛔ <b>No tienes permiso para usar este comando.</b>"
            )

            return

        alertas[user_id] = {
            "texto": None,
            "multimedia": None,
            "botones": [],
            "fijar": False
        }

        mostrar_panel(bot, message.chat.id, user_id)


    # =====================================================
    # PANEL
    # =====================================================

    def mostrar_panel(bot, chat_id, user_id):

        datos = alertas.get(user_id, {})

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

        bot.send_message(
            chat_id,
            "📢 <b>Difusión · Guía</b>\n"
            "<i>Envía un mensaje simultáneamente a todos "
            "los usuarios que iniciaron el bot.</i>",
            reply_markup=markup
        )


    # =====================================================
    # CONFIGURAR TEXTO
    # =====================================================

    @bot.callback_query_handler(
        func=lambda call: call.data == "alerta_texto"
    )
    def alerta_texto(call):

        if call.from_user.id not in ADMIN_IDS:
            return

        bot.answer_callback_query(call.id)

        mensaje = bot.send_message(
            call.message.chat.id,
            "🔤 <b>Texto</b>\n\n"
            "Envíame el texto que quieres mandar en la difusión.\n\n"
            "Puedes utilizar HTML."
        )

        bot.register_next_step_handler(
            mensaje,
            guardar_texto
        )


    def guardar_texto(message):

        user_id = message.from_user.id

        if user_id not in ADMIN_IDS:
            return

        if user_id not in alertas:

            alertas[user_id] = {
                "texto": None,
                "multimedia": None,
                "botones": [],
                "fijar": False
            }

        alertas[user_id]["texto"] = message.text

        bot.send_message(
            message.chat.id,
            "✅ <b>Texto guardado correctamente.</b>"
        )

        mostrar_panel(
            bot,
            message.chat.id,
            user_id
        )


    # =====================================================
    # MULTIMEDIA
    # =====================================================

    @bot.callback_query_handler(
        func=lambda call: call.data == "alerta_multimedia"
    )
    def alerta_multimedia(call):

        if call.from_user.id not in ADMIN_IDS:
            return

        bot.answer_callback_query(call.id)

        mensaje = bot.send_message(
            call.message.chat.id,
            "🖼️ <b>Multimedia</b>\n\n"
            "Envíame una foto o un video."
        )

        bot.register_next_step_handler(
            mensaje,
            guardar_multimedia
        )


    def guardar_multimedia(message):

        user_id = message.from_user.id

        if user_id not in ADMIN_IDS:
            return

        if user_id not in alertas:
            return

        if message.photo:

            alertas[user_id]["multimedia"] = {
                "tipo": "foto",
                "file_id": message.photo[-1].file_id
            }

        elif message.video:

            alertas[user_id]["multimedia"] = {
                "tipo": "video",
                "file_id": message.video.file_id
            }

        else:

            bot.send_message(
                message.chat.id,
                "❌ Solamente puedes enviar una foto o video."
            )

            return

        bot.send_message(
            message.chat.id,
            "✅ <b>Multimedia guardado.</b>"
        )

        mostrar_panel(
            bot,
            message.chat.id,
            user_id
        )


    # =====================================================
    # VER TEXTO
    # =====================================================

    @bot.callback_query_handler(
        func=lambda call: call.data == "alerta_ver_texto"
    )
    def alerta_ver_texto(call):

        datos = alertas.get(
            call.from_user.id,
            {}
        )

        texto = datos.get("texto")

        if not texto:

            bot.answer_callback_query(
                call.id,
                "❌ Todavía no agregaste texto.",
                show_alert=True
            )

            return

        bot.answer_callback_query(call.id)

        bot.send_message(
            call.message.chat.id,
            "🔤 <b>Texto actual:</b>\n\n"
            + texto
        )


    # =====================================================
    # VER MULTIMEDIA
    # =====================================================

    @bot.callback_query_handler(
        func=lambda call: call.data == "alerta_ver_multimedia"
    )
    def alerta_ver_multimedia(call):

        datos = alertas.get(
            call.from_user.id,
            {}
        )

        multimedia = datos.get("multimedia")

        if not multimedia:

            bot.answer_callback_query(
                call.id,
                "❌ No hay multimedia.",
                show_alert=True
            )

            return

        bot.answer_callback_query(call.id)

        if multimedia["tipo"] == "foto":

            bot.send_photo(
                call.message.chat.id,
                multimedia["file_id"]
            )

        elif multimedia["tipo"] == "video":

            bot.send_video(
                call.message.chat.id,
                multimedia["file_id"]
            )


    # =====================================================
    # FIJAR
    # =====================================================

    @bot.callback_query_handler(
        func=lambda call: call.data == "alerta_fijar"
    )
    def alerta_fijar(call):

        user_id = call.from_user.id

        if user_id not in alertas:
            return

        alertas[user_id]["fijar"] = not alertas[user_id].get(
            "fijar",
            False
        )

        estado = (
            "✅ Activado"
            if alertas[user_id]["fijar"]
            else "❌ Desactivado"
        )

        bot.answer_callback_query(
            call.id,
            f"📌 Fijar: {estado}"
        )


    # =====================================================
    # VISTA PREVIA
    # =====================================================

    @bot.callback_query_handler(
        func=lambda call: call.data == "alerta_preview"
    )
    def alerta_preview(call):

        datos = alertas.get(
            call.from_user.id,
            {}
        )

        texto = datos.get("texto")
        multimedia = datos.get("multimedia")

        if not texto and not multimedia:

            bot.answer_callback_query(
                call.id,
                "❌ Agrega contenido primero.",
                show_alert=True
            )

            return

        bot.answer_callback_query(call.id)

        enviar_contenido(
            bot,
            call.message.chat.id,
            datos
        )


    # =====================================================
    # SIGUIENTE
    # =====================================================

    @bot.callback_query_handler(
        func=lambda call: call.data == "alerta_siguiente"
    )
    def alerta_siguiente(call):

        datos = alertas.get(
            call.from_user.id,
            {}
        )

        if not datos.get("texto") and not datos.get("multimedia"):

            bot.answer_callback_query(
                call.id,
                "❌ Primero agrega texto o multimedia.",
                show_alert=True
            )

            return

        bot.answer_callback_query(call.id)

        markup = types.InlineKeyboardMarkup()

        markup.row(
            types.InlineKeyboardButton(
                "🚀 ENVIAR AHORA",
                callback_data="alerta_enviar"
            )
        )

        markup.row(
            types.InlineKeyboardButton(
                "⬅️ Regresar",
                callback_data="alerta_regresar"
            ),

            types.InlineKeyboardButton(
                "❌ Cancelar",
                callback_data="alerta_cancelar"
            )
        )

        bot.send_message(
            call.message.chat.id,
            "🚨 <b>CONFIRMAR DIFUSIÓN</b>\n\n"
            "El mensaje se enviará a todos los usuarios "
            "registrados y activos de la API.\n\n"
            "¿Deseas continuar?",
            reply_markup=markup
        )


    # =====================================================
    # ENVIAR DIFUSIÓN
    # =====================================================

    @bot.callback_query_handler(
        func=lambda call: call.data == "alerta_enviar"
    )
    def alerta_enviar(call):

        admin_id = call.from_user.id

        if admin_id not in ADMIN_IDS:
            return

        datos = alertas.get(admin_id)

        if not datos:
            return

        bot.answer_callback_query(
            call.id,
            "🚀 Iniciando difusión..."
        )

        estado = bot.send_message(
            call.message.chat.id,
            "⏳ <b>Cargando usuarios de la API...</b>"
        )

        usuarios = obtener_usuarios()

        if not usuarios:

            bot.edit_message_text(
                "❌ <b>No se pudieron obtener usuarios.</b>",
                call.message.chat.id,
                estado.message_id
            )

            return

        total = len(usuarios)

        bot.edit_message_text(
            f"🚀 <b>DIFUSIÓN INICIADA</b>\n\n"
            f"👥 Usuarios: <b>{total}</b>\n"
            f"📤 Enviados: <b>0</b>\n"
            f"❌ Fallidos: <b>0</b>",
            call.message.chat.id,
            estado.message_id
        )

        enviados = 0
        fallidos = 0
        bloqueados = 0

        for indice, telegram_id in enumerate(
            usuarios,
            start=1
        ):

            try:

                mensaje_enviado = enviar_contenido(
                    bot,
                    telegram_id,
                    datos
                )

                enviados += 1

                # Fijar mensaje solamente si es posible
                if datos.get("fijar") and mensaje_enviado:

                    try:

                        bot.pin_chat_message(
                            telegram_id,
                            mensaje_enviado.message_id,
                            disable_notification=True
                        )

                    except Exception:
                        pass

            except ApiTelegramException as e:

                fallidos += 1

                error = str(e).lower()

                if (
                    "blocked by the user" in error
                    or "chat not found" in error
                    or "user is deactivated" in error
                ):
                    bloqueados += 1

            except Exception as e:

                fallidos += 1

                print(
                    f"❌ Error con {telegram_id}: {e}"
                )

            # Pequeña pausa para evitar saturar Telegram
            time.sleep(0.05)

            # Actualizar progreso cada 25 usuarios
            if indice % 25 == 0 or indice == total:

                try:

                    porcentaje = round(
                        (indice / total) * 100,
                        1
                    )

                    bot.edit_message_text(
                        f"🚀 <b>DIFUSIÓN EN PROCESO</b>\n\n"
                        f"👥 Total: <b>{total}</b>\n"
                        f"📤 Enviados: <b>{enviados}</b>\n"
                        f"❌ Fallidos: <b>{fallidos}</b>\n"
                        f"🚫 Bloquearon bot: <b>{bloqueados}</b>\n\n"
                        f"📊 Progreso: <b>{porcentaje}%</b>",
                        call.message.chat.id,
                        estado.message_id
                    )

                except Exception:
                    pass


        # =================================================
        # TERMINADO
        # =================================================

        bot.edit_message_text(
            f"✅ <b>DIFUSIÓN FINALIZADA</b>\n\n"
            f"👥 Usuarios procesados: <b>{total}</b>\n"
            f"✅ Enviados: <b>{enviados}</b>\n"
            f"❌ Fallidos: <b>{fallidos}</b>\n"
            f"🚫 Bloquearon el bot: <b>{bloqueados}</b>",
            call.message.chat.id,
            estado.message_id
        )

        alertas.pop(
            admin_id,
            None
        )


    # =====================================================
    # REGRESAR
    # =====================================================

    @bot.callback_query_handler(
        func=lambda call: call.data == "alerta_regresar"
    )
    def alerta_regresar(call):

        bot.answer_callback_query(call.id)

        mostrar_panel(
            bot,
            call.message.chat.id,
            call.from_user.id
        )


    # =====================================================
    # CANCELAR
    # =====================================================

    @bot.callback_query_handler(
        func=lambda call: call.data == "alerta_cancelar"
    )
    def alerta_cancelar(call):

        alertas.pop(
            call.from_user.id,
            None
        )

        bot.answer_callback_query(
            call.id,
            "Difusión cancelada"
        )

        try:

            bot.edit_message_text(
                "❌ <b>Difusión cancelada.</b>",
                call.message.chat.id,
                call.message.message_id
            )

        except Exception:
            pass


# =====================================================
# FUNCIÓN PARA ENVIAR EL CONTENIDO
# =====================================================

def enviar_contenido(bot, telegram_id, datos):

    texto = datos.get("texto")
    multimedia = datos.get("multimedia")

    if multimedia:

        if multimedia["tipo"] == "foto":

            return bot.send_photo(
                telegram_id,
                multimedia["file_id"],
                caption=texto or "",
                parse_mode="HTML"
            )

        elif multimedia["tipo"] == "video":

            return bot.send_video(
                telegram_id,
                multimedia["file_id"],
                caption=texto or "",
                parse_mode="HTML"
            )

    elif texto:

        return bot.send_message(
            telegram_id,
            texto,
            parse_mode="HTML"
        )

    return None