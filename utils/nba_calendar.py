import json
from bs4 import BeautifulSoup
import requests
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_date(fecha_str):
    """Convierte una fecha en formato '24 oct 2024' o similar en día, mes y año."""
    # Mapeo de nombres de meses en español a números
    meses = {
        "ene": "01", "feb": "02", "mar": "03", "abr": "04",
        "may": "05", "jun": "06", "jul": "07", "ago": "08",
        "sep": "09", "oct": "10", "nov": "11", "dic": "12"
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
    tabla = soup.find("div", class_="table__outer")
    if not tabla:
        logger.error("No se encontró la tabla principal en la página.")
        return []

    filas = tabla.find("table", class_="table").find_all("tr")[1:]  # Ignorar encabezados

    calendario = []

    for fila in filas:
        try:
            celdas = fila.find_all("td")
            if len(celdas) < 4:
                continue

            # Obtener fecha
            fecha_str = celdas[0].text.strip()
            dia, mes, anio = get_date(fecha_str)

            # Obtener hora
            hora = celdas[1].text.strip()

            # Obtener equipos
            equipo_home = celdas[2].text.strip()
            equipo_away = celdas[3].text.strip()

            # Agregar al calendario
            calendario.append({
                "date": {"day": dia, "month": mes, "year": anio},
                "time": hora,
                "home": equipo_home,
                "away": equipo_away
            })

        except Exception as e:
            logger.error(f"Error al procesar una fila: {e}")
            continue

    # Guardar en un archivo JSON
    with open("calendar.json", "w", encoding="utf-8") as f:
        json.dump(calendario, f, ensure_ascii=False, indent=4)

    logger.info("Calendario guardado en calendar.json")
    return calendario

if __name__ == "__main__":
    get_calendar()
