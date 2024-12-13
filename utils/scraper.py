import os
import json
import logging
import requests
import numpy as np
from bs4 import BeautifulSoup
import pandas as pd

BASE_URL = "https://www.proballers.com"  # Cambia a la URL base de tu web scraping
DATA_DIR = "data"  # Carpeta donde se almacenan los JSON

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
        logging.info(f"Leyendo el archivo JSON del equipo: {file_path}")
        team_data = json.load(file)

    # Verifica si el jugador está en los datos
    player_stats = team_data.get("players", {}).get(player_name)
    if not player_stats:
        raise ValueError(f"El jugador {player_name} no se encuentra en el equipo {team_name}.")

    return player_stats

def get_player_stats(player_url, team_role):
    """
    Scrapea las estadísticas individuales de un jugador.
    """
    response = requests.get(player_url)
    if response.status_code != 200:
        logging.error(f"error del servidor: {response}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    stats_table = soup.find('table', class_='table')
    logging.info(f"tabla de stats obtenida: {stats_table}")
    if not stats_table:
        return []

    rows = stats_table.find_all('tr')[1:]
    logging.info(f"filas de las tablas: {rows}")
    player_stats = []
    for row in rows:
        cols = row.find_all('td')
        logging.info(f"columnas del jugador: {cols}")
        if len(cols) < 19:
            logging.error(f"Menos de 19 columnas, fila ignorada.")
            continue

        try:
            # Extraer detalles del partido
            opponent_info = cols[0].find('a').text.strip() if cols[0].find('a') else cols[0].text.strip()
            is_home = "vs" in opponent_info
            opponent = opponent_info.replace("vs", "").replace("@", "").strip()

            # Validar si el oponente está en la lista de equipos válidos
            if opponent not in equipos:
                logging.warning(f"Oponente '{opponent}' no es un equipo válido. Fila ignorada.")
                continue

            # Columna 2 contiene la fecha
            date = cols[1].find('a').text.strip() if cols[1].find('a') else cols[1].text.strip()

            # Extraer estadísticas individuales del jugador
            stats = {
                "date": date,
                "opponent": opponent,
                "home_or_away": "home" if is_home else "away",
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

            # Añadir combinaciones de estadísticas
            stats["PTS+AST"] = stats["PTS"] + stats["AST"]
            stats["REB+AST"] = stats["REB"] + stats["AST"]
            stats["PTS+REB"] = stats["PTS"] + stats["REB"]
            stats["PTS+REB+AST"] = stats["PTS"] + stats["REB"] + stats["AST"]

            player_stats.append(stats)
        except (ValueError, IndexError) as e:
            logging.error(f"Error procesando fila: {e}")
            continue

    return player_stats

def calculate_global_stats(player_stats):
    """
    Calcula estadísticas globales para un equipo a partir de las estadísticas individuales de los jugadores.
    """
    all_stats = {
        "PTS": [],
        "REB": [],
        "AST": [],
        "STL": [],
        "BLK": [],
        "TO": [],
        "2M": [],
        "2A": [],
        "3M": [],
        "3A": [],
        "PTS+AST": [],
        "REB+AST": [],
        "PTS+REB": [],
        "PTS+REB+AST": [],
    }

    for player_name, stats in player_stats.items():
        for stat_entry in stats:
            for key in all_stats.keys():
                if key in stat_entry:
                    all_stats[key].append(stat_entry[key])

    global_stats = {key: round(np.mean(values), 2) for key, values in all_stats.items() if values}
    return global_stats

def get_team_url(team_name):
    """
    Devuelve la URL completa del equipo basado en su nombre.
    """
    team_path = equipos.get(team_name)
    logging.info(f"Team path: {team_path}")
    if not team_path:
        logging.error(f"Team path: {team_path}")
        raise ValueError(f"No se encontró la ruta para el equipo: {team_name}")
    return f"{BASE_URL}/es/baloncesto/equipo/{team_path}"

def needs_update(team_name):
    """Verifica si un equipo necesita actualización."""
    file_path = os.path.join(DATA_DIR, f"{team_name}.json")

    # Si el archivo no existe, necesita actualización
    if not os.path.exists(file_path):
        logging.info(f"Archivo no encontrado para {team_name}, necesita actualización.")
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
            logging.info(f"Leyendo json: {file_path}")
            return json.load(file)
    return {}

def write_json(data, file_path):
    """Escribe un archivo JSON."""
    with open(file_path, 'w') as file:
        logging.info(f"Escribiendo json: {file_path}")
        json.dump(data, file, indent=4)

def scrape_team_stats(team_name):
    """
    Scrapea estadísticas de un equipo y actualiza el JSON si es necesario.
    """
    # Verificar si el equipo necesita actualización
    file_path = os.path.join(DATA_DIR, f"{team_name}.json")

    if not needs_update(team_name) and os.path.exists(file_path):
        logging.info(f"No se requiere actualización para el equipo: {team_name}")
        return read_json(file_path)

    # Obtener la URL del equipo
    team_url = get_team_url(team_name)
    response = requests.get(team_url)
    logging.info(f"Scraping del equipo: {team_name} con {team_url}")

    if response.status_code != 200:
        raise ValueError(f"No se pudo acceder a {team_url}")

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
    logging.info(f"Jugadores extraídos: {players}")

    # Obtener estadísticas de los jugadores
    player_stats = {}
    for player_name, player_url in players.items():
        stats = get_player_stats(player_url, team_name)
        logging.info(f"Estadísticas del jugador {player_name} extraídas: {stats}")
        player_stats[player_name] = stats
        
    global_stats = calculate_global_stats(player_stats)
    global_stats["last_updated"] = pd.Timestamp.today().strftime("%Y-%m-%d")

    # Calcular estadísticas globales
    logging.info(f"Estadísticas globales calculadas: {global_stats}")

    # Crear el objeto de datos final
    team_data = {
        "team_name": team_name,
        "players": player_stats,
        "global_stats": global_stats,
    }

    # Guardar en el JSON
    write_json(team_data, file_path)
    logging.info(f"Datos del equipo {team_name} guardados en {file_path}")

    return team_data


OUTPUT_FILE = os.path.join(DATA_DIR, "opponent_stats.json")

def calculate_opponent_stats():
    """
    Genera estadísticas de rendimiento de los jugadores que han jugado contra cada equipo,
    incluyendo solo las líneas de los jugadores correspondientes al equipo oponente.
    """
    opponent_stats = {}

    # Recorrer los archivos de los equipos
    for team_file in os.listdir(DATA_DIR):
        if not team_file.endswith(".json"):
            continue

        team_path = os.path.join(DATA_DIR, team_file)

        try:
            with open(team_path, "r") as file:
                team_data = json.load(file)
        except json.JSONDecodeError as e:
            print(f"Error al cargar {team_file}: {e}")
            continue

        current_team_name = team_data.get("team_name")
        if not current_team_name:
            print(f"Archivo {team_file} no contiene 'team_name'.")
            continue

        # Recorrer los jugadores y sus juegos
        players = team_data.get("players", {})
        if not isinstance(players, dict):
            print(f"'players' no es un diccionario en {team_file}.")
            continue

        for player_name, games in players.items():
            if not isinstance(games, list):
                print(f"'games' no es una lista para {player_name} en {team_file}.")
                continue

            for game in games:
                opponent = game.get("opponent")
                if not opponent:
                    print(f"Juego inválido encontrado en {team_file}: {game}")
                    continue

                # Asegurar que el oponente esté inicializado
                if opponent not in opponent_stats:
                    opponent_stats[opponent] = []

                # Crear una línea de rendimiento
                line = game.copy()
                line["player"] = player_name
                line["team"] = current_team_name

                # Añadir la línea al equipo oponente
                opponent_stats[opponent].append(line)

    # Guardar el archivo JSON
    try:
        with open(OUTPUT_FILE, "w") as output_file:
            json.dump(opponent_stats, output_file, indent=4)
            print(f"Archivo guardado en {OUTPUT_FILE}")
    except Exception as e:
        print(f"Error al guardar el archivo {OUTPUT_FILE}: {e}")






