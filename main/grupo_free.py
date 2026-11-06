import hashlib
import re
import sqlite3
import threading
import time
import unicodedata
from pathlib import Path

import requests
import telebot

ID_GRUPO = -1004497451670
WEB_KEYS = "https://loschuckys.com/key"
API_CANJEAR = "https://bot-apis-zkmk.vercel.app/api/keys/canjear"
API_CONTACTOS = "https://bot-apis-zkmk.vercel.app/api/contactos"
DB = Path(__file__).with_name("grupo_free.db")
TIMEOUT = (5, 25)

_lock_guard = threading.Lock()
_locks = {}


def _lock(uid):
    with _lock_guard:
        return _locks.setdefault(uid, threading.Lock())


def _db():
    db = sqlite3.connect(DB, timeout=10)
    db.execute("""CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY,
        contacto INTEGER NOT NULL DEFAULT 0,
        pendiente INTEGER NOT NULL DEFAULT 0,
        ultima_key TEXT NOT NULL DEFAULT '',
        ultimo_estado TEXT NOT NULL DEFAULT ''
    )""")
    return db


def _estado(uid):
    with _db() as db:
        fila = db.execute("SELECT contacto, pendiente, ultima_key, ultimo_estado FROM usuarios WHERE id=?", (uid,)).fetchone()
    return fila or (0, 0, "", "")


def _guardar(uid, **campos):
    permitidos = {"contacto", "pendiente", "ultima_key", "ultimo_estado"}
    if not set(campos).issubset(permitidos):
        raise ValueError("Campo de estado desconocido")
    with _db() as db:
        db.execute("INSERT OR IGNORE INTO usuarios(id) VALUES(?)", (uid,))
        for nombre, valor in campos.items():
            db.execute(f"UPDATE usuarios SET {nombre}=? WHERE id=?", (valor, uid))


def contacto_registrado(uid):
    if _estado(uid)[0]:
        return True
    # Si tu proyecto ya guardaba contactos, también reconoce esos registros.
    try:
        from main.guardar import usuario_registrado_contactos
        if usuario_registrado_contactos(uid) is True:
            _guardar(uid, contacto=1)
            return True
    except (ImportError, AttributeError):
        pass
    except Exception as exc:
        print("⚠️ Consultando contacto anterior:", type(exc).__name__)
    return False


def _normalizar(valor):
    texto = unicodedata.normalize("NFKD", str(valor).casefold())
    return "".join(ch for ch in texto if not unicodedata.combining(ch)).strip()


def _respuesta_canje(respuesta):
    """Devuelve True/False/None. None = sin confirmación, no repetir POST."""
    codigo = respuesta.status_code
    print("📡 API canje - HTTP", codigo)
    if codigo == 204:
        return True  # 204 confirma éxito sin contenido.
    if codigo in (408, 429) or codigo >= 500:
        return None
    if not (200 <= codigo < 300):
        return False

    try:
        cuerpo = respuesta.json()
    except ValueError:
        cuerpo = (respuesta.text or "").strip()

    # Solo mostrar nombres de campos, nunca teléfono ni key del usuario.
    if isinstance(cuerpo, dict):
        print("📋 Campos API:", list(cuerpo.keys()))

    def flag(valor):
        if valor is True or valor == 1 or _normalizar(valor) in ("true", "si", "yes"):
            return True
        if valor is False or valor == 0 or _normalizar(valor) in ("false", "no"):
            return False
        return None

    objetos = []
    textos = []

    def recorrer(obj, profundidad=0):
        if profundidad > 3:
            return
        if isinstance(obj, dict):
            objetos.append(obj)
            for campo in ("data", "resultado", "result", "respuesta"):
                if isinstance(obj.get(campo), (dict, list)):
                    recorrer(obj[campo], profundidad + 1)
            for campo in ("message", "mensaje", "detail", "detalle", "status", "estado"):
                if isinstance(obj.get(campo), str):
                    textos.append(_normalizar(obj[campo]))
        elif isinstance(obj, list):
            for x in obj[:5]:
                recorrer(x, profundidad + 1)
        elif isinstance(obj, str):
            textos.append(_normalizar(obj))

    if isinstance(cuerpo, bool):
        return cuerpo
    recorrer(cuerpo)

    # Una señal clara de error prevalece sobre cualquier mensaje positivo.
    for item in objetos:
        err = item.get("error")
        if err not in (None, False, "", 0, [], {}):
            return False
        for campo in ("success", "ok", "canjeada", "canjeado", "redeemed", "exito"):
            if campo in item and flag(item[campo]) is False:
                return False

    negativos = (
        "invalida", "invalido", "incorrecta", "incorrecto", "vencida", "vencido",
        "expirada", "expirado", "ya utilizada", "ya utilizado", "ya canjeada",
        "ya canjeado", "no encontrada", "no encontrado", "rechazad",
        "sin saldo", "no se pudo", "error", "failed", "invalid", "expired", "used",
    )
    if any(fragmento in t for t in textos for fragmento in negativos):
        return False

    for item in objetos:
        for campo in ("success", "ok", "canjeada", "canjeado", "redeemed", "exito"):
            if campo in item and flag(item[campo]) is True:
                return True

    positivos = (
        "canjeada", "canjeado", "canje exitoso", "canje realizado", "canje completado",
        "canje correcto", "se canjeo", "se ha canjeado", "redeemed",
        "acceso concedido", "operacion exitosa", "operacion completada",
    )
    if any(fragmento in t for t in textos for fragmento in positivos):
        return True
    if any(t in ("ok", "success", "exitoso", "completado", "true") for t in textos):
        return True

    print("⚠️ La API no devolvió una confirmación conocida. Revisa el formato JSON del servidor.")
    return None


