import json
from datetime import date, datetime, timezone
from pathlib import Path

import requests
import yaml


def load_config(path="config/pipeline.yml"):
    """Lit le fichier de configuration et vérifie qu'il est cohérent."""
    with open(path, encoding="utf-8") as file:
        config = yaml.safe_load(file)

    if config["period"]["end"] is None:
        config["period"]["end"] = date.today().year
    if config["period"]["start"] > config["period"]["end"]:
        raise ValueError("period.start doit être inférieur ou égal à period.end")
    if not config["countries"]:
        raise ValueError("La liste des pays est vide")
    return config


def collect(indicator, config):
    """Collecte un indicateur pour tous les pays et sauvegarde le brut dans bronze."""
    countries = ";".join(config["countries"])
    url = f"{config['base_url']}/country/{countries}/indicator/{indicator}"
    params = {
        "format": "json",
        "per_page": config["per_page"],
        "date": f"{config['period']['start']}:{config['period']['end']}",
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()

    pages = payload[0]["pages"]
    if pages > 1:
        print(f"  ATTENTION : {indicator} a {pages} pages, seule la première est récupérée")

    collected_at = datetime.now(timezone.utc)
    stamp = collected_at.strftime("%Y%m%dT%H%M%S%fZ")
    path = Path(config["data_dir"]) / "bronze" / "worldbank" / indicator / f"{stamp}.json"
    path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "source": "worldbank_indicators_v2",
        "indicator": indicator,
        "indicator_label": config["indicators"][indicator],
        "collected_at": collected_at.isoformat(),
        "request": {"url": url, "params": params},
        "payload": payload,
    }
    with open(path, "x", encoding="utf-8") as file:
        json.dump(record, file, ensure_ascii=False)

    rows = payload[1]
    missing = sum(1 for row in rows if row["value"] is None)
    return path, len(rows), missing


config = load_config()
for indicator in config["indicators"]:
    path, rows, missing = collect(indicator, config)
    print(f"{indicator}: {rows} lignes, dont {missing} sans valeur")
    print(f"  -> {path}")
