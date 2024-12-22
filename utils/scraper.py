import os
import json
import logging
from logging.handlers import RotatingFileHandler
import requests
import numpy as np
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime

BASE_URL = "https://www.proballers.com"  # Cambia a la URL base de tu web scraping
DATA_DIR = "data"  # Carpeta donde se almacenan los JSON

#TODO: SEPARAR LOS LOGS EN DOS ARCHIVOS DIFERENTES PARA EVITAR EL FILE HANDLER
# Configurar logger local de utils
logger = logging.getLogger('logger')  # Logger específico para utils
logger.setLevel(logging.INFO)

# Configurar el FileHandler para escribir siempre en el mismo archivo
utils_log_file = 'utils/log.json'
file_handler = logging.FileHandler(utils_log_file, mode='w')  # Sobrescribir el archivo en cada ejecución

# Formato JSON para el log
log_formatter = logging.Formatter('{"time": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}')
file_handler.setFormatter(log_formatter)

# Evitar agregar handlers duplicados
if not logger.hasHandlers():
    logger.addHandler(file_handler)

#TODO: cambiar el uso de variable por scraping directo en la web o moverlo a un archivo de configuracion
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

def get_player_data(team_name, player_name):
    """
    Devuelve las estadísticas del jugador almacenadas en el JSON de un equipo.
    """
    # Ruta al archivo JSON del equipo
    file_path = os.path.join(DATA_DIR, f"{team_name}.json")

    # Verifica si el archivo existe
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"El archivo JSON para el equipo {team_name} no existe.")

    # Lee los datos del JSON
    with open(file_path, "r") as file:
        logger.info(f"Leyendo el archivo JSON del equipo: {file_path}")
        team_data = json.load(file)

    # Verifica si el jugador está en los datos
    player_stats = team_data.get("stats", {}).get(player_name)
    if not player_stats:
        raise ValueError(f"El jugador {player_name} no se encuentra en el equipo {team_name}.")

    return player_stats


def get_date(fecha_str):
    """Convierte una fecha en formato '24 oct 2024' o similar en día, mes y año."""
    # Mapeo de nombres de meses en español a números
    meses = {
        "ene": "01", "feb": "02", "mar": "03", "abr": "04",
        "may": "05", "jun": "06", "jul": "07", "ago": "08",
        "sep": "09", "sept": "09", "oct": "10", "nov": "11", "dic": "12"
    }

    try:
        # Dividir la fecha para mapear el mes
        partes = fecha_str.lower().split()
        dia = int(partes[0])
        mes = meses[partes[1]]
        anio = int(partes[2])

        # Construir una fecha válida
        fecha = datetime.strptime(f"{dia}-{mes}-{anio}", "%d-%m-%Y")
    except (ValueError, KeyError) as e:
        logger.error(f"Formato de fecha no reconocido: {fecha_str} - Error: {e}")
        raise
    return fecha.day, fecha.month, fecha.year

from bisect import bisect_left, bisect_right

def get_team(day, month, year, opponent):
    """
    Busca en un archivo JSON la información de un equipo según la fecha y el oponente.

    Args:
        day (int): Día del partido.
        month (int): Mes del partido.
        year (int): Año del partido.
        opponent (str): Nombre del equipo contrario.

    Returns:
        str: Nombre del equipo ("home" o "away") que corresponde al partido dado, o None si no se encuentra.
    """
    try:
        # Cargar el archivo JSON
        with open('utils/calendar.json', 'r') as file:
            schedule = json.load(file)

        # Validar que el archivo contiene una lista
        if not isinstance(schedule, list):
            logger.error("El archivo JSON no contiene una lista válida de partidos.")
            return None

        # Crear una lista de fechas para búsqueda binaria
        dates = [(game['date']['year'], game['date']['month'], game['date']['day']) for game in schedule]

        # Buscar la posición inicial y final usando búsqueda binaria
        target_date = (year, month, day)
        left_idx = bisect_left(dates, target_date)
        right_idx = bisect_right(dates, target_date)

        # Recorrer el rango de partidos que coinciden con la fecha
        for idx in range(left_idx, right_idx):
            game = schedule[idx]
            if game.get("home") == opponent:
                return game.get("away")
            elif game.get("away") == opponent:
                return game.get("home")

        # Si no se encuentra el partido
        logger.warning(f"No se encontró un partido con la fecha {day}/{month}/{year} y oponente {opponent}.")
        return None

    except FileNotFoundError:
        logger.error("El archivo calendar.json no se encontró.")
        return None
    except json.JSONDecodeError:
        logger.error("Error al decodificar el archivo JSON.")
        return None

