import os
import json
import logging
from flask import Flask, jsonify
from utils.scraper import scrape_stats, calculate_all_stats, initialize_collections
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

# TODO: modificar la funcion para que se obtengan los nombres de equipo desde la constante equipos
from datetime import datetime

#TODO: modificar el uso de date ids para modificar la cantidad de partidos
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


        for team_name in equipos.items():
            try:
                #scrape_team_stats(team_name)
                scrape_stats()
            except Exception as e:
                logger.error(f"Error al actualizar el equipo {team_name}: {str(e)}")

        logger.info("Todos los equipos actualizados. Iniciando cálculo de estadisticas consolidadas...")

        # Llamar a la función calculate_all stats
        calculate_all_stats()

        # Definir la ruta del archivo de salida
        consolidated_file = os.path.join(DATA_DIR, "v1_opponent_stats.json")

        if os.path.exists(consolidated_file):
            logger.info(f"Estadisticas consolidadas guardadas en {consolidated_file}")
            
            process_opponent_stats(consolidated_file, date_ids_path, output_path)

            return jsonify({
                "status": "success",
                "message": "Estadísticas de oponentes calculadas y guardadas correctamente.",
                "file": consolidated_file
            }), 200
        else:
            logger.error("El archivo consolidado no se encontró después de calcular las estadisticas.")
            return jsonify({
                "status": "error",
                "message": "El archivo consolidado no se generó correctamente."
            }), 500

    except Exception as e:
        logger.error(f"Error al procesar estadísticas de oponentes: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

import json
from collections import defaultdict

#TODO: modificar para que añada el identificador de fecha, cambiar signatura de la funcuion
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

initialize_collections()
scrape_stats()
calculate_all_stats()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
