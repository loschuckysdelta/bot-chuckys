import io
import time
import base64
import requests
import json
import os
from datetime import datetime
from telebot import types

# ========================================================
# 1. ENDPOINTS DE LAS APIs
# ========================================================

URL_VOUCHERS = "https://chucky-vouchers.vercel.app/api"
URL_ACTIVACIONES = "https://activaciones.vercel.app/api"

X_TOKEN = "4d5a7b9c1e2f3a4b5c6d7e8f9a0b1c2d"

ADMIN_IDS = [8635600472]


# ========================================================
# 2. ALMACENAMIENTO EN MEMORIA
# ========================================================

ARCHIVO_GRUPOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "grupos_autorizados.json")

# Claves usadas en grupos: (chat_id, user_id) -> ultimo uso
# Así el AntiSpam es independiente para cada persona.
# AntiSpam separado para evitar que una persona bloquee a las demás.
# Formato grupos:
# COOLDOWN_GRUPOS[chat_id][user_id] = timestamp
COOLDOWN_GRUPOS = {}

# Chat privado:
# COOLDOWN_PRIVADO[user_id] = timestamp
COOLDOWN_PRIVADO = {}

USOS_USUARIOS_DIARIOS = {}

# Confirmaciones temporales para /resetdb
RESET_DB_CONFIRMACIONES = {}

# Caché de vouchers de ejemplo generados por la API.
# Evita volver a consumir la API cada vez que se usan las flechas.
EJEMPLOS_CACHE = {}

def cargar_grupos():
    if not os.path.exists(ARCHIVO_GRUPOS):
        return {}
    try:
        with open(ARCHIVO_GRUPOS, "r", encoding="utf-8") as archivo:
            datos = json.load(archivo)

        grupos = {}

        for group_id, info in datos.items():
            info = dict(info)

            # Migración automática desde versiones anteriores:
            # antes "usos_hoy" era un contador compartido por el grupo.
            # Ahora cada usuario tiene su propio contador.
            if "usuarios" not in info or not isinstance(info.get("usuarios"), dict):
                info["usuarios"] = {}

            info.pop("usos_hoy", None)
            info.pop("fecha", None)

            grupos[int(group_id)] = info

        return grupos
    except Exception as e:
        print(f"❌ Error cargando grupos_autorizados.json: {e}")
        return {}

