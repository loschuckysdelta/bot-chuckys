
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from urllib.parse import quote
from telebot.apihelper import ApiTelegramException

IMAGEN_VIP = "https://i.postimg.cc/q7MX4Vdb/image.png"
VENDEDOR = "ReinaDark_x"

def enlace_compra(nombre, precio):
    mensaje = f"Hola, quiero comprar el plan VIP de {nombre} por S/ {precio}. ¿Cómo puedo pagar?"
    return f"https://t.me/{VENDEDOR}?text={quote(mensaje, safe='')}"


PLANES_VIP = {
    "7": ("7 DÍAS", 5),
    "30": ("30 DÍAS", 20),
    "60": ("2 MESES", 35),
    "permanente": ("PAGO ÚNICO", 50)
}


# ==================================================
# MOSTRAR MENÚ VIP
# ==================================================

def ejecutar_grupo_vip(bot, call):

    chat_id = call.message.chat.id

    markup = InlineKeyboardMarkup(row_width=1)

    markup.add(
        InlineKeyboardButton(
            "💰 S/ 5 — 7 DÍAS",
            url=enlace_compra("7 DÍAS", 5)
        ),
        InlineKeyboardButton(
            "🔥 S/ 20 — 30 DÍAS 👑 MÁS VENDIDO",
            url=enlace_compra("30 DÍAS", 20)
        ),
        InlineKeyboardButton(
            "💎 S/ 35 — 2 MESES",
            url=enlace_compra("2 MESES", 35)
        ),
        InlineKeyboardButton(
            "♾️ S/ 50 — PAGO ÚNICO ⭐",
            url=enlace_compra("PAGO ÚNICO", 50)
        )
    )

    texto = (
        "👑 <b>GRUPO VIP — ACCESO EXCLUSIVO</b>\n\n"
        "🔥 <b>¡ELIGE TU PLAN VIP!</b>\n\n"
        "✅ Acceso a contenidos exclusivos\n"
        "✅ Acceso a los grupos incluidos\n"
        "✅ Videos completos\n"
        "✅ Soporte y actualizaciones\n\n"
        "👇 <b>Selecciona un plan para continuar:</b>"
    )

    try:
        bot.send_photo(
            chat_id, IMAGEN_VIP, caption=texto,
            reply_markup=markup, parse_mode="HTML", timeout=15
        )
    except Exception as error:
        print(f"⚠️ No se pudo enviar imagen VIP: {error}")
        bot.send_message(chat_id, texto, reply_markup=markup, parse_mode="HTML")


# ==================================================
# REGISTRAR BOTONES VIP
# ==================================================

def registrar_planes_vip(bot):

    @bot.callback_query_handler(
        func=lambda call: (
            (call.data or "").startswith("vip_plan_")
            or call.data == "vip_volver_planes"
        )
    )
    def manejar_plan_vip(call):

        try:
            bot.answer_callback_query(call.id)
        except ApiTelegramException as error:
            print(f"⚠️ Error confirmando botón: {error}")

        try:
            chat_id = call.message.chat.id

            if call.data == "vip_volver_planes":
                ejecutar_grupo_vip(bot, call)
                return

            plan_id = call.data.replace("vip_plan_", "", 1)
            plan = PLANES_VIP.get(plan_id)

            if not plan:
                bot.send_message(chat_id, "❌ Plan no encontrado.")
                return

            nombre, precio = plan

            print(
                f"✅ PLAN VIP SELECCIONADO: "
                f"{nombre} — S/ {precio}"
            )

            solicitud = (
                f"Hola, quiero comprar el plan VIP "
                f"{nombre} de S/ {precio}."
            )

            texto = (
                "👑 <b>PLAN VIP SELECCIONADO</b>\n\n"
                f"📦 <b>Plan:</b> {nombre}\n"
                f"💰 <b>Precio:</b> S/ {precio}\n\n"
                "🎁 <b>BENEFICIOS:</b>\n"
                "✅ Acceso al grupo VIP\n"
                "✅ Contenido exclusivo\n"
                "✅ Videos completos\n\n"
                "📲 <b>PARA COMPRAR:</b>\n"
                "Copia tu solicitud y contacta "
                "con el administrador.\n\n"
                f"💬 <b>Solicitud:</b>\n{solicitud}"
            )

            markup = InlineKeyboardMarkup(row_width=1)

            markup.add(
                InlineKeyboardButton(
                    "💳 COMPRAR ESTE PLAN",
                    url=enlace_compra(nombre, precio)
                ),
                InlineKeyboardButton(
                    "📋 COPIAR SOLICITUD",
                    copy_text=__import__("telebot").types.CopyTextButton(text=solicitud)
                ),
                InlineKeyboardButton(
                    "🔙 VER OTROS PLANES",
                    callback_data="vip_volver_planes"
                )
            )

            bot.send_message(
                chat_id,
                texto,
                parse_mode="HTML",
                reply_markup=markup
            )

        except Exception as error:
            print(f"❌ ERROR EN BOTÓN VIP: {error}")

            try:
                bot.send_message(
                    call.message.chat.id,
                    "❌ No se pudo procesar el plan VIP."
                )
            except Exception:
                pass

    print("✅ BOTONES DE PLANES VIP REGISTRADOS")
