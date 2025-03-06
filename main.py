# main.py
import os
import logging
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    CallbackContext,
    JobQueue
)

# Configuraciones y sistema de guardado
from bot.config.settings import (
    TOKEN, 
    SUCCESS_MESSAGES, 
    ERROR_MESSAGES, 
    logger
)
from bot.config.premium_settings import PREMIUM_FEATURES
from bot.utils.save_system import save_game_data, load_game_data, get_all_user_ids, backup_data
from bot.utils.keyboard import generar_botones

# Import temporalmente (TON SDK comentado)
class TonClientException(Exception):
    pass
TonClientError = TonClientException
# ton_client = initialize_ton_client()
# wallet_manager = initialize_wallet_manager()

# Importar todos los handlers
from bot.handlers import (
    start,  # Si tienes otro start, lo diferenciamos
    button,
    error_handler,
    help_command,
    stats_command,
    recolectar,
    alimentar,
    estado,
    quick_combat,
    view_combat_stats,
    miniboss_handler,
    siguiente_miniboss,
    retirarse_miniboss, 
    claim_daily_reward,
    check_daily_reset,
    check_weekly_tickets,
    tienda,
    comprar,
    check_premium_expiry,
    comprar_fragmentos,
    portal_menu,
    spin_portal
)
from bot.handlers.shop import premium_shop, get_premium_item
from bot.handlers.miniboss import retry_miniboss_battle
from bot.handlers.social import social_menu, handle_social_visit, handle_social_button
from bot.handlers.ads import (
    ads_menu,
    process_ad_watch,
    retry_combat_ad,
    register_handlers
)
# Portal free Tickets for New Players
from bot.handlers.base import initialize_combat_stats
from bot.handlers.portal import give_free_tickets_to_new_player
# Weekly contest
from bot.handlers.weekly_usdt_contest import (
    setup_weekly_contest, 
    start_weekly_contest, 
    end_weekly_contest, 
    weekly_contest_menu,
    TEST_MODE
)

# Función de inicialización de un nuevo jugador (se redefine aquí para asegurar la creación de datos)
def initialize_new_player():
    """Inicializa los datos para un nuevo jugador."""
    return {
        "mascota": {
            "hambre": 100,
            "energia": 100,
            "nivel": 1,
            "oro": 0,
            "oro_hora": 1,
        },
        "comida": 0,
        "última_alimentación": datetime.now().timestamp(),
        "última_actualización": datetime.now().timestamp(),
        "inventario": {},
        "combat_stats": initialize_combat_stats(0),
        "daily_reward": {
            "last_claim": 0,
            "streak": 1,
            "last_weekly_tickets": 0
        },
        "combat_stats": {
            "level": 1,
            "exp": 0,
            "hp": 100,
            "atk": 10,
            "mp": 50,
            "def_p": 5,
            "def_m": 5,
            "agi": 10,
            "battles_today": 0,
            "last_battle_date": str(datetime.now().date()),
            "fire_coral": 0
        },
        "premium_features": {
            "premium_status": False,
            "premium_status_expires": 0,
            "tickets": 0,  # "Fragmentos del Destino" en la interfaz, "tickets" en el código
        },
        "watershard": 0,
        "miniboss_stats": {
            "attempts_today": 0,
            "last_attempt_date": None
        },
        "herraduras": 0
    }

# Handler principal para /start
async def start(update: Update, context: CallbackContext):
    """Inicializa los datos del usuario y comienza el juego."""
    try:
        user_id = update.effective_user.id
        player_data = load_game_data(user_id)
        if player_data is None:
            player_data = initialize_new_player()
            save_game_data(user_id, player_data)
            mensaje = SUCCESS_MESSAGES["welcome"]
        else:
            mensaje = "¡Ya tienes una mascota! Usa los botones para jugar."
            
        if update.callback_query and update.callback_query.message:
            await update.callback_query.message.reply_text(mensaje, reply_markup=generar_botones(player_data))
        elif update.message:
            await update.message.reply_text(mensaje, reply_markup=generar_botones(player_data))
    except Exception as e:
        logger.error(f"Error en el comando start: {e}")
        if update.callback_query and update.callback_query.message:
            await update.callback_query.message.reply_text(ERROR_MESSAGES["generic_error"])
        elif update.message:
            await update.message.reply_text(ERROR_MESSAGES["generic_error"])

