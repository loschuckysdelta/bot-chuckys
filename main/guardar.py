import telebot
import json
import os
import threading
import time
import requests


# =========================================================
# CONFIGURACIÓN
# =========================================================

ARCHIVO_RECIBIDOS = "guardados.json"
ARCHIVO_INTERCAMBIOS = "intercambios.json"

API_CONTACTOS = "https://bot-apis-zkmk.vercel.app/api/contactos"
API_USERS = "https://bot-apis-zkmk.vercel.app/api/users"


# =========================================================
# CONTACTOS / REGISTRO
# =========================================================

def _buscar_contacto_en_respuesta(datos, telegram_id):
    """Devuelve True/False si la respuesta permite saberlo; None si es inconclusa."""
    objetivo = str(telegram_id)

    if not isinstance(datos, dict):
        return None

    # Respuesta de un contacto individual
    for clave in ("contacto", "usuario", "user"):
        item = datos.get(clave)
        if isinstance(item, dict):
            return str(item.get("telegramId")) == objetivo

    # Respuesta de listado
    contactos = datos.get("contactos")
    if isinstance(contactos, list):
        for contacto in contactos:
            if isinstance(contacto, dict) and str(contacto.get("telegramId")) == objetivo:
                return True

        # Si la API devolvió un resultado filtrado pequeño, la ausencia sí es concluyente.
        total = datos.get("total")
        if isinstance(total, int) and total <= len(contactos):
            return False

    # Algunos backends devuelven flags de existencia
    for clave in ("exists", "existe", "registrado"):
        if clave in datos and isinstance(datos.get(clave), bool):
            return datos.get(clave)

    return None


def usuario_registrado_contactos(telegram_id):
    """
    Comprueba el registro usando búsquedas directas.
    Retorna True si existe, False si no existe y None si la API no pudo verificarse.
    """
    intentos = (
        {"telegramId": telegram_id},
        {"buscar": str(telegram_id)},
    )

    for params in intentos:
        try:
            respuesta = requests.get(
                API_CONTACTOS,
                params=params,
                timeout=10
            )

            if respuesta.status_code != 200:
                continue

            resultado = _buscar_contacto_en_respuesta(
                respuesta.json(),
                telegram_id
            )

            if resultado is not None:
                return resultado

        except Exception as error:
            print("Error verificando contacto:", error)

    return None


def _buscar_usuario_en_respuesta(datos, telegram_id):
    """Devuelve True/False si la respuesta permite saberlo; None si es inconclusa."""
    objetivo = str(telegram_id)

    if not isinstance(datos, dict):
        return None

    for clave in ("usuario", "user"):
        item = datos.get(clave)
        if isinstance(item, dict):
            return str(item.get("telegramId")) == objetivo

    usuarios = datos.get("usuarios")
    if isinstance(usuarios, list):
        for usuario in usuarios:
            if isinstance(usuario, dict) and str(usuario.get("telegramId")) == objetivo:
                return True

        total = datos.get("total")
        if isinstance(total, int) and total <= len(usuarios):
            return False

    for clave in ("exists", "existe", "registrado"):
        if clave in datos and isinstance(datos.get(clave), bool):
            return datos.get(clave)

    return None


def usuario_registrado_users(telegram_id):
    intentos = (
        {"telegramId": telegram_id},
        {"buscar": str(telegram_id)},
    )

    for params in intentos:
        try:
            respuesta = requests.get(API_USERS, params=params, timeout=10)
            if respuesta.status_code != 200:
                continue

            resultado = _buscar_usuario_en_respuesta(respuesta.json(), telegram_id)
            if resultado is not None:
                return resultado
        except Exception as error:
            print("Error verificando /api/users:", error)

    return None


def asegurar_usuario_en_users(usuario):
    """Registra/actualiza al usuario en /api/users. No bloquea si la API ya lo tiene."""
    datos = {
        "telegramId": usuario.id,
        "username": usuario.username or "",
        "nombre": (
            " ".join(
                parte for parte in [usuario.first_name or "", usuario.last_name or ""]
                if parte
            ).strip() or "SinNombre"
        ),
    }

    try:
        respuesta = requests.post(API_USERS, json=datos, timeout=10)
        return respuesta.status_code in (200, 201)
    except Exception as error:
        print("Error registrando /api/users:", error)
        return False


