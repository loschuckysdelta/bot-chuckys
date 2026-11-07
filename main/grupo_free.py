import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlencode

import requests
import telebot

ID_GRUPO = -1004350121410
WEB_VERIFICACION = "https://loschuckys.com/key.html"
API_VERIFICAR = "https://bot-apis-zkmk.vercel.app/api/verificar"
API_USUARIOS = "https://bot-apis-zkmk.vercel.app/api/users"
API_CONTACTOS = "https://bot-apis-zkmk.vercel.app/api/contactos"
DB = Path(__file__).with_name("grupo_free.db")
TIMEOUT = (4, 8)
INTERVALO = 5  # segundos entre rondas de consulta
ESPERA_MAXIMA = 10 * 60  # el bot escucha 10 minutos; la verificación en la API puede durar 24 h
MAX_PENDIENTES_RONDA = 100

_monitor_guard = threading.Lock()
_monitor_iniciado = False


@contextmanager
def _db():
    db = sqlite3.connect(DB, timeout=15)
    try:
        db.execute("PRAGMA busy_timeout = 15000")
        # Se conserva la tabla antigua para que los contactos no se pierdan.
        db.execute("""CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY,
            contacto INTEGER NOT NULL DEFAULT 0,
            pendiente INTEGER NOT NULL DEFAULT 0,
            ultima_key TEXT NOT NULL DEFAULT '',
            ultimo_estado TEXT NOT NULL DEFAULT ''
        )""")
        # NUEVA tabla independiente: los campos de keys antiguos no se usan.
        db.execute("""CREATE TABLE IF NOT EXISTS verificacion_free (
            id INTEGER PRIMARY KEY,
            estado TEXT NOT NULL DEFAULT 'pendiente',
            iniciado REAL NOT NULL DEFAULT 0,
            actualizado REAL NOT NULL DEFAULT 0,
            ultimo_enlace TEXT NOT NULL DEFAULT '',
            enlace_expira REAL NOT NULL DEFAULT 0
        )""")
        with db:
            yield db
    finally:
        db.close()

def _guardar_contacto(uid):
    with _db() as db:
        db.execute("INSERT OR IGNORE INTO usuarios(id) VALUES(?)", (uid,))
        db.execute("UPDATE usuarios SET contacto=1 WHERE id=?", (uid,))


def contacto_registrado(uid):
    with _db() as db:
        fila = db.execute("SELECT contacto FROM usuarios WHERE id=?", (uid,)).fetchone()
    if fila and fila[0]:
        return True
    try:
        from main.guardar import usuario_registrado_contactos
        if usuario_registrado_contactos(uid) is True:
            _guardar_contacto(uid)
            return True
    except (ImportError, AttributeError):
        pass
    except Exception as exc:
        print("⚠️ Registro de contacto anterior:", type(exc).__name__)
    return False


def _miembro(bot, uid):
    try:
        return bot.get_chat_member(ID_GRUPO, uid).status in ("member", "administrator", "creator")
    except Exception:
        return False


def _puede_invitar(bot):
    try:
        admin = bot.get_chat_member(ID_GRUPO, bot.get_me().id)
        return admin.status == "creator" or (
            admin.status == "administrator" and admin.can_invite_users is True
        )
    except Exception as exc:
        print("❌ Permisos del bot:", type(exc).__name__)
        return False


def _sincronizar_usuario(user):
    """La API /api/verificar requiere que el ID exista en /api/users."""
    if not user or not getattr(user, "id", None):
        return False
    nombre = " ".join(x for x in [user.first_name, user.last_name] if x).strip()
    payload = {
        "telegramId": user.id,
        "nombre": nombre or "Usuario Telegram",
        "username": user.username or "",
    }
    try:
        r = requests.post(API_USUARIOS, json=payload, timeout=TIMEOUT)
        if not r.ok:
            print("❌ API usuarios HTTP", r.status_code)
            return False
        data = r.json()
        return data.get("success") is True and not data.get("usuario", {}).get("botBloqueado", False)
    except (requests.RequestException, ValueError, AttributeError) as exc:
        print("❌ API usuarios:", type(exc).__name__)
        return False


