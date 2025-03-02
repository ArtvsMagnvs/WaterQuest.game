# handlers/combat.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import random
from datetime import datetime, timedelta
import logging

from bot.config.settings import (
    SUCCESS_MESSAGES, 
    ERROR_MESSAGES, 
    logger,
    MAX_BATTLES_PER_DAY,
    PET_LEVEL_REQUIREMENT,
    EXP_MULTIPLIER,
    GOLD_PER_LEVEL
)
from bot.utils.keyboard import generar_botones
from bot.utils.save_system import save_game_data, load_game_data
from bot.config.premium_settings import PREMIUM_FEATURES

def calculate_rewards(enemy_level: int, player_level: int, is_premium: bool = False):
    """Calculate rewards based on enemy level and player level."""
    base_exp = 10 + (enemy_level * 5)
    base_gold_per_min = 1 + (enemy_level * 0.5)
    base_coral = 1 + (enemy_level // 5)

    # Ajuste progresivo basado en el nivel del jugador
    level_multiplier = 1 + (player_level * 0.05)  # 5% de aumento por nivel

    exp = int(base_exp * level_multiplier)
    gold_per_min = round(base_gold_per_min * level_multiplier, 2)
    coral = int(base_coral * level_multiplier)

    # Bono premium
    if is_premium:
        exp = int(exp * 1.5)
        gold_per_min = round(gold_per_min * 1.5, 2)
        coral = int(coral * 1.5)

    return {
        "exp": exp,
        "gold_per_min": gold_per_min,
        "coral": coral
    }

def exp_needed_for_level(level: int) -> int:
    """Calculate experience needed for next level."""
    return int(100 * (1.5 ** level))

def calculate_rewards(enemy_level: int, combat_level: int, is_premium: bool = False):
    """Calculate rewards based on enemy level and player's combat level."""
    base_exp = 10 + (enemy_level * 5)
    base_gold_per_min = 1 + (enemy_level * 0.5)
    base_coral = 1 + (enemy_level // 5)

    # Progressive adjustment based on combat level
    level_multiplier = 1 + (combat_level * 0.05)  # 5% increase per combat level

    exp = int(base_exp * level_multiplier)
    gold_per_min = round(base_gold_per_min * level_multiplier, 2)
    coral = int(base_coral * level_multiplier)

    # Premium bonus
    if is_premium:
        exp = int(exp * 1.5)
        gold_per_min = round(gold_per_min * 1.5, 2)
        coral = int(coral * 1.5)

    return {
        "exp": exp,
        "gold_per_min": gold_per_min,
        "coral": coral
    }



async def quick_combat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle quick combat encounters."""
    try:
        user_id = str(update.effective_user.id)
        player = load_game_data(user_id)
        if not player:
            await update.message.reply_text(ERROR_MESSAGES["no_game"])
            return

        stats = player["combat_stats"]

        default_stats = {
            "level": 1,
            "hp": 100,
            "atk": 10,
            "mp": 50,
            "def_p": 5,
            "def_m": 5,
            "agi": 10,
            "sta": 100,
            "battles_today": 0,
            "last_battle_date": None,
            "exp": 0,
            "fire_coral": 0
        }
        for key, value in default_stats.items():
            if key not in stats:
                stats[key] = value

        if player["mascota"]["nivel"] < PET_LEVEL_REQUIREMENT:
            message = f"⚠️ Necesitas nivel {PET_LEVEL_REQUIREMENT} de mascota para acceder al Combate Rápido."
            await update.message.reply_text(message, reply_markup=generar_botones())
            return

        current_time = datetime.now()
        one_day_ago = current_time - timedelta(days=1)

        if 'timestamps' not in player:
            player['timestamps'] = {}
        if 'battle' not in player['timestamps']:
            player['timestamps']['battle'] = []

        player['timestamps']['battle'] = [ts for ts in player['timestamps']['battle'] if datetime.fromisoformat(ts) > one_day_ago]
        battle_timestamps = player['timestamps']['battle']

        max_battles = MAX_BATTLES_PER_DAY
        if player.get('premium_features', {}).get('premium_status', False):
            max_battles += 10

        if len(battle_timestamps) >= max_battles:
            message = f"⚠️ Ya has realizado todas tus batallas en las últimas 24 horas! ({max_battles})"
            await update.message.reply_text(message, reply_markup=generar_botones())
            return

        combat_level = stats["level"]
        enemy_level = max(0, combat_level - 1 + random.randint(0, 2))

        base_chance = 0.75
        agi_bonus = stats["agi"] / 1000
        victory_chance = base_chance + agi_bonus
        victory = random.random() < victory_chance

        if victory:
            is_premium = player.get('premium_features', {}).get('premium_status', False)
            rewards = calculate_rewards(enemy_level, combat_level, is_premium)

            stats["exp"] += rewards["exp"]
            player["mascota"]["oro_hora"] += rewards["gold_per_min"]
            stats["fire_coral"] += rewards["coral"]

            while stats["exp"] >= exp_needed_for_level(stats["level"]):
                stats["exp"] -= exp_needed_for_level(stats["level"])
                stats["level"] += 1
                stats = update_stats_on_level_up(stats)

            message = (
                f"🗡 ¡Victoria!\n"
                f"💫 EXP ganada: {rewards['exp']}\n"
                f"💰 Oro por minuto +{rewards['gold_per_min']}\n"
                f"🌺 Coral de Fuego +{rewards['coral']}"
            )
            if stats["level"] > combat_level:
                message += f"\n\n🎉 ¡Subiste al nivel de combate {stats['level']}!"
        else:
            message = "❌ ¡Derrota! Mejor suerte la próxima vez."

        battle_timestamps.append(current_time.isoformat())
        stats['battles_today'] = len(battle_timestamps)
        player['timestamps']['battle'] = battle_timestamps

        battles_left = max_battles - len(battle_timestamps)
        message += f"\n\n⚔️ Batallas restantes en las próximas 24 horas: {battles_left}"

        player["combat_stats"] = stats
        save_game_data(user_id, player)

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
        logger.error(f"Error in quick_combat function: {e}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(ERROR_MESSAGES["generic_error"], reply_markup=generar_botones())
        else:
            await update.message.reply_text(ERROR_MESSAGES["generic_error"], reply_markup=generar_botones())



def exp_needed_for_level(level: int) -> int:
    """Calculate the experience needed for the next level."""
    return int(100 * (1.5 ** (level - 1)))

def update_stats_on_level_up(stats: dict) -> dict:
    """Update combat stats when leveling up."""
    level = stats["level"]
    stats.update({
        "hp": 100 + (level * 10),
        "atk": 10 + (level * 2),
        "mp": 50 + (level * 5),
        "def_p": 5 + (level * 1.5),
        "def_m": 5 + (level * 1.5),
        "agi": 10 + (level * 1)
    })
    return stats

async def view_combat_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View detailed combat statistics."""
    try:
        user_id = update.effective_user.id
        player = load_game_data(str(user_id))
        if not player:
            if update.callback_query:
                await update.callback_query.message.reply_text(ERROR_MESSAGES["no_game"])
            else:
                await update.message.reply_text(ERROR_MESSAGES["no_game"])
            return

        stats = player["combat_stats"]
        
        message = (
            "⚔️ *Estadísticas de Combate*\n\n"
            f"📊 Nivel: {stats['level']}\n"
            f"❤️ HP: {stats['hp']}\n"
            f"⚔️ ATK: {stats['atk']}\n"
            f"🌟 MP: {stats['mp']}\n"
            f"🛡️ DEF Física: {stats['def_p']}\n"
            f"✨ DEF Mágica: {stats['def_m']}\n"
            f"💨 Agilidad: {stats['agi']}\n"
            f"💪 Aguante: {stats['sta']}\n"
            f"🌺 Coral de Fuego: {stats['fire_coral']}\n\n"
            f"📈 EXP: {stats['exp']}/{exp_needed_for_level(stats['level'])}\n"
            f"⚔️ Batallas hoy: {stats['battles_today']}/{MAX_BATTLES_PER_DAY}"
        )

        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="start")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if update.callback_query:
            await update.callback_query.message.reply_text(
                message,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                message,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )

    except Exception as e:
        logger.error(f"Error in view_combat_stats: {e}")
        if update.callback_query:
            await update.callback_query.message.reply_text(ERROR_MESSAGES["generic_error"])
        else:
            await update.message.reply_text(ERROR_MESSAGES["generic_error"])