def teclado_ir_privado(bot):
    try:
        username_bot = bot.get_me().username
    except Exception:
        username_bot = None

    teclado = telebot.types.InlineKeyboardMarkup()

    if username_bot:
        teclado.add(
            telebot.types.InlineKeyboardButton(
                "📩 ABRIR PRIVADO",
                url=f"https://t.me/{username_bot}"
            )
        )

    return teclado


def teclado_completar_registro():
    teclado = telebot.types.InlineKeyboardMarkup()
    teclado.add(
        telebot.types.InlineKeyboardButton(
            "📱 COMPLETAR REGISTRO",
            callback_data="completar_registro_contacto"
        )
    )
    return teclado


def teclado_compartir_contacto():
    teclado = telebot.types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        one_time_keyboard=True
    )

    teclado.add(
        telebot.types.KeyboardButton(
            "📱 REGISTRAR MI NÚMERO",
            request_contact=True
        )
    )

    return teclado


db_lock = threading.Lock()

# Contenido pendiente por usuario
contenidos_pendientes = {}


# =========================================================
# CARGAR JSON
# =========================================================

def cargar_json(nombre_archivo):

    if not os.path.exists(nombre_archivo):
        return {}

    try:

        with open(
            nombre_archivo,
            "r",
            encoding="utf-8"
        ) as archivo:

            datos = json.load(archivo)

            if isinstance(datos, dict):
                return datos

            return {}

    except Exception as error:

        print(
            f"Error cargando {nombre_archivo}:",
            error
        )

        return {}


# =========================================================
# GUARDAR JSON
# =========================================================

def guardar_json(nombre_archivo, datos):

    with db_lock:

        try:

            with open(
                nombre_archivo,
                "w",
                encoding="utf-8"
            ) as archivo:

                json.dump(
                    datos,
                    archivo,
                    indent=4,
                    ensure_ascii=False
                )

        except Exception as error:

            print(
                f"Error guardando {nombre_archivo}:",
                error
            )


# =========================================================
# BASES DE DATOS
# =========================================================

archivos_recibidos = cargar_json(
    ARCHIVO_RECIBIDOS
)

archivos_intercambio = cargar_json(
    ARCHIVO_INTERCAMBIOS
)


# =========================================================
# PREPARAR USUARIO
# =========================================================

def preparar_usuario(base, usuario_id):

    usuario = str(usuario_id)

    if usuario not in base:
        base[usuario] = []

    return usuario


# =========================================================
# COMPROBAR SI YA RECIBIÓ EL CONTENIDO
# =========================================================

def ya_recibio_archivo(
    usuario_id,
    file_unique_id
):

    usuario = preparar_usuario(
        archivos_recibidos,
        usuario_id
    )

    return (
        file_unique_id
        in archivos_recibidos[usuario]
    )


# =========================================================
# REGISTRAR CONTENIDO RECIBIDO
# =========================================================

def registrar_recibido(
    usuario_id,
    file_unique_id
):

    usuario = preparar_usuario(
        archivos_recibidos,
        usuario_id
    )

    if (
        file_unique_id
        not in archivos_recibidos[usuario]
    ):

        archivos_recibidos[usuario].append(
            file_unique_id
        )

        guardar_json(
            ARCHIVO_RECIBIDOS,
            archivos_recibidos
        )


# =========================================================
# COMPROBAR INTERCAMBIO REPETIDO
# =========================================================

def intercambio_ya_usado(
    usuario_id,
    file_unique_id
):

    usuario = preparar_usuario(
        archivos_intercambio,
        usuario_id
    )

    return (
        file_unique_id
        in archivos_intercambio[usuario]
    )


# =========================================================
# REGISTRAR INTERCAMBIO
# =========================================================

def registrar_intercambio(
    usuario_id,
    file_unique_id
):

    usuario = preparar_usuario(
        archivos_intercambio,
        usuario_id
    )

    if (
        file_unique_id
        not in archivos_intercambio[usuario]
    ):

        archivos_intercambio[usuario].append(
            file_unique_id
        )

        guardar_json(
            ARCHIVO_INTERCAMBIOS,
            archivos_intercambio
        )