def get_player_stats(player_url, player_name, last_game_date=None):
    """
    Scrapea las estadísticas individuales de un jugador, filtrando por fecha.
    """
    response = requests.get(player_url)
    if response.status_code != 200:
        logger.error(f"error del servidor: {response}")
        return [], None

    soup = BeautifulSoup(response.text, 'html.parser')

    # Verificar el título del HTML
    title = soup.find('title')
    if title:
        title_text = title.text.strip()
        if not "2024-2025" in title_text:
            logger.warning(f"El título indica un año diferente a 2024-2025: {title_text}. Jugador ignorado.")
            return [], None
    else:
        logger.warning("No se encontró un título en el HTML. Jugador ignorado.")
        return [], None

    stats_table = soup.find('table', class_='table')
    if not stats_table:
        return [], None

    rows = stats_table.find_all('tr')[1:]
    player_stats = []
    latest_game_date = last_game_date

    for row in rows:
        cols = row.find_all('td')
        if len(cols) < 19:
            logger.error(f"Menos de 19 columnas, fila ignorada.")
            continue

        try:
            # Extraer detalles del partido
            opponent_info = cols[0].find('a').text.strip() if cols[0].find('a') else cols[0].text.strip()
            location = "home" if "vs" in opponent_info else "away"
            opponent = opponent_info.replace("vs", "").replace("@", "").strip()

            # Columna 2 contiene la fecha
            date = cols[1].find('a').text.strip() if cols[1].find('a') else cols[1].text.strip()
            day, month, year = get_date(date)

            game_date = datetime(year, month, day)
            if last_game_date and game_date <= last_game_date:
                continue  # Ignorar juegos anteriores a la última fecha conocida

            # Actualizar latest_game_date
            if not latest_game_date or game_date > latest_game_date:
                latest_game_date = game_date

            # Extraer estadísticas individuales del jugador
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
                "TO": float(cols[17].text.strip()) if cols[17].text.strip().isdigit() else 0,
            }

            player_stats.append(stats)
        except (ValueError, IndexError) as e:
            logger.error(f"Error procesando fila: {e}")
            continue

    return player_stats, latest_game_date

def get_team_url(team_name):
    """
    Devuelve la URL completa del equipo basado en su nombre.
    """
    team_path = equipos.get(team_name)
    logger.info(f"Team path: {team_path}")
    if not team_path:
        logger.error(f"Team path: {team_path}")
        raise ValueError(f"No se encontró la ruta para el equipo: {team_name}")
    return f"{BASE_URL}/es/baloncesto/equipo/{team_path}"

#TODO: eliminar last_updated, modificar la funcion para usar el calendario y actualizar una vez al dia tras el ultimo partido
def needs_update(team_name):
    """Verifica si un equipo necesita actualización."""
    file_path = os.path.join(DATA_DIR, f"{team_name}.json")

    # Si el archivo no existe, necesita actualización
    if not os.path.exists(file_path):
        logger.info(f"Archivo no encontrado para {team_name}, necesita actualización.")
        return True

    data = read_json(file_path)
    last_updated = data.get("global_stats", {}).get("last_updated")

    # Si no hay fecha de actualización o la fecha es anterior a hoy, necesita actualización
    if not last_updated:
        return True

    today = pd.Timestamp.today().date()
    last_date = pd.Timestamp(last_updated).date()
    return last_date < today


