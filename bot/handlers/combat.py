# handlers/combat.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import random
import logging
from datetime import datetime, timedelta

# Configurar el logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

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
        logger.info(f"Inicio de combate rápido para el jugador {user_id}")
        player = load_game_data(user_id)

        if not player:
            logger.warning(f"Jugador {user_id} no tiene datos de juego.")
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
            "exp": 0,
            "fire_coral": 0,
            "battles_today": 20  # Inicializamos las batallas diarias a 20
        }
        for key, value in default_stats.items():
            if key not in stats:
                stats[key] = value

        if player["mascota"]["nivel"] < PET_LEVEL_REQUIREMENT:
            message = f"⚠️ Necesitas nivel {PET_LEVEL_REQUIREMENT} de mascota para acceder al Combate Rápido."
            await update.message.reply_text(message, reply_markup=generar_botones())
            logger.info(f"Jugador {user_id} no cumple el requisito de nivel de mascota para combate rápido.")
            return

        # Verificamos si ya ha pasado el día, si es así, asignamos nuevos 20 puntos de combate
        current_time = datetime.now()
        last_battle_date = player.get("last_battle_date", None)
        
        if not last_battle_date or current_time.day != datetime.fromisoformat(last_battle_date).day:
            player["combat_stats"]["battles_today"] = 20  # Se asignan 20 batallas por día a las 00h
            player["combat_stats"]["last_battle_date"] = current_time.isoformat()  # Guardamos la fecha del día
        
        # Verificamos si hay puntos de batalla suficientes
        if player["combat_stats"]["battles_today"] <= 0:
            message = "⚠️ Ya no tienes puntos de batalla disponibles hoy. Vuelve mañana para más batallas."
            await update.message.reply_text(message, reply_markup=generar_botones())
            logger.info(f"Jugador {user_id} ya no tiene puntos de batalla disponibles hoy.")
            return

        # Realizamos el combate
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
            logger.info(f"Jugador {user_id} ha ganado la batalla y ha recibido recompensas.")
        else:
            message = "❌ ¡Derrota! Mejor suerte la próxima vez."
            logger.info(f"Jugador {user_id} ha perdido la batalla.")

        # Restamos 1 punto de batalla
        player["combat_stats"]["battles_today"] -= 1

        # Guardamos los datos del jugador
        save_game_data(user_id, player)
        logger.info(f"Datos guardados para el jugador {user_id}.")

        # Calculamos las batallas restantes
        battles_left = player["combat_stats"]["battles_today"]
        message += f"\n\n⚔️ Batallas restantes hoy: {battles_left}"

        # Preparar el teclado de respuesta
        keyboard = [
            [InlineKeyboardButton("⚔️ Otro Combate", callback_data="combate")],
            [InlineKeyboardButton("🏠 Volver", callback_data="start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Enviar la respuesta al usuario
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