def _miembro(bot, uid):
    try:
        return bot.get_chat_member(ID_GRUPO, uid).status in ("member", "administrator", "creator")
    except Exception:
        return False


def _puede_invitar(bot):
    try:
        admin = bot.get_chat_member(ID_GRUPO, bot.get_me().id)
        return admin.status == "creator" or (admin.status == "administrator" and admin.can_invite_users is True)
    except Exception as exc:
        print("❌ Permiso de invitación:", type(exc).__name__)
        return False


def _entregar_enlace(bot, uid):
    try:
        if _miembro(bot, uid):
            _guardar(uid, pendiente=0, ultimo_estado="en_grupo")
            bot.send_message(uid, "✅ Ya estás en el GRUPO FREE.")
            return
        invitacion = bot.create_chat_invite_link(
            ID_GRUPO, member_limit=1, expire_date=int(time.time()) + 86400,
            name=f"FREE-{uid}",
        )
        bot.send_message(uid, "✅ KEY CANJEADA CORRECTAMENTE\n\n"
                         "👥 Entra al GRUPO FREE:\n" + invitacion.invite_link +
                         "\n\n⏳ Enlace válido por 24 horas, para una persona.")
        _guardar(uid, pendiente=0, ultimo_estado="entregado")
    except Exception as exc:
        print("❌ Enlace:", type(exc).__name__, exc)
        try:
            bot.send_message(uid, "⚠️ Tu key fue aceptada, pero falló el enlace. "
                                  "Vuelve a tocar CANJEAR MI KEY para recuperarlo sin otra key.")
        except Exception:
            pass


def mostrar_menu_keys(bot, uid):
    if not contacto_registrado(uid):
        bot.send_message(uid, "📱 Primero toca GRUPO FREE y comparte tu contacto.")
        return
    menu = telebot.types.InlineKeyboardMarkup(row_width=1)
    menu.add(telebot.types.InlineKeyboardButton("🔑 GENERAR MI KEY", url=WEB_KEYS))
    menu.add(telebot.types.InlineKeyboardButton("✅ CANJEAR MI KEY", callback_data="free_canjear_key"))
    bot.send_message(uid, "👥 GRUPO FREE\n\n1️⃣ Genera tu key en la página.\n"
                          "2️⃣ Toca CANJEAR MI KEY.\n3️⃣ Escribe los 6 números.\n"
                          "4️⃣ Recibe el enlace del grupo.", reply_markup=menu)


def verificar_key(bot, message, uid):
    if message.chat.type != "private" or message.from_user.id != uid:
        return
    key = (message.text or "").strip()
    if not re.fullmatch(r"[0-9]{6}", key):
        bot.send_message(uid, "❌ Debes enviar exactamente 6 números. Toca CANJEAR MI KEY otra vez.")
        return
    bloqueo = _lock(uid)
    if not bloqueo.acquire(blocking=False):
        bot.send_message(uid, "⏳ Ya estoy verificando una solicitud. No la repitas.")
        return
    try:
        if not contacto_registrado(uid):
            bot.send_message(uid, "📱 Primero registra tu contacto en GRUPO FREE.")
            return
        if _estado(uid)[1]:
            _entregar_enlace(bot, uid)
            return
        if _miembro(bot, uid):
            bot.send_message(uid, "✅ Ya estás dentro del grupo.")
            return
        if not _puede_invitar(bot):
            bot.send_message(uid, "⚠️ El bot no puede generar invitaciones. Tu key no fue consumida por este intento.")
            return

        huella = hashlib.sha256(f"{uid}:{key}".encode()).hexdigest()
        _, _, anterior, estado = _estado(uid)
        if anterior == huella and estado == "sin_confirmar":
            bot.send_message(uid, "⚠️ Ya se envió esta key, pero la API no confirmó el resultado. "
                                  "No la reenviaré para evitar consumirla dos veces. "
                                  "El administrador debe comprobar su estado en el panel.")
            return

        _guardar(uid, ultima_key=huella, ultimo_estado="enviado")
        bot.send_message(uid, "⏳ Verificando tu key...")
        try:
            respuesta = requests.post(API_CANJEAR,
                                     json={"key": key, "usuarioId": str(uid)},
                                     headers={"Accept": "application/json"}, timeout=TIMEOUT)
            resultado = _respuesta_canje(respuesta)
        except requests.exceptions.RequestException as exc:
            print("❌ La API no respondió:", type(exc).__name__)
            resultado = None

        if resultado is True:
            _guardar(uid, pendiente=1, ultimo_estado="aceptado")
            _entregar_enlace(bot, uid)
        elif resultado is False:
            _guardar(uid, ultimo_estado="rechazado")
            bot.send_message(uid, "❌ La API rechazó la key. Revisa si está vencida, usada o incorrecta.")
        else:
            _guardar(uid, ultimo_estado="sin_confirmar")
            bot.send_message(uid, "⚠️ No se pudo confirmar el canje desde la API. "
                                  "No vuelvas a enviar esta key; el administrador debe revisar el servidor.")
    finally:
        bloqueo.release()