# Handler para los botones de callback
async def button_handler(update: Update, context: CallbackContext):
    """Maneja las pulsaciones de botones."""
    try:
        query = update.callback_query
        try:
            await query.answer()
        except Exception:
            pass  # Si el callback_query expiró
        
        user_id = query.from_user.id
        player = load_game_data(user_id)
        if player is None:
            logger.warning(f"Datos de jugador no encontrados para el user_id: {user_id}")
            await query.message.reply_text(ERROR_MESSAGES["player_not_found"])
            return

        # Ruteo según el callback_data
        data = query.data
        if data == "start":
            await start(update, context)
        elif data == "recolectar":
            await recolectar(update, context)
        elif data == "alimentar":
            await alimentar(update, context)
        elif data == "estado":
            await estado(update, context)
        elif data == "tienda":
            await tienda(update, context)
        elif data == "combate":
            await quick_combat(update, context)
        elif data == "miniboss":
            await miniboss_handler(update, context)
        elif data == "siguiente_miniboss":
            await siguiente_miniboss(update, context)
        elif data == "retirarse_miniboss":
            await retirarse_miniboss(update, context)
        elif data.startswith("retry_miniboss_"):
            await retry_miniboss_battle(update, context)
        elif data == "daily_reward":
            await claim_daily_reward(update, context)
        elif data.startswith("comprar_"):
            item_name = data.split("_")[1]
            await comprar(update, context, item_name)
        elif data == "portal":
            await portal_menu(update, context)
        elif data.startswith("portal_spin_"):
            await spin_portal(update, context)
        elif data == "ads_menu":
            await ads_menu(update, context)
        elif data == "watch_ad":
            await process_ad_watch(update, context)
        elif data.startswith("retry_miniboss_"):
            combat_type = data.split("_")[3]
            await retry_combat_ad(update, context, combat_type)
        elif data == "premium_shop":
            await premium_shop(update, context)
        elif data == "weekly_contest":
            await weekly_contest_menu(update, context)
        elif data == "social":
            await social_menu(update, context)
        elif data == "comprar_fragmentos":
            await comprar_fragmentos(update, context)
        else:
            logger.warning(f"callback_data no manejada: {data}")
            await query.message.reply_text(ERROR_MESSAGES["generic_error"], reply_markup=generar_botones(player))
    except Exception as e:
        logger.error(f"Error en el handler de button: {e}")
        if update.callback_query and update.callback_query.message:
            await update.callback_query.message.reply_text(ERROR_MESSAGES["generic_error"], reply_markup=generar_botones(player))
        elif update.message:
            await update.message.reply_text(ERROR_MESSAGES["generic_error"])

# Handler de errores
async def global_error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ocurrió un error: {context.error}")
    try:
        if update and update.effective_message:
            if update.callback_query and update.callback_query.message:
                await update.callback_query.message.reply_text(ERROR_MESSAGES["generic_error"])
            elif update.message:
                await update.message.reply_text(ERROR_MESSAGES["generic_error"])
    except Exception as e:
        logger.error(f"Error en el handler global: {e}")

# Handler de ejemplo para abrir una Web App desde Telegram
async def web_app_handler(update: Update, context: CallbackContext):
    """Envía un botón que abre una Web App en el cliente de Telegram."""
    try:
        web_app_url = os.environ.get("WEBAPP_URL", "https://tu-dominio.com/tu_web_app")
        button = InlineKeyboardButton("Abrir Web App", web_app=WebAppInfo(url=web_app_url))
        markup = InlineKeyboardMarkup([[button]])
        await update.message.reply_text("Abriendo Web App:", reply_markup=markup)
    except Exception as e:
        logger.error(f"Error en web_app_handler: {e}")
        await update.message.reply_text(ERROR_MESSAGES["generic_error"])

def main():
    """Inicia el bot en modo webhook para integración con Web App."""
    try:
        application = Application.builder().token(TOKEN).build()
        # Se inicializa el diccionario de jugadores
        application.bot_data['players'] = {}

        # Agregar handlers de comandos
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("stats", stats_command))
        # Handler para abrir la Web App
        application.add_handler(CommandHandler("webapp", web_app_handler))
        
        # Handler para callback queries
        application.add_handler(CallbackQueryHandler(button_handler))
        
        # Handler para errores
        application.add_error_handler(global_error_handler)
        
        # Handler para items premium (usando patrón en callback_data)
        application.add_handler(CallbackQueryHandler(get_premium_item, pattern=r'^get_premium_'))

        # Programar tareas (jobs)
        job_queue = application.job_queue
        job_queue.run_once(setup_weekly_contest, when=1)  # Ejecuta el setup inmediatamente
        
        job_queue.run_repeating(
            check_weekly_tickets,
            interval=86400,  # Revisa diariamente
            first=10
        )
        job_queue.run_repeating(
            check_premium_expiry,
            interval=3600,  # Cada hora
            first=10
        )
        job_queue.run_repeating(
            check_daily_reset,
            interval=21600,  # Cada 6 horas
            first=10
        )
        job_queue.run_repeating(
            start_weekly_contest,
            interval=604800,  # Una semana en segundos
            first=10
        )
        job_queue.run_repeating(
            end_weekly_contest,
            interval=604800,  # Una semana en segundos
            first=604810  # Una semana + 10 segundos después del inicio
        )

        # Configuración para ejecutar el bot en modo webhook
        USE_WEBHOOK = True  # Cambia a False si prefieres usar polling
        if USE_WEBHOOK:
            # Configura las variables de entorno o usa valores por defecto
            WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://artvsmagnvs.github.io/WaterQuest.game/")
            PORT = int(os.environ.get("PORT", "8443"))
            print("Bot iniciado en modo webhook...")
            application.run_webhook(
                listen="0.0.0.0",
                port=PORT,
                url_path=TOKEN,
                webhook_url=f"{WEBHOOK_URL}/{TOKEN}"
            )
        else:
            print("Bot iniciado en modo polling...")
            application.run_polling()

        return application

    except Exception as e:
        logger.error(f"Error iniciando el bot: {e}")
        return None