def read_json(file_path):
    """Lee un archivo JSON."""
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            logger.info(f"Leyendo json: {file_path}")
            return json.load(file)
    return {}

def write_json(data, file_path):
    """Escribe un archivo JSON."""
    with open(file_path, 'w') as file:
        logger.info(f"Escribiendo json: {file_path}")
        json.dump(data, file, indent=4)


# def scrape_team_stats(team_name):
#     """
#     Scrapea estadísticas de un equipo y actualiza el JSON si es necesario.
#     """
#     # Verificar si el equipo necesita actualización
#     file_path = os.path.join(DATA_DIR, f"{team_name}.json")

#     if not needs_update(team_name) and os.path.exists(file_path):
#         logger.info(f"No se requiere actualización para el equipo: {team_name}")
#         return read_json(file_path)

#     # Obtener la URL del equipo
#     team_url = get_team_url(team_name)
#     response = requests.get(team_url)
#     logger.info(f"Scraping del equipo: {team_name} con {team_url}")

#     if response.status_code != 200:
#         raise ValueError(f"No se pudo acceder a {team_url}")

#     soup = BeautifulSoup(response.text, 'html.parser')

#     # Función para extraer jugadores y sus URLs
#     def extract_players(soup):
#         stats = {}
#         player_entries = soup.find_all('a', class_='list-player-entry stats-player')
#         for entry in player_entries:
#             href = entry.get('href')
#             title = entry.get('title')
#             if href and title:
#                 stats[title] = f"{BASE_URL}{href}/partidos"
#         return stats

#     # Extraer jugadores
#     stats = extract_players(soup)
#     logger.info(f"Jugadores extraídos: {stats}")

#     # Obtener estadísticas de los jugadores
#     player_stats = {}
#     last_game_date = None
#     for player_name, player_url in stats.items():
#         stats, player_last_game_date = get_player_stats(player_url)
#         logger.info(f"Estadísticas del jugador {player_name} extraídas: {stats}")
#         player_stats[player_name] = stats

#         # Actualizar la última fecha de juego a nivel de equipo
#         if player_last_game_date and (not last_game_date or player_last_game_date > last_game_date):
#             last_game_date = player_last_game_date

#     # Crear el objeto de datos final
#     team_data = {
#         "team_name": team_name,
#         "stats": player_stats,
#         "last_game_date": {
#             "day": last_game_date.day if last_game_date else None,
#             "month": last_game_date.month if last_game_date else None,
#             "year": last_game_date.year if last_game_date else None,
#         },
#     }

#     # Guardar en el JSON
#     write_json(team_data, file_path)
#     logger.info(f"Datos del equipo {team_name} guardados en {file_path}")

#     return team_data

