import datetime
import json

def generate_date_ids(start_year, end_year):
    """
    Genera un diccionario con IDs consecutivos para cada fecha desde el año inicial hasta el final.
    """
    date_ids = {}
    start_date = datetime.date(start_year, 1, 1)
    end_date = datetime.date(end_year, 12, 31)
    delta = datetime.timedelta(days=1)

    current_date = start_date
    unique_id = 1  # ID inicial

    meses_espanol = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

    while current_date <= end_date:
        # Formatear la fecha y generar un ID consecutivo
        dia = current_date.day
        mes = meses_espanol[current_date.month - 1]
        anio = current_date.year

        # Formato "1 ene 2024" sin ceros delante
        date_str = f"{dia} {mes} {anio}"
        date_ids[date_str] = unique_id

        # Incrementar fecha e ID
        current_date += delta
        unique_id += 1

    return date_ids

# Generar IDs de fecha desde 2019 hasta 2026
date_ids = generate_date_ids(2019, 2028)

# Guardar en un archivo JSON
output_file = "date_ids.json"
with open(output_file, "w", encoding="utf-8") as file:
    json.dump(date_ids, file, indent=4, ensure_ascii=False)

print(f"Archivo {output_file} generado con IDs de fecha.")
