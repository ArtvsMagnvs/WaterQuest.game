#weekly_usdt_contest.py

import random
import asyncio
from datetime import datetime, timedelta, time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, CallbackContext
from bot.config.settings import logger
from bot.utils.save_system import load_game_data, save_game_data


# Contest Configuration
CONTEST_CONFIG = {
    "start_day": 0,  # Monday
    "start_hour": 17,  # 17:00 CET
    "duration_days": 7,
    "max_daily_ads": 10,
    "max_weekly_ads": 70,
    "daily_bonus_threshold": 10,
    "daily_bonus_tickets": 5,
    "weekly_bonus_threshold": 70,
    "weekly_bonus_tickets": 50,
    "min_ads_for_entry": 1,
    "prizes": [
        {"amount": 20, "count": 1},
        {"amount": 10, "count": 2},
        {"amount": 5, "count": 3},
        {"amount": 3, "count": 4},
        {"amount": 1, "count": 10}
    ]
}

# Test Mode Configuration
TEST_MODE = False
TEST_CONTEST_DURATION = timedelta(minutes=1)


async def weekly_contest_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display the weekly contest menu."""
    user_id = update.effective_user.id
    contest_data = context.bot_data.get("weekly_contest", {})
    player_data = load_game_data(str(user_id))
    if player_data is None:
        await update.callback_query.message.reply_text(ERROR_MESSAGES["no_game"])
        return
    player_contest_data = player_data.get("contest_data", {"tickets": 0})

    if not contest_data or datetime.now() > contest_data.get("end_time", datetime.now()):
        message = "No hay un concurso activo en este momento. ¡Espera al próximo concurso semanal!"
    else:
        time_left = contest_data["end_time"] - datetime.now()
        message = (
            f"🏆 Concurso Semanal USDT\n\n"
            f"Tiempo restante: {time_left.days} días, {time_left.seconds // 3600} horas\n"
            f"Tus boletos: {player_contest_data['tickets']}\n\n"
            f"¡Mira anuncios para ganar más boletos!"
        )

    keyboard = [
        [InlineKeyboardButton("Ver Anuncio", callback_data="view_ad")],
        [InlineKeyboardButton("🏠 Volver", callback_data="start")]
    ]

    if update.callback_query:
        await update.callback_query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def start_weekly_contest(context: ContextTypes.DEFAULT_TYPE):
    """Start the weekly contest."""
    contest_data = {
        "start_time": datetime.now(),
        "end_time": datetime.now() + (TEST_CONTEST_DURATION if TEST_MODE else timedelta(days=CONTEST_CONFIG["duration_days"])),
        "participants": {}
    }
    context.bot_data["weekly_contest"] = contest_data
    
    # Programar recordatorios diarios
    for day in range(CONTEST_CONFIG["duration_days"]):
        context.job_queue.run_once(
            send_daily_reminder,
            when=contest_data["start_time"] + timedelta(days=day, hours=12)
        )

    # Schedule the end of the contest
    context.job_queue.run_once(end_weekly_contest, TEST_CONTEST_DURATION if TEST_MODE else timedelta(days=CONTEST_CONFIG["duration_days"]))
    
    # Notify all users
    for user_id in context.bot_data["players"]:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="🎉 ¡El concurso semanal ha comenzado! Mira anuncios para ganar boletos y participar en el sorteo de 100 USDT.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Ver Anuncio", callback_data="view_ad")]])
            )
        except Exception as e:
            logger.error(f"Error notifying user {user_id}: {e}")

async def end_weekly_contest(context: ContextTypes.DEFAULT_TYPE):
    """End the weekly contest and distribute prizes."""
    contest_data = context.bot_data.get("weekly_contest", {})
    participants = contest_data.get("participants", {})
    
    if not participants:
        logger.warning("No participants in the weekly contest.")
        return
    
    winners = select_winners(participants)
    
    for user_id, prize in winners.items():
        player = load_game_data(str(user_id))
        if player:
            player["balance"] = player.get("balance", 0) + prize
            save_game_data(str(user_id), player)
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🎊 ¡Felicidades! Has ganado {prize} USDT en el concurso semanal."
            )
    
    # Notify non-winners
    for user_id in participants:
        if user_id not in winners:
            await context.bot.send_message(
                chat_id=user_id,
                text="El concurso semanal ha terminado. ¡Gracias por participar! Mejor suerte la próxima vez."
            )
    
    
    
    # Reset contest data
    context.bot_data["weekly_contest"] = {}
    
    # Schedule the next contest
    next_contest_time = get_next_contest_start_time()
    context.job_queue.run_once(start_weekly_contest, next_contest_time - datetime.now())

def select_winners(participants):
    """Select winners based on their tickets."""
    all_tickets = []
    for user_id, tickets in participants.items():
        all_tickets.extend([user_id] * tickets)
    
    winners = {}
    for prize in CONTEST_CONFIG["prizes"]:
        for _ in range(prize["count"]):
            if all_tickets:
                winner = random.choice(all_tickets)
                winners[winner] = winners.get(winner, 0) + prize["amount"]
                all_tickets = [t for t in all_tickets if t != winner]
    
    return winners

def get_next_contest_start_time():
    """Get the start time for the next contest."""
    now = datetime.now()
    days_ahead = CONTEST_CONFIG["start_day"] - now.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    next_contest = now.replace(hour=CONTEST_CONFIG["start_hour"], minute=0, second=0, microsecond=0) + timedelta(days=days_ahead)
    return next_contest

async def view_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle ad viewing and update contest tickets."""
    user_id = update.effective_user.id
    contest_data = context.bot_data.get("weekly_contest", {})
    
    if not contest_data or datetime.now() > contest_data.get("end_time", datetime.now()):
        await update.callback_query.answer("No hay un concurso activo en este momento.")
        return
    
    player = load_game_data(str(user_id))
    if player is None:
        await update.callback_query.answer("Debes iniciar el juego primero con /start.")
        return
    if not player:
        await update.callback_query.answer("Debes iniciar el juego primero con /start.")
        return
    
    # Update player's contest data
    player_contest_data = player.setdefault("contest_data", {"daily_ads": 0, "weekly_ads": 0, "tickets": 0})
    player_contest_data["daily_ads"] += 1
    player_contest_data["weekly_ads"] += 1
    player_contest_data["tickets"] += 1
    
    # Apply bonuses
    if player_contest_data["daily_ads"] == CONTEST_CONFIG["daily_bonus_threshold"]:
        player_contest_data["tickets"] += CONTEST_CONFIG["daily_bonus_tickets"]
    if player_contest_data["weekly_ads"] == CONTEST_CONFIG["weekly_bonus_threshold"]:
        player_contest_data["tickets"] += CONTEST_CONFIG["weekly_bonus_tickets"]
    
    # Update contest participants
    contest_data["participants"][user_id] = player_contest_data["tickets"]

    save_game_data(str(user_id), player)
    
    # Check milestone after updating the player's data
    await check_milestone(update, context)
    
    await update.callback_query.edit_message_text(
        f"Anuncio visto. Tienes {player_contest_data['tickets']} boletos para el concurso semanal.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Ver Otro Anuncio", callback_data="view_ad")]])
    )