def guardar_grupos():
    try:
        with open(ARCHIVO_GRUPOS, "w", encoding="utf-8") as archivo:
            json.dump(GRUPOS_AUTORIZADOS, archivo, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Error guardando grupos_autorizados.json: {e}")

GRUPOS_AUTORIZADOS = cargar_grupos()


def convertir_antispam(valor):
    """
    Convierte el AntiSpam a segundos.

    Formatos aceptados:
      10   -> 10 segundos
      30s  -> 30 segundos
      1m   -> 60 segundos
      2m   -> 120 segundos
    """
    valor = str(valor).strip().lower()

    if valor.endswith("s"):
        cantidad = int(valor[:-1])
        segundos = cantidad
    elif valor.endswith("m"):
        cantidad = int(valor[:-1])
        segundos = cantidad * 60
    else:
        segundos = int(valor)

    if segundos < 0:
        raise ValueError("AntiSpam negativo")

    return segundos


def texto_antispam(segundos):
    segundos = int(segundos)

    if segundos == 0:
        return "0 segundos"

    if segundos % 60 == 0:
        minutos = segundos // 60
        return f"{minutos} minuto" if minutos == 1 else f"{minutos} minutos"

    if segundos >= 60:
        minutos = segundos // 60
        resto = segundos % 60
        txt_min = f"{minutos} minuto" if minutos == 1 else f"{minutos} minutos"
        txt_seg = f"{resto} segundo" if resto == 1 else f"{resto} segundos"
        return f"{txt_min} {txt_seg}"

    return f"{segundos} segundo" if segundos == 1 else f"{segundos} segundos"


# ========================================================
# 3. SERVICIOS
# ========================================================

NOMBRES_SERVICIOS = {
    "yape": "Yape",
    "plin": "Plin",
    "bim": "Bim",
    "sip": "Sip",
    "agora": "Agora",
    "lemon": "Lemon",
    "panda": "Panda",
    "prexpe": "Prexpe",
    "bcp": "BCP",
    "ibk": "Interbank",
    "bbva": "BBVA",
    "scotiabank": "Scotiabank",
    "ripley": "Ripley",
    "falabella": "Falabella",
    "caja": "Caja"
}


# ========================================================
# 4. CONSULTAR DÍAS DEL USUARIO
# ========================================================

def consultar_dias_api(user_id):
    """
    Consulta los días del usuario.

    days > 0:
        consultas ilimitadas

    days == 0:
        plan gratuito de 3 consultas por día
    """

    headers = {
        "X-TOKEN": X_TOKEN
    }

    url = f"{URL_ACTIVACIONES}/user?id={user_id}"

    try:

        response = requests.get(
            url,
            headers=headers,
            timeout=5
        )

        if response.status_code == 200:

            data = response.json()

            # Respuesta esperada:
            #
            # {
            #   "success": true,
            #   "user": {
            #       "telegramId": "...",
            #       "credits": 0,
            #       "days": 10
            #   }
            # }

            if data.get("success") is True and "user" in data:

                user = data["user"]

                dias_restantes = int(
                    user.get("days", 0) or 0
                )

                if dias_restantes > 0:
                    return True, dias_restantes

                return False, 0

        else:

            print(
                f"⚠️ Error consultando usuario: "
                f"{response.status_code} - {response.text}"
            )

    except Exception as e:

        print(
            f"Error consultando días API: {e}"
        )

    return False, 0


# ========================================================
# 5. EVALUAR PERMISO
# ========================================================

def evaluar_permiso(chat_id, user_id):

    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    ahora = time.time()

    # ====================================================
    # A. GRUPO
    # ====================================================

    if chat_id < 0:

        if chat_id not in GRUPOS_AUTORIZADOS:
            # Grupo no autorizado: ignorar silenciosamente.
            return False, None

        datos_grupo = GRUPOS_AUTORIZADOS[chat_id]

        limite_diario = int(
            datos_grupo.get("limite_diario", 3)
        )

        anti_spam = int(
            datos_grupo.get("anti_spam", 5)
        )

        # ------------------------------------------------
        # CONTADOR DIARIO POR PERSONA
        # ------------------------------------------------

        usuarios_grupo = datos_grupo.setdefault(
            "usuarios",
            {}
        )

        clave_usuario = str(user_id)

        registro_usuario = usuarios_grupo.get(
            clave_usuario,
            {
                "fecha": fecha_hoy,
                "usos": 0
            }
        )

        if registro_usuario.get("fecha") != fecha_hoy:
            registro_usuario = {
                "fecha": fecha_hoy,
                "usos": 0
            }

        # ------------------------------------------------
        # ANTISPAM POR PERSONA
        #
        # Cada grupo tiene un diccionario y dentro de él
        # cada Telegram user_id tiene su propio tiempo.
        # ------------------------------------------------

        cooldown_del_grupo = COOLDOWN_GRUPOS.setdefault(
            chat_id,
            {}
        )

        ultimo_uso = cooldown_del_grupo.get(
            user_id,
            0
        )

        tiempo_transcurrido = ahora - ultimo_uso

        if tiempo_transcurrido < anti_spam:

            tiempo_espera = max(
                1,
                int(anti_spam - tiempo_transcurrido)
            )

            return False, (
                "⚠️ <b>AntiSpam personal activado</b>\n\n"
                f"👤 Tu ID: <code>{user_id}</code>\n"
                f"⏱ Tú debes esperar "
                f"<b>{texto_antispam(tiempo_espera)}</b>.\n\n"
                "✅ Las demás personas del grupo "
                "pueden seguir consultando normalmente."
            )

        # ------------------------------------------------
        # LÍMITE DIARIO SOLO DE ESTA PERSONA
        # ------------------------------------------------

        if registro_usuario["usos"] >= limite_diario:

            usuarios_grupo[clave_usuario] = registro_usuario
            guardar_grupos()

            return False, (
                "⚠️ <b>Tu límite diario fue alcanzado</b>\n\n"
                f"👤 Tu ID: <code>{user_id}</code>\n"
                f"📊 Usaste <b>{limite_diario}/"
                f"{limite_diario}</b> consultas.\n\n"
                "✅ Las demás personas del grupo "
                "conservan sus propios límites."
            )

        # ------------------------------------------------
        # CONSUMIR 1 CONSULTA SOLO A ESTA PERSONA
        # ------------------------------------------------

        registro_usuario["usos"] += 1
        usuarios_grupo[clave_usuario] = registro_usuario

        guardar_grupos()

        # Inicia el AntiSpam SOLO para este user_id.
        cooldown_del_grupo[user_id] = ahora

        restantes_usuario = (
            limite_diario - registro_usuario["usos"]
        )

        return True, (
            "👥 <b>Grupo autorizado</b>\n"
            f"👤 Usuario: <code>{user_id}</code>\n"
            f"📊 Tus consultas: "
            f"<b>{registro_usuario['usos']}/"
            f"{limite_diario}</b>\n"
            f"🔎 Te quedan: <b>{restantes_usuario}</b>\n"
            f"⏱ Tu AntiSpam: "
            f"<b>{texto_antispam(anti_spam)}</b>"
        )

    # ====================================================
    # B. CHAT PRIVADO
    # ====================================================

    ultimo_uso = COOLDOWN_PRIVADO.get(
        user_id,
        0
    )

    tiempo_transcurrido = ahora - ultimo_uso

    if tiempo_transcurrido < 5:

        tiempo_espera = max(
            1,
            int(5 - tiempo_transcurrido)
        )

        return False, (
            "⚠️ <b>AntiSpam Activado:</b> "
            f"Espera {tiempo_espera}s antes "
            "de enviar otro comando."
        )

    tiene_dias, cantidad_dias = consultar_dias_api(
        user_id
    )

    if tiene_dias:

        COOLDOWN_PRIVADO[user_id] = ahora

        return True, (
            "🌟 <b>Plan con días activo</b>\n"
            f"📅 Días restantes: <b>{cantidad_dias}</b>\n"
            "♾️ Consultas: <b>Ilimitadas</b>"
        )

    registro = USOS_USUARIOS_DIARIOS.get(
        user_id,
        {
            "fecha": fecha_hoy,
            "usos": 0
        }
    )

    if registro["fecha"] != fecha_hoy:
        registro = {
            "fecha": fecha_hoy,
            "usos": 0
        }

    if registro["usos"] >= 3:

        USOS_USUARIOS_DIARIOS[user_id] = registro

        return False, (
            "⚠️ <b>Plan Gratuito agotado</b>\n\n"
            "Ya utilizaste tus "
            "<b>3 consultas gratuitas de hoy.</b>\n\n"
            "📅 Vuelve mañana para obtener otras "
            "3 consultas o adquiere días para tener "
            "consultas ilimitadas."
        )

    registro["usos"] += 1
    USOS_USUARIOS_DIARIOS[user_id] = registro

    COOLDOWN_PRIVADO[user_id] = ahora

    usos_restantes = 3 - registro["usos"]

    return True, (
        "🎁 <b>Plan Gratuito</b>\n"
        f"🔎 Consulta: <b>{registro['usos']}/3</b>\n"
        f"📊 Te quedan: "
        f"<b>{usos_restantes}</b> consultas hoy"
    )


# ========================================================
# 6. SOLICITAR VOUCHER A LA API
# ========================================================

def solicitar_voucher_api(endpoint, payload):

    url = f"{URL_VOUCHERS}{endpoint}"

    headers = {
        "X-TOKEN": X_TOKEN,
        "Content-Type": "application/json"
    }

    try:

        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=20
        )

        if response.status_code == 200:

            data = response.json()

            if data.get("status") and "base64" in data:

                b64_string = data["base64"]

                if "," in b64_string:
                    b64_string = b64_string.split(",")[1]

                return (
                    base64.b64decode(b64_string),
                    None
                )

            return (
                None,
                "Respuesta inválida de la API de vouchers."
            )

        else:

            print(
                f"⚠️ Error {response.status_code} "
                f"en {endpoint}: {response.text}"
            )

            return (
                None,
                f"Error HTTP {response.status_code}: "
                f"{response.text}"
            )

    except Exception as e:

        return (
            None,
            f"Error de conexión: {str(e)}"
        )


