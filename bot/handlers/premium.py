from bot.config.premium_settings import PREMIUM_FEATURES
from telegram.ext import ContextTypes
import time
from bot.utils.save_system import load_game_data, save_game_data

async def distribute_weekly_tickets(context: ContextTypes.DEFAULT_TYPE):
    """Distribute weekly tickets to premium users"""
    current_time = time.time()
    
    # Obtener todos los IDs de usuario
    user_ids = context.bot_data.get('user_ids', [])
    
    for user_id in user_ids:
        player = load_game_data(str(user_id))
        if player is None:
            continue
        
        premium_features = player.get('premium_features', {})
        if premium_features.get('premium_status', False):
            # Reset and add new tickets
            premium_features['tickets'] = PREMIUM_FEATURES['weekly_tickets']
            premium_features['last_ticket_distribution'] = current_time
            
            # Guardar los cambios
            save_game_data(str(user_id), player)
            
            # Debug: Mostrar el número de tickets asignados
            print(f"User {user_id} ahora tiene {premium_features['tickets']} tickets.")

