from main.start import botonera_principal
from main.grupo_free import ejecutar_grupo_free
from main.grupo_vip import ejecutar_grupo_vip
from main.yape_free import ejecutar_yape_free
from main.yape_app import ejecutar_yape_app

# NUEVOS
from main.menu_free import ejecutar_menu_free
from main.bot_yape_free import ejecutar_bot_yape_free


IMAGEN_MENU = "https://i.postimg.cc/R0YhtDCr/image.png"


def registrar_botones(bot):

    @bot.callback_query_handler(
        func=lambda call: call.data == "grupo_free"
    )
    def boton_grupo_free(call):
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass

        ejecutar_grupo_free(bot, call)


    @bot.callback_query_handler(
        func=lambda call: call.data == "grupo_vip"
    )
    def boton_grupo_vip(call):
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass

        ejecutar_grupo_vip(bot, call)


    @bot.callback_query_handler(
        func=lambda call: call.data == "yape_free"
    )
    def boton_yape_free(call):
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass

        ejecutar_yape_free(bot, call)


    @bot.callback_query_handler(
        func=lambda call: call.data == "yape_app"
    )
    def boton_yape_app(call):
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass

        ejecutar_yape_app(bot, call)


    @bot.callback_query_handler(
        func=lambda call: call.data == "menu_free"
    )
    def boton_menu_free(call):
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass

        ejecutar_menu_free(bot, call)


    @bot.callback_query_handler(
        func=lambda call: call.data == "bot_yape_free"
    )
    def boton_bot_yape_free(call):
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass

        ejecutar_bot_yape_free(bot, call)


    @bot.callback_query_handler(
        func=lambda call: call.data == "volver_inicio"
    )
    def volver_inicio(call):

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

        bot.send_photo(
            call.message.chat.id,
            IMAGEN_MENU,
            caption=(
                "🏠 <b>MENÚ PRINCIPAL</b>\n\n"
                "👇 Selecciona una opción:"
            ),
            parse_mode="HTML",
            reply_markup=botonera_principal()
        )