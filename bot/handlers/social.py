from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from bot.config.settings import SUCCESS_MESSAGES, ERROR_MESSAGES, logger
from bot.utils.keyboard import generar_botones
from bot.utils.save_system import load_game_data, save_game_data
import asyncio

SOCIAL_ACTIONS = {
    "follow_twitter": {
        "name": "Follow Twitter",
        "link": "https://x.com/niidesevenmoons",
        "reward": 10,
        "message": "Follow us on Twitter!"
    },
    "join_discord": {
        "name": "Join Discord Weekly Contest",
        "link": "https://discord.gg/M4DUpMB4Ap",
        "reward": 50,
        "message": "Win 100$ in USDT!"
    },
    "play_niide": {
        "name": "Play Niide Game Daily Contest",
        "link": "https://niide.io/",
        "reward": 25,
        "message": "Win 100$ in $KRUUM TOKEN every day!"
    },
    "visit_token_sale": {
        "name": "Visit Token Sale Website",
        "link": "https://kruumsale.niide.io/",
        "reward": 30,
        "message": "$KRUUM Pre-Sale is live!"
    }
}

async def social_menu(update: Update, context: CallbackContext):
    """Display the social missions menu."""
    query = update.callback_query
    if query:
        await query.answer()

    user_id = str(update.effective_user.id)
    player = load_game_data(user_id)

    keyboard = []
    for action_id, action in SOCIAL_ACTIONS.items():
        button_text = f"{action['name']} (+{action['reward']} 🐎)"
        button = InlineKeyboardButton(button_text, url=action["link"], callback_data=f"visit_{action_id}")
        keyboard.append([button])

    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="start")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = "🌐 Misiones Sociales:\nCompleta estas misiones para ganar recompensas."
    
    if query:
        await query.message.edit_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)

async def handle_social_visit(update: Update, context: CallbackContext):
    """Handle reward assignment after visiting a social link."""
    query = update.callback_query
    action_id = query.data.split('_')[1]
    action = SOCIAL_ACTIONS.get(action_id)
    
    if not action:
        logger.warning(f"Unhandled social action: {action_id}")
        await query.message.reply_text(ERROR_MESSAGES["generic_error"])
        return
    
    user_id = str(update.effective_user.id)
    player = load_game_data(user_id)
    
    if not player:
        await query.message.reply_text("Por favor, inicia el juego primero con /start.")
        return
    
    if "social_rewards" not in player:
        player["social_rewards"] = {}
    
    if action_id in player["social_rewards"]:
        await query.answer("Ya has recibido esta recompensa.", show_alert=True)
        return
    
    await query.answer("Recompensa en camino...", show_alert=True)
    await asyncio.sleep(10)
    
    player["herraduras"] = player.get("herraduras", 0) + action["reward"]
    player["social_rewards"][action_id] = True
    save_game_data(user_id, player)
    
    await query.message.reply_text(
        f"¡Has completado la acción '{action['name']}'! "
        f"Has recibido {action['reward']} 🐎 Herraduras como recompensa.",
        reply_markup=generar_botones(player)
    )

async def handle_social_button(update: Update, context: CallbackContext):
    """Handle social mission button presses."""
    query = update.callback_query
    
    if query.data.startswith("visit_"):
        await handle_social_visit(update, context)
    else:
        logger.warning(f"Unhandled social callback_data: {query.data}")
        await query.message.reply_text(ERROR_MESSAGES["generic_error"])