def _preparar_espera(uid):
    ahora = time.time()
    with _db() as db:
        row = db.execute(
            "SELECT estado, iniciado FROM verificacion_free WHERE id=?", (uid,)
        ).fetchone()
        # Si ya está esperando, no reiniciar su tiempo con cada clic.
        if row and row[0] in ("pendiente", "procesando") and ahora - row[1] < ESPERA_MAXIMA:
            return
        db.execute("""INSERT INTO verificacion_free(id, estado, iniciado, actualizado)
                      VALUES(?, 'pendiente', ?, ?)
                      ON CONFLICT(id) DO UPDATE SET
                         estado='pendiente', iniciado=excluded.iniciado,
                         actualizado=excluded.actualizado""", (uid, ahora, ahora))


def _estado_web(uid):
    try:
        r = requests.get(
            API_VERIFICAR,
            params={"telegramId": str(uid)},
            headers={"Accept": "application/json"},
            timeout=TIMEOUT,
        )
        if not r.ok:
            print(f"⚠️ Verificar {uid}: HTTP {r.status_code}")
            return False
        data = r.json()
        if (not isinstance(data, dict)
                or data.get("success") is not True
                or data.get("verificado") is not True
                or str(data.get("telegramId", "")) != str(uid)):
            return False
        # Respetar el vencimiento si la API lo proporciona.
        if data.get("expiraEn"):
            from datetime import datetime, timezone
            try:
                fin = datetime.fromisoformat(str(data["expiraEn"]).replace("Z", "+00:00"))
                if fin.tzinfo is None:
                    fin = fin.replace(tzinfo=timezone.utc)
                if fin <= datetime.now(timezone.utc):
                    return False
            except (ValueError, TypeError):
                return False
        return True
    except (requests.RequestException, ValueError) as exc:
        print("⚠️ Consultando verificación:", type(exc).__name__)
        return False


def _reclamar(uid):
    """Evita entregar dos invitaciones si se ejecutan varias rondas a la vez."""
    with _db() as db:
        cur = db.execute(
            "UPDATE verificacion_free SET estado='procesando', actualizado=? "
            "WHERE id=? AND estado='pendiente'", (time.time(), uid)
        )
        return cur.rowcount == 1


def _finalizar(uid, estado, enlace=None, vence=None):
    with _db() as db:
        if enlace is None:
            db.execute("UPDATE verificacion_free SET estado=?, actualizado=? WHERE id=?",
                       (estado, time.time(), uid))
        else:
            db.execute("""UPDATE verificacion_free SET estado=?, actualizado=?,
                          ultimo_enlace=?, enlace_expira=? WHERE id=?""",
                       (estado, time.time(), enlace, vence, uid))


def _enlace_anterior(uid):
    with _db() as db:
        row = db.execute("SELECT ultimo_enlace, enlace_expira, actualizado "
                         "FROM verificacion_free WHERE id=?", (uid,)).fetchone()
    # Reutilizar un enlace reciente; evita crear varios si pulsa GRUPO FREE repetidamente.
    if row and row[0] and row[1] > time.time() + 60 and time.time() - row[2] < 120:
        return row[0], row[1]
    return None