def _solicitar_key(bot, uid):
    if not contacto_registrado(uid):
        bot.send_message(uid, "📱 Primero comparte tu contacto en GRUPO FREE.")
        return
    if _estado(uid)[1]:
        with _lock(uid):
            _entregar_enlace(bot, uid)
        return
    if _miembro(bot, uid):
        bot.send_message(uid, "✅ Ya estás en el GRUPO FREE.")
        return
    bot.clear_step_handler_by_chat_id(uid)
    msg = bot.send_message(uid, "🔑 CANJEAR KEY\n\nEscribe tu código de 6 dígitos:")
    bot.register_next_step_handler(msg, lambda m: verificar_key(bot, m, uid))


def registrar_canje_free(bot):
    # Registrar solamente una vez al iniciar el programa.
    @bot.callback_query_handler(func=lambda call: call.data == "free_canjear_key")
    def on_canjear(call):
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass
        if call.message and call.message.chat.type == "private":
            _solicitar_key(bot, call.from_user.id)


def _solicitar_contacto(bot, uid):
    teclado = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    teclado.add(telebot.types.KeyboardButton("📱 Compartir mi número", request_contact=True))
    bot.clear_step_handler_by_chat_id(uid)
    msg = bot.send_message(uid, "👥 GRUPO FREE\n\nPara registrarte, puedes compartir "
                                "tu número de Telegram. Se enviará a la API de contactos "
                                "para gestionar tu acceso.", reply_markup=teclado)
    bot.register_next_step_handler(msg, lambda m: _registrar_contacto(bot, m, uid))


def _registrar_contacto(bot, message, uid):
    if message.chat.type != "private" or message.from_user.id != uid:
        return
    contacto = message.contact
    if not contacto or contacto.user_id != uid:
        bot.send_message(uid, "⚠️ Comparte tu propio número con el botón de Telegram.")
        _solicitar_contacto(bot, uid)
        return
    usuario = message.from_user
    datos = {"telegramId": uid, "username": usuario.username or "",
             "nombre": " ".join(x for x in [usuario.first_name, usuario.last_name] if x),
             "telefono": (contacto.phone_number or "").replace(" ", "").replace("-", "").lstrip("+")}
    bot.send_message(uid, "⏳ Registrando contacto...", reply_markup=telebot.types.ReplyKeyboardRemove())
    try:
        respuesta = requests.post(API_CONTACTOS, json=datos, timeout=TIMEOUT)
        aprobado = respuesta.ok
        try:
            r = respuesta.json()
            if isinstance(r, dict) and (r.get("success") is False or r.get("ok") is False or r.get("error")):
                aprobado = False
        except ValueError:
            pass
    except requests.exceptions.RequestException as exc:
        print("❌ API contactos:", type(exc).__name__)
        bot.send_message(uid, "⚠️ El servidor no confirmó tu registro. Reintenta desde GRUPO FREE.")
        return
    if not aprobado:
        bot.send_message(uid, "❌ No se pudo registrar el contacto. Intenta de nuevo.")
        return
    _guardar(uid, contacto=1)
    bot.send_message(uid, "✅ Contacto registrado correctamente.")
    mostrar_menu_keys(bot, uid)


def ejecutar_grupo_free(bot, call):
    # Lo llama tu callback de GRUPO FREE, que ya existe en main.py.
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    if not call.message or call.message.chat.type != "private":
        return
    uid = call.from_user.id
    if _miembro(bot, uid):
        bot.send_message(uid, "✅ Ya eres miembro del GRUPO FREE.")
    elif _estado(uid)[1]:
        with _lock(uid):
            _entregar_enlace(bot, uid)
    elif contacto_registrado(uid):
        mostrar_menu_keys(bot, uid)
    else:
        _solicitar_contacto(bot, uid)