def scrape_stats():
    """
    Scrapea estadísticas de equipos y acumula solo los datos nuevos en un JSON único.
    """
    # Archivo donde se guardarán los datos
    file_path = os.path.join(DATA_DIR, "data.json")

    # Leer datos existentes
    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            existing_data = json.load(file)
            last_game_date = datetime(
                existing_data["last_game_date"]["year"],
                existing_data["last_game_date"]["month"],
                existing_data["last_game_date"]["day"],
            ) if existing_data["last_game_date"]["year"] else None
            all_player_stats = existing_data["stats"]
    else:
        last_game_date = None
        all_player_stats = []

    for team_url in equipos.values():
        # Obtener la URL del equipo
        response = requests.get(f"{BASE_URL}/es/baloncesto/equipo/{team_url}")
        logger.info(f"Scraping de {team_url}")

        if response.status_code != 200:
            raise ValueError(f"No se pudo acceder a {BASE_URL}/es/baloncesto/equipo/{team_url}")

        soup = BeautifulSoup(response.text, 'html.parser')

        # Función para extraer jugadores y sus URLs
        def extract_players(soup):
            players = {}
            player_entries = soup.find_all('a', class_='list-player-entry stats-player')
            for entry in player_entries:
                href = entry.get('href')
                title = entry.get('title')
                if href and title:
                    players[title] = f"{BASE_URL}{href}/partidos"
            return players

        # Extraer jugadores
        players = extract_players(soup)
        logger.info(f"Jugadores extraídos: {players}")

        latest_game_date = last_game_date  # Para rastrear la fecha más reciente por equipo

        for player_name, player_url in players.items():
            # Obtener solo estadísticas nuevas del jugador
            player_stats, player_last_game_date = get_player_stats(player_url, player_name, last_game_date)

            if player_stats:
                all_player_stats.extend(player_stats)  # Agregar estadísticas nuevas

            # Actualizar la fecha más reciente
            if player_last_game_date and (not latest_game_date or player_last_game_date > latest_game_date):
                latest_game_date = player_last_game_date

        last_game_date = latest_game_date if latest_game_date else last_game_date

    # Crear el objeto de datos final
    data = {
        "stats": all_player_stats,
        "last_game_date": {
            "day": last_game_date.day if last_game_date else None,
            "month": last_game_date.month if last_game_date else None,
            "year": last_game_date.year if last_game_date else None,
        },
    }

    # Guardar en el JSON
    write_json(data, file_path)
    logger.info(f"Datos actualizados guardados en {file_path}")

    return data


OUTPUT_FILE = os.path.join(DATA_DIR, "opponent_stats.json")
#TODO: modificar construccion de los totales para ir añadiendo los nuevos valores
def calculate_opponent_stats():
    """
    Genera estadísticas de rendimiento de los jugadores que han jugado contra cada equipo,
    utilizando los datos consolidados en data.json.
    """
    # Ruta al archivo de datos consolidado
    file_path = os.path.join(DATA_DIR, "data.json")

    try:
        with open(file_path, "r") as file:
            data = json.load(file)
    except json.JSONDecodeError as e:
        print(f"Error al cargar data.json: {e}")
        return

    opponent_stats = {}
    team_totals = {}

    # Recorrer las estadísticas de los jugadores
    for game in data.get("stats", []):
        opponent = game.get("opponent")
        team = game.get("team")
        player_name = game.get("name", "Unknown Player")

        if not opponent or not team:
            print(f"Juego inválido encontrado: {game}")
            continue

        # Inicializar estadísticas totales del equipo
        if team not in team_totals:
            team_totals[team] = {"PTS": 0, "REB": 0, "AST": 0, "STL": 0, "BLK": 0, "TO": 0}

        # Sumar estadísticas al total del equipo
        for stat in ["PTS", "REB", "AST", "STL", "BLK", "TO"]:
            team_totals[team][stat] += game.get(stat, 0)

        # Inicializar estadísticas del oponente
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

        # Sumar estadísticas al total del oponente
        for stat in ["PTS", "REB", "AST", "STL", "BLK", "TO"]:
            opponent_stats[opponent][stat] += game.get(stat, 0)

        # Crear una línea de rendimiento del jugador
        line = game.copy()
        line["player"] = player_name

        # Añadir la línea al oponente
        opponent_stats[opponent]["games"].append(line)

    # Guardar los resultados en un archivo JSON
    output_data = {
        "opponents": opponent_stats,
        "team_totals": team_totals
    }

    try:
        with open("opponent_stats.json", "w") as output_file:
            json.dump(output_data, output_file, indent=4)
            print(f"Archivo guardado en opponent_stats.json")
    except Exception as e:
        print(f"Error al guardar el archivo opponent_stats.json: {e}")

