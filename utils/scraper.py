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

def calculate_opponent_and_team_stats():
    """
    Calcula estadísticas agrupadas por equipo (team_game_stats) y oponente (opponent_stats).
    Inserta los datos agrupados en las colecciones correspondientes y calcula totales y promedios
    (general, en casa y fuera) para cada equipo y oponente.
    """
    try:
        # Obtener estadísticas directamente de la colección `stats`
        stats = list(db.stats.find({}, {
            "name": 1,
            "date": 1,
            "opponent": 1,
            "team": 1,
            "home_or_away": 1,
            "PTS": 1,
            "REB": 1,
            "AST": 1,
            "2A": 1,
            "2M": 1,
            "3A": 1,
            "3M": 1,
            "STL": 1,
            "BLK": 1,
            "TO": 1
        }))

        if not stats:
            logger.warning("No se encontraron datos en la colección 'stats'.")
            return

        logger.info(f"Se encontraron estadísticas de {len(stats)} registros en la colección 'stats'.")
    except Exception as e:
        logger.error(f"Error al obtener datos de la colección 'stats': {e}")
        return

    # Inicializar estructuras
    opponent_stats = {}
    team_game_stats = {}
    team_game_dates = {}
    opponent_game_dates = {}

    # Agrupar estadísticas por equipo y oponente
    for game in stats:
        try:
            team = game["team"]
            opponent = game["opponent"]
            game_date = game["date"]
            home_or_away = game["home_or_away"]

            if not team or not opponent or not game_date or home_or_away not in ["home", "away"]:
                logger.warning(f"Juego inválido encontrado: {game}")
                continue

            # Registrar fechas únicas por equipo y oponente
            if team not in team_game_dates:
                team_game_dates[team] = set()
            if opponent not in opponent_game_dates:
                opponent_game_dates[opponent] = set()

            team_game_dates[team].add(game_date)
            opponent_game_dates[opponent].add(game_date)

            # Inicializar estructura de team_game_stats
            if team not in team_game_stats:
                team_game_stats[team] = {"team_games": {}}
            if game_date not in team_game_stats[team]["team_games"]:
                team_game_stats[team]["team_games"][game_date] = {
                    "date": game_date,
                    "opponent": opponent,
                    "home_or_away": home_or_away,
                    "PTS": 0,
                    "REB": 0,
                    "AST": 0,
                    "2A": 0,
                    "2M": 0,
                    "3A": 0,
                    "3M": 0,
                    "STL": 0,
                    "BLK": 0,
                    "TO": 0
                }

            # Inicializar estructura de opponent_stats
            if opponent not in opponent_stats:
                opponent_stats[opponent] = {"opponent_games": {}}
            if game_date not in opponent_stats[opponent]["opponent_games"]:
                opponent_stats[opponent]["opponent_games"][game_date] = {}

            if team not in opponent_stats[opponent]["opponent_games"][game_date]:
                opponent_stats[opponent]["opponent_games"][game_date][team] = {
                    "PTS": 0,
                    "REB": 0,
                    "AST": 0,
                    "2A": 0,
                    "2M": 0,
                    "3A": 0,
                    "3M": 0,
                    "STL": 0,
                    "BLK": 0,
                    "TO": 0
                }

            # Actualizar estadísticas del equipo y del oponente
            for stat in ["PTS", "REB", "AST", "2A", "2M", "3A", "3M", "STL", "BLK", "TO"]:
                value = game.get(stat, 0)
                if not isinstance(value, (int, float)):
                    logger.warning(f"Valor inválido para la estadística {stat} en el juego: {game}")
                    continue

                team_game_stats[team]["team_games"][game_date][stat] += value
                opponent_stats[opponent]["opponent_games"][game_date][team][stat] += value

        except KeyError as e:
            logger.error(f"Clave faltante: {e} en el juego: {game}")
            continue

    # Calcular totales y promedios por equipo
    team_totals = {}
    for team, game_dates in team_game_dates.items():
        total_stats = {stat: 0 for stat in ["PTS", "REB", "AST", "2A", "2M", "3A", "3M", "STL", "BLK", "TO"]}
        home_stats = {stat: 0 for stat in total_stats}
        away_stats = {stat: 0 for stat in total_stats}
        home_games = 0
        away_games = 0

        for game_date in game_dates:
            stats = team_game_stats[team]["team_games"][game_date]
            for stat in total_stats:
                total_stats[stat] += stats[stat]
                if stats["home_or_away"] == "home":
                    home_stats[stat] += stats[stat]
                else:
                    away_stats[stat] += stats[stat]

        home_games = len([date for date in game_dates if team_game_stats[team]["team_games"][date]["home_or_away"] == "home"])
        away_games = len([date for date in game_dates if team_game_stats[team]["team_games"][date]["home_or_away"] == "away"])

        team_totals[team] = {
            "totals": total_stats,
            "average": {stat: total_stats[stat] / len(game_dates) for stat in total_stats},
            "home_average": {stat: home_stats[stat] / home_games if home_games > 0 else 0 for stat in home_stats},
            "away_average": {stat: away_stats[stat] / away_games if away_games > 0 else 0 for stat in away_stats}
        }

    # Calcular totales y promedios por oponente
    opponent_totals = {}
    for opponent, game_dates in opponent_game_dates.items():
        total_stats = {stat: 0 for stat in ["PTS", "REB", "AST", "2A", "2M", "3A", "3M", "STL", "BLK", "TO"]}
        home_stats = {stat: 0 for stat in total_stats}
        away_stats = {stat: 0 for stat in total_stats}
        home_games = 0
        away_games = 0

        for game_date in game_dates:
            for team, stats in opponent_stats[opponent]["opponent_games"][game_date].items():
                for stat in total_stats:
                    total_stats[stat] += stats[stat]
                    if team_game_stats[team]["team_games"][game_date]["home_or_away"] == "away":
                        home_stats[stat] += stats[stat]
                    else:
                        away_stats[stat] += stats[stat]

        home_games = len([date for date in game_dates if any(
            team_game_stats[team]["team_games"][date]["home_or_away"] == "away"
            for team in opponent_stats[opponent]["opponent_games"][date]
        )])
        away_games = len([date for date in game_dates if any(
            team_game_stats[team]["team_games"][date]["home_or_away"] == "home"
            for team in opponent_stats[opponent]["opponent_games"][date]
        )])

        opponent_totals[opponent] = {
            "totals": total_stats,
            "average": {stat: total_stats[stat] / len(game_dates) for stat in total_stats},
            "home_average": {stat: home_stats[stat] / home_games if home_games > 0 else 0 for stat in home_stats},
            "away_average": {stat: away_stats[stat] / away_games if away_games > 0 else 0 for stat in away_stats}
        }

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
            {"_id": "opponent_stats", "opponents": opponent_stats, "opponent_totals": opponent_totals},
            upsert=True
        )
        logger.info("Estadísticas de rendimiento por oponente (opponent_stats) calculadas y almacenadas correctamente.")
    except Exception as e:
        logger.error(f"Error al guardar datos en 'opponent_stats': {e}")


def calculate_all_stats():
    """
    Calcula tanto las estadísticas por oponente como las acumuladas por equipo.
    """
    calculate_opponent_and_team_stats()
    logger.info("Cálculo completo de estadísticas.")

def initialize_collections():
    """
    Crea las colecciones necesarias en MongoDB si no existen.
    """
    required_collections = ["stats", "games", "opponent_stats", "team_game_stats"]
    for collection_name in required_collections:
        if collection_name not in db.list_collection_names():
            db[collection_name].insert_one({"init": True})  # Inserta un documento inicial
            logger.info(f"Colección '{collection_name}' creada.")

if __name__ == "__main__":
    scrape_stats()

#TODO: cambiar el uso de variable por scraping directo en la web o moverlo a un archivo de configuracion


