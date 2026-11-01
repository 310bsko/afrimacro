import json
from pathlib import Path

BRONZE = Path("data/bronze/worldbank")


def latest_file(indicator_dir):
    """Le nom contient la date de collecte : le dernier par ordre alphabétique est le plus récent."""
    return sorted(indicator_dir.glob("*.json"))[-1]


def flatten(record):
    """Transforme l'enveloppe bronze en une liste de lignes simples (une par pays, indicateur et année)."""
    rows = []
    for page in record["pages"]:
        source_updated = page[0]["lastupdated"]
        for item in page[1] or []:
            rows.append({
                "country_code": item["countryiso3code"],
                "country_name": item["country"]["value"],
                "indicator_code": item["indicator"]["id"],
                "indicator_label": item["indicator"]["value"],
                "year": int(item["date"]),
                "value": None if item["value"] is None else float(item["value"]),
                "source": "worldbank",
                "source_updated": source_updated,
                "collected_at": record["collected_at"],
            })
    return rows


all_rows = []
for indicator_dir in sorted(BRONZE.iterdir()):
    record = json.loads(latest_file(indicator_dir).read_text(encoding="utf-8"))
    all_rows.extend(flatten(record))
keys = {(r["country_code"], r["indicator_code"], r["year"]) for r in all_rows}
print("clés uniques :", len(keys), "| doublons :", len(all_rows) - len(keys))        
print("lignes :", len(all_rows))
print("sans valeur :", sum(1 for r in all_rows if r["value"] is None))
for row in all_rows[:3]:
    print(row)
