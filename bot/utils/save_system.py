#save_system.py

import psycopg2
import json
import logging
from datetime import datetime
from typing import Dict, Optional, List
from psycopg2.extras import RealDictCursor

# Configuración de la base de datos
import os

DB_CONFIG = {
    "dbname": os.environ.get("PGDATABASE"),
    "user": os.environ.get("PGUSER"),
    "password": os.environ.get("PGPASSWORD"),
    "host": os.environ.get("PGHOST"),
    "port": os.environ.get("PGPORT")
}

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_connection():
    """Conectar a la base de datos PostgreSQL."""
    return psycopg2.connect(**DB_CONFIG)

def create_table():
    """Crear la tabla si no existe."""
    query = """
    CREATE TABLE IF NOT EXISTS game_data (
        user_id TEXT PRIMARY KEY,
        mascota_hambre INT,
        mascota_energia INT,
        mascota_nivel INT,
        mascota_oro INT,
        mascota_oro_hora INT,
        comida INT,
        ultima_alimentacion TIMESTAMP,
        ultima_actualizacion TIMESTAMP,
        inventario TEXT,
        combat_level INT,
        combat_exp INT,
        battles_today INT,
        battle_timestamps TEXT, 
        fire_coral INT,
        daily_ads INT,
        miniboss_attempts INT,
        gold_multiplier FLOAT,
        premium_features TEXT,
        weekly_contest TEXT,
        portal_stats TEXT,
        pity_counter INT,
        last_epic_pull TIMESTAMP,
        last_legendary_pull TIMESTAMP
    );
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            conn.commit()
    logger.info("Tabla game_data verificada/existente.")



# ... (código anterior sin cambios)

def save_game_data(user_id: str, data: Dict) -> bool:
    """Guarda los datos del usuario en la base de datos."""
    try:
        query = """
        INSERT INTO game_data (
            user_id, mascota_hambre, mascota_energia, mascota_nivel, mascota_oro, mascota_oro_hora, comida,
            ultima_alimentacion, ultima_actualizacion, inventario,
            combat_level, combat_exp, battles_today, fire_coral,
            daily_ads, miniboss_attempts, gold_multiplier,
            premium_features, weekly_contest, portal_stats,
            pity_counter, last_epic_pull, last_legendary_pull, timestamps
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (user_id) DO UPDATE SET
            mascota_hambre = EXCLUDED.mascota_hambre,
            mascota_energia = EXCLUDED.mascota_energia,
            mascota_nivel = EXCLUDED.mascota_nivel,
            mascota_oro = EXCLUDED.mascota_oro,
            mascota_oro_hora = EXCLUDED.mascota_oro_hora,
            comida = EXCLUDED.comida,
            ultima_alimentacion = EXCLUDED.ultima_alimentacion,
            ultima_actualizacion = EXCLUDED.ultima_actualizacion,
            inventario = EXCLUDED.inventario,
            combat_level = EXCLUDED.combat_level,
            combat_exp = EXCLUDED.combat_exp,
            battles_today = EXCLUDED.battles_today,
            fire_coral = EXCLUDED.fire_coral,
            daily_ads = EXCLUDED.daily_ads,
            miniboss_attempts = EXCLUDED.miniboss_attempts,
            gold_multiplier = EXCLUDED.gold_multiplier,
            premium_features = EXCLUDED.premium_features,
            weekly_contest = EXCLUDED.weekly_contest,
            portal_stats = EXCLUDED.portal_stats,
            pity_counter = EXCLUDED.pity_counter,
            last_epic_pull = EXCLUDED.last_epic_pull,
            last_legendary_pull = EXCLUDED.last_legendary_pull,
            timestamps = EXCLUDED.timestamps;
        """
        
        # Preparar el diccionario de timestamps
        timestamps = {
            'battle': data['combat_stats'].get('battle_timestamps', []),
            'daily_reward': data.get('daily_reward_timestamp'),
            'miniboss': data.get('miniboss_timestamp'),
            # Añade aquí más tipos de timestamps según sea necesario
        }
        
        values = (
            str(user_id),
            data['mascota']['hambre'],
            data['mascota']['energia'],
            data['mascota']['nivel'],
            data['mascota']['oro'],
            data['mascota']['oro_hora'],
            data['comida'],
            datetime.fromtimestamp(data['última_alimentación']),
            datetime.fromtimestamp(data['última_actualización']),
            json.dumps(data['inventario']),
            data['combat_stats']['level'],
            data['combat_stats']['exp'],
            data['combat_stats']['battles_today'],
            data['combat_stats']['fire_coral'],
            data.get('daily_ads', 0),
            data.get('miniboss_attempts', 0),
            data.get('gold_multiplier', 1.0),
            json.dumps(data.get('premium_features', {})),
            json.dumps(data.get('weekly_contest', {})),
            json.dumps(data.get('portal_stats', {})),
            data.get('pity_counter', 0),
            datetime.fromtimestamp(data.get('last_epic_pull', 0)) if data.get('last_epic_pull') else None,
            datetime.fromtimestamp(data.get('last_legendary_pull', 0)) if data.get('last_legendary_pull') else None,
            json.dumps(timestamps)  # Nuevo campo timestamps
        )
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, values)
                conn.commit()
        
        logger.info(f"Datos guardados para {user_id}.")
        return True
    except Exception as e:
        logger.error(f"Error guardando datos para {user_id}: {e}")
        return False

def load_game_data(user_id: str) -> Optional[Dict]:
    """Carga los datos del usuario desde la base de datos."""
    try:
        query = """
        SELECT * FROM game_data WHERE user_id = %s;
        """
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (str(user_id),))
                row = cur.fetchone()
                
                if not row:
                    logger.info(f"No hay datos guardados para {user_id}.")
                    return None
                
                # Convertir el resultado a un diccionario
                data = dict(row)
                
                # Convertir campos JSON
                json_fields = ['inventario', 'premium_features', 'weekly_contest', 'portal_stats', 'timestamps']
                for field in json_fields:
                    if field in data and data[field]:
                        try:
                            data[field] = json.loads(data[field])
                        except json.JSONDecodeError:
                            logger.warning(f"Error decodificando {field} para {user_id}. Usando valor por defecto.")
                            data[field] = {} if field != 'inventario' else []
                
                # Convertir timestamps
                timestamp_fields = ['ultima_alimentacion', 'ultima_actualizacion', 'last_epic_pull', 'last_legendary_pull']
                for field in timestamp_fields:
                    if field in data and data[field]:
                        data[field] = data[field].timestamp()
                
                # Estructurar los datos
                structured_data = {
                    "mascota": {
                        "hambre": data['mascota_hambre'],
                        "energia": data['mascota_energia'],
                        "nivel": data['mascota_nivel'],
                        "oro": data['mascota_oro'],
                        "oro_hora": data['mascota_oro_hora']
                    },
                    "comida": data['comida'],
                    "última_alimentación": data['ultima_alimentacion'],
                    "última_actualización": data['ultima_actualizacion'],
                    "inventario": data['inventario'],
                    "combat_stats": {
                        "level": data['combat_level'],
                        "exp": data['combat_exp'],
                        "battles_today": data['battles_today'],
                        "battle_timestamps": data['timestamps'].get('battle', []),
                        "fire_coral": data.get('fire_coral', 0)
                    },
                    "daily_ads": data.get('daily_ads', 0),
                    "miniboss_attempts": data.get('miniboss_attempts', 0),
                    "gold_multiplier": data.get('gold_multiplier', 1.0),
                    "premium_features": data.get('premium_features', {}),
                    "weekly_contest": data.get('weekly_contest', {}),
                    "portal_stats": data.get('portal_stats', {}),
                    "pity_counter": data.get('pity_counter', 0),
                    "last_epic_pull": data.get('last_epic_pull', 0),
                    "last_legendary_pull": data.get('last_legendary_pull', 0),
                    "daily_reward_timestamp": data['timestamps'].get('daily_reward'),
                    "miniboss_timestamp": data['timestamps'].get('miniboss')
                }
                
                return structured_data
    except Exception as e:
        logger.error(f"Error cargando datos para {user_id}: {e}")
        return None


def get_all_user_ids() -> List[str]:
    """Recupera todos los user_ids de la base de datos."""
    try:
        query = """
        SELECT user_id FROM game_data;
        """
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                rows = cur.fetchall()
                
        user_ids = [row[0] for row in rows]
        logger.info(f"Recuperados {len(user_ids)} user_ids de la base de datos.")
        return user_ids
    except Exception as e:
        logger.error(f"Error recuperando user_ids: {e}")
        return []
    
def backup_data(user_id: str, data: Dict) -> bool:
    """Crea una copia de seguridad de los datos del usuario."""
    try:
        # Crear un nombre de archivo único con la fecha y hora actual
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"backup_{user_id}_{timestamp}.json"
        
        # Ruta al directorio de copias de seguridad
        backup_dir = "backups"
        
        # Asegurarse de que el directorio de copias de seguridad existe
        import os
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        # Ruta completa del archivo de copia de seguridad
        backup_path = os.path.join(backup_dir, filename)
        
        # Guardar los datos en el archivo JSON
        with open(backup_path, 'w') as f:
            json.dump(data, f, indent=4)
        
        logger.info(f"Copia de seguridad creada para el usuario {user_id}: {filename}")
        return True
    except Exception as e:
        logger.error(f"Error creando copia de seguridad para el usuario {user_id}: {e}")
        return False

# Crear la tabla al iniciar
create_table()
    