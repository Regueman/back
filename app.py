import os
import json
import logging
from flask import Flask, jsonify
from scraper import scrape_team_stats, get_player_data, needs_update, write_json, calculate_opponent_stats

from flask_cors import CORS
app = Flask(__name__)
# Configura CORS permitiendo solo el origen necesario
CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}})

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



# Configuración del logger
LOG_FILE = "log.json"
DATA_DIR = "data"  # Carpeta donde se encuentran los archivos JSON

# Configuración del logger en formato JSON
logger = logging.getLogger("flask_app_logger")
logger.setLevel(logging.DEBUG)

# Formateador personalizado para registrar en JSON
class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "level": record.levelname,
            "message": record.getMessage(),
            "time": self.formatTime(record, self.datefmt),
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record)

# Handler para escribir en archivo
file_handler = logging.FileHandler(LOG_FILE)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(JSONFormatter())

# Añadir el handler al logger
logger.addHandler(file_handler)


@app.route("/api/team/<team_name>", methods=["GET"])
def get_team_data(team_name):
    try:
        logger.info(f"Fetching data for team: {team_name}")
        team_data = scrape_team_stats(team_name)
        return jsonify(team_data)
    except Exception as e:
        logger.error(f"Error fetching data for team {team_name}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/team/<team_name>/<player_name>", methods=["GET"])
def api_get_player_data(team_name, player_name):
    try:
        logger.info(f"Fetching data for player {player_name} in team {team_name}")
        player_data = get_player_data(team_name, player_name)
        return jsonify(player_data)
    except FileNotFoundError as e:
        logger.warning(f"File not found for team {team_name}: {str(e)}")
        return jsonify({"error": f"Archivo no encontrado: {str(e)}"}), 404
    except ValueError as e:
        logger.warning(f"Player not found: {player_name} in team {team_name}")
        return jsonify({"error": f"Jugador no encontrado: {str(e)}"}), 404
    except Exception as e:
        logger.error(f"Internal error while fetching data for player {player_name} in team {team_name}: {str(e)}")
        return jsonify({"error": f"Error interno: {str(e)}"}), 500

@app.route("/api/players/<team_name>/", methods=["GET"])
def api_get_player_list(team_name):
    try:
        logger.info(f"Fetching player list for team: {team_name}")
        file_path = os.path.join(DATA_DIR, f"{team_name}.json")
        if not os.path.exists(file_path):
            logger.warning(f"File does not exist for team: {team_name}")
            return jsonify({"error": f"El archivo para el equipo {team_name} no existe."}), 404

        with open(file_path, "r") as file:
            team_data = json.load(file)

        player_names = list(team_data.get("players", {}).keys())
        return jsonify(player_names)
    except Exception as e:
        logger.error(f"Internal error while fetching player list for team {team_name}: {str(e)}")
        return jsonify({"error": f"Error interno: {str(e)}"}), 500

@app.route("/api/teams", methods=["GET"])
def api_get_teams():
    try:
        logger.info("Fetching list of all teams")
        
        # Ruta del archivo JSON en la misma carpeta que el archivo ejecutable
        file_path = os.path.join(os.path.dirname(__file__), "equipos.json")
        if not os.path.exists(file_path):
            logger.warning("File equipos.json does not exist")
            return jsonify({"error": "El archivo equipos.json no existe."}), 404

        with open(file_path, "r") as file:
            teams_data = json.load(file)
        
        # Obtener nombres de los equipos
        team_names = [team["name"] for team in teams_data.get("teams", [])]
        
        # Imprimir y devolver los nombres
        print(team_names)
        return jsonify(team_names)
    except Exception as e:
        logger.error(f"Internal error while fetching list of teams: {str(e)}")
        return jsonify({"error": f"Error interno: {str(e)}"}), 500

from datetime import datetime