def _entregar_enlace(bot, uid):
    try:
        if _miembro(bot, uid):
            bot.send_message(uid, "✅ Ya estás en el GRUPO FREE.")
            _finalizar(uid, "en_grupo")
            return
        if not contacto_registrado(uid):
            _finalizar(uid, "sin_contacto")
            return
        if not _puede_invitar(bot):
            bot.send_message(uid, "⚠️ La verificación fue registrada, pero el bot no tiene permiso para invitar.")
            _finalizar(uid, "error")
            return
        antiguo = _enlace_anterior(uid)
        if antiguo:
            enlace, vence = antiguo
        else:
            vence = int(time.time()) + 86400
            invitacion = bot.create_chat_invite_link(
                ID_GRUPO,
                member_limit=1,
                expire_date=vence,
                name=f"FREE-VERIFICADO-{uid}"[:32],
            )
            enlace = invitacion.invite_link
        bot.send_message(
            uid,
            "✅ VERIFICACIÓN CONFIRMADA\n\n"
            "👥 Este es tu enlace personal para el GRUPO FREE:\n"
            f"{enlace}\n\n"
            "⏳ Válido por 24 horas y para un solo ingreso.",
            disable_web_page_preview=True,
        )
        _finalizar(uid, "entregado", enlace, vence)
    except Exception as exc:
        print("❌ No se pudo entregar enlace:", type(exc).__name__, exc)
        _finalizar(uid, "error")
        try:
            bot.send_message(uid, "⚠️ Verificación registrada, pero no pude enviar la invitación. Vuelve a tocar GRUPO FREE.")
        except Exception:
            pass


def _revisar_pendiente(bot, uid, iniciado):
    if time.time() - iniciado >= ESPERA_MAXIMA:
        if _reclamar(uid):
            _finalizar(uid, "expirado")
            try:
                bot.send_message(uid, "⌛ Se terminó el tiempo de espera. Toca GRUPO FREE para intentarlo de nuevo.")
            except Exception:
                pass
        return
    if not _estado_web(uid):
        return
    if _reclamar(uid):
        _entregar_enlace(bot, uid)


def _monitor(bot):
    print("✅ Monitor de verificaciones GRUPO FREE activo")
    with ThreadPoolExecutor(max_workers=8, thread_name_prefix="free-verif") as pool:
        while True:
            try:
                with _db() as db:
                    # Recuperar procesos interrumpidos tras un reinicio del VPS.
                    db.execute("UPDATE verificacion_free SET estado='pendiente' "
                               "WHERE estado='procesando' AND actualizado < ?",
                               (time.time() - 60,))
                    pendientes = db.execute(
                        "SELECT id, iniciado FROM verificacion_free "
                        "WHERE estado='pendiente' ORDER BY iniciado LIMIT ?",
                        (MAX_PENDIENTES_RONDA,),
                    ).fetchall()
                tareas = [pool.submit(_revisar_pendiente, bot, uid, inicio)
                          for uid, inicio in pendientes]
                for tarea in tareas:
                    try:
                        tarea.result()
                    except Exception as exc:
                        print("⚠️ Monitor:", type(exc).__name__, exc)
            except Exception as exc:
                print("❌ Monitor DB:", type(exc).__name__, exc)
            time.sleep(INTERVALO)


def registrar_verificacion_free(bot):
    """Llamar una sola vez desde main.py, antes del polling del bot."""
    global _monitor_iniciado
    with _monitor_guard:
        if not _monitor_iniciado:
            threading.Thread(target=_monitor, args=(bot,), daemon=True,
                             name="grupo-free-verificacion").start()
            _monitor_iniciado = True

    # Compatibilidad con botones viejos de CANJEAR KEY de mensajes históricos.
    if not getattr(bot, "_free_legacy_handler", False):
        @bot.callback_query_handler(func=lambda call: call.data == "free_canjear_key")
        def _callback_legacy(call):
            try:
                bot.answer_callback_query(call.id)
            except Exception:
                pass
            if call.message and call.message.chat.type == "private":
                mostrar_menu_verificacion(bot, call.from_user)
        bot._free_legacy_handler = True