# =========================================================
# CREAR BARRA
# =========================================================

def crear_barra(
    transcurrido,
    total=10
):

    if transcurrido < 0:
        transcurrido = 0

    if transcurrido > total:
        transcurrido = total

    llenos = transcurrido
    vacios = total - transcurrido

    return (
        "🟩" * llenos
        +
        "⬜" * vacios
    )


# =========================================================
# REGISTRAR MÓDULO GUARDAR
# =========================================================

def registrar_guardar(bot):


    # =====================================================
    # BORRAR CONTENIDO DESPUÉS DE 10 MINUTOS
    # =====================================================

    def temporizador_borrado(
        usuario_id,
        mensaje_contenido_id,
        mensaje_barra_id
    ):

        try:

            for minuto_pasado in range(0, 10):

                minutos_restantes = (
                    10 - minuto_pasado
                )

                barra = crear_barra(
                    minuto_pasado
                )

                try:

                    bot.edit_message_text(
                        chat_id=usuario_id,
                        message_id=mensaje_barra_id,
                        text=(
                            "⏳ <b>TIEMPO PARA DESCARGAR</b>\n\n"

                            f"{barra}\n\n"

                            f"🕐 Quedan "
                            f"<b>{minutos_restantes} minutos</b>.\n\n"

                            "📥 Descarga el contenido "
                            "antes de que sea eliminado "
                            "automáticamente."
                        )
                    )

                except Exception as error:

                    print(
                        "Error actualizando barra:",
                        error
                    )

                time.sleep(60)


            # =================================================
            # BORRAR FOTO / VIDEO
            # =================================================

            try:

                bot.delete_message(
                    chat_id=usuario_id,
                    message_id=mensaje_contenido_id
                )

                print(
                    f"Contenido eliminado del usuario "
                    f"{usuario_id}"
                )

            except Exception as error:

                print(
                    "No se pudo borrar el contenido:",
                    error
                )


            # =================================================
            # BARRA FINAL
            # =================================================

            try:

                bot.edit_message_text(
                    chat_id=usuario_id,
                    message_id=mensaje_barra_id,
                    text=(
                        "⌛ <b>TIEMPO FINALIZADO</b>\n\n"

                        "🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩\n\n"

                        "🗑 <b>El contenido fue eliminado.</b>\n\n"

                        "Para obtener otro contenido "
                        "vuelve al grupo y utiliza "
                        "<code>/guardar</code>."
                    )
                )

            except Exception as error:

                print(
                    "No se pudo actualizar "
                    "el mensaje final:",
                    error
                )


        except Exception as error:

            print(
                "Error en temporizador:",
                error
            )


    # =====================================================
    # ENTREGAR CONTENIDO AL PRIVADO
    # =====================================================

    def entregar_contenido(
        usuario_id,
        pendiente
    ):

        mensaje_enviado = bot.copy_message(
            chat_id=usuario_id,
            from_chat_id=pendiente["chat_id"],
            message_id=pendiente["message_id"]
        )

        barra = crear_barra(0)

        mensaje_barra = bot.send_message(
            usuario_id,

            "⏳ <b>TIEMPO PARA DESCARGAR</b>\n\n"

            f"{barra}\n\n"

            "🕐 Tienes <b>10 minutos</b> "
            "para descargar este contenido.\n\n"

            "⚠️ Cuando termine el tiempo "
            "la foto o video será eliminado "
            "automáticamente."
        )

        hilo = threading.Thread(
            target=temporizador_borrado,
            args=(
                usuario_id,
                mensaje_enviado.message_id,
                mensaje_barra.message_id
            ),
            daemon=True
        )

        hilo.start()


    # =====================================================
    # BOTÓN: COMPLETAR REGISTRO DESDE EL GRUPO
    # =====================================================

    @bot.callback_query_handler(
        func=lambda call: call.data == "completar_registro_contacto"
    )
    def completar_registro_contacto(call):

        usuario = call.from_user
        usuario_id = usuario.id

        # Primero comprobamos si ya terminó el registro.
        en_contactos = usuario_registrado_contactos(usuario_id)

        if en_contactos is True:
            bot.answer_callback_query(
                call.id,
                "✅ Ya estás registrado. Puedes usar /guardar.",
                show_alert=True
            )
            return

        # Este botón está pensado para usuarios que ya existen en /api/users.
        en_users = usuario_registrado_users(usuario_id)

        if en_users is not True:
            bot.answer_callback_query(
                call.id,
                "⚠️ Primero debes registrarte con /registro en privado.",
                show_alert=True
            )
            return

        try:
            bot.send_message(
                usuario_id,
                "📱 <b>COMPLETAR REGISTRO</b>\n\n"
                "✅ Tu cuenta ya está registrada en el bot.\n"
                "❌ Solo falta registrar tu contacto.\n\n"
                "👇 Pulsa <b>📱 REGISTRAR MI NÚMERO</b> "
                "y comparte tu propio número de Telegram.",
                reply_markup=teclado_compartir_contacto()
            )

            bot.answer_callback_query(
                call.id,
                "📩 Te envié la botonera a tu privado.",
                show_alert=True
            )

        except telebot.apihelper.ApiTelegramException:
            bot.answer_callback_query(
                call.id,
                "📩 Abre primero el privado del bot y vuelve a tocar el botón.",
                show_alert=True
            )

            try:
                bot.send_message(
                    call.message.chat.id,
                    "⚠️ <b>NO PUDE ESCRIBIRTE AL PRIVADO</b>\n\n"
                    "Abre el chat privado del bot y luego vuelve a tocar "
                    "<b>📱 COMPLETAR REGISTRO</b>.",
                    reply_markup=teclado_ir_privado(bot)
                )
            except Exception:
                pass


    # =====================================================
    # /REGISTRO - SOLO PRIVADO
    # =====================================================

    @bot.message_handler(commands=["registro"])
    def iniciar_registro(message):

        if message.chat.type != "private":
            bot.reply_to(
                message,
                "📩 <b>EL REGISTRO SE HACE EN PRIVADO</b>\n\n"
                "Abre el chat privado del bot y escribe "
                "<code>/registro</code>.",
                reply_markup=teclado_ir_privado(bot)
            )
            return

        usuario = message.from_user
        usuario_id = usuario.id

        en_contactos = usuario_registrado_contactos(usuario_id)

        if en_contactos is True:
            bot.send_message(
                message.chat.id,
                "✅ <b>YA ESTÁS HABILITADO</b>\n\n"
                "Tu número ya está registrado.\n\n"
                "👥 Regresa al grupo y utiliza <code>/guardar</code>.",
                reply_markup=telebot.types.ReplyKeyboardRemove()
            )
            return

        en_users = usuario_registrado_users(usuario_id)
        if en_users is not True:
            asegurar_usuario_en_users(usuario)

        bot.send_message(
            message.chat.id,
            "📱 <b>COMPLETAR REGISTRO</b>\n\n"
            "Tu cuenta del bot ya está lista. Solo falta registrar "
            "tu número para habilitar <code>/guardar</code>.\n\n"
            "👇 Pulsa el botón y comparte <b>tu propio número</b>.",
            reply_markup=teclado_compartir_contacto()
        )


    # =====================================================
    # RECIBIR / REGISTRAR CONTACTO - SOLO PRIVADO
    # =====================================================

    @bot.message_handler(content_types=["contact"])
    def registrar_contacto(message):

        if message.chat.type != "private":
            return

        contacto = message.contact
        usuario = message.from_user

        if contacto.user_id != usuario.id:
            bot.reply_to(
                message,
                "❌ <b>DEBES COMPARTIR TU PROPIO NÚMERO</b>\n\n"
                "Pulsa <b>📱 REGISTRAR MI NÚMERO</b> y comparte tu contacto."
            )
            return

        asegurar_usuario_en_users(usuario)

        datos = {
            "telegramId": usuario.id,
            "username": usuario.username or "",
            "nombre": (
                " ".join(
                    parte for parte in [usuario.first_name or "", usuario.last_name or ""]
                    if parte
                ).strip() or "SinNombre"
            ),
            "telefono": contacto.phone_number
        }

        try:
            respuesta = requests.post(API_CONTACTOS, json=datos, timeout=10)

            if respuesta.status_code in (200, 201):
                bot.send_message(
                    message.chat.id,
                    "✅ <b>REGISTRO COMPLETADO</b>\n\n"
                    "Tu cuenta y tu contacto quedaron habilitados.\n\n"
                    "👥 Regresa al grupo y utiliza <code>/guardar</code>.",
                    reply_markup=telebot.types.ReplyKeyboardRemove()
                )
                return

            print("Error registrando contacto:", respuesta.status_code, respuesta.text[:500])
            bot.send_message(
                message.chat.id,
                "❌ <b>NO SE PUDO COMPLETAR EL REGISTRO</b>\n\n"
                "La API rechazó la solicitud. Inténtalo nuevamente con "
                "<code>/registro</code>.",
                reply_markup=telebot.types.ReplyKeyboardRemove()
            )

        except Exception as error:
            print("Error registrando contacto:", error)
            bot.send_message(
                message.chat.id,
                "❌ <b>ERROR DE CONEXIÓN</b>\n\n"
                "No se pudo conectar con la base de contactos.",
                reply_markup=telebot.types.ReplyKeyboardRemove()
            )


    # =====================================================
    # /GUARDAR
    # =====================================================

    @bot.message_handler(
        commands=["guardar"]
    )
    def guardar(message):

        usuario_id = message.from_user.id


        # =================================================
        # VERIFICAR /API/USERS + /API/CONTACTOS
        # =================================================

        en_contactos = usuario_registrado_contactos(usuario_id)

        if en_contactos is False:
            en_users = usuario_registrado_users(usuario_id)

            if en_users is True:
                bot.reply_to(
                    message,
                    "🔐 <b>FALTA COMPLETAR TU REGISTRO</b>\n\n"
                    "✅ Ya estás registrado en el bot.\n"
                    "❌ Solo falta registrar tu contacto.\n\n"
                    "👇 Pulsa <b>📱 COMPLETAR REGISTRO</b>.\n\n"
                    "El bot te enviará automáticamente al privado la "
                    "botonera para compartir tu número.",
                    reply_markup=teclado_completar_registro()
                )
            else:
                bot.reply_to(
                    message,
                    "🔒 <b>NO ESTÁS REGISTRADO</b>\n\n"
                    "Para utilizar <code>/guardar</code> primero debes "
                    "registrar tu cuenta.\n\n"
                    "📩 Abre el privado del bot y escribe:\n\n"
                    "<code>/registro</code>",
                    reply_markup=teclado_ir_privado(bot)
                )

            return

        if en_contactos is None:
            bot.reply_to(
                message,
                "⚠️ <b>NO PUDE VERIFICAR TU REGISTRO</b>\n\n"
                "La base de contactos no respondió correctamente. "
                "Inténtalo nuevamente en unos momentos."
            )
            return


        # =================================================
        # DEBE RESPONDER A UN MENSAJE
        # =================================================

        if not message.reply_to_message:

            bot.reply_to(
                message,

                "⚠️ <b>DEBES RESPONDER "
                "A UNA FOTO O VIDEO</b>\n\n"

                "1️⃣ Busca el contenido.\n"
                "2️⃣ Pulsa responder.\n"
                "3️⃣ Escribe:\n\n"

                "<code>/guardar</code>"
            )

            return


        contenido = message.reply_to_message


        # =================================================
        # FOTO
        # =================================================

        if contenido.photo:

            foto = contenido.photo[-1]

            file_id = foto.file_id
            file_unique_id = foto.file_unique_id


            if ya_recibio_archivo(
                usuario_id,
                file_unique_id
            ):

                bot.reply_to(
                    message,

                    "⚠️ <b>YA GUARDASTE ESTA FOTO</b>\n\n"

                    "Esta foto ya fue recibida "
                    "anteriormente."
                )

                return


            contenidos_pendientes[
                usuario_id
            ] = {

                "tipo": "photo",

                "file_id": file_id,

                "file_unique_id": file_unique_id,

                "chat_id": contenido.chat.id,

                "message_id": contenido.message_id
            }


            bot.reply_to(
                message,

                "📥 <b>AMIGO, ENVÍA UN CONTENIDO</b>\n\n"

                "Para recibir esta foto debes "
                "enviar ahora:\n\n"

                "🖼 Una foto\n"
                "o\n"
                "🎥 Un video\n\n"

                "⚠️ Debe ser contenido diferente "
                "y que no hayas utilizado antes.\n\n"

                "❌ Para cancelar usa "
                "<code>/cancelar</code>"
            )

            return


        # =================================================
        # VIDEO
        # =================================================

        if contenido.video:

            video = contenido.video

            file_id = video.file_id
            file_unique_id = video.file_unique_id


            if ya_recibio_archivo(
                usuario_id,
                file_unique_id
            ):

                bot.reply_to(
                    message,

                    "⚠️ <b>YA GUARDASTE ESTE VIDEO</b>\n\n"

                    "Este video ya fue recibido "
                    "anteriormente."
                )

                return


            contenidos_pendientes[
                usuario_id
            ] = {

                "tipo": "video",

                "file_id": file_id,

                "file_unique_id": file_unique_id,

                "chat_id": contenido.chat.id,

                "message_id": contenido.message_id
            }


            bot.reply_to(
                message,

                "📥 <b>AMIGO, ENVÍA UN CONTENIDO</b>\n\n"

                "Para recibir este video debes "
                "enviar ahora:\n\n"

                "🖼 Una foto\n"
                "o\n"
                "🎥 Un video\n\n"

                "⚠️ Debe ser contenido diferente "
                "y que no hayas utilizado antes.\n\n"

                "❌ Para cancelar usa "
                "<code>/cancelar</code>"
            )

            return


        # =================================================
        # CONTENIDO NO VÁLIDO
        # =================================================

        bot.reply_to(
            message,

            "❌ <b>CONTENIDO NO PERMITIDO</b>\n\n"

            "Solo puedes utilizar "
            "<code>/guardar</code> respondiendo a:\n\n"

            "🖼 Fotos\n"
            "🎥 Videos"
        )


    # =====================================================
    # PROCESAR INTERCAMBIO
    # =====================================================

    def procesar_intercambio(
        message,
        file_unique_id
    ):

        usuario_id = message.from_user.id


        if usuario_id not in contenidos_pendientes:
            return


        pendiente = contenidos_pendientes[
            usuario_id
        ]


        # =================================================
        # VOLVER A VERIFICAR REGISTRO ANTES DE ENTREGAR
        # =================================================

        registrado = usuario_registrado_contactos(usuario_id)

        if registrado is not True:
            contenidos_pendientes.pop(usuario_id, None)

            if registrado is False:
                bot.reply_to(
                    message,
                    "🔒 <b>YA NO PUEDO CONTINUAR</b>\n\n"
                    "Tu Telegram no aparece registrado en la base "
                    "de contactos.\n\n"
                    "Pulsa <b>IR AL PRIVADO</b>, escribe "
                    "<code>/registro</code> y vuelve a iniciar el intercambio.",
                    reply_markup=teclado_ir_privado(bot)
                )
            else:
                bot.reply_to(
                    message,
                    "⚠️ <b>NO PUDE VERIFICAR TU REGISTRO</b>\n\n"
                    "No se entregó ningún contenido. Vuelve a "
                    "intentarlo cuando la API esté disponible."
                )

            return


        # =================================================
        # MISMO ARCHIVO
        # =================================================

        if (
            file_unique_id
            == pendiente["file_unique_id"]
        ):

            bot.reply_to(
                message,

                "⚠️ <b>NO PUEDES USAR "
                "EL MISMO CONTENIDO</b>\n\n"

                "Debes enviar otra foto "
                "o video diferente."
            )

            return


        # =================================================
        # INTERCAMBIO REPETIDO
        # =================================================

        if intercambio_ya_usado(
            usuario_id,
            file_unique_id
        ):

            bot.reply_to(
                message,

                "⚠️ <b>CONTENIDO REPETIDO</b>\n\n"

                "Este archivo ya lo enviaste "
                "anteriormente.\n\n"

                "❌ Ya no puedes utilizarlo "
                "otra vez.\n\n"

                "📥 Envía otra foto "
                "o video diferente."
            )

            return


        # =================================================
        # ENTREGAR
        # =================================================

        try:

            entregar_contenido(
                usuario_id,
                pendiente
            )


            # =============================================
            # REGISTRAR INTERCAMBIO
            # =============================================

            registrar_intercambio(
                usuario_id,
                file_unique_id
            )


            # =============================================
            # REGISTRAR CONTENIDO RECIBIDO
            # =============================================

            registrar_recibido(
                usuario_id,
                pendiente["file_unique_id"]
            )


            # =============================================
            # BORRAR PENDIENTE
            # =============================================

            contenidos_pendientes.pop(
                usuario_id,
                None
            )


            bot.reply_to(
                message,

                "✅ <b>INTERCAMBIO ACEPTADO</b>\n\n"

                "📩 El contenido fue enviado "
                "a tu privado.\n\n"

                "⏳ Tienes <b>10 minutos</b> "
                "para descargarlo."
            )


        # =================================================
        # ERROR TELEGRAM
        # =================================================

        except telebot.apihelper.ApiTelegramException as error:

            error_texto = str(error).lower()


            if (
                "chat not found" in error_texto
                or
                "forbidden" in error_texto
            ):

                bot.reply_to(
                    message,

                    "⚠️ <b>NO PUEDO ENVIARTE "
                    "EL CONTENIDO</b>\n\n"

                    "Primero abre mi chat privado "
                    "y pulsa <b>START</b>.\n\n"

                    "Después vuelve al grupo "
                    "e inténtalo nuevamente."
                )

            else:

                bot.reply_to(
                    message,

                    "❌ <b>ERROR DE TELEGRAM</b>\n\n"

                    f"<code>{error}</code>"
                )


        # =================================================
        # OTROS ERRORES
        # =================================================

        except Exception as error:

            print(
                "ERROR:",
                error
            )

            bot.reply_to(
                message,

                "❌ <b>ERROR AL ENTREGAR "
                "EL CONTENIDO</b>\n\n"

                f"<code>{error}</code>\n\n"

                "Tu intercambio no fue registrado."
            )


    # =====================================================
    # FOTO COMO INTERCAMBIO
    # =====================================================

    @bot.message_handler(
        content_types=["photo"]
    )
    def recibir_foto(message):

        usuario_id = message.from_user.id


        if (
            usuario_id
            not in contenidos_pendientes
        ):
            return


        foto = message.photo[-1]

        file_unique_id = (
            foto.file_unique_id
        )


        procesar_intercambio(
            message,
            file_unique_id
        )


    # =====================================================
    # VIDEO COMO INTERCAMBIO
    # =====================================================

    @bot.message_handler(
        content_types=["video"]
    )
    def recibir_video(message):

        usuario_id = message.from_user.id


        if (
            usuario_id
            not in contenidos_pendientes
        ):
            return


        video = message.video

        file_unique_id = (
            video.file_unique_id
        )


        procesar_intercambio(
            message,
            file_unique_id
        )


    # =====================================================
    # OTROS CONTENIDOS COMO INTERCAMBIO
    # =====================================================

    @bot.message_handler(
        content_types=[
            "document",
            "audio",
            "voice",
            "animation",
            "sticker",
            "video_note"
        ]
    )
    def contenido_no_permitido(message):

        usuario_id = message.from_user.id


        if (
            usuario_id
            not in contenidos_pendientes
        ):
            return


        bot.reply_to(
            message,

            "❌ <b>CONTENIDO NO VÁLIDO</b>\n\n"

            "Para completar el intercambio "
            "solo puedes enviar:\n\n"

            "🖼 Foto\n"
            "🎥 Video\n\n"

            "📥 Tu contenido pendiente "
            "sigue reservado."
        )


    # =====================================================
    # /CANCELAR
    # =====================================================

    @bot.message_handler(
        commands=["cancelar"]
    )
    def cancelar(message):

        usuario_id = message.from_user.id


        if (
            usuario_id
            not in contenidos_pendientes
        ):

            bot.reply_to(
                message,

                "⚠️ <b>NO TIENES "
                "NINGÚN INTERCAMBIO PENDIENTE</b>"
            )

            return


        contenidos_pendientes.pop(
            usuario_id,
            None
        )


        bot.reply_to(
            message,

            "✅ <b>INTERCAMBIO CANCELADO</b>\n\n"

            "Ya puedes elegir otro contenido "
            "respondiendo con:\n\n"

            "<code>/guardar</code>"
        )