@app.route("/api/update_teams", methods=["GET"])
def update_teams():
    """
    Actualiza los datos de todos los equipos y luego procesa el archivo consolidado con
    estadísticas permitidas por oponente.
    """
    # Rutas de los archivos
    date_ids_path = "date_ids.json"  # Ruta al archivo de IDs de fecha
    output_path = "opponent_stats_updated.json"  # Ruta para guardar el archivo actualizado

    try:
        logger.info("Iniciando actualización de datos de todos los equipos...")


        for team_name in equipos.keys():
            try:
                logger.info(f"Procesando estadísticas para el equipo: {team_name}")
                scrape_team_stats(team_name)
            except Exception as e:
                logger.error(f"Error al actualizar el equipo {team_name}: {str(e)}")

        logger.info("Todos los equipos actualizados. Iniciando cálculo de estadísticas consolidadas...")

        # Llamar a la función calculate_opponent_stats
        calculate_opponent_stats()

        # Definir la ruta del archivo de salida
        consolidated_file = os.path.join(DATA_DIR, "opponent_stats.json")

        if os.path.exists(consolidated_file):
            logger.info(f"Estadísticas consolidadas guardadas en {consolidated_file}")
            
            process_opponent_stats(consolidated_file, date_ids_path, output_path)

            return jsonify({
                "status": "success",
                "message": "Estadísticas de oponentes calculadas y guardadas correctamente.",
                "file": consolidated_file
            }), 200
        else:
            logger.error("El archivo consolidado no se encontró después de calcular las estadísticas.")
            return jsonify({
                "status": "error",
                "message": "El archivo consolidado no se generó correctamente."
            }), 500

    except Exception as e:
        logger.error(f"Error al procesar estadísticas de oponentes: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500



OUTPUT_FILE = os.path.join(DATA_DIR, "opponent_stats.json")
@app.route("/api/opponent_stats/<team_name>", methods=["GET"])
def get_team_opponent_stats(team_name):
    """
    Devuelve las estadísticas permitidas por oponente para un equipo específico.
    """
    try:
        with open(OUTPUT_FILE, "r") as file:
            opponent_stats = json.load(file)

        team_stats = opponent_stats.get(team_name)
        if not team_stats:
            return jsonify({"error": f"No se encontraron estadísticas para {team_name}"}), 404

        return jsonify(team_stats), 200
    except FileNotFoundError:
        return jsonify({"error": "No se encontraron estadísticas de oponentes calculadas."}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/opponent_stats", methods=["GET"])
def get_opponent_stats():
    """
    Devuelve las estadísticas permitidas por oponente.
    """
    try:
        with open(OUTPUT_FILE, "r") as file:
            opponent_stats = json.load(file)
        return jsonify(opponent_stats), 200
    except FileNotFoundError:
        return jsonify({"error": "No se encontraron estadísticas de oponentes calculadas."}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

import json
from collections import defaultdict

def process_opponent_stats(opponent_stats_path, date_ids_path, output_path):
    """
    Actualiza opponent_stats.json con date_id y calcula estadísticas (total y average),
    generando una estructura de salida más completa.
    """
    # Cargar los datos
    with open(opponent_stats_path, "r", encoding="utf-8") as file:
        opponent_stats = json.load(file)

    with open(date_ids_path, "r", encoding="utf-8") as file:
        date_ids = json.load(file)

    # Crear estructura para el archivo actualizado
    updated_stats = {}

    # Procesar cada equipo y calcular estadísticas
    for team, games in opponent_stats.items():
        games_with_date_id = []
        team_totals = defaultdict(float)
        unique_date_ids = set()

        for game in games:
            # Obtener el date_id correspondiente
            game_date = game.get("date")
            date_id = date_ids.get(game_date)
            if not date_id:
                print(f"Fecha {game_date} no encontrada en date_ids.json. Saltando entrada.")
                continue

            # Añadir el date_id al juego
            game["date_id"] = date_id
            games_with_date_id.append(game)

            # Acumular estadísticas del equipo
            unique_date_ids.add(date_id)  # Contar partidos únicos
            for stat, value in game.items():
                if isinstance(value, (int, float)):  # Solo sumar estadísticas numéricas
                    team_totals[stat] += value

        # Calcular promedios
        num_games = len(unique_date_ids)
        team_averages = {stat: total / num_games for stat, total in team_totals.items()} if num_games > 0 else {}

        # Actualizar la estructura del equipo
        updated_stats[team] = {
            "games": games_with_date_id,
            "total": dict(team_totals),
            "average": team_averages
        }

    # Guardar el archivo actualizado
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(updated_stats, file, indent=4, ensure_ascii=False)

    print(f"Archivo actualizado guardado en {output_path}.")



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)























# import os
# import json
# import pandas as pd
# import numpy as np
# import matplotlib
# import matplotlib.pyplot as plt
# import requests
# import logging
# from io import BytesIO
# import base64
# from bs4 import BeautifulSoup
# from flask import Flask, request, jsonify
# from flask_cors import CORS


# DATA_DIR = "data"  # Carpeta donde se encuentran los archivos JSON
# OUTPUT_DIR = "static/player_graphs"  # Carpeta para guardar las gráficas HTML

# # Configuración básica del log
# logging.basicConfig(
#     level=logging.INFO,  # Nivel de log: DEBUG, INFO, WARNING, ERROR, CRITICAL
#     format='%(asctime)s - %(levelname)s - %(message)s',
#     handlers=[logging.FileHandler("app.log"), logging.StreamHandler()]
# )

# BASE_URL = "https://www.proballers.com"
# DATA_DIR = "data"
# equipos = {
#             "Atlanta Hawks": "100/atlanta-hawks",
#             "Boston Celtics": "101/boston-celtics",
#             "Brooklyn Nets": "116/brooklyn-nets",
#             "Charlotte Hornets": "825/charlotte-hornets",
#             "Chicago Bulls": "103/chicago-bulls",
#             "Cleveland Cavaliers": "104/cleveland-cavaliers",
#             "Dallas Mavericks": "105/dallas-mavericks",
#             "Denver Nuggets": "106/denver-nuggets",
#             "Detroit Pistons": "107/detroit-pistons",
#             "Golden State Warriors": "108/golden-state-warriors",
#             "Houston Rockets": "109/houston-rockets",
#             "Indiana Pacers": "110/indiana-pacers",
#             "Los Angeles Clippers": "111/los-angeles-clippers",
#             "Los Angeles Lakers": "112/los-angeles-lakers",
#             "Memphis Grizzlies": "127/memphis-grizzlies",
#             "Miami Heat": "113/miami-heat",
#             "Milwaukee Bucks": "114/milwaukee-bucks",
#             "Minnesota Timberwolves": "115/minnesota-timberwolves",
#             "New Orleans Pelicans": "102/new-orleans-pelicans",
#             "New York Knicks": "117/new-york-knicks",
#             "Oklahoma City Thunder": "1827/oklahoma-city-thunder",
#             "Orlando Magic": "118/orlando-magic",
#             "Philadelphia 76ers": "119/philadelphia-76ers",
#             "Phoenix Suns": "120/phoenix-suns",
#             "Portland Trail Blazers": "121/portland-trail-blazers",
#             "Sacramento Kings": "122/sacramento-kings",
#             "San Antonio Spurs": "123/san-antonio-spurs",
#             "Toronto Raptors": "125/toronto-raptors",
#             "Utah Jazz": "126/utah-jazz",
#             "Washington Wizards": "128/washington-wizards"
#     }

# #        
# def get_team_url(team_name):
#     """
#     Devuelve la URL completa del equipo basado en su nombre.
#     """
#     team_path = equipos.get(team_name)
#     logging.info(f"Team path: {team_path}")
#     if not team_path:
#         logging.error(f"Team path: {team_path}")
#         raise ValueError(f"No se encontró la ruta para el equipo: {team_name}")
#     return f"{BASE_URL}/es/baloncesto/equipo/{team_path}"

# def needs_update(team_name):
#     """Verifica si un equipo necesita actualización."""
#     file_path = os.path.join(DATA_DIR, f"{team_name}.json")
#     data = read_json(file_path)
#     last_updated = data.get("global_stats", {}).get("last_updated")
#     if not last_updated:
#         return True

#     today = pd.Timestamp.today().date()
#     last_date = pd.Timestamp(last_updated).date()
#     return last_date < today

# # REUSAR
# def read_json(file_path):
#     """Lee un archivo JSON."""
#     if os.path.exists(file_path):
#         with open(file_path, 'r') as file:
#             logging.info(f"Leyendo json: {file_path}")
#             return json.load(file)
#     return {}

# ## REUSAR
# def write_json(data, file_path):
#     """Escribe un archivo JSON."""
#     with open(file_path, 'w') as file:
#         logging.info(f"Escribiendo json: {file_path}")
#         json.dump(data, file, indent=4)

# ## REUSAR
# def update_teams_data(team_name, new_player_stats, global_stats):
#     """Actualiza o crea un archivo JSON para un equipo."""
#     for equipo in equipos:
#         file_path = os.path.join(DATA_DIR, f"{equipo}.json")
#         data = read_json(file_path)

#         data["team_name"] = team_name
#         data["global_stats"]["last_updated"] = str(pd.Timestamp.today().date())

#         if "players" not in data:
#             data["players"] = {}

#         for player_name, stats in new_player_stats.items():
#             if player_name not in data["players"]:
#                 data["players"][player_name] = []

#             existing_dates = {entry["date"] for entry in data["players"][player_name]}
#             for stat_entry in stats:
#                 if stat_entry["date"] not in existing_dates:
#                     data["players"][player_name].append(stat_entry)

        
#         data["global_stats"] = calculate_global_stats(data)

#         write_json(data, file_path)

# def scrape_team_stats(team_name):
#     """
#     Scrapea estadísticas de un equipo.
#     """
#     team_url = get_team_url(team_name)  # Usar la función para obtener la URL
#     response = requests.get(team_url)
#     logging.info(f"Scraping del equipo: {team_name} con {team_url}")

#     if response.status_code != 200:
#         raise ValueError(f"No se pudo acceder a {team_url}")

#     soup = BeautifulSoup(response.text, 'html.parser')

#     #    Obtener jugadores y sus URLs
#     def extract_players(soup):
#         players = {}
#         player_entries = soup.find_all('a', class_='list-player-entry stats-player')
#         for entry in player_entries:
#             href = entry.get('href')
#             title = entry.get('title')
#             if href and title:
#                 players[title] = f"{BASE_URL}{href}/partidos"
#         return players
    
#     players = extract_players(soup)
#     logging.info(f"jugadores extraidos: {players}")
#     player_stats = {}
#     for player_name, player_url in players.items():
#         stats = get_player_stats(player_url, team_name)
#         logging.info(f"estadisticas del jugador extraido: {stats}")
#         player_stats[player_name] = stats

#             # Calcular estadísticas globales
    
#     global_stats = calculate_global_stats(player_stats)
#     logging.info(f"estadisticas extraidas: {player_stats}")
#     return player_stats, global_stats

# def get_player_stats(player_url, team_role, rival_name):
#     """
#     Scrapea las estadísticas individuales de un jugador.
#     """
#     response = requests.get(player_url)
#     if response.status_code != 200:
#         logging.error(f"error del servidor: {response}")
#         return []

#     soup = BeautifulSoup(response.text, 'html.parser')
#     stats_table = soup.find('table', class_='table')
#     logging.info(f"tabla de stats obtenida: {stats_table}")
#     if not stats_table:
#         return []

#     rows = stats_table.find_all('tr')[1:]
#     logging.info(f"filas de las tablas: {rows}")
#     player_stats = []
#     for row in rows:
#         cols = row.find_all('td')
#         logging.info(f"columnas del jugador: {cols}")
#         if len(cols) < 19:
#             logging.error(f"Menos de 19 columnas, fila ignorada.")
#             continue

#         try:
#             # Extraer detalles del partido
#             opponent_info = cols[0].find('a').text.strip() if cols[0].find('a') else cols[0].text.strip()
#             is_home = "vs" in opponent_info
#             opponent = opponent_info.replace("vs", "").replace("@", "").strip()

#             # Validar si el oponente está en la lista de equipos válidos
#             if opponent not in equipos:
#                 logging.warning(f"Oponente '{opponent}' no es un equipo válido. Fila ignorada.")
#                 continue

#             # Columna 2 contiene la fecha
#             date = cols[1].find('a').text.strip() if cols[1].find('a') else cols[1].text.strip()

#             # Extraer estadísticas individuales del jugador
#             stats = {
#                 "date": date,
#                 "opponent": opponent,
#                 "home_or_away": "home" if is_home else "away",
#                 "PTS": float(cols[3].text.strip()) if cols[3].text.strip().isdigit() else 0,
#                 "REB": float(cols[4].text.strip()) if cols[4].text.strip().isdigit() else 0,
#                 "AST": float(cols[5].text.strip()) if cols[5].text.strip().isdigit() else 0,
#                 "MIN": float(cols[6].text.strip()) if cols[6].text.strip().isdigit() else 0,
#                 "2M": float(cols[7].text.split('-')[0]) if "-" in cols[7].text else 0,
#                 "2A": float(cols[7].text.split('-')[1]) if "-" in cols[7].text else 0,
#                 "3M": float(cols[8].text.split('-')[0]) if "-" in cols[8].text else 0,
#                 "3A": float(cols[8].text.split('-')[1]) if "-" in cols[8].text else 0,
#                 "STL": float(cols[16].text.strip()) if cols[16].text.strip().isdigit() else 0,
#                 "BLK": float(cols[18].text.strip()) if cols[18].text.strip().isdigit() else 0,
#                 "TO": float(cols[17].text.strip()) if cols[17].text.strip().isdigit() else 0,
#             }

#             # Añadir combinaciones de estadísticas
#             stats["PTS+AST"] = stats["PTS"] + stats["AST"]
#             stats["REB+AST"] = stats["REB"] + stats["AST"]
#             stats["PTS+REB"] = stats["PTS"] + stats["REB"]
#             stats["PTS+REB+AST"] = stats["PTS"] + stats["REB"] + stats["AST"]

#             player_stats.append(stats)
#         except (ValueError, IndexError) as e:
#             logging.error(f"Error procesando fila: {e}")
#             continue

#     return player_stats

# def calculate_global_stats(player_stats):
#     """
#     Calcula estadísticas globales para un equipo a partir de las estadísticas individuales de los jugadores.
#     """
#     all_stats = {
#         "PTS": [],
#         "REB": [],
#         "AST": [],
#         "STL": [],
#         "BLK": [],
#         "TO": [],
#         "2M": [],
#         "2A": [],
#         "3M": [],
#         "3A": [],
#         "PTS+AST": [],
#         "REB+AST": [],
#         "PTS+REB": [],
#         "PTS+REB+AST": [],
#     }

#     for player_name, stats in player_stats.items():
#         for stat_entry in stats:
#             for key in all_stats.keys():
#                 if key in stat_entry:
#                     all_stats[key].append(stat_entry[key])

#     global_stats = {key: round(np.mean(values), 2) for key, values in all_stats.items() if values}
#     return global_stats

# @app.route('/analyze', methods=['POST'])
# def analyze():
#     data = request.json
#     local_team_name = data.get('localTeamName')
#     visitor_team_name = data.get('visitorTeamName')
#     logging.info(f"Analizando los equipos {local_team_name} y {visitor_team_name}")
#     try:
#         # Usar la lista `equipos` para verificar que los equipos son válidos
#         if local_team_name not in equipos or visitor_team_name not in equipos:
#             return jsonify({"status": "error", "message": "Equipo no válido"}), 400

#         # Scraping y actualización
#         if needs_update(local_team_name):
#             logging.info(f"Analizando equipo local")
#             local_players_stats, local_global_stats = scrape_team_stats(local_team_name, "home")
#             update_team_data(local_team_name, local_players_stats, local_global_stats)

#         if needs_update(visitor_team_name):
#             logging.info(f"Analizando equipo visitante")
#             visitor_players_stats, visitor_global_stats = scrape_team_stats(visitor_team_name, "away")
#             update_team_data(visitor_team_name, visitor_players_stats, visitor_global_stats)

#         # Leer datos actualizados
#         local_data = read_json(os.path.join(DATA_DIR, f"{local_team_name}.json"))
#         visitor_data = read_json(os.path.join(DATA_DIR, f"{visitor_team_name}.json"))

#         result = {
#             "status": "success",
#             "local_team": local_data,
#             "visitor_team": visitor_data,
#         }
#         return jsonify(result)

#     except Exception as e:
#         return jsonify({"status": "error", "message": str(e)}), 500

# @app.route('/player_action', methods=['POST'])
# def player_action():
#     data = request.json
#     player_name = data.get("playerName")
#     team_name = data.get("teamName")
#     role = data.get("role")  # "local" o "visitor"
#     action = data.get("action")  # "graph" o "table"
#     value = data.get("stat", "MIN")  # Estadística específica; por defecto es "MIN"

#     if not player_name or not team_name or not role or not action:
#         return jsonify({"status": "error", "message": "Datos insuficientes"}), 400

#     try:
#         # Leer los datos del equipo desde el archivo JSON
#         file_path = os.path.join(DATA_DIR, f"{team_name}.json")
#         team_data = read_json(file_path)

#         if not team_data or player_name not in team_data.get("players", {}):
#             return jsonify({"status": "error", "message": f"No se encontraron datos para {player_name} en {team_name}"}), 404

#         # Extraer datos del jugador
#         player_data = team_data["players"][player_name]
#         if not player_data:
#             return jsonify({"status": "error", "message": "No hay datos disponibles para este jugador"}), 404

#         if action == "graph":
#             # Generar gráfica con la estadística solicitada
#             html_path = os.path.join("static", "player_graphs", f"{player_name}_{value}.html")
#             generate_player_graph_bokeh(player_name, player_data, value)
#             return jsonify({"status": "success", "html_path": f"/{html_path}"})

#         elif action == "table":
#             # Preparar datos de la tabla
#             return generate_player_table(player_name, player_data)

#         else:
#             return jsonify({"status": "error", "message": "Acción no válida"}), 400

#     except Exception as e:
#         return jsonify({"status": "error", "message": str(e)}), 500

# def generate_player_graph(player_name, player_data, value):
#     """
#     Genera una gráfica de barras para un jugador específico con líneas que marcan
#     el máximo, el mínimo y el valor que se supera el 90%, 80% y 70% del tiempo.
#     Si el value es 2 o 3, se genera una gráfica apilada con intentos y aciertos.
#     """

#     try:
#         # Extraer fechas
#         dates = [entry["date"] for entry in player_data]

#         if value == 2 or value == 3:
#             # Gráfica apilada para tiros de 2 o 3
#             attempts_key = f"{value}A"  # Ejemplo: "2m" o "3m"
#             successes_key = f"{value}M"  # Ejemplo: "2a" o "3a"
#             attempts = [entry[attempts_key] for entry in player_data]
#             successes = [entry[successes_key] for entry in player_data]

#             # Ajustar límites del gráfico
#             max_attempts = max(attempts)
#             lower_limit = 0  # Límite inferior fijo
#             upper_limit = max_attempts + (0.1 * max_attempts)  # Límite superior dinámico

#             # Crear la gráfica apilada
#             plt.figure(figsize=(14, 8))
#             bars_attempts = plt.bar(dates, attempts, color="skyblue", edgecolor="black", label="Intentos")
#             bars_successes = plt.bar(dates, successes, color="green", edgecolor="black", label="Aciertos")

#             # Añadir etiquetas para intentos y aciertos
#             for bar_attempt, bar_success, attempt, success in zip(bars_attempts, bars_successes, attempts, successes):
#                 # Etiqueta para intentos (en la parte superior de la barra completa)
#                 plt.text(bar_attempt.get_x() + bar_attempt.get_width() / 2, bar_attempt.get_height() + 0.5,
#                          f"{attempt}", ha='center', va='bottom', fontsize=10, fontweight='bold', color="black")
#                 # Etiqueta para aciertos (justo debajo del límite superior de la barra de aciertos)
#                 plt.text(bar_success.get_x() + bar_success.get_width() / 2, bar_success.get_height() - 0.5,
#                          f"{success}", ha='center', va='top', fontsize=10, fontweight='bold', color="white")

#             # Títulos y etiquetas
#             plt.title(f"Tiros de {value} puntos: {player_name}", fontsize=16, fontweight='bold')
#             plt.xlabel("Fecha", fontsize=14, fontweight='bold')
#             plt.ylabel(f"Tiros de {value} puntos", fontsize=14, fontweight='bold')
#             plt.xticks(rotation=45, ha='right', fontsize=12, fontweight='bold')
#             plt.yticks(fontsize=12, fontweight='bold')
#             plt.ylim(lower_limit, upper_limit)

#             # Ajuste de la leyenda
#             plt.legend(loc="upper left", fontsize=12)
#             plt.tight_layout()

#         else:
#             # Gráfica normal para otros valores
#             values = [entry[value] for entry in player_data]

#             # Calcular estadísticos
#             max_value = max(values)
#             min_value = min(values)

#             # Calcular los límites superados el 90%, 80% y 70% del tiempo
#             sorted_values = sorted(values)
#             threshold_90 = sorted_values[int(len(sorted_values) * 0.1)]
#             threshold_80 = sorted_values[int(len(sorted_values) * 0.2)]
#             threshold_70 = sorted_values[int(len(sorted_values) * 0.3)]

#             # Ajustar límites del gráfico
#             lower_limit = min_value - (0.1 * (max_value - min_value))
#             upper_limit = max_value + (0.1 * (max_value - min_value))

#             # Crear la gráfica
#             plt.figure(figsize=(12, 8))
#             bars = plt.bar(dates, values, color="skyblue", edgecolor="black")

#             # Añadir líneas horizontales
#             plt.axhline(threshold_90, color="green", linestyle="--", linewidth=2,
#                         label=f"Superado 90%: {threshold_90}", alpha=0.8)
#             plt.axhline(threshold_80, color="yellow", linestyle="--", linewidth=2,
#                         label=f"Superado 80%: {threshold_80}", alpha=0.8)
#             plt.axhline(threshold_70, color="orange", linestyle="--", linewidth=2,
#                         label=f"Superado 70%: {threshold_70}", alpha=0.8)

#             # Añadir líneas horizontales en el fondo
#             plt.grid(axis='y', linestyle='--', linewidth=0.7, alpha=0.7)

#             # Añadir etiquetas dentro de las barras
#             for bar, bar_value in zip(bars, values):
#                 plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() - (0.05 * bar.get_height()),
#                          f"{bar_value}", ha='center', va='top', fontsize=10, fontweight='bold', color="black")

#             # Títulos y etiquetas
#             plt.title(f"Gráfica de {value}: {player_name}", fontsize=16, fontweight='bold')
#             plt.xlabel("Fecha", fontsize=14, fontweight='bold')
#             plt.ylabel(f"{value}", fontsize=14, fontweight='bold')
#             plt.xticks(rotation=45, ha='right', fontsize=12, fontweight='bold')
#             plt.yticks(fontsize=12, fontweight='bold')
#             plt.ylim(lower_limit, upper_limit)

#             # Ajuste de la leyenda
#             plt.legend(loc="upper left", fontsize=12)
#             plt.tight_layout()

#         # Convertir gráfica a base64
#         buffer = BytesIO()
#         plt.savefig(buffer, format="png")
#         buffer.seek(0)
#         encoded_image = base64.b64encode(buffer.getvalue()).decode("utf-8")
#         buffer.close()
#         plt.close()

#         return jsonify({"status": "success", "image": encoded_image})

#     except Exception as e:
#         return jsonify({"status": "error", "message": f"Error generando gráfica: {str(e)}"}), 500

# def generate_player_table(player_name, player_data):
#     """
#     Devuelve los datos del jugador en formato JSON para generar una tabla en el frontend.
#     """
#     try:
#         # Preparar los datos
#         table_data = [
#             {
#                 "date": entry["date"],
#                 "opponent": entry["opponent"],
#                 "home_or_away": entry["home_or_away"],
#                 "PTS": entry["PTS"],
#                 "REB": entry["REB"],
#                 "AST": entry["AST"],
#                 "MIN": entry["MIN"],
#                 "PTS+REB": entry["PTS"] + entry["REB"],
#                 "PTS+AST": entry["PTS"] + entry["AST"],
#                 "REB+AST": entry["REB"] + entry["AST"],
#                 "PTS+REB+AST": entry["PTS"] + entry["REB"] + entry["AST"],
#             }
#             for entry in player_data
#         ]

#         return jsonify({"status": "success", "data": table_data})

#     except Exception as e:
#         return jsonify({"status": "error", "message": f"Error generando tabla: {str(e)}"}), 500

# # def generate_player_graph(player_name, player_data, value):
# #     """
# #     Genera una gráfica animada para un jugador específico con líneas que marcan
# #     el máximo, el mínimo y el valor que se supera el 90%, 80% y 70% del tiempo.
# #     Si el value es 2 o 3, se genera una gráfica apilada con intentos y aciertos.
# #     """
# #     try:
# #         dates = [entry["date"] for entry in player_data]

# #         fig, ax = plt.subplots(figsize=(14, 8))
        
# #         if value == 2 or value == 3:
# #             # Preparar datos para gráfica apilada
# #             attempts_key = f"{value}A"
# #             successes_key = f"{value}M"
# #             attempts = [entry[attempts_key] for entry in player_data]
# #             successes = [entry[successes_key] for entry in player_data]
# #             bar_width = 0.8
# #             max_attempts = max(attempts)

# #             # Crear barras vacías inicialmente
# #             bars_attempts = ax.bar(dates, [0] * len(dates), bar_width, color="skyblue", label="Intentos")
# #             bars_successes = ax.bar(dates, [0] * len(dates), bar_width, color="green", label="Aciertos")
# #             ax.set_ylim(0, max_attempts * 1.2)

# #             def update(frame):
# #                 # Actualizar las alturas de las barras
# #                 for bar, attempt in zip(bars_attempts, attempts):
# #                     bar.set_height(min(attempt, frame))
# #                 for bar, success in zip(bars_successes, successes):
# #                     bar.set_height(min(success, frame))

# #                 return list(bars_attempts) + list(bars_successes)

# #         else:
# #             # Preparar datos para gráfica normal
# #             values = [entry[value] for entry in player_data]
# #             max_value = max(values)
# #             sorted_values = sorted(values)
# #             threshold_90 = sorted_values[int(len(sorted_values) * 0.1)]
# #             threshold_80 = sorted_values[int(len(sorted_values) * 0.2)]
# #             threshold_70 = sorted_values[int(len(sorted_values) * 0.3)]
            
# #             bars = ax.bar(dates, [0] * len(dates), color="skyblue", edgecolor="black")
# #             ax.set_ylim(0, max_value * 1.2)

# #             # Dibujar líneas horizontales
# #             thresholds = [
# #                 (threshold_90, "green", "90%"),
# #                 (threshold_80, "yellow", "80%"),
# #                 (threshold_70, "orange", "70%"),
# #             ]
# #             lines = [ax.axhline(y=0, color=color, linestyle="--", label=f"Superado {label}") for _, color, label in thresholds]

# #             def update(frame):
# #                 # Actualizar las alturas de las barras
# #                 for bar, value in zip(bars, values):
# #                     bar.set_height(min(value, frame))
                
# #                 # Actualizar las líneas
# #                 for line, (threshold, _, _) in zip(lines, thresholds):
# #                     line.set_ydata([min(threshold, frame)] * 2)
                
# #                 return list(bars) + lines

# #         # Configurar ejes, títulos y leyenda
# #         ax.set_title(f"Gráfica Animada: {player_name}", fontsize=16)
# #         ax.set_xlabel("Fecha", fontsize=14)
# #         ax.set_ylabel("Valores", fontsize=14)
# #         ax.legend(fontsize=12)
# #         ax.grid(True)

# #         # Crear lista de imágenes para animación
# #         frames = []
# #         for frame in np.arange(0, max_value * 1.2, max_value * 0.05):
# #             update(frame)
# #             # Convertir el gráfico actual a imagen y agregarla a la lista de frames
# #             buffer = BytesIO()
# #             plt.savefig(buffer, format="png")
# #             buffer.seek(0)
# #             frames.append(Image.open(buffer))
# #             buffer.close()  # Cerramos cada buffer inmediatamente después de usarlo
        
# #         # Guardar como GIF
# #         gif_buffer = BytesIO()
# #         frames[0].save(
# #             gif_buffer,
# #             format="GIF",
# #             save_all=True,
# #             append_images=frames[1:],
# #             duration=100,
# #             loop=0,
# #         )
# #         gif_buffer.seek(0)
# #         encoded_gif = base64.b64encode(gif_buffer.getvalue()).decode("utf-8")
# #         gif_buffer.close()  # Cerramos el buffer del GIF solo después de codificarlo

# #         # Mostrar la gráfica en VSC para depuración
# #         plt.show()  # Agregado para visualizar la gráfica
# #         plt.close()

# #         return jsonify({"status": "success", "animation": encoded_gif})

# #     except Exception as e:
# #         return jsonify({"status": "error", "message": f"Error generando gráfica: {str(e)}"}), 500

# def generate_player_graph(player_name, player_data, value):
#     """
#     Genera una gráfica de barras para un jugador específico con líneas que marcan
#     el máximo, el mínimo y el valor que se supera el 90%, 80% y 70% del tiempo.
#     Si el value es 2 o 3, se genera una gráfica apilada con intentos y aciertos.
#     """
#     try:
#         # Extraer fechas
#         dates = [entry["date"] for entry in player_data]

#         if value == 2 or value == 3:
#             # Gráfica apilada para tiros de 2 o 3
#             attempts_key = f"{value}A"  # Ejemplo: "2A" o "3A"
#             successes_key = f"{value}M"  # Ejemplo: "2M" o "3M"
#             attempts = [entry[attempts_key] for entry in player_data]
#             successes = [entry[successes_key] for entry in player_data]

#             source = ColumnDataSource(data=dict(
#                 dates=dates,
#                 attempts=attempts,
#                 successes=successes
#             ))

#             # Crear gráfica apilada
#             p = figure(
#                 x_range=dates,
#                 title=f"Tiros de {value} puntos: {player_name}",
#                 toolbar_location=None,
#                 tools=""
#             )
#             p.vbar_stack(
#                 ['successes', 'attempts'], 
#                 x='dates', 
#                 width=0.8, 
#                 color=["green", "skyblue"], 
#                 source=source,
#                 legend_label=["Aciertos", "Intentos"]
#             )

#             # Personalización
#             p.xgrid.grid_line_color = None
#             p.y_range.start = 0
#             p.yaxis.axis_label = f"Tiros de {value} puntos"
#             p.xaxis.axis_label = "Fecha"
#             p.xaxis.major_label_orientation = 1.2

#         else:
#             # Gráfica normal para otros valores
#             values = [entry[value] for entry in player_data]

#             # Calcular estadísticos
#             max_value = max(values)
#             min_value = min(values)
#             sorted_values = sorted(values)
#             threshold_90 = sorted_values[int(len(sorted_values) * 0.1)]
#             threshold_80 = sorted_values[int(len(sorted_values) * 0.2)]
#             threshold_70 = sorted_values[int(len(sorted_values) * 0.3)]

#             source = ColumnDataSource(data=dict(
#                 dates=dates,
#                 values=values
#             ))

#             # Crear gráfica
#             p = figure(
#                 x_range=dates,
#                 title=f"Gráfica de {value}: {player_name}",
#                 toolbar_location=None,
#                 tools=""
#             )
#             p.vbar(
#                 x='dates', 
#                 top='values', 
#                 width=0.8, 
#                 source=source, 
#                 color="skyblue", 
#                 legend_label="Valores"
#             )

#             # Líneas horizontales
#             p.line(dates, [threshold_90] * len(dates), line_dash="dashed", line_color="green", legend_label="90%")
#             p.line(dates, [threshold_80] * len(dates), line_dash="dashed", line_color="yellow", legend_label="80%")
#             p.line(dates, [threshold_70] * len(dates), line_dash="dashed", line_color="orange", legend_label="70%")

#             # Personalización
#             p.xgrid.grid_line_color = None
#             p.y_range.start = 0
#             p.yaxis.axis_label = value
#             p.xaxis.axis_label = "Fecha"
#             p.xaxis.major_label_orientation = 1.2

#         # Configuración de la salida HTML
#         output_file_path = f"static/{player_name}_graph.html"
#         output_file(output_file_path)
#         save(p)
        
#         # Devolver el path relativo del archivo HTML
#         return jsonify({"status": "success", "html_path": output_file_path})

#     except Exception as e:
#         return jsonify({"status": "error", "message": f"Error generando gráfica: {str(e)}"}), 500