async def send_daily_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Send a daily reminder to all participants."""
    contest_data = context.bot_data.get("weekly_contest", {})
    if not contest_data:
        return

    for user_id in contest_data["participants"]:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="🔔 ¡Recuerda participar en el concurso semanal de USDT! Mira anuncios para ganar más boletos."
            )
        except Exception as e:
            logger.error(f"Error sending reminder to user {user_id}: {e}")

async def check_milestone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check if user is close to reaching a milestone and notify them."""
    user_id = update.effective_user.id
    player = load_game_data(str(user_id))
    if not player:
        return

    player_contest_data = player.get("contest_data", {})
    daily_ads = player_contest_data.get("daily_ads", 0)
    weekly_ads = player_contest_data.get("weekly_ads", 0)

    if daily_ads == CONTEST_CONFIG["daily_bonus_threshold"] - 1:
        await update.callback_query.answer("¡Estás a un anuncio de ganar el bono diario!")
    elif weekly_ads == CONTEST_CONFIG["weekly_bonus_threshold"] - 1:
        await update.callback_query.answer("¡Estás a un anuncio de ganar el bono semanal!")

async def contest_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the current status of the contest."""
    contest_data = context.bot_data.get("weekly_contest", {})
    if not contest_data:
        await update.message.reply_text("No hay un concurso activo en este momento.")
        return

    time_left = contest_data["end_time"] - datetime.now()
    participants_count = len(contest_data["participants"])
    total_tickets = sum(contest_data["participants"].values())

    status_message = (
        f"📊 Estado del Concurso Semanal USDT\n\n"
        f"Tiempo restante: {time_left.days} días, {time_left.seconds // 3600} horas\n"
        f"Participantes: {participants_count}\n"
        f"Total de boletos: {total_tickets}\n"
    )

    await update.message.reply_text(status_message)

async def show_ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the current ranking of the contest."""
    contest_data = context.bot_data.get("weekly_contest", {})
    if not contest_data:
        await update.message.reply_text("No hay un concurso activo en este momento.")
        return

    participants = contest_data["participants"]
    sorted_participants = sorted(participants.items(), key=lambda x: x[1], reverse=True)

    ranking_message = "🏆 Ranking del Concurso Semanal USDT\n\n"
    for i, (user_id, tickets) in enumerate(sorted_participants[:10], start=1):
        user = await context.bot.get_chat(user_id)
        ranking_message += f"{i}. {user.first_name}: {tickets} boletos\n"

    user_id = update.effective_user.id
    user_rank = next((i for i, (uid, _) in enumerate(sorted_participants, start=1) if uid == user_id), None)
    if user_rank:
        ranking_message += f"\nTu posición: {user_rank} con {participants[user_id]} boletos"

    await update.message.reply_text(ranking_message)

from datetime import datetime, timedelta, time

def setup_weekly_contest(context: CallbackContext):
    """Set up the weekly contest."""
    now = datetime.now()
    
    # Set the contest to start at the next occurrence of Monday at 00:00
    start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
    while start_time.weekday() != 0:  # 0 is Monday
        start_time += timedelta(days=1)
    
    # Set the end time to 7 days after the start time
    end_time = start_time + timedelta(days=7)
    
    if TEST_MODE:
        # For testing: start immediately and end after 1 minute
        start_time = now
        end_time = start_time + timedelta(minutes=1)
    
    context.bot_data["weekly_contest"] = {
        "start_time": start_time,
        "end_time": end_time,
        "participants": {}
    }
    
    # Schedule the start and end of the contest
    context.job_queue.run_once(start_weekly_contest, start_time)
    context.job_queue.run_once(end_weekly_contest, end_time)


