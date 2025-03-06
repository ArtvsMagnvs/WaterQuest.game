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
        # Add reward information to the link button
        button_text = f"{action['name']} (+{action['reward']} 🐎)"
        button = InlineKeyboardButton(button_text, url=action["link"])
        keyboard.append([button])
        if "message" in action:
            # Informational button that does nothing when clicked
            info_button = InlineKeyboardButton(action["message"], callback_data="do_nothing")
            keyboard.append([info_button])
        # Removed the claim button
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="start")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "🌐 Misiones Sociales:\nCompleta estas misiones para ganar recompensas."
    if query:
        await query.message.edit_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)

async def handle_social_claim(update: Update, context: CallbackContext, action_id):
    """Handle claiming rewards for social actions automatically."""
    user_id = str(update.effective_user.id)
    player = load_game_data(user_id)
    if not player:
        await update.message.reply_text("Por favor, inicia el juego primero con /start.")
        return
    # Check if the user has already claimed this reward
    if "social_rewards" not in player:
        player["social_rewards"] = {}
    if action_id in player["social_rewards"]:
        await update.message.reply_text("Ya has reclamado esta recompensa.")
        return
    # Add the reward
    action = SOCIAL_ACTIONS.get(action_id)
    player["herraduras"] = player.get("herraduras", 0) + action["reward"]
    player["social_rewards"][action_id] = True
    save_game_data(user_id, player)
    await update.message.reply_text(
        f"¡Has completado la acción '{action['name']}'! "
        f"Has recibido {action['reward']} 🐎 Herraduras como recompensa.",
        reply_markup=generar_botones(player)
    )

    save_game_data(user_id, player)

    

async def handle_social_button(update: Update, context: CallbackContext):
    """Handle social mission button presses."""
    query = update.callback_query
    if query.data == "do_nothing":
        # Do nothing for informational buttons
        await query.answer()
    elif query.data.startswith("follow_") or query.data.startswith("join_") or query.data.startswith("play_") or query.data.startswith("visit_"):
        # Extract action_id from the query data
        action_id = query.data.split('_')[1]
        await query.answer()  # Acknowledge the button press
        await asyncio.sleep(10)  # Wait for 10 seconds
        await handle_social_claim(update, context, action_id)  # Automatically claim the reward
    else:
        logger.warning(f"Unhandled social callback_data: {query.data}")
        await query.message.reply_text(ERROR_MESSAGES["generic_error"])