# ========================================================
# 7. REGISTRAR BETA
# ========================================================

def registrar_vaucher(bot):


    # ====================================================
    # /ejemplos - carrusel automático
    #
    # Genera las imágenes DIRECTAMENTE con la API para
    # todos los servicios definidos en NOMBRES_SERVICIOS.
    # No necesitas subir ni configurar imágenes manuales.
    #
    # La primera vez que se abre un servicio consume la API.
    # Después se reutiliza desde EJEMPLOS_CACHE.
    # ====================================================

    def _lista_ejemplos():
        """Devuelve todos los servicios usando la configuración principal."""
        return list(NOMBRES_SERVICIOS.items())

    def _texto_ejemplo(indice):
        servicios = _lista_ejemplos()
        comando, nombre = servicios[indice]
        total = len(servicios)

        return (
            f"🚀 <b>Voucher {nombre} ({indice + 1}/{total})</b>\n\n"
            f"🕹️ <b>Comando:</b>\n"
            f"<code>/{comando} monto|titular|3 dígitos o 9 dígitos|mensaje|destino</code>\n\n"
            f"✅ <b>Ejemplo de uso:</b>\n\n"
            f"<pre>"
            f"/{comando} 150|Pedro Castillo\n"
            f"/{comando} 150|Pedro Castillo|999\n"
            f"/{comando} 150|Pedro Castillo|999999999\n"
            f"/{comando} 150|Pedro Castillo|999|Pago realizado\n"
            f"/{comando} 150|Pedro Castillo|999|Pago realizado|Plin"
            f"</pre>"
        )

    def _botones_ejemplo(indice):
        servicios = _lista_ejemplos()
        total = len(servicios)

        anterior = (indice - 1) % total
        siguiente = (indice + 1) % total

        markup = types.InlineKeyboardMarkup(row_width=3)
        markup.row(
            types.InlineKeyboardButton(
                "⬅️",
                callback_data=f"ejemplo_{anterior}"
            ),
            types.InlineKeyboardButton(
                f"{indice + 1}/{total}",
                callback_data="ejemplo_nada"
            ),
            types.InlineKeyboardButton(
                "➡️",
                callback_data=f"ejemplo_{siguiente}"
            )
        )
        markup.row(
            types.InlineKeyboardButton(
                "❌ Cerrar",
                callback_data="ejemplo_cerrar"
            )
        )

        return markup

    def _generar_imagen_ejemplo(comando, user_id):
        """
        Genera un voucher real de ejemplo mediante la API.
        Si ya fue generado antes, devuelve el contenido en caché.
        """

        if comando in EJEMPLOS_CACHE:
            return EJEMPLOS_CACHE[comando], None

        payload = {
            "id": str(user_id),
            "monto": "150",
            "nombre": "Pedro Castillo",
            "digitos": "999",
            "mensaje": "Pago realizado",
            "destino": "Plin"
        }

        imagen, error = solicitar_voucher_api(
            f"/{comando}",
            payload
        )

        if imagen:
            EJEMPLOS_CACHE[comando] = imagen

        return imagen, error

    def _archivo_imagen_ejemplo(imagen_bytes, comando):
        archivo = io.BytesIO(imagen_bytes)
        archivo.name = f"{comando}_ejemplo.png"
        archivo.seek(0)
        return archivo

    @bot.message_handler(commands=["ejemplos"])
    def mostrar_ejemplos(message):
        servicios = _lista_ejemplos()

        if not servicios:
            bot.reply_to(
                message,
                "⚠️ No hay servicios configurados.",
                parse_mode="HTML"
            )
            return

        indice = 0
        comando, nombre = servicios[indice]

        msg_espera = bot.reply_to(
            message,
            f"⏳ <i>Generando ejemplo de <b>{nombre}</b>...</i>",
            parse_mode="HTML"
        )

        imagen, error = _generar_imagen_ejemplo(
            comando,
            message.from_user.id
        )

        try:
            bot.delete_message(
                message.chat.id,
                msg_espera.message_id
            )
        except Exception:
            pass

        if not imagen:
            bot.reply_to(
                message,
                f"❌ <b>No se pudo generar el ejemplo de {nombre}.</b>\n\n"
                f"<code>{error}</code>",
                parse_mode="HTML"
            )
            return

        foto = _archivo_imagen_ejemplo(
            imagen,
            comando
        )

        bot.send_photo(
            chat_id=message.chat.id,
            photo=foto,
            caption=_texto_ejemplo(indice),
            reply_markup=_botones_ejemplo(indice),
            parse_mode="HTML",
            reply_to_message_id=message.message_id
        )

    @bot.callback_query_handler(
        func=lambda call: call.data and call.data.startswith("ejemplo_")
    )
    def navegar_ejemplos(call):

        # Contador central: no hace nada.
        if call.data == "ejemplo_nada":
            try:
                bot.answer_callback_query(call.id)
            except Exception:
                pass
            return

        # Cerrar carrusel.
        if call.data == "ejemplo_cerrar":
            try:
                bot.answer_callback_query(call.id)
            except Exception:
                pass

            try:
                bot.delete_message(
                    call.message.chat.id,
                    call.message.message_id
                )
            except Exception:
                pass
            return

        try:
            indice = int(call.data.split("_", 1)[1])
        except Exception:
            try:
                bot.answer_callback_query(
                    call.id,
                    "Ejemplo inválido.",
                    show_alert=True
                )
            except Exception:
                pass
            return

        servicios = _lista_ejemplos()

        if indice < 0 or indice >= len(servicios):
            try:
                bot.answer_callback_query(
                    call.id,
                    "Ejemplo inválido.",
                    show_alert=True
                )
            except Exception:
                pass
            return

        comando, nombre = servicios[indice]

        try:
            bot.answer_callback_query(
                call.id,
                f"Generando {nombre}..."
            )
        except Exception:
            pass

        imagen, error = _generar_imagen_ejemplo(
            comando,
            call.from_user.id
        )

        if not imagen:
            bot.send_message(
                call.message.chat.id,
                f"❌ <b>No se pudo generar el ejemplo de {nombre}.</b>\n\n"
                f"<code>{error}</code>",
                parse_mode="HTML"
            )
            return

        foto = _archivo_imagen_ejemplo(
            imagen,
            comando
        )

        media = types.InputMediaPhoto(
            media=foto,
            caption=_texto_ejemplo(indice),
            parse_mode="HTML"
        )

        try:
            bot.edit_message_media(
                media=media,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=_botones_ejemplo(indice)
            )
        except Exception as e:
            # Si Telegram no permite editar por algún motivo,
            # eliminamos el anterior y enviamos uno nuevo.
            print(f"⚠️ No se pudo editar el ejemplo: {e}")

            try:
                bot.delete_message(
                    call.message.chat.id,
                    call.message.message_id
                )
            except Exception:
                pass

            foto.seek(0)

            bot.send_photo(
                chat_id=call.message.chat.id,
                photo=foto,
                caption=_texto_ejemplo(indice),
                reply_markup=_botones_ejemplo(indice),
                parse_mode="HTML"
            )

    # ====================================================
    # /resetdb
    #
    # SOLO ADMIN.
    # Primer paso:
    #   /resetdb
    #
    # Confirmación:
    #   /resetdb confirmar
    #
    # Borra:
    # - grupos_autorizados.json
    # - contadores diarios por persona
    # - AntiSpam de grupos
    # - AntiSpam privado
    # - usos gratuitos diarios en memoria
    # ====================================================

    @bot.message_handler(commands=["resetdb"])
    def resetear_base_datos(message):

        admin_id = message.from_user.id

        if admin_id not in ADMIN_IDS:
            bot.reply_to(
                message,
                "❌ <b>No tienes permiso para usar este comando.</b>",
                parse_mode="HTML"
            )
            return

        partes = message.text.strip().split(maxsplit=1)

        # -----------------------------------------------
        # PASO 1: PEDIR CONFIRMACIÓN
        # -----------------------------------------------

        if len(partes) == 1:

            RESET_DB_CONFIRMACIONES[admin_id] = time.time()

            bot.reply_to(
                message,
                "⚠️ <b>CONFIRMAR BORRADO TOTAL</b>\n\n"
                "Este comando eliminará:\n"
                "• Todos los grupos autorizados\n"
                "• Todos los contadores por persona\n"
                "• Todos los AntiSpam\n"
                "• Todos los usos diarios guardados\n\n"
                "Para confirmar escribe dentro de 60 segundos:\n\n"
                "<code>/resetdb confirmar</code>",
                parse_mode="HTML"
            )
            return

        # -----------------------------------------------
        # PASO 2: VALIDAR CONFIRMACIÓN
        # -----------------------------------------------

        confirmacion = partes[1].strip().lower()

        if confirmacion != "confirmar":
            bot.reply_to(
                message,
                "⚠️ Confirmación inválida.\n\n"
                "Usa:\n"
                "<code>/resetdb confirmar</code>",
                parse_mode="HTML"
            )
            return

        tiempo_confirmacion = RESET_DB_CONFIRMACIONES.get(
            admin_id,
            0
        )

        if not tiempo_confirmacion:
            bot.reply_to(
                message,
                "⚠️ Primero debes usar <code>/resetdb</code>.",
                parse_mode="HTML"
            )
            return

        if time.time() - tiempo_confirmacion > 60:

            RESET_DB_CONFIRMACIONES.pop(admin_id, None)

            bot.reply_to(
                message,
                "⌛ La confirmación expiró.\n\n"
                "Vuelve a usar <code>/resetdb</code>.",
                parse_mode="HTML"
            )
            return

        # -----------------------------------------------
        # BORRAR TODO
        # -----------------------------------------------

        try:
            GRUPOS_AUTORIZADOS.clear()
            COOLDOWN_GRUPOS.clear()
            COOLDOWN_PRIVADO.clear()
            USOS_USUARIOS_DIARIOS.clear()

            # Sobrescribir el JSON con un objeto vacío.
            with open(
                ARCHIVO_GRUPOS,
                "w",
                encoding="utf-8"
            ) as archivo:
                json.dump(
                    {},
                    archivo,
                    indent=4,
                    ensure_ascii=False
                )

            RESET_DB_CONFIRMACIONES.pop(admin_id, None)

            bot.reply_to(
                message,
                "✅ <b>Base de datos reiniciada completamente.</b>\n\n"
                "🗑️ Grupos autorizados: borrados\n"
                "🗑️ Contadores por persona: borrados\n"
                "🗑️ AntiSpam: borrado\n"
                "🗑️ Usos diarios: borrados\n\n"
                "El archivo "
                f"<code>{ARCHIVO_GRUPOS}</code> "
                "quedó vacío.",
                parse_mode="HTML"
            )

        except Exception as e:

            bot.reply_to(
                message,
                "❌ <b>Error al reiniciar la base de datos.</b>\n\n"
                f"<code>{str(e)}</code>",
                parse_mode="HTML"
            )

    # ====================================================
    # /miid
    # Sirve para comprobar que Telegram realmente está
    # entregando un ID distinto para cada persona.
    # ====================================================

    @bot.message_handler(commands=["miid"])
    def ver_mi_id(message):

        sender_chat = getattr(message, "sender_chat", None)

        # Cuando un administrador publica de forma anónima,
        # Telegram no entrega su identidad personal real.
        if sender_chat is not None:
            bot.reply_to(
                message,
                "⚠️ <b>Estás enviando como anónimo o como el grupo.</b>\n\n"
                "Telegram no permite distinguir qué administrador "
                "real envió el mensaje.\n\n"
                "Desactiva <b>Ser anónimo</b> / "
                "<b>Permanecer anónimo</b> y vuelve a probar.\n\n"
                f"📣 sender_chat: <code>{sender_chat.id}</code>",
                parse_mode="HTML"
            )
            return

        bot.reply_to(
            message,
            "✅ <b>Identidad detectada</b>\n\n"
            f"👤 Telegram ID: <code>{message.from_user.id}</code>\n"
            f"👥 Chat ID: <code>{message.chat.id}</code>\n\n"
            "Cada persona normal del grupo debe mostrar "
            "un Telegram ID diferente.",
            parse_mode="HTML"
        )

    # ====================================================
    # /addgrupo
    #
    # EJEMPLOS:
    #
    # /addgrupo -1001234567890 10 30s
    # /addgrupo -1001234567890 10 1m
    # /addgrupo -1001234567890 10 2m
    #
    # -1001234567890 = ID grupo
    # 10 = consultas diarias POR PERSONA
    # 30s = 30 segundos
    # 1m = 1 minuto
    # 2m = 2 minutos
    # ====================================================

    @bot.message_handler(commands=["addgrupo"])
    def agregar_grupo(message):

        if message.from_user.id not in ADMIN_IDS:
            return

        try:

            partes = message.text.split()

            if len(partes) != 4:
                raise ValueError("Formato incorrecto")

            group_id = int(partes[1])
            limite_diario = int(partes[2])
            anti_spam = convertir_antispam(partes[3])

            if group_id >= 0:
                bot.reply_to(
                    message,
                    "❌ El ID debe ser de un grupo.\n\n"
                    "Ejemplo:\n"
                    "<code>/addgrupo -1001234567890 10 1m</code>",
                    parse_mode="HTML"
                )
                return

            if limite_diario <= 0:
                bot.reply_to(
                    message,
                    "❌ El límite diario debe ser mayor a 0.",
                    parse_mode="HTML"
                )
                return

            if anti_spam < 0:
                bot.reply_to(
                    message,
                    "❌ El AntiSpam no puede ser negativo.",
                    parse_mode="HTML"
                )
                return

            # Si el grupo ya existía, conservamos los contadores
            # individuales de sus usuarios.
            usuarios_existentes = {}

            if group_id in GRUPOS_AUTORIZADOS:
                usuarios_existentes = GRUPOS_AUTORIZADOS[group_id].get(
                    "usuarios",
                    {}
                )

            GRUPOS_AUTORIZADOS[group_id] = {
                "limite_diario": limite_diario,
                "anti_spam": anti_spam,
                "usuarios": usuarios_existentes
            }

            guardar_grupos()

            bot.reply_to(
                message,
                "✅ <b>Grupo Autorizado</b>\n\n"
                f"🆔 ID: <code>{group_id}</code>\n"
                f"📊 Límite diario por persona: "
                f"<b>{limite_diario}</b> consultas\n"
                f"⏱ AntiSpam: "
                f"<b>{texto_antispam(anti_spam)}</b>",
                parse_mode="HTML"
            )

        except Exception:

            bot.reply_to(
                message,
                "⚠️ <b>Formato incorrecto</b>\n\n"
                "<code>/addgrupo ID_GRUPO LIMITE ANTISPAM</code>\n\n"
                "✅ Ejemplos:\n"
                "<code>/addgrupo -1001234567890 10 30s</code>\n"
                "<code>/addgrupo -1001234567890 10 1m</code>\n"
                "<code>/addgrupo -1001234567890 10 2m</code>\n\n"
                "📊 10 = consultas por día para cada persona\n"
                "⏱ 30s = 30 segundos\n"
                "⏱ 1m = 1 minuto\n"
                "⏱ 2m = 2 minutos\n"
                "ℹ️ Si pones solo 10, serán 10 segundos.",
                parse_mode="HTML"
            )

    # ====================================================
    # /delgrupo
    # ====================================================

    @bot.message_handler(commands=["delgrupo"])
    def eliminar_grupo(message):

        if message.from_user.id not in ADMIN_IDS:
            return

        try:

            partes = message.text.split()

            group_id = int(partes[1])

            if group_id in GRUPOS_AUTORIZADOS:

                del GRUPOS_AUTORIZADOS[group_id]

                guardar_grupos()

                # Eliminar todos los AntiSpam individuales
                # pertenecientes únicamente a este grupo.
                COOLDOWN_GRUPOS.pop(group_id, None)

                bot.reply_to(
                    message,
                    f"🗑️ Grupo "
                    f"<code>{group_id}</code> "
                    "eliminado con éxito.",
                    parse_mode="HTML"
                )

            else:

                bot.reply_to(
                    message,
                    "⚠️ El grupo no está registrado.",
                    parse_mode="HTML"
                )

        except Exception:

            bot.reply_to(
                message,
                "⚠️ Formato:\n"
                "<code>/delgrupo [ID_GRUPO]</code>",
                parse_mode="HTML"
            )

    # ====================================================
    # COMANDOS DISPONIBLES
    # ====================================================

    TODOS_LOS_COMANDOS = list(
        NOMBRES_SERVICIOS.keys()
    )

    # ====================================================
    # GESTOR GENERAL DE VOUCHERS
    # ====================================================

    @bot.message_handler(
        commands=TODOS_LOS_COMANDOS
    )
    def gestor_vouchers_general(message):

        chat_id = message.chat.id

        # IMPORTANTE:
        # Si el mensaje fue enviado como administrador anónimo
        # o "como el grupo", Telegram NO revela qué persona real
        # lo mandó. En ese caso no es posible aplicar un AntiSpam
        # individual correctamente.
        sender_chat = getattr(message, "sender_chat", None)

        if chat_id < 0 and sender_chat is not None:
            bot.reply_to(
                message,
                "⚠️ <b>No puedo identificarte individualmente.</b>\n\n"
                "Estás enviando el comando como "
                "<b>administrador anónimo</b> o como el grupo.\n\n"
                "Para que el límite y el AntiSpam sean por persona, "
                "envía el comando con tu perfil personal "
                "(desactiva <b>Ser anónimo</b>).",
                parse_mode="HTML"
            )
            return

        user_id = message.from_user.id

        comando = (
            message.text
            .split()[0]
            .replace("/", "")
            .lower()
        )

        endpoint = f"/{comando}"

        nombre_servicio = NOMBRES_SERVICIOS.get(
            comando,
            comando.capitalize()
        )

        texto_completo = message.text.strip()

        partes_comando = texto_completo.split(
            maxsplit=1
        )

        # =================================================
        # FORMATO INCORRECTO
        # =================================================

        if len(partes_comando) == 1:

            mensaje_ayuda = (
                f"⚠️ <b>Formato incorrecto.</b>\n\n"
                f"Uso:\n"
                f"<code>/{comando} "
                "monto|titular|3 dígitos|mensaje|destino"
                "</code>\n\n"
                "✅ <b>Ejemplo de uso:</b>\n\n"
                "<pre>"
                f"/{comando} 150|Pedro Castillo\n"
                f"/{comando} 150|Pedro Castillo|999\n"
                f"/{comando} 150|Pedro Castillo|999|Pago realizado\n"
                f"/{comando} 150|Pedro Castillo|999|Pago realizado|Plin"
                "</pre>"
            )

            bot.reply_to(
                message,
                mensaje_ayuda,
                parse_mode="HTML"
            )

            return

        # =================================================
        # EVALUAR PERMISO
        # =================================================

        permitido, info_plan = evaluar_permiso(
            chat_id,
            user_id
        )

        if not permitido:

            # Si el grupo no está autorizado, info_plan será None
            # y el bot no mostrará ningún mensaje.
            if info_plan:
                bot.reply_to(
                    message,
                    info_plan,
                    parse_mode="HTML"
                )

            return

        # =================================================
        # LEER PARÁMETROS
        # =================================================

        args_raw = partes_comando[1]

        parametros = [
            arg.strip()
            for arg in args_raw.split("|")
        ]

        monto = (
            parametros[0]
            if len(parametros) > 0
            else "0"
        )

        titular = (
            parametros[1]
            if len(parametros) > 1
            else ""
        )

        payload_voucher = {
            "id": str(user_id),
            "monto": monto,
            "nombre": titular
        }

        if (
            len(parametros) > 2
            and parametros[2]
        ):
            payload_voucher["digitos"] = parametros[2]

        if (
            len(parametros) > 3
            and parametros[3]
        ):
            payload_voucher["mensaje"] = parametros[3]

        if (
            len(parametros) > 4
            and parametros[4]
        ):
            payload_voucher["destino"] = parametros[4]

        # =================================================
        # MENSAJE GENERANDO
        # =================================================

        msg_espera = bot.reply_to(
            message,
            f"⏳ <i>Generando comprobante de "
            f"<b>{nombre_servicio}</b>...</i>",
            parse_mode="HTML"
        )

        # =================================================
        # SOLICITAR VOUCHER
        # =================================================

        img_bytes, error = solicitar_voucher_api(
            endpoint,
            payload_voucher
        )

        # =================================================
        # BORRAR MENSAJE DE ESPERA
        # =================================================

        try:

            bot.delete_message(
                chat_id,
                msg_espera.message_id
            )

        except Exception:
            pass

        # =================================================
        # VOUCHER GENERADO
        # =================================================

        if img_bytes:

            photo_file = io.BytesIO(
                img_bytes
            )

            photo_file.name = (
                "Screenshot_250826.png"
            )

            caption_respuesta = (
                f"✅ <b>Voucher "
                f"{nombre_servicio} generado</b>\n\n"

                f"💰 <b>Monto:</b> S/ {monto}\n"

                f"👤 <b>Titular:</b> "
                f"{titular}\n\n"

                "👤 <b>Estado del usuario:</b>\n"
                f"{info_plan}"
            )

            bot.send_document(
                chat_id,
                document=photo_file,
                caption=caption_respuesta,
                reply_to_message_id=message.message_id,
                parse_mode="HTML"
            )

        # =================================================
        # ERROR
        # =================================================

        else:

            bot.reply_to(
                message,
                f"❌ <b>Error:</b> {error}",
                parse_mode="HTML"
            )