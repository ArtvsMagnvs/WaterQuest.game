import random
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import load_game_data, save_game_data
from utils import generar_botones, calculate_rewards, exp_needed_for_level, update_stats_on_level_up
from config import ERROR_MESSAGES, PET_LEVEL_REQUIREMENT

logger = logging.getLogger(__name__)
DAILY_BATTLE_POINTS = 20

def reset_battle_points(player):
    """Resets the player's daily battle points if 24 hours have passed since the last reset."""
    last_reset = player.get("timestamps", {}).get("battle")
    now = datetime.now()
    if not last_reset or datetime.fromisoformat(last_reset) < now - timedelta(days=1):
        player["battles_today"] = DAILY_BATTLE_POINTS
        player["timestamps"]["battle"] = now.isoformat()

def can_fight_battle(player):
    """Checks if the player has remaining battle points."""
    return player.get("battles_today", 0) > 0

async def quick_combat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle quick combat encounters."""
    try:
        user_id = str(update.effective_user.id)
        logger.info(f"Inicio de combate rápido para el jugador {user_id}")
        player = load_game_data(user_id)

        if not player:
            logger.warning(f"Jugador {user_id} no tiene datos de juego.")
            await update.message.reply_text(ERROR_MESSAGES["no_game"])
            return

        reset_battle_points(player)

        if not can_fight_battle(player):
            message = f"⚠️ Ya has agotado tus batallas diarias ({DAILY_BATTLE_POINTS})!"
            await update.message.reply_text(message, reply_markup=generar_botones())
            logger.info(f"Jugador {user_id} ha alcanzado el límite de batallas diarias.")
            return

        stats = player.get("combat_stats", {})
        default_stats = {
            "level": 1, "hp": 100, "atk": 10, "mp": 50,
            "def_p": 5, "def_m": 5, "agi": 10, "sta": 100,
            "exp": 0, "fire_coral": 0
        }
        for key, value in default_stats.items():
            stats.setdefault(key, value)

        if player["mascota"].get("nivel", 0) < PET_LEVEL_REQUIREMENT:
            message = f"⚠️ Necesitas nivel {PET_LEVEL_REQUIREMENT} de mascota para acceder al Combate Rápido."
            await update.message.reply_text(message, reply_markup=generar_botones())
            logger.info(f"Jugador {user_id} no cumple el requisito de nivel de mascota para combate rápido.")
            return

        combat_level = stats["level"]
        enemy_level = max(0, combat_level - 1 + random.randint(0, 2))
        base_chance = 0.75 + stats["agi"] / 1000
        victory = random.random() < base_chance

        if victory:
            is_premium = player.get("premium_features", {}).get("premium_status", False)
            rewards = calculate_rewards(enemy_level, combat_level, is_premium)
            stats["exp"] += rewards["exp"]
            player["mascota"]["oro_hora"] += rewards["gold_per_min"]
            stats["fire_coral"] += rewards["coral"]

            while stats["exp"] >= exp_needed_for_level(stats["level"]):
                stats["exp"] -= exp_needed_for_level(stats["level"])
                stats["level"] += 1
                stats = update_stats_on_level_up(stats)

            message = (
                f"🗡 ¡Victoria!\n💫 EXP ganada: {rewards['exp']}\n"
                f"💰 Oro por minuto +{rewards['gold_per_min']}\n🌺 Coral de Fuego +{rewards['coral']}"
            )
            if stats["level"] > combat_level:
                message += f"\n\n🎉 ¡Subiste al nivel de combate {stats['level']}!"
            logger.info(f"Jugador {user_id} ha ganado la batalla y ha recibido recompensas.")
        else:
            message = "❌ ¡Derrota! Mejor suerte la próxima vez."
            logger.info(f"Jugador {user_id} ha perdido la batalla.")

        player["battles_today"] -= 1
        save_game_data(user_id, player)
        logger.info(f"Datos guardados para el jugador {user_id}.")

        battles_left = player["battles_today"]
        message += f"\n\n⚔️ Batallas restantes hoy: {battles_left}"

        keyboard = [
            [InlineKeyboardButton("⚔️ Otro Combate", callback_data="combate")],
            [InlineKeyboardButton("🏠 Volver", callback_data="start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(message, reply_markup=reply_markup)
        else:
            await update.message.reply_text(message, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Error en quick_combat para el jugador {user_id}: {e}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(ERROR_MESSAGES["generic_error"], reply_markup=generar_botones())
        else:
            await update.message.reply_text(ERROR_MESSAGES["generic_error"], reply_markup=generar_botones())