import os
import logging
import requests
from logging.handlers import RotatingFileHandler
from bs4 import BeautifulSoup
from datetime import datetime
from pymongo import MongoClient

BASE_URL = "https://www.proballers.com"

# Configuración de MongoDB
MONGO_URI = "mongodb://localhost:27017/"
DATABASE_NAME = "datips"
mongo_client = MongoClient(MONGO_URI)
db = mongo_client[DATABASE_NAME]



equipos = {
    "Atlanta Hawks": "100/atlanta-hawks",
    "Boston Celtics": "101/boston-celtics",
    "Brooklyn Nets": "116/brooklyn-nets",
    "Charlotte Hornets": "825/charlotte-hornets",
    "Chicago Bulls": "103/chicago-bulls",
    "Cleveland Cavaliers": "104/cleveland-cavaliers",
    "Dallas Mavericks": "105/dallas-mavericks",
    "Denver Nuggets": "106/denver-nuggets",
    "Detroit Pistons": "107/detroit-pistons",
    "Golden State Warriors": "108/golden-state-warriors",
    "Houston Rockets": "109/houston-rockets",
    "Indiana Pacers": "110/indiana-pacers",
    "Los Angeles Clippers": "111/los-angeles-clippers",
    "Los Angeles Lakers": "112/los-angeles-lakers",
    "Memphis Grizzlies": "127/memphis-grizzlies",
    "Miami Heat": "113/miami-heat",
    "Milwaukee Bucks": "114/milwaukee-bucks",
    "Minnesota Timberwolves": "115/minnesota-timberwolves",
    "New Orleans Pelicans": "102/new-orleans-pelicans",
    "New York Knicks": "117/new-york-knicks",
    "Oklahoma City Thunder": "1827/oklahoma-city-thunder",
    "Orlando Magic": "118/orlando-magic",
    "Philadelphia 76ers": "119/philadelphia-76ers",
    "Phoenix Suns": "120/phoenix-suns",
    "Portland Trail Blazers": "121/portland-trail-blazers",
    "Sacramento Kings": "122/sacramento-kings",
    "San Antonio Spurs": "123/san-antonio-spurs",
    "Toronto Raptors": "125/toronto-raptors",
    "Utah Jazz": "126/utah-jazz",
    "Washington Wizards": "128/washington-wizards"
}


# Configurar logger local
logger = logging.getLogger('logger')
logger.setLevel(logging.INFO)
utils_log_file = 'utils/log.json'
file_handler = logging.FileHandler(utils_log_file, mode='w')
log_formatter = logging.Formatter('{"time": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}')
file_handler.setFormatter(log_formatter)
if not logger.hasHandlers():
    logger.addHandler(file_handler)

def get_date(fecha_str):
    """Convierte una fecha en formato '24 oct 2024' o similar en día, mes y año."""
    meses = {
        "ene": "01", "feb": "02", "mar": "03", "abr": "04",
        "may": "05", "jun": "06", "jul": "07", "ago": "08",
        "sep": "09", "oct": "10", "nov": "11", "dic": "12"
    }
    partes = fecha_str.lower().split()
    dia = int(partes[0])
    mes = meses[partes[1]]
    anio = int(partes[2])
    return dia, int(mes), anio

def get_team(day, month, year, opponent):
    """
    Busca en MongoDB la información de un equipo según la fecha y el oponente.
    """
    game = db.games.find_one({
        "date.day": day,
        "date.month": month,
        "date.year": year,
        "$or": [
            {"home": opponent},
            {"away": opponent}
        ]
    })
    if not game:
        logger.warning(f"No se encontró un partido con la fecha {day}/{month}/{year} y oponente {opponent}.")
        return None

    return game["away"] if game["home"] == opponent else game["home"]