if __name__ == '__main__':
    app = None
    try:
        app = main()
    except KeyboardInterrupt:
        print("\nBot detenido manualmente")
    finally:
        # Al finalizar, guardar y respaldar los datos de cada jugador
        if app:
            user_ids = get_all_user_ids()
            for user_id in user_ids:
                player_data = load_game_data(user_id)
                if player_data:
                    save_game_data(user_id, player_data)
                    backup_data(user_id, player_data)
            print("Datos guardados. ¡Hasta luego!")









#====================================================================================================

# WaterQuest Functions
""" async def show_waterquest_menu(update: Update, context: CallbackContext):
#    Display available WaterQuests.
    try:
        user_id = update.effective_user.id
        if user_id not in context.bot_data.get('players', {}):
            await update.callback_query.message.reply_text(ERROR_MESSAGES["no_game"])
            return

        player = context.bot_data['players'][user_id]
        completed_quests = player["waterquest_data"]["completed_quests"]
        
        mensaje = (
            "📜 WaterQuests Disponibles 📜\n\n"
            "Misiones especiales que te llevarán a través del océano seco "
            "en busca de respuestas y poder.\n\n"
            "Misiones disponibles:"
        )
        
        # Lista de quests disponibles
        mensaje += "\n\n📜 La Voz del Abismo\n" \
                  "Una misteriosa voz llama desde las profundidades..."
        
        if "voice_of_abyss" in completed_quests:
            mensaje += "\n✅ Completada"

        # Usar reply_text si no hay mensaje para editar
        if update.callback_query and update.callback_query.message:
            try:
                await update.callback_query.message.edit_text(
                    mensaje,
                    reply_markup=create_waterquest_menu_keyboard()
                )
            except:
                await update.callback_query.message.reply_text(
                    mensaje,
                    reply_markup=create_waterquest_menu_keyboard()
                )
        else:
            await update.message.reply_text(
                mensaje,
                reply_markup=create_waterquest_menu_keyboard()
            )

    except Exception as e:
        logger.error(f"Error in waterquest_menu: {e}")
        if update.callback_query and update.callback_query.message:
            await update.callback_query.message.reply_text(
                ERROR_MESSAGES["generic_error"],
                reply_markup=generar_botones(player if 'player' in locals() else None)
            )
        elif update.message:
            await update.message.reply_text(ERROR_MESSAGES["generic_error"])

async def start_voice_of_abyss_quest(update: Update, context: CallbackContext):
#    Start the Voice of Abyss quest.
    try:
        user_id = update.effective_user.id
        if user_id not in context.bot_data.get('players', {}):
            await update.callback_query.message.reply_text(ERROR_MESSAGES["no_game"])
            return

        player = context.bot_data['players'][user_id]
        
        # Initialize quest if not exists
        if 'voice_of_abyss' not in context.bot_data:
            context.bot_data['voice_of_abyss'] = VoiceOfAbyssQuest()

        quest = context.bot_data['voice_of_abyss']
        success, message, data = await quest.start_quest(user_id, player)

        if success:
            # Store quest data
            player["waterquest_data"]["active_quests"]["voice_of_abyss"] = {
                "started_at": datetime.now().timestamp(),
                "current_node": data["node"].id
            }
            save_game_data(context.bot_data['players'])

            await update.callback_query.message.edit_text(
                data["node"].text,
                reply_markup=create_waterquest_dialogue_keyboard(data["node"].responses)
            )
        else:
            await update.callback_query.message.edit_text(
                message,
                reply_markup=generar_botones(player)
            )

    except Exception as e:
        logger.error(f"Error starting Voice of Abyss quest: {e}")
        await update.callback_query.message.reply_text(ERROR_MESSAGES["generic_error"])

async def process_quest_choice(update: Update, context: CallbackContext, choice_id: str):
    #   Process a choice made in a WaterQuest.
    try:
        user_id = update.effective_user.id
        player = context.bot_data['players'][user_id]
        quest = context.bot_data['voice_of_abyss']

        success, message, data = await quest.process_choice(
            user_id,
            choice_id,
            player
        )

        if success:
            # Update quest progress
            player["waterquest_data"]["active_quests"]["voice_of_abyss"]["current_node"] = data["node"].id
            save_game_data(context.bot_data['players'])

            await update.callback_query.message.edit_text(
                data["node"].text,
                reply_markup=create_waterquest_dialogue_keyboard(data["node"].responses)
            )
        else:
            await update.callback_query.message.edit_text(
                message,
                reply_markup=generar_botones(player)
            )

    except Exception as e:
        logger.error(f"Error processing quest choice: {e}")
        await update.callback_query.message.reply_text(ERROR_MESSAGES["generic_error"])"""


# ... (resto de funciones existentes) ...