# handlers/portal.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import random
import logging
import asyncio
from datetime import datetime


from bot.config.settings import (
    SUCCESS_MESSAGES, 
    ERROR_MESSAGES, 
    logger,
    MAX_ENERGY
)
from bot.utils.keyboard import generar_botones
from bot.utils.save_system import save_game_data, load_game_data
from bot.handlers.shop import comprar_fragmentos


def give_free_tickets_to_new_player(player):
    """
    Give 100 free tickets to a new player.
    This function should be called when initializing a new player.
    """
    if 'premium_features' not in player:
        player['premium_features'] = {}
    
    if 'tickets' not in player['premium_features']:
        player['premium_features']['tickets'] = 100
    else:
        # If the player already has tickets, we'll add to them
        player['premium_features']['tickets'] += 100

    # Initialize portal stats if not present
    if 'portal_stats' not in player:
        player['portal_stats'] = {
            'total_spins': 0,
            'spins_since_legendary': 0,
            'spins_since_epic': 0,
            'spins_since_rare': 0
        }

    return player

PORTAL_REWARDS = {
    "legendary": {  # 1% probabilidad
        "rewards": [
            {
                "type": "premium_status",
                "value": 7,  # días
                "name": "🌟 Bendición de las Mareas (Premium 7 días)",
                "weight": 1
            },
            {
                "type": "coral",
                "value": 1000,
                "name": "🌺 Tesoro de Coral Ancestral (1000 coral)",
                "weight": 1
            },
            {
                "type": "watershard",
                "value": 10,
                "name": "💎 WaterShard (10 WTR)",
                "description": "Fragmentos cristalizados de agua ancestral",
                "weight": 1
            }
        ]
    },
    "epic": {  # 5% probabilidad
        "rewards": [
            {
                "type": "gold_boost",
                "value": 0.05,  # 5%
                "name": "💫 Encantamiento de Oro (+5% producción permanente)",
                "weight": 2
            },
            {
                "type": "coral",
                "value": 500,
                "name": "🌺 Cofre de Coral (500 coral)",
                "weight": 3
            },
            {
                "type": "watershard",
                "value": 5,
                "name": "💎 WaterShard (5 WTR)",
                "weight": 2
            }
        ]
    },
    "rare": {  # 14% probabilidad
        "rewards": [
            {
                "type": "gold",
                "value": 10000,
                "name": "💰 Tesoro Marino (10,000 oro)",
                "weight": 5
            },
            {
                "type": "energy",
                "value": 100,
                "name": "⚡ Esencia de las Mareas (Energía completa)",
                "weight": 4
            },
            {
                "type": "combat_boost",
                "value": 5,
                "name": "⚔️ Bendición del Guerrero (+5 combates)",
                "weight": 5
            },
            {
                "type": "watershard",
                "value": 2,
                "name": "💎 WaterShard (2 WTR)",
                "weight": 3
            }
        ]
    },
    "common": {  # 80% probabilidad
        "rewards": [
            {
                "type": "gold",
                "value": 1000,
                "name": "💰 Monedas Marinas (1,000 oro)",
                "weight": 20
            },
            {
                "type": "coral",
                "value": 50,
                "name": "🌺 Fragmentos de Coral (50 coral)",
                "weight": 20
            },
            {
                "type": "energy",
                "value": 25,
                "name": "⚡ Gota de Marea (+25 energía)",
                "weight": 20
            },
            {
                "type": "food",
                "value": 20,
                "name": "🍖 Festín Marino (20 comida)",
                "weight": 20
            },
            {
                "type": "watershard",
                "value": 1,
                "name": "💎 WaterShard (1 WTR)",
                "weight": 5
            }
        ]
    }
}

PORTAL_MESSAGES = {
    "opening": "🌊 El Portal de las Mareas se está abriendo...",
    "spinning": [
        "✨ Las energías marinas fluyen...",
        "💫 Los destinos se entrelazan...",
        "🌊 Las mareas predicen tu fortuna..."
    ],
    "legendary": "🌟 ¡Las mareas legendarias te bendicen!",
    "epic": "💫 ¡El océano te otorga un poder épico!",
    "rare": "✨ ¡Las corrientes te traen un regalo especial!",
    "common": "🌊 Las mareas te traen un obsequio...",
    "no_tickets": "❌ No tienes suficientes Fragmentos de Destino",
    "guaranteed": "✨ ¡Giro garantizado de rareza superior activado!"
}

RARITY_CHANCES = {
    "legendary": 0.01,  # 1%
    "epic": 0.05,      # 5%
    "rare": 0.14,      # 14%
    "common": 0.80     # 80%
}

PITY_SYSTEM = {
    "legendary_pity": 100,  # Garantizado legendario cada 100 giros
    "epic_pity": 20,       # Garantizado épico cada 20 giros sin épico o mejor
    "rare_pity": 10        # Garantizado raro cada 10 giros sin raro o mejor
}

async def portal_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display Portal of Tides menu."""
    try:
        user_id = update.effective_user.id
        player = load_game_data(str(user_id))
        if player is None:
            if update.callback_query:
                await update.callback_query.message.reply_text(ERROR_MESSAGES["no_game"])
            else:
                await update.message.reply_text(ERROR_MESSAGES["no_game"])
            return
        
        
        
        # Verifica si 'portal_stats' existe, si no lo inicializa
        if 'portal_stats' not in player:
            player['portal_stats'] = {
                'total_spins': 0,
                'spins_since_legendary': 0,
                'spins_since_epic': 0,
                'spins_since_rare': 0
            }

        tickets = player.get('premium_features', {}).get('tickets', 0)
        
        mensaje = (
            "🌊 Portal de las Mareas 🌊\n\n"
            "Usa tus Fragmentos de Destino para obtener recompensas:\n\n"
            "🌟 Legendario: 1%\n"
            "💫 Épico: 5%\n"
            "✨ Raro: 14%\n"
            "🌊 Común: 80%\n\n"
            f"💎 WaterShards obtenidos: {player.get('watershard', 0)} WTR\n"
            f"🎫 Fragmentos disponibles: {tickets}\n\n"
            f"🎲 Giros totales: {player['portal_stats']['total_spins']}\n"
            f"⭐ Giros hasta legendario garantizado: {PITY_SYSTEM['legendary_pity'] - player['portal_stats']['spins_since_legendary']}\n"
            f"💫 Giros hasta épico garantizado: {PITY_SYSTEM['epic_pity'] - player['portal_stats']['spins_since_epic']} giros\n"
            f"✨ Giros hasta raro garantizado: {PITY_SYSTEM['rare_pity'] - player['portal_stats']['spins_since_rare']} giros"
        )
        
        # Botón para abrir el portal si tiene tickets suficientes
        keyboard = []
        if tickets >= 1:
            keyboard.append([InlineKeyboardButton("🌊 Abrir Portal (1 Fragmento)", callback_data="portal_spin_1")])
        if tickets >= 10:
            keyboard.append([InlineKeyboardButton("🌟 10 Aperturas (Raro+ garantizado)", callback_data="portal_spin_10")])

        # Este botón siempre estará activo en el menú
        keyboard.append([InlineKeyboardButton("🛒 Comprar Fragmentos de Destino", callback_data="buy_tickets")])

        # Opción para volver al menú principal
        keyboard.append([InlineKeyboardButton("🏠 Volver al Menú", callback_data="start")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)

        if update.callback_query:
            try:
                # Intenta editar el mensaje existente
                await update.callback_query.message.edit_text(mensaje, reply_markup=reply_markup)
            except Exception as edit_error:
                # Si falla, manda un nuevo mensaje
                logger.warning(f"Could not edit message, sending new one: {edit_error}")
                await update.callback_query.message.reply_text(mensaje, reply_markup=reply_markup)
        else:
            await update.message.reply_text(mensaje, reply_markup=reply_markup)
            
    except Exception as e:
        logger.error(f"Error in portal_menu: {e}")
        try:
            if update.callback_query:
                await update.callback_query.message.reply_text(ERROR_MESSAGES["generic_error"])
            else:
                await update.message.reply_text(ERROR_MESSAGES["generic_error"])
        except Exception as reply_error:
            logger.error(f"Failed to send error message: {reply_error}")


async def spin_portal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle portal spinning."""
    try:
        user_id = update.effective_user.id
        player = load_game_data(str(user_id))
        if player is None:
            await update.callback_query.message.reply_text(ERROR_MESSAGES["no_game"])
            return
        
        # Check if multi-spin
        is_multi = update.callback_query.data == "portal_spin_10"
        tickets_needed = 10 if is_multi else 1
        
        # Check tickets
        if player.get('premium_features', {}).get('tickets', 0) < tickets_needed:
            await update.callback_query.message.reply_text(PORTAL_MESSAGES["no_tickets"])
            return

        # Animation message
        message = await update.callback_query.message.reply_text(PORTAL_MESSAGES["opening"])
        
        rewards = []
        for _ in range(tickets_needed):
            # Update pity counters
            player['portal_stats']['total_spins'] += 1
            player['portal_stats']['spins_since_legendary'] += 1
            player['portal_stats']['spins_since_epic'] += 1
            player['portal_stats']['spins_since_rare'] += 1

            # Check pity system
            if player['portal_stats']['spins_since_legendary'] >= PITY_SYSTEM['legendary_pity']:
                rarity = "legendary"
            elif player['portal_stats']['spins_since_epic'] >= PITY_SYSTEM['epic_pity'] and is_multi:
                rarity = "epic"
            elif player['portal_stats']['spins_since_rare'] >= PITY_SYSTEM['rare_pity'] and is_multi:
                rarity = "rare"
            else:
                rarity = random.choices(
                    list(RARITY_CHANCES.keys()),
                    list(RARITY_CHANCES.values())
                )[0]

            # Reset appropriate pity counters
            if rarity == "legendary":
                player['portal_stats']['spins_since_legendary'] = 0
                player['portal_stats']['spins_since_epic'] = 0
                player['portal_stats']['spins_since_rare'] = 0
            elif rarity == "epic":
                player['portal_stats']['spins_since_epic'] = 0
                player['portal_stats']['spins_since_rare'] = 0
            elif rarity == "rare":
                player['portal_stats']['spins_since_rare'] = 0

            # Select reward from rarity pool
            possible_rewards = PORTAL_REWARDS[rarity]["rewards"]
            weights = [r["weight"] for r in possible_rewards]
            reward = random.choices(possible_rewards, weights=weights)[0]
            rewards.append((rarity, reward))

            # Animation
            for spin_message in PORTAL_MESSAGES["spinning"]:
                await message.edit_text(spin_message)
                await asyncio.sleep(0.5)

            # Apply reward
            if reward["type"] == "gold":
                player["mascota"]["oro"] += reward["value"]
            elif reward["type"] == "coral":
                player["combat_stats"]["fire_coral"] += reward["value"]
            elif reward["type"] == "energy":
                player["mascota"]["energia"] = min(MAX_ENERGY, player["mascota"]["energia"] + reward["value"])
            elif reward["type"] == "food":
                player["comida"] += reward["value"]
            elif reward["type"] == "gold_boost":
                player["mascota"]["oro_hora"] *= (1 + reward["value"])
            elif reward["type"] == "combat_boost":
                player["combat_stats"]["battles_today"] = max(0, player["combat_stats"]["battles_today"] - reward["value"])
            elif reward["type"] == "premium_status":
                if not player['premium_features'].get('premium_status'):
                    player['premium_features']['premium_status'] = True
                    player['premium_features']['premium_status_expires'] = datetime.now().timestamp() + (reward["value"] * 24 * 60 * 60)
            elif reward["type"] == "watershard":
                if 'watershard' not in player:
                    player['watershard'] = 0
                player['watershard'] += reward["value"]

        # Deduct tickets
        player['premium_features']['tickets'] -= tickets_needed
        
        # Save changes
        save_game_data(str(user_id), player)

        # Show rewards
        rewards_message = f"{PORTAL_MESSAGES[rewards[0][0]]}\n\n"
        for rarity, reward in rewards:
            rewards_message += f"{reward['name']}\n"

        await message.edit_text(rewards_message)
        await portal_menu(update, context)

    except Exception as e:
        logger.error(f"Error in spin_portal: {e}")
        await update.callback_query.message.reply_text(ERROR_MESSAGES["generic_error"])