def get_player_stats(player_url, player_name):
    """
    Scrapea las estadísticas individuales de un jugador y las devuelve.
    """
    response = requests.get(player_url)
    if response.status_code != 200:
        logger.error(f"Error del servidor al acceder a {player_url}: {response.status_code}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    stats_table = soup.find('table', class_='table')
    if not stats_table:
        logger.warning(f"No se encontró la tabla de estadísticas en {player_url}.")
        return []

    rows = stats_table.find_all('tr')[1:]
    player_stats = []

    for row in rows:
        cols = row.find_all('td')
        try:
            opponent_info = cols[0].get_text(strip=True)
            location = "home" if "vs" in opponent_info else "away"
            opponent = opponent_info.replace("vs", "").replace("@", "").strip()

            date = cols[1].get_text(strip=True)
            day, month, year = get_date(date)

            stats = {
                "name": player_name,
                "date": date,
                "day": day,
                "month": month,
                "year": year,
                "team": get_team(day, month, year, opponent),
                "opponent": opponent,
                "home_or_away": location,
                "PTS": float(cols[3].text.strip()) if cols[3].text.strip().isdigit() else 0,
                "REB": float(cols[4].text.strip()) if cols[4].text.strip().isdigit() else 0,
                "AST": float(cols[5].text.strip()) if cols[5].text.strip().isdigit() else 0,
                "MIN": float(cols[6].text.strip()) if cols[6].text.strip().isdigit() else 0,
                "2M": float(cols[7].text.split('-')[0]) if "-" in cols[7].text else 0,
                "2A": float(cols[7].text.split('-')[1]) if "-" in cols[7].text else 0,
                "3M": float(cols[8].text.split('-')[0]) if "-" in cols[8].text else 0,
                "3A": float(cols[8].text.split('-')[1]) if "-" in cols[8].text else 0,
                "STL": float(cols[16].text.strip()) if cols[16].text.strip().isdigit() else 0,
                "BLK": float(cols[18].text.strip()) if cols[18].text.strip().isdigit() else 0,
                "TO": float(cols[17].get_text(strip=True) or 0),
            
            }

            player_stats.append(stats)
        except Exception as e:
            logger.error(f"Error procesando fila: {e}")
            continue

    return player_stats

def scrape_stats():
    """
    Scrapea estadísticas de equipos y las almacena en MongoDB.
    """
    for team_name, team_url in equipos.items():
        response = requests.get(f"{BASE_URL}/es/baloncesto/equipo/{team_url}")
        if response.status_code != 200:
            logger.error(f"No se pudo acceder a {BASE_URL}/es/baloncesto/equipo/{team_url}")
            continue

        soup = BeautifulSoup(response.text, 'html.parser')
        players = {
            entry.get('title'): f"{BASE_URL}{entry.get('href')}/partidos"
            for entry in soup.find_all('a', class_='list-player-entry stats-player')
        }

        for player_name, player_url in players.items():
            stats = get_player_stats(player_url, player_name)
            for stat in stats:
                db.stats.update_one(
                    # Filtro para identificar si ya existe la estadística
                    {
                        "name": stat["name"],  # Nombre del jugador
                        "date": stat["date"],  # Fecha del partido
                        "opponent": stat["opponent"],  # Equipo contrario
                        "team": stat["team"]  # Equipo del jugador
                    },
                    # Operación de actualización o inserción
                    {
                        "$set": stat  # Reemplaza o inserta las estadísticas completas
                    },
                    upsert=True  # Si no existe, inserta el documento
                )


def needs_update(team_name):
    """
    Verifica si un equipo necesita actualización basándose en los datos específicos
    del equipo almacenados en MongoDB y el calendario de partidos.

    Args:
        team_name (str): Nombre del equipo.

    Returns:
        bool: True si necesita actualización, False en caso contrario.
    """
    team_stats = list(db.stats.find({"team": team_name}).sort("date", -1))
    if not team_stats:
        logger.info(f"No se encontraron datos registrados para el equipo {team_name}. Se requiere actualización.")
        return True

    last_game_date = team_stats[0]["date"]
    last_game_date = datetime.strptime(last_game_date, "%Y-%m-%d")

    today = datetime.today()
    upcoming_games = list(db.games.find({
        "date": {"$gt": last_game_date, "$lt": today},
        "$or": [{"home": team_name}, {"away": team_name}]
    }))

    if upcoming_games:
        logger.info(f"El equipo {team_name} tiene partidos pendientes que necesitan actualización.")
        return True

    logger.info(f"{team_name} está actualizado hasta {last_game_date}. No se encontraron partidos jugados desde entonces.")
    return False

def calculate_opponent_stats():
    """
    Genera estadísticas de rendimiento de los jugadores que han jugado contra cada equipo,
    utilizando los datos consolidados en MongoDB desde la colección `players.stats`.
    """
    # Obtener todos los jugadores y sus estadísticas
    players = list(db.players.find({}, {"name": 1, "stats": 1}))

    opponent_stats = {}
    team_totals = {}

    for player in players:
        player_name = player["name"]
        stats = player.get("stats", [])

        for game in stats:
            opponent = game.get("opponent")
            team = game.get("team")

            if not opponent or not team:
                logger.warning(f"Juego inválido encontrado: {game}")
                continue

            # Inicializar estadísticas totales por equipo
            if team not in team_totals:
                team_totals[team] = {"PTS": 0, "REB": 0, "AST": 0, "STL": 0, "BLK": 0, "TO": 0}

            # Actualizar estadísticas totales del equipo
            for stat in ["PTS", "REB", "AST", "STL", "BLK", "TO"]:
                team_totals[team][stat] += game.get(stat, 0)

            # Inicializar estadísticas de los oponentes
            if opponent not in opponent_stats:
                opponent_stats[opponent] = {
                    "PTS": 0,
                    "REB": 0,
                    "AST": 0,
                    "STL": 0,
                    "BLK": 0,
                    "TO": 0,
                    "games": []
                }

            # Actualizar estadísticas de los oponentes
            for stat in ["PTS", "REB", "AST", "STL", "BLK", "TO"]:
                opponent_stats[opponent][stat] += game.get(stat, 0)

            # Agregar detalles del partido
            line = game.copy()
            line["player"] = player_name

            opponent_stats[opponent]["games"].append(line)

    # Reemplazar datos en MongoDB
    db.opponent_stats.replace_one(
        {},
        {"opponents": opponent_stats, "team_totals": team_totals},
        upsert=True
    )
    logger.info("Estadísticas por oponente calculadas y almacenadas correctamente.")

def calculate_team_game_stats():
    """
    Genera estadísticas acumuladas por partido para cada equipo y las almacena en MongoDB,
    utilizando la colección `players.stats`.
    """
    # Obtener todos los jugadores y sus estadísticas
    players = list(db.players.find({}, {"name": 1, "stats": 1}))

    team_game_stats = {}
    team_totals = {}

    for player in players:
        player_name = player["name"]
        stats = player.get("stats", [])

        for game in stats:
            team = game.get("team")
            game_date = game.get("date")

            if not team or not game_date:
                logger.warning(f"Juego inválido encontrado: {game}")
                continue

            # Inicializar estadísticas totales por equipo
            if team not in team_totals:
                team_totals[team] = {"PTS": 0, "REB": 0, "AST": 0, "STL": 0, "BLK": 0, "TO": 0}

            # Inicializar estadísticas de partidos del equipo
            if team not in team_game_stats:
                team_game_stats[team] = {}

            if game_date not in team_game_stats[team]:
                team_game_stats[team][game_date] = {
                    "date": game_date,
                    "opponent": game.get("opponent"),
                    "home_or_away": game.get("home_or_away"),
                    "PTS": 0,
                    "REB": 0,
                    "AST": 0,
                    "STL": 0,
                    "BLK": 0,
                    "TO": 0,
                    "players_count": 0,
                    "team": team
                }

            # Actualizar estadísticas totales y por partido
            for stat in ["PTS", "REB", "AST", "STL", "BLK", "TO"]:
                team_totals[team][stat] += game.get(stat, 0)
                team_game_stats[team][game_date][stat] += game.get(stat, 0)

            # Incrementar el conteo de jugadores para el partido
            team_game_stats[team][game_date]["players_count"] += 1

    # Reemplazar datos en MongoDB
    db.team_game_stats.replace_one(
        {},
        {"team_games": team_game_stats, "team_totals": team_totals},
        upsert=True
    )
    logger.info("Estadísticas de partidos por equipo calculadas y almacenadas correctamente.")

def calculate_stats():
    """
    Calcula estadísticas de rendimiento para los equipos (team_game_stats) y los oponentes (opponent_stats),
    utilizando los datos consolidados en MongoDB desde la colección `stats`.
    """
    try:
        # Verificar conexión a MongoDB y existencia de la colección `stats`
        collections = db.list_collection_names()
        if "stats" not in collections:
            logger.error("La colección 'stats' no existe en la base de datos.")
            return
        
        stats_data = list(db.stats.find())
        if not stats_data:
            logger.warning("No se encontraron estadísticas en la colección 'stats'.")
            return
        
        logger.info(f"Se encontraron {len(stats_data)} registros de estadísticas en la colección 'stats'.")
    except Exception as e:
        logger.error(f"Error al obtener datos de la colección 'stats': {e}")
        return

    opponent_stats = {}
    team_game_stats = {}
    team_totals = {}

    # Procesar estadísticas de cada juego en `stats`
    for game in stats_data:
        player_name = game.get("name", "Unknown Player")
        opponent = game.get("opponent")
        team = game.get("team")
        game_date = game.get("date")

        if not team or not opponent or not game_date:
            logger.warning(f"Juego inválido encontrado para el jugador {player_name}: {game}")
            continue

        # Inicializar estadísticas totales por equipo
        if team not in team_totals:
            team_totals[team] = {"PTS": 0, "REB": 0, "AST": 0, "STL": 0, "BLK": 0, "TO": 0}

        # Inicializar estadísticas de partidos del equipo
        if team not in team_game_stats:
            team_game_stats[team] = {}

        if game_date not in team_game_stats[team]:
            team_game_stats[team][game_date] = {
                "date": game_date,
                "opponent": opponent,
                "home_or_away": game.get("home_or_away"),
                "PTS": 0,
                "REB": 0,
                "AST": 0,
                "STL": 0,
                "BLK": 0,
                "TO": 0,
                "players_count": 0,
                "team": team
            }

        # Actualizar estadísticas totales y por partido
        for stat in ["PTS", "REB", "AST", "STL", "BLK", "TO"]:
            value = game.get(stat, 0)
            team_totals[team][stat] += value
            team_game_stats[team][game_date][stat] += value

        # Incrementar el conteo de jugadores para el partido
        team_game_stats[team][game_date]["players_count"] += 1

        # Inicializar estadísticas de los oponentes
        if opponent not in opponent_stats:
            opponent_stats[opponent] = {
                "PTS": 0,
                "REB": 0,
                "AST": 0,
                "STL": 0,
                "BLK": 0,
                "TO": 0,
                "games": []
            }

        # Actualizar estadísticas de los oponentes
        for stat in ["PTS", "REB", "AST", "STL", "BLK", "TO"]:
            opponent_stats[opponent][stat] += game.get(stat, 0)

        # Agregar detalles del partido al oponente
        line = game.copy()
        line["player"] = player_name
        opponent_stats[opponent]["games"].append(line)

    # Reemplazar datos en MongoDB
    try:
        db.team_game_stats.replace_one(
            {"_id": "team_game_stats"},
            {"_id": "team_game_stats", "team_games": team_game_stats, "team_totals": team_totals},
            upsert=True
        )
        logger.info("Estadísticas de partidos por equipo (team_game_stats) calculadas y almacenadas correctamente.")
    except Exception as e:
        logger.error(f"Error al guardar datos en 'team_game_stats': {e}")

    try:
        db.opponent_stats.replace_one(
            {"_id": "opponent_stats"},
            {"_id": "opponent_stats", "opponents": opponent_stats},
            upsert=True
        )
        logger.info("Estadísticas de rendimiento por oponente (opponent_stats) calculadas y almacenadas correctamente.")
    except Exception as e:
        logger.error(f"Error al guardar datos en 'opponent_stats': {e}")


def calculate_all_stats():
    """
    Calcula tanto las estadísticas por oponente como las acumuladas por equipo.
    """
    # calculate_opponent_stats()
    # calculate_team_game_stats()
    calculate_stats()
    logger.info("Cálculo completo de estadísticas.")

def initialize_collections():
    """
    Crea las colecciones necesarias en MongoDB si no existen.
    """
    required_collections = ["players", "stats", "teams", "games", "opponent_stats", "team_game_stats"]
    for collection_name in required_collections:
        if collection_name not in db.list_collection_names():
            db[collection_name].insert_one({"init": True})  # Inserta un documento inicial
            logger.info(f"Colección '{collection_name}' creada.")

if __name__ == "__main__":
    scrape_stats()

#TODO: cambiar el uso de variable por scraping directo en la web o moverlo a un archivo de configuracion


