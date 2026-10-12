"""Módulo VIP para bot TeleBot existente. pip install pyTelegramBotAPI requests"""
import os
import time
import sqlite3
import logging
import threading
from datetime import datetime, timezone
from urllib.parse import quote
import requests
from telebot import types

CHAT_ID = -1004361223083
ADMIN_IDS = {7219427873, 8635600472}
API_BASE = os.getenv('VIP_API_URL', 'https://bot-apis-zkmk.vercel.app').rstrip('/')
DB_PATH = os.getenv('VIP_LOCAL_DB', 'vip_links.sqlite3')
# La API actual utiliza días enteros. 2 meses se representan como 60 días.
PLANS = {'7': ('S/5 • 7 días', 7, False), '30': ('S/20 • 30 días', 30, False),
         '60': ('S/35 • 2 meses (60 días)', 60, False),
         'permanent': ('S/50 • Pago único', None, True)}
log = logging.getLogger(__name__)


def db():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.execute('CREATE TABLE IF NOT EXISTS links (link TEXT PRIMARY KEY, plan TEXT NOT NULL, used INTEGER DEFAULT 0)')
    conn.execute('CREATE TABLE IF NOT EXISTS removals (user_id TEXT PRIMARY KEY, expires_at TEXT NOT NULL)')
    conn.commit()
    return conn


def api(method, path, payload=None):
    r = requests.request(method, API_BASE + path, json=payload, timeout=20)
    r.raise_for_status()
    data = r.json()
    if not data.get('success', False):
        raise ValueError(data.get('error', 'Respuesta inválida de la API'))
    return data


def parse_date(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def register_vip(bot):
    with db():
        pass

    @bot.message_handler(commands=['vip'])
    def command_vip(message):
        if message.from_user.id not in ADMIN_IDS or message.chat.type != 'private':
            return
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        for code, (title, _, _) in PLANS.items():
            keyboard.add(types.InlineKeyboardButton(title, callback_data='vipplan:' + code))
        bot.send_message(message.chat.id, '👑 Elige una membresía VIP:', reply_markup=keyboard)

    @bot.callback_query_handler(func=lambda c: bool(c.data and c.data.startswith('vipplan:')))
    def create_link(call):
        if call.from_user.id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, 'Solo administradores', show_alert=True)
            return
        code = call.data.partition(':')[2]
        if code not in PLANS:
            bot.answer_callback_query(call.id, 'Plan no válido', show_alert=True)
            return
        try:
            invite = bot.create_chat_invite_link(CHAT_ID, name='VIP-' + code,
                                                 expire_date=int(time.time()) + 86400,
                                                 member_limit=1)
            with db() as con:
                con.execute('INSERT INTO links (link, plan) VALUES (?, ?)', (invite.invite_link, code))
            bot.answer_callback_query(call.id, 'Enlace creado')
            bot.send_message(call.from_user.id,
                             f'👑 {PLANS[code][0]}\n🔗 {invite.invite_link}\n'
                             'Enlace para 1 ingreso; caduca en 24 horas si no se usa.')
        except Exception:
            log.exception('Error generando enlace VIP')
            bot.answer_callback_query(call.id, 'Error creando enlace', show_alert=True)

    @bot.chat_member_handler(func=lambda u: u.chat.id == CHAT_ID)
    def on_join(update):
        if update.old_chat_member.status in ('member', 'administrator', 'creator'):
            return
        if update.new_chat_member.status not in ('member', 'administrator'):
            return
        invite = getattr(update, 'invite_link', None)
        if not invite:
            return
        user = update.new_chat_member.user
        try:
            with db() as con:
                record = con.execute('SELECT plan, used FROM links WHERE link=?',
                                     (invite.invite_link,)).fetchone()
                if not record or record[1]:
                    return
                code = record[0]
                _, days, permanent = PLANS[code]
                # API real: POST /api/vip exige telegram_user_id y crea fecha al registrarse.
                # No marcar el enlace usado si la API falla, para poder reintentar.
                try:
                    api('POST', '/api/vip', {'telegram_user_id': user.id,
                                            'telegram_username': user.username or '',
                                            'days': days, 'permanent': permanent})
                except requests.HTTPError as exc:
                    if exc.response is None or exc.response.status_code != 409:
                        raise
                    # Si ya existe, solo añadir días; nunca reducir membresía activa.
                    api('PATCH', '/api/vip/' + str(user.id),
                        {'days': days, 'permanent': permanent, 'operation': 'add'})
                con.execute('UPDATE links SET used=1 WHERE link=?', (invite.invite_link,))
            bot.send_message(user.id, '👑 Tu membresía VIP está activa.')
        except Exception:
            log.exception('No se pudo registrar al usuario %s', user.id)

    def check_expired():
        # Si la API no responde, NO expulsar a nadie.
        result = api('GET', '/api/vip')
        members = result.get('memberships', [])
        now = datetime.now(timezone.utc)
        for member in members:
            try:
                uid = member.get('telegramUserId')
                expiry = member.get('expiresAt')
                if not uid or not expiry or member.get('permanent'):
                    continue
                if parse_date(expiry) > now:
                    continue
                with db() as con:
                    last = con.execute('SELECT expires_at FROM removals WHERE user_id=?',
                                       (str(uid),)).fetchone()
                if last and last[0] == expiry:
                    continue
                # Reconsultar antes de expulsar: pudo haber una renovación reciente.
                latest = api('GET', '/api/vip/' + quote(str(uid)))['membership']
                latest_expiry = latest.get('expiresAt')
                if latest.get('permanent') or not latest_expiry or parse_date(latest_expiry) > datetime.now(timezone.utc):
                    continue
                if latest_expiry != expiry:
                    continue
                bot.ban_chat_member(CHAT_ID, int(uid))
                bot.unban_chat_member(CHAT_ID, int(uid), only_if_banned=True)
                with db() as con:
                    con.execute('INSERT OR REPLACE INTO removals(user_id, expires_at) VALUES (?, ?)',
                                (str(uid), expiry))
                log.info('VIP vencido retirado: %s', uid)
            except Exception:
                log.exception('Error verificando vencimiento VIP: %s', member.get('telegramUserId'))

    def loop():
        while True:
            try:
                check_expired()
            except Exception:
                log.exception('Error consultando API VIP; sin expulsiones en este ciclo')
            time.sleep(60)

    threading.Thread(target=loop, name='vip-expiry', daemon=True).start()
