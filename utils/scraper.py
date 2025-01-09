import os
import json
import logging
import requests
from bson import ObjectId
from logging.handlers import RotatingFileHandler
from bs4 import BeautifulSoup
from datetime import datetime
from pymongo import MongoClient
from pymongo.errors import CollectionInvalid

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
    """Convierte una fecha en formato 'Nov 21, 2024' o similar en día, mes y año."""
    try:
        # Convertir la cadena a un objeto datetime usando el formato adecuado
        fecha = datetime.strptime(fecha_str, "%b %d, %Y")
    except ValueError as e:
        logger.error(f"Formato de fecha no reconocido: {fecha_str} - Error: {e}")
        raise
    return fecha.day, fecha.month, fecha.year

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

def create_player_entry(player_name, player_url):
    """
    Crea un documento en la colección `players` con el nombre del jugador y su posición.
    Scrapea el perfil del jugador para determinar la posición.
    """
    response = requests.get(player_url)
    if response.status_code != 200:
        logger.error(f"Error al acceder al perfil del jugador {player_name} en {player_url}: {response.status_code}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    profile_text = soup.get_text().lower()

    # Palabras clave para definir la posición del jugador
    positions = {
        "center": "C",
        "power forward": "PF",
        "small forward": "SF",
        "point guard": "PG",
        "shooting guard": "SG"
    }

    player_position = "Unknown"
    for position, abbreviation in positions.items():
        if position in profile_text:
            player_position = abbreviation
            break

    # Insertar el jugador en la colección `players`
    db.players.insert_one({
        "name": player_name,
        "position": player_position,
        "url": player_url
    })
    logger.info(f"Se creó la entrada para el jugador {player_name} con la posición {player_position}.")



def get_player_stats(player_url, player_name):
    """
    Scrapea las estadísticas individuales de un jugador y las devuelve.
    """
   # Verificar si la colección `players` existe
    if "players" not in db.list_collection_names():
        try:
            db.create_collection("players")
            logger.info("Se creó la colección 'players'.")
        except CollectionInvalid:
            logger.error("Error al crear la colección 'players'.")

    # Verificar si el jugador ya existe en la colección
    player_entry = db.players.find_one({"name": player_name})
    if not player_entry:
        logger.info(f"No se encontró entrada para el jugador {player_name}. Creando una nueva entrada...")
        create_player_entry(player_name, player_url)        
        player_entry = db.players.find_one({"name": player_name})  # Recuperar la entrada recién creada

    # Obtener la posición del jugador
    player_position = player_entry.get("position", "Unknown")
   
   
    response = requests.get(f"{player_url}/games")
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
                "position": player_position, 
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
        # TODO: revisar needs_update para comprobar correctamente la ultima fecha y hora del calendario, de mongobd y la actual
        if not needs_update(team_name):
            logger.info(f"Saltando actualización de {team_name}.")
            continue
        response = requests.get(f"{BASE_URL}/basketball/team/{team_url}")
        if response.status_code != 200:
            logger.error(f"No se pudo acceder a {BASE_URL}/basketball/team/{team_url}")
            continue

        soup = BeautifulSoup(response.text, 'html.parser')
        players = {
            entry.get('title'): f"{BASE_URL}{entry.get('href')}"
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
    Determina si un equipo necesita ser actualizado.
    """
    try:
        # Obtener las estadísticas más recientes del equipo
        team_stats = list(db.stats.find({"team": team_name}).sort("date", -1))
        if not team_stats:
            logger.info(f"No se encontraron estadísticas para {team_name}. Necesita actualización.")
            return True

        # Obtener la última fecha del partido
        last_game_date = team_stats[0]["date"]  # last_game_date debería ser un objeto
        if isinstance(last_game_date, str):  # Si es un string, convertirlo
            last_game_date = json.loads(last_game_date)

        # Convertir la fecha a un objeto datetime
        last_game_date = datetime(
            year=last_game_date["year"],
            month=last_game_date["month"],
            day=last_game_date["day"]
        )

        # Obtener la fecha actual
        today = datetime.today()

        # Verificar si hay partidos después de la última fecha registrada
        upcoming_games = list(db.games.find({
            "date.year": {"$gte": last_game_date.year},
            "date.month": {"$gte": last_game_date.month},
            "date.day": {"$gte": last_game_date.day},
            "$or": [{"home": team_name}, {"away": team_name}]
        }))

        if upcoming_games:
            logger.info(f"El equipo {team_name} tiene partidos pendientes.")
            return True

        logger.info(f"El equipo {team_name} está actualizado hasta {last_game_date}.")
        return False

    except Exception as e:
        logger.error(f"Error al verificar la necesidad de actualización para {team_name}: {e}")
        return True

    logger.info(f"{team_name} está actualizado hasta {last_game_date}. No se encontraron partidos jugados desde entonces.")
    return False

def calculate_stat_rankings():
    """
    Calcula los rankings de estadísticas (top average, top home, top away) para equipos y oponentes.
    Inserta los resultados en una colección de MongoDB llamada 'rankings'.
    """
    try:
        # Obtener team_totals y opponent_totals de MongoDB
        team_totals = db.team_game_stats.find_one({"_id": "team_game_stats"}).get("team_totals", {})
        opponent_totals = db.opponent_stats.find_one({"_id": "opponent_stats"}).get("opponent_totals", {})

        # Inicializar listas para team y opponent
        team_rankings = {"top_average": {}, "top_home": {}, "top_away": {}}
        opponent_rankings = {"top_average": {}, "top_home": {}, "top_away": {}}

        # Estadísticas que se ordenarán
        stats_list = ["PTS", "REB", "AST", "2A", "2M", "3A", "3M", "STL", "BLK", "TO"]

        # Inicializar estructuras para almacenar rankings
        for ranking_type in ["top_average", "top_home", "top_away"]:
            for stat in stats_list:
                team_rankings[ranking_type][stat] = []
                opponent_rankings[ranking_type][stat] = []

        # Calcular rankings para teams
        for ranking_type, stat_key in [("top_average", "average"), ("top_home", "home_average"), ("top_away", "away_average")]:
            for stat in stats_list:
                # Ordenar los equipos por la estadística correspondiente en orden descendente
                sorted_teams = sorted(team_totals.items(), key=lambda x: x[1][stat_key][stat], reverse=True)
                for position, (team, stats) in enumerate(sorted_teams, start=1):
                    team_rankings[ranking_type][stat].append({"team": team, "position": position, "value": stats[stat_key][stat]})

        # Calcular rankings para opponents
        for ranking_type, stat_key in [("top_average", "average"), ("top_home", "home_average"), ("top_away", "away_average")]:
            for stat in stats_list:
                # Ordenar los oponentes por la estadística correspondiente en orden descendente
                sorted_opponents = sorted(opponent_totals.items(), key=lambda x: x[1][stat_key][stat], reverse=True)
                for position, (opponent, stats) in enumerate(sorted_opponents, start=1):
                    opponent_rankings[ranking_type][stat].append({"opponent": opponent, "position": position, "value": stats[stat_key][stat]})

        # Preparar los datos para la colección 'rankings'
        rankings_data = {
            "team_rankings": team_rankings,
            "opponent_rankings": opponent_rankings
        }

        # Insertar o actualizar los datos en la colección 'rankings'
        try:
            db.rankings.replace_one(
                {"_id": "rankings"},
                {"_id": "rankings", **rankings_data},
                upsert=True
            )
            logger.info("Rankings calculados y almacenados correctamente en la colección 'rankings'.")
        except Exception as e:
            logger.error(f"Error al guardar datos en la colección 'rankings': {e}")

        return team_rankings, opponent_rankings

    except Exception as e:
        logger.error(f"Error al calcular los rankings de estadísticas: {e}")
        return None, None

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
                    "TO": 0,
                    "players": []
                }

            # Inicializar estructura de opponent_stats
            if opponent not in opponent_stats:
                opponent_stats[opponent] = {"opponent_games": {}}
            if game_date not in opponent_stats[opponent]["opponent_games"]:
                opponent_stats[opponent]["opponent_games"][game_date] = {}

            if team not in opponent_stats[opponent]["opponent_games"][game_date]:
                opponent_stats[opponent]["opponent_games"][game_date][team] = {
                    "date": game_date,
                    "PTS": 0,
                    "REB": 0,
                    "AST": 0,
                    "2A": 0,
                    "2M": 0,
                    "3A": 0,
                    "3M": 0,
                    "STL": 0,
                    "BLK": 0,
                    "TO": 0,
                    "players": []
                }

            # Actualizar estadísticas del equipo y del oponente
            for stat in ["PTS", "REB", "AST", "2A", "2M", "3A", "3M", "STL", "BLK", "TO"]:
                value = game.get(stat, 0)
                if not isinstance(value, (int, float)):
                    logger.warning(f"Valor inválido para la estadística {stat} en el juego: {game}")
                    continue

                team_game_stats[team]["team_games"][game_date][stat] += value
                opponent_stats[opponent]["opponent_games"][game_date][team][stat] += value
                
            team_game_stats[team]["team_games"][game_date]["players"].append(game["name"])
            opponent_stats[opponent]["opponent_games"][game_date][team]["players"].append(game["name"]) 
                

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

def calculate_stats_by_position():
    """
    Calcula estadísticas agrupadas por posición (PG, SG, SF, PF, C) para equipos y oponentes.
    Los resultados se almacenan en las colecciones `team_game_stats` y `opponent_stats`,
    bajo los campos `team_totals_by_position` y `opponent_totals_by_position`.
    """
    try:
        # Obtener estadísticas directamente de la colección `stats`
        stats = list(db.stats.find({}, {
            "name": 1,
            "position": 1,
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
            "TO": 1,
            "day": 1,
            "month": 1,
            "year": 1
        }))

        # Leer equipos del diccionario global
        team_names = set(equipos.keys())

        # Filtrar stats solo para equipos válidos
        stats = [stat for stat in stats if stat["team"] in team_names and stat["opponent"] in team_names]

        if not stats:
            logger.warning("No se encontraron estadísticas válidas en la colección 'stats'.")
            return

        logger.info(f"Se encontraron {len(stats)} registros válidos en la colección 'stats'.")

    except Exception as e:
        logger.error(f"Error al obtener datos de la colección 'stats': {e}")
        return

    
    positions = ["PG", "SG", "SF", "PF", "C", "Unknown"]
    stats_keys = ["PTS", "REB", "AST", "2A", "2M", "3A", "3M", "STL", "BLK", "TO"]

    def initialize_position_structure():
        """Estructura base para almacenar datos por posición."""
        return {
            "totals": {pos: {"stats": {key: 0 for key in stats_keys}, "games": set()} for pos in positions},
            "average_home": {pos: {"stats": {key: 0 for key in stats_keys}, "games": set()} for pos in positions},
            "average_away": {pos: {"stats": {key: 0 for key in stats_keys}, "games": set()} for pos in positions},
            "average": {pos: {"stats": {key: 0 for key in stats_keys}, "games": set()} for pos in positions}
        }

    # Inicializar estructuras
    team_totals_by_position = {team: initialize_position_structure() for team in team_names}
    opponent_totals_by_position = {team: initialize_position_structure() for team in team_names}


    # Procesar cada registro en stats
    for game in stats:
        try:
            position = game.get("position")
            if position not in positions:
                continue

            day = game["day"]
            month = game["month"]
            year = game["year"]
            date_key = (day, month, year)

            home_or_away = game["home_or_away"]
            team = game["team"]
            opponent = game["opponent"]

            for stat_key in stats_keys:
                value = game.get(stat_key, 0)
                if not isinstance(value, (int, float)):
                    continue

                # Procesar datos del equipo
                team_totals_by_position[team]["totals"][position]["stats"][stat_key] += value
                team_totals_by_position[team]["totals"][position]["games"].add(date_key)

                if home_or_away == "home":
                    team_totals_by_position[team]["average_home"][position]["stats"][stat_key] += value
                    team_totals_by_position[team]["average_home"][position]["games"].add(date_key)
                elif home_or_away == "away":
                    team_totals_by_position[team]["average_away"][position]["stats"][stat_key] += value
                    team_totals_by_position[team]["average_away"][position]["games"].add(date_key)

                # Procesar datos del oponente
                opponent_totals_by_position[opponent]["totals"][position]["stats"][stat_key] += value
                opponent_totals_by_position[opponent]["totals"][position]["games"].add(date_key)

                if home_or_away == "home":
                    opponent_totals_by_position[opponent]["average_away"][position]["stats"][stat_key] += value
                    opponent_totals_by_position[opponent]["average_away"][position]["games"].add(date_key)
                elif home_or_away == "away":
                    opponent_totals_by_position[opponent]["average_home"][position]["stats"][stat_key] += value
                    opponent_totals_by_position[opponent]["average_home"][position]["games"].add(date_key)

        except KeyError as e:
            logger.warning(f"Clave faltante en el registro: {e}")
            continue

    # Calcular promedios
    # Calcular promedios
    def calculate_averages(data):
        """Calcula los promedios basados en los totales y el número de juegos únicos."""
        for entity, positions_data in data.items():
            for position, stats_data in positions_data["totals"].items():
                total_games = len(stats_data["games"])
                if total_games > 0:
                    for key in stats_keys:
                        positions_data["average"][position]["stats"][key] = stats_data["stats"][key] / total_games

                for avg_type in ["average_home", "average_away"]:
                    games_count = len(positions_data[avg_type][position]["games"])
                    if games_count > 0:
                        for key in stats_keys:
                            positions_data[avg_type][position]["stats"][key] /= games_count

        # Convertir sets a listas para almacenamiento en MongoDB
        for entity, positions_data in data.items():
            for position in positions:
                positions_data["totals"][position]["games"] = list(positions_data["totals"][position]["games"])
                positions_data["average_home"][position]["games"] = list(positions_data["average_home"][position]["games"])
                positions_data["average_away"][position]["games"] = list(positions_data["average_away"][position]["games"])
                positions_data["average"][position]["games"] = list(positions_data["average"][position]["games"])

    calculate_averages(team_totals_by_position)
    calculate_averages(opponent_totals_by_position)

    # Guardar en MongoDB
    try:
        db.team_game_stats.update_one(
            {"_id": "team_totals_by_position"},
            {"$set": {"team_totals_by_position": team_totals_by_position}},
            upsert=True
        )
        logger.info("Estadísticas de equipos por posición calculadas correctamente.")
    except Exception as e:
        logger.error(f"Error al guardar datos en 'team_game_stats': {e}")

    try:
        db.opponent_stats.update_one(
            {"_id": "opponent_totals_by_position"},
            {"$set": {"opponent_totals_by_position": opponent_totals_by_position}},
            upsert=True
        )
        logger.info("Estadísticas de oponentes por posición calculadas correctamente.")
    except Exception as e:
        logger.error(f"Error al guardar datos en 'opponent_stats': {e}")

def calculate_team_statistics():
    """
    Genera una colección `team_statistics` con información de partidos ganados y perdidos de cada equipo
    utilizando exclusivamente la estructura de `team_game_stats` y validando los puntos con el oponente.
    """
    try:
        # Verificar si la colección existe, si no, crearla
        if "team_statistics" not in db.list_collection_names():
            db.create_collection("team_statistics")
            logger.info("Se creó la colección 'team_statistics'.")

        # Obtener los datos de `team_game_stats`
        team_game_stats = db.team_game_stats.find_one({"_id": "team_game_stats"})
        if not team_game_stats:
            logger.warning("No se encontraron datos en la colección 'team_game_stats'.")
            return

        # Extraer los datos de los equipos
        team_games = team_game_stats.get("team_games", {})

        # Diccionario para almacenar estadísticas por equipo
        team_stats = {}

        for team, team_data in team_games.items():
            games = team_data.get("team_games", {})

            # Inicializar estadísticas para el equipo
            team_stats[team] = {
                "home_wins": 0,
                "home_losses": 0,
                "away_wins": 0,
                "away_losses": 0,
                "last_15_home": [],
                "last_15_away": [],
                "last_5_results": "",
                "last_5_home_results": "",
                "last_5_away_results": ""
            }

            results = []
            home_results = []
            away_results = []

            for date, game in games.items():
                home_or_away = game.get("home_or_away")
                opponent = game.get("opponent")
                pts = int(game.get("PTS", 0))

                # Validar puntos del oponente
                opponent_data = team_games.get(opponent, {}).get("team_games", {}).get(date, {})
                opponent_pts = int(opponent_data.get("PTS", 0))

                # Determinar resultado del partido
                result = "W" if pts > opponent_pts else "L"

                if home_or_away == "home":
                    if result == "W":
                        team_stats[team]["home_wins"] += 1
                    else:
                        team_stats[team]["home_losses"] += 1

                    # Agregar a la lista de últimos 15 partidos en casa
                    team_stats[team]["last_15_home"].append({
                        "date": date,
                        "opponent": opponent,
                        "score": {"team": pts, "opponent": opponent_pts},
                        "REB": game.get("REB", 0),
                        "AST": game.get("AST", 0),
                        "STL": game.get("STL", 0),
                        "BLK": game.get("BLK", 0),
                        "TO": game.get("TO", 0),
                    })
                    home_results.append(result)

                elif home_or_away == "away":
                    if result == "W":
                        team_stats[team]["away_wins"] += 1
                    else:
                        team_stats[team]["away_losses"] += 1

                    # Agregar a la lista de últimos 15 partidos fuera
                    team_stats[team]["last_15_away"].append({
                        "date": date,
                        "opponent": opponent,
                        "score": {"team": pts, "opponent": opponent_pts},
                        "REB": game.get("REB", 0),
                        "AST": game.get("AST", 0),
                        "STL": game.get("STL", 0),
                        "BLK": game.get("BLK", 0),
                        "TO": game.get("TO", 0),
                    })
                    away_results.append(result)

                results.append(result)

                # Mantener solo los últimos 15 partidos
                team_stats[team]["last_15_home"] = team_stats[team]["last_15_home"][-15:]
                team_stats[team]["last_15_away"] = team_stats[team]["last_15_away"][-15:]

            # Generar historial de los últimos 5 partidos
            team_stats[team]["last_5_results"] = " ".join(results[-5:])
            team_stats[team]["last_5_home_results"] = " ".join(home_results[-5:])
            team_stats[team]["last_5_away_results"] = " ".join(away_results[-5:])

        # Guardar estadísticas en MongoDB
        for team, stats in team_stats.items():
            db.team_statistics.update_one(
                {"team": team},
                {"$set": stats},
                upsert=True
            )

        logger.info("Estadísticas de equipos generadas y almacenadas correctamente en 'team_statistics'.")

    except Exception as e:
        logger.error(f"Error al generar estadísticas de equipos: {e}")





def calculate_all_stats():
    """
    Calcula tanto las estadísticas por oponente como las acumuladas por equipo.
    """
    calculate_opponent_and_team_stats()
    calculate_stat_rankings()
    calculate_stats_by_position()
    calculate_position_rankings()
    calculate_team_statistics()
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

def get_player_team_opponent_data(team, player_name, home_or_away, opponent):
    """
    Devuelve los datos necesarios para crear un gráfico y diferentes marcadores.
    """
    try:
        # Obtener la posición del jugador desde la colección `players`
        player = db.players.find_one({"name": player_name}, {"position": 1})
        if not player or "position" not in player:
            return {"error": f"Posición no encontrada para el jugador {player_name}"}
        position = player["position"]

        # Obtener las estadísticas del jugador en el equipo
        player_stats = list(db.stats.find({"name": player_name, "team": team}))
        
        # Obtener las estadísticas del jugador con home_or_away en el equipo
        player_stats_home_or_away = list(db.stats.find({"name": player_name, "team": team, "home_or_away": home_or_away}))

        # Obtener las posiciones de rankings
        rankings = db.rankings.find_one({}, {"team_rankings": 1, "opponent_rankings": 1})
        if not rankings:
            return {"error": "Rankings no encontrados"}
        
        # Procesar team_rankings
        team_rankings = rankings.get("team_rankings", {})
        team_top_average = {}
        team_top_home_or_away = {}

        if "top_average" in team_rankings:
            for stat, teams in team_rankings["top_average"].items():
                for index, team_data in enumerate(teams):
                    if team_data["team"] == team:
                        team_top_average[stat] = {
                            "position": index + 1,
                            "value": team_data["value"]
                        }

        if f"top_{home_or_away}" in team_rankings:
            for stat, teams in team_rankings[f"top_{home_or_away}"].items():
                for index, team_data in enumerate(teams):
                    if team_data["team"] == team:
                        team_top_home_or_away[stat] = {
                            "position": index + 1,
                            "value": team_data["value"]
                        }

        # Procesar opponent_rankings
        opponent_rankings = rankings.get("opponent_rankings", {})
        opponent_top_average = {}
        opponent_top_home_or_away = {}

        # Determinar el contrario de home_or_away
        opposite_home_or_away = "home" if home_or_away == "away" else "away"

        if "top_average" in opponent_rankings:
            for stat, opponents in opponent_rankings["top_average"].items():
                for index, opponent_data in enumerate(opponents):
                    if opponent_data["opponent"] == opponent:
                        opponent_top_average[stat] = {
                            "position": index + 1,
                            "value": opponent_data["value"]
                        }

        if f"top_{opposite_home_or_away}" in opponent_rankings:
            for stat, opponents in opponent_rankings[f"top_{opposite_home_or_away}"].items():
                for index, opponent_data in enumerate(opponents):
                    if opponent_data["opponent"] == opponent:
                        opponent_top_home_or_away[stat] = {
                            "position": index + 1,
                            "value": opponent_data["value"]
                        }

        # Obtener estadísticas de `team_game_stats` para el equipo y posición
        team_stats = db.team_game_stats.find_one(
            {"_id": "team_totals_by_position"},
            {f"team_totals_by_position.{team}.average.{position}.stats": 1,
             f"team_totals_by_position.{team}.average_{home_or_away}.{position}.stats": 1}
        )

        if not team_stats or "team_totals_by_position" not in team_stats:
            return {"error": f"Estadísticas de equipo no encontradas para {team}"}
        
        team_average_stats = team_stats["team_totals_by_position"][team]["average"][position]["stats"]
        team_average_home_or_away_stats = team_stats["team_totals_by_position"][team][f"average_{home_or_away}"][position]["stats"]

        # Obtener estadísticas de `opponent_stats` para el oponente y posición
        opponent_stats = db.opponent_stats.find_one(
            {"_id": "opponent_totals_by_position"},
            {f"opponent_totals_by_position.{opponent}.average.{position}.stats": 1,
             f"opponent_totals_by_position.{opponent}.average_{home_or_away}.{position}.stats": 1}
        )

        if not opponent_stats or "opponent_totals_by_position" not in opponent_stats:
            return {"error": f"Estadísticas del oponente no encontradas para {opponent}"}
        
        opponent_average_stats = opponent_stats["opponent_totals_by_position"][opponent]["average"][position]["stats"]
        opponent_average_home_or_away_stats = opponent_stats["opponent_totals_by_position"][opponent][f"average_{home_or_away}"][position]["stats"]

        # Obtener rankings por posición de la colección `rankings`
        position_rankings = db.rankings.find_one({}, {"team_position_ranking": 1, "opponent_position_ranking": 1})
        if not position_rankings:
            return {"error": "Rankings por posición no encontrados"}

        # Procesar team_position_ranking
        team_position_ranking = position_rankings.get("team_position_ranking", {})
        team_position_top_average = {}
        team_position_top_home_or_away = {}

        if "top_average" in team_position_ranking:
            for stat, positions in team_position_ranking["top_average"].items():
                if position in positions:
                    for entry in positions[position]:
                        if entry["team"] == team:
                            team_position_top_average[stat] = {
                                "position": entry["position"],
                                "value": entry["value"]
                            }

        if f"top_{home_or_away}" in team_position_ranking:
            for stat, positions in team_position_ranking[f"top_{home_or_away}"].items():
                if position in positions:
                    for entry in positions[position]:
                        if entry["team"] == team:
                            team_position_top_home_or_away[stat] = {
                                "position": entry["position"],
                                "value": entry["value"]
                            }

        # Procesar opponent_position_ranking
        opponent_position_ranking = position_rankings.get("opponent_position_ranking", {})
        opponent_position_top_average = {}
        opponent_position_top_home_or_away = {}

        if "top_average" in opponent_position_ranking:
            for stat, positions in opponent_position_ranking["top_average"].items():
                if position in positions:
                    for entry in positions[position]:
                        if entry["opponent"] == opponent:
                            opponent_position_top_average[stat] = {
                                "position": entry["position"],
                                "value": entry["value"]
                            }

        if f"top_{opposite_home_or_away}" in opponent_position_ranking:
            for stat, positions in opponent_position_ranking[f"top_{opposite_home_or_away}"].items():
                if position in positions:
                    for entry in positions[position]:
                        if entry["opponent"] == opponent:
                            opponent_position_top_home_or_away[stat] = {
                                "position": entry["position"],
                                "value": entry["value"]
                            }

        # Estructura de salida
        response = {
            "player": {
                "name": player_name,
                "position": position,
                "team": team,
                "stats": player_stats,
                "stats_home_or_away": player_stats_home_or_away
            },
            "team": {
                "name": team,
                "rankings": {
                    "top_average": team_top_average,
                    f"top_{home_or_away}": team_top_home_or_away
                },
                "position_rankings": {
                    "top_average": team_position_top_average,
                    f"top_{home_or_away}": team_position_top_home_or_away
                },
                "stats": {
                    "average": team_average_stats,
                    f"average_{home_or_away}": team_average_home_or_away_stats
                }
            },
            "opponent": {
                "name": opponent,
                "rankings": {
                    "top_average": opponent_top_average,
                    f"top_{opposite_home_or_away}": opponent_top_home_or_away
                },
                "position_rankings": {
                    "top_average": opponent_position_top_average,
                    f"top_{opposite_home_or_away}": opponent_position_top_home_or_away
                },
                "stats": {
                    "average": opponent_average_stats,
                    f"average_{home_or_away}": opponent_average_home_or_away_stats
                }
            }
        }

        # Añadir estos valores a la respuesta
        response["team"]["position_rankings"] = {
            "top_average": team_position_top_average,
            f"top_{home_or_away}": team_position_top_home_or_away
        }
        response["opponent"]["position_rankings"] = {
            "top_average": opponent_position_top_average,
            f"top_{opposite_home_or_away}": opponent_position_top_home_or_away
        }


        # Transformar ObjectId a string en todos los documentos
        def transform_object_id(data):
            if isinstance(data, dict):
                return {k: transform_object_id(v) if isinstance(v, (dict, list)) else (str(v) if isinstance(v, ObjectId) else v) for k, v in data.items()}
            elif isinstance(data, list):
                return [transform_object_id(item) for item in data]
            return data

        response = transform_object_id(response)
        return response

    except Exception as e:
        logger.error(f"Error al procesar los datos: {e}")
        return {"error": str(e)}

def calculate_position_rankings():
    """
    Calcula los rankings por posición para equipos y oponentes basados en las estadísticas
    `team_totals_by_position` y `opponent_totals_by_position` y los agrega a la colección `rankings`.
    """
    try:
        # Leer datos de team_totals_by_position y opponent_totals_by_position
        team_totals = db.team_game_stats.find_one({"_id": "team_totals_by_position"})
        opponent_totals = db.opponent_stats.find_one({"_id": "opponent_totals_by_position"})

        if not team_totals or not opponent_totals:
            logger.error("No se encontraron datos en `team_totals_by_position` o `opponent_totals_by_position`.")
            return

        team_totals_by_position = team_totals.get("team_totals_by_position", {})
        opponent_totals_by_position = opponent_totals.get("opponent_totals_by_position", {})

        # Inicializar estructuras
        team_position_ranking = {
            "top_average": {},
            "top_home": {},
            "top_away": {}
        }
        opponent_position_ranking = {
            "top_average": {},
            "top_home": {},
            "top_away": {}
        }

        stats_keys = ["PTS", "REB", "AST", "2A", "2M", "3A", "3M", "STL", "BLK", "TO"]
        positions = ["PG", "SG", "SF", "PF", "C"]

        # Helper function to process rankings
        def process_rankings(data, ranking_structure, entity_key):
            for category in ["average", "average_home", "average_away"]:
                key = "top_" + category.split("_")[1] if "_" in category else "top_average"
                ranking_structure[key] = {}
                for stat in stats_keys:
                    ranking_structure[key][stat] = {}
                    for position in positions:
                        temp_data = []
                        for entity, entity_data in data.items():
                            # Validar existencia de posición y estadística
                            try:
                                position_data = entity_data.get(category, {}).get(position, {})
                                value = position_data.get("stats", {}).get(stat, None)
                                if value is not None:
                                    temp_data.append({
                                        entity_key: entity,
                                        "value": value
                                    })
                            except Exception as e:
                                logger.error(f"Error procesando {entity_key} {entity}: {e}")
                                continue

                        # Verificar y depurar la lista temporal
                        if not temp_data:
                            logger.warning(f"No se encontraron datos para {key} - {stat} - {position}")
                            ranking_structure[key][stat][position] = []
                            continue

                        # Ordenar los datos y asignar posiciones
                        temp_data.sort(key=lambda x: x["value"], reverse=True)
                        for idx, item in enumerate(temp_data):
                            item["position"] = idx + 1
                        ranking_structure[key][stat][position] = temp_data

                        # Debugging
                        logger.info(f"Procesados {len(temp_data)} elementos para {key} - {stat} - {position}")

        # Procesar rankings para equipos y oponentes
        logger.info("Procesando rankings de equipos...")
        process_rankings(team_totals_by_position, team_position_ranking, "team")
        logger.info("Procesando rankings de oponentes...")
        process_rankings(opponent_totals_by_position, opponent_position_ranking, "opponent")

        # Guardar en la colección rankings
        db.rankings.update_one(
            {"_id": "rankings"},
            {"$set": {
                "team_position_ranking": team_position_ranking,
                "opponent_position_ranking": opponent_position_ranking
            }},
            upsert=True
        )

        logger.info("Rankings por posición calculados y almacenados correctamente en `rankings`.")

    except Exception as e:
        logger.error(f"Error al calcular rankings por posición: {e}")


if __name__ == "__main__":
    scrape_stats()

#TODO: cambiar el uso de variable por scraping directo en la web o moverlo a un archivo de configuracion


