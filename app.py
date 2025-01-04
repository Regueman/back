import os
import json
import logging
from flask import Flask, request, jsonify
from pymongo import MongoClient
from utils.scraper import initialize_collections, scrape_stats, calculate_all_stats, get_player_team_opponent_data
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

# Configuración de MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["datips"]

@app.route('/rankings', methods=['GET'])
def get_rankings():
    """
    Endpoint para obtener las posiciones de los rankings de un equipo y un oponente,
    tanto en general como en la posición específica (home/away).
    """
    try:
        # Obtener parámetros de la solicitud
        team = request.args.get('team')
        opponent = request.args.get('opponent')
        home_or_away = request.args.get('home_or_away')

        if not team or not opponent or home_or_away not in ["home", "away"]:
            return jsonify({"error": "Parámetros inválidos. Se requieren 'team', 'opponent' y 'home_or_away' (home o away)."}), 400

        # Leer rankings de la base de datos
        rankings = db.rankings.find_one({"_id": "rankings"})
        if not rankings:
            return jsonify({"error": "No se encontraron datos de rankings en la base de datos."}), 404

        # Procesar rankings del equipo
        team_rankings = {"global": {}, "home_or_away": {}}
        opponent_rankings = {"global": {}, "home_or_away": {}}

        # Acceso a rankings globales
        for stat in ["PTS", "REB", "AST", "2A", "2M", "3A", "3M", "STL", "BLK", "TO"]:
            # Acceso a team_rankings
            team_stat_data = rankings.get("team_rankings", {}).get("top_average", {}).get(stat, [])
            for item in team_stat_data:
                if item["team"] == team:
                    team_rankings["global"][stat] = {
                        "position": item["position"],
                        "value": item["value"]
                    }
                    break

            # Acceso a opponent_rankings
            opponent_stat_data = rankings.get("opponent_rankings", {}).get("top_average", {}).get(stat, [])
            for item in opponent_stat_data:
                if item["opponent"] == opponent:
                    opponent_rankings["global"][stat] = {
                        "position": item["position"],
                        "value": item["value"]
                    }
                    break

        # Acceso a rankings específicos (home/away)
        specific_team_key = "top_home" if home_or_away == "home" else "top_away"
        specific_opponent_key = "top_away" if home_or_away == "home" else "top_home"

        for stat in ["PTS", "REB", "AST", "2A", "2M", "3A", "3M", "STL", "BLK", "TO"]:
            # Acceso a team_rankings específicos
            specific_team_stat_data = rankings.get("team_rankings", {}).get(specific_team_key, {}).get(stat, [])
            for item in specific_team_stat_data:
                if item["team"] == team:
                    team_rankings["home_or_away"][stat] = {
                        "position": item["position"],
                        "value": item["value"]
                    }
                    break

            # Acceso a opponent_rankings específicos
            specific_opponent_stat_data = rankings.get("opponent_rankings", {}).get(specific_opponent_key, {}).get(stat, [])
            for item in specific_opponent_stat_data:
                if item["opponent"] == opponent:
                    opponent_rankings["home_or_away"][stat] = {
                        "position": item["position"],
                        "value": item["value"]
                    }
                    break

        # Devolver el resultado
        return jsonify({
            team: team_rankings,
            opponent: opponent_rankings
        })

    except Exception as e:
        logger.error(f"Error al procesar los rankings: {e}")
        return jsonify({"error": f"Error al procesar los rankings: {e}"}), 500


@app.route("/api/player-stats", methods=["GET"])
def player_stats():
    """
    Endpoint para obtener las estadísticas del jugador, equipo y oponente.
    """
    try:
        team = request.args.get("team")
        player_name = request.args.get("player_name")
        home_or_away = request.args.get("home_or_away")
        opponent = request.args.get("opponent")

        if not all([team, player_name, home_or_away, opponent]):
            return jsonify({"error": "Parámetros incompletos"}), 400

        data = get_player_team_opponent_data(team, player_name, home_or_away, opponent)

        return jsonify(data)
    except Exception as e:
        logger.error(f"Error al procesar la solicitud: {str(e)}")
        return jsonify({"error": f"Error al procesar la solicitud: {str(e)}"}), 500

@app.route('/api/teams', methods=['GET'])
def get_teams():
    """
    Devuelve una lista de equipos disponibles en la base de datos.
    """
    try:
        teams = list(equipos.keys())  # Usamos la variable global `equipos`
        return jsonify(teams), 200
    except Exception as e:
        logger.error(f"Error al obtener la lista de equipos: {e}")
        return jsonify({"error": "Error al obtener la lista de equipos"}), 500

@app.route('/api/players/<team>', methods=['GET'])
def get_players_by_team(team):
    """
    Devuelve una lista de jugadores que han jugado en un equipo específico
    basándose en la colección `stats`.
    """
    try:
        if team not in equipos:
            return jsonify({"error": "Equipo no encontrado"}), 404

        players = db.stats.distinct("name", {"team": team})

        if not players:
            return jsonify([]), 200

        return jsonify(players), 200
    except Exception as e:
        logger.error(f"Error al obtener jugadores del equipo {team}: {e}")
        return jsonify({"error": "Error al obtener jugadores"}), 500



import json

initialize_collections()
scrape_stats()
calculate_all_stats()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
