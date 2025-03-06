# handlers/__init__.py

from bot.handlers.base import (
    start, 
    button, 
    error_handler, 
    help_command, 
    stats_command
)
from .combat import quick_combat, view_combat_stats
from .miniboss import (
    miniboss_handler, 
    siguiente_miniboss, 
    retirarse_miniboss
)
from .daily import claim_daily_reward, check_daily_reset
from .shop import tienda, comprar, comprar_fragmentos  # Removed premium_shop and handle_premium_purchase
from .pet import (
    recolectar, 
    alimentar, 
    estado, 
    check_premium_expiry
)
from .social import (  
    social_menu,
    handle_social_button,
    handle_social_visit
)

from .daily import claim_daily_reward, check_daily_reset, check_weekly_tickets
from bot.config.premium_settings import PREMIUM_FEATURES

from .portal import (
    portal_menu, 
    spin_portal,
)

__all__ = [
    # Base handlers
    'start',
    'button',
    'error_handler',
    'help_command',
    'stats_command',
    
    # Combat handlers
    'quick_combat',
    'view_combat_stats',
    
    # MiniBoss handlers
    'miniboss_handler',
    'siguiente_miniboss',
    'retirarse_miniboss',
    
    # Daily reward handlers
    'claim_daily_reward',
    'check_daily_reset',
    'check_weekly_tickets',
    
    # Shop handlers
    'tienda',
    'comprar',  # Removed premium_shop and handle_premium_purchase
    
    # Pet handlers
    'recolectar',
    'alimentar',
    'estado',
    'check_premium_expiry',

    # Portal handlers
    'portal_menu',
    'spin_portal',

    # Social handlers  # Añadido
    'social_menu',
    'handle_social_button',
    'handle_social_visit',
]