def mostrar_menu_verificacion(bot, usuario):
    uid = usuario.id
    if not contacto_registrado(uid):
        bot.send_message(uid, "📱 Primero comparte tu contacto desde GRUPO FREE.")
        return
    if _miembro(bot, uid):
        bot.send_message(uid, "✅ Ya eres miembro del GRUPO FREE.")
        return
    if not _puede_invitar(bot):
        bot.send_message(uid, "⚠️ El bot necesita permisos de administrador para crear invitaciones.")
        return
    if not _sincronizar_usuario(usuario):
        bot.send_message(uid, "⚠️ No pude registrar tu usuario en la API. Intenta nuevamente más tarde.")
        return

    registrar_verificacion_free(bot)
    _preparar_espera(uid)
    url = WEB_VERIFICACION + ("&" if "?" in WEB_VERIFICACION else "?") + urlencode({"id": str(uid)})
    menu = telebot.types.InlineKeyboardMarkup(row_width=1)
    menu.add(telebot.types.InlineKeyboardButton("✅ ABRIR VERIFICACIÓN", url=url))
    bot.send_message(
        uid,
        "👥 GRUPO FREE\n\n"
        "1️⃣ Pulsa ABRIR VERIFICACIÓN.\n"
        "2️⃣ En la página, toca VERIFICAR MI CUENTA.\n"
        "3️⃣ Cuando la API confirme tu estado, recibirás aquí automáticamente el enlace del grupo.\n\n"
        "⏳ Este aviso queda a la espera hasta 10 minutos.",
        reply_markup=menu,
    )


def mostrar_menu_keys(bot, uid):
    """Alias de compatibilidad si main.py todavía llama esta función."""
    try:
        user = bot.get_chat(uid)
        mostrar_menu_verificacion(bot, user)
    except Exception as exc:
        print("⚠️ Menú desde alias:", type(exc).__name__)
        bot.send_message(uid, "Toca GRUPO FREE nuevamente para abrir la verificación.")


def registrar_canje_free(bot):
    """Nombre antiguo conservado para que main.py no falle al iniciar."""
    registrar_verificacion_free(bot)


def _solicitar_contacto(bot, usuario):
    uid = usuario.id
    teclado = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    teclado.add(telebot.types.KeyboardButton("📱 Compartir mi número", request_contact=True))
    bot.clear_step_handler_by_chat_id(uid)
    msg = bot.send_message(
        uid,
        "👥 GRUPO FREE\n\nPara registrarte, comparte tu propio contacto de Telegram. "
        "Los datos se enviarán a nuestra API para gestionar el acceso.",
        reply_markup=teclado,
    )
    bot.register_next_step_handler(msg, lambda m: _registrar_contacto(bot, m, usuario))


def _registrar_contacto(bot, message, usuario_original):
    uid = usuario_original.id
    if message.chat.type != "private" or message.from_user.id != uid:
        return
    contacto = message.contact
    if not contacto or contacto.user_id != uid:
        bot.send_message(uid, "⚠️ Debes compartir tu propio contacto con el botón.")
        _solicitar_contacto(bot, usuario_original)
        return
    usuario = message.from_user
    datos = {
        "telegramId": uid,
        "username": usuario.username or "",
        "nombre": " ".join(x for x in [usuario.first_name, usuario.last_name] if x),
        "telefono": (contacto.phone_number or "").replace(" ", "").replace("-", "").lstrip("+"),
    }
    bot.send_message(uid, "⏳ Registrando contacto...", reply_markup=telebot.types.ReplyKeyboardRemove())
    try:
        r = requests.post(API_CONTACTOS, json=datos, timeout=TIMEOUT)
        data = r.json() if r.ok else {}
        aceptado = r.ok and (not isinstance(data, dict) or (
            data.get("success") is not False and not data.get("error")))
    except (requests.RequestException, ValueError) as exc:
        print("❌ API contactos:", type(exc).__name__)
        aceptado = False
    if not aceptado:
        bot.send_message(uid, "❌ No se pudo registrar el contacto. Pulsa GRUPO FREE y reintenta.")
        return
    _guardar_contacto(uid)
    bot.send_message(uid, "✅ Contacto registrado correctamente.")
    mostrar_menu_verificacion(bot, usuario)


def ejecutar_grupo_free(bot, call):
    """El callback GRUPO FREE de main.py sigue usando esta función."""
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    if not call.message or call.message.chat.type != "private":
        return
    usuario = call.from_user
    if _miembro(bot, usuario.id):
        bot.send_message(usuario.id, "✅ Ya eres miembro del GRUPO FREE.")
    elif contacto_registrado(usuario.id):
        mostrar_menu_verificacion(bot, usuario)
    else:
        _solicitar_contacto(bot, usuario)