def calculate_team_game_stats():
    """
    Genera estadísticas acumuladas por partido para cada equipo y guarda un archivo team_stats.json.
    Utiliza el archivo consolidado data.json.
    """
    # Ruta al archivo de datos consolidado
    file_path = os.path.join(DATA_DIR, "data.json")

    try:
        with open(file_path, "r") as file:
            data = json.load(file)
    except json.JSONDecodeError as e:
        print(f"Error al cargar data.json: {e}")
        return

    team_game_stats = {}
    team_totals = {}

    # Recorrer las estadísticas de los jugadores
    for game in data.get("stats", []):
        team = game.get("team")
        game_date = game.get("date")

        if not team or not game_date:
            print(f"Juego inválido encontrado: {game}")
            continue

        # Inicializar estadísticas totales del equipo
        if team not in team_totals:
            team_totals[team] = {"PTS": 0, "REB": 0, "AST": 0, "STL": 0, "BLK": 0, "TO": 0}

        # Inicializar estadísticas por partido del equipo
        if team not in team_game_stats:
            team_game_stats[team] = {}

        if game_date not in team_game_stats[team]:
            team_game_stats[team][game_date] = {
                "date": game_date,
                "day": game.get("day"),
                "month": game.get("month"),
                "year": game.get("year"),
                "opponent": game.get("opponent"),
                "home_or_away": game.get("home_or_away"),
                "PTS": 0,
                "REB": 0,
                "AST": 0,
                "STL": 0,
                "BLK": 0,
                "TO": 0,
                "players_count": 0,  # Para calcular promedios si es necesario
                "team": team
            }

        # Sumar estadísticas del jugador al total del equipo
        for stat in ["PTS", "REB", "AST", "STL", "BLK", "TO"]:
            team_totals[team][stat] += game.get(stat, 0)
            team_game_stats[team][game_date][stat] += game.get(stat, 0)

        # Incrementar el conteo de jugadores en el partido
        team_game_stats[team][game_date]["players_count"] += 1

    # Transformar juegos en listas
    for team, games in team_game_stats.items():
        team_game_stats[team] = list(games.values())

    # Guardar los resultados en un archivo JSON
    output_data = {
        "team_games": team_game_stats,
        "team_totals": team_totals
    }

    try:
        with open("team_stats.json", "w") as output_file:
            json.dump(output_data, output_file, indent=4)
            print(f"Archivo guardado en team_stats.json")
    except Exception as e:
        print(f"Error al guardar el archivo team_stats.json: {e}")


def calculate_all_stats():
    """
    Calcula tanto las estadísticas por oponente como las acumuladas por equipo.
    """
    calculate_opponent_stats()
    calculate_team_game_stats()
    print("Cálculo completo de estadísticas.")


def get_calendar():
    """
    Scrapea el calendario de la temporada 2024-2025 de la NBA y lo guarda en un archivo JSON.
    """
    url = "https://www.proballers.com/es/baloncesto/liga/3/nba/calendario"
    response = requests.get(url)
    if response.status_code != 200:
        logger.error(f"Error del servidor: {response.status_code}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    juegos = soup.find_all("div", class_="home-league__schedule__content__entry home-league__schedule__content__boxscore")

    calendario = []

    for juego in juegos:
        try:
            # Obtener fecha
            fecha_str = juego.find("div", class_="home-league__schedule__date").text.strip()
            dia, mes, anio = get_date(fecha_str)

            # Obtener hora
            hora = juego.find("div", class_="home-league__schedule__time").text.strip()

            # Obtener equipos
            equipos = juego.find_all("div", class_="home-league__schedule__team")
            equipo_home = equipos[0].text.strip()
            equipo_away = equipos[1].text.strip()

            # Agregar al calendario
            calendario.append({
                "fecha": {"dia": dia, "mes": mes, "anio": anio},
                "hora": hora,
                "home": equipo_home,
                "away": equipo_away
            })

        except Exception as e:
            logger.error(f"Error al procesar un juego: {e}")
            continue

    # Guardar en un archivo JSON
    with open("calendar.json", "w", encoding="utf-8") as f:
        json.dump(calendario, f, ensure_ascii=False, indent=4)

    logger.info("Calendario guardado en calendar.json")

