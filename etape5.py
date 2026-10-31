import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests
import yaml


class IngestionError(Exception):
    """Erreur de collecte : l'API est injoignable ou répond de façon inattendue."""


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


def get_json(url, params, retries=3, backoff=2):
    """Appelle l'API. Si elle ne répond pas, réessaie avec des pauses de plus en plus longues."""
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as error:
            if attempt == retries:
                raise IngestionError(f"échec après {retries} essais ({type(error).__name__})") from error
            wait = backoff ** attempt
            print(f"  essai {attempt}/{retries} échoué ({type(error).__name__}), nouvel essai dans {wait}s")
            time.sleep(wait)


def fetch_pages(url, params, indicator):
    """Lit toutes les pages de la réponse. Retourne la liste des réponses brutes."""
    pages = []
    page = 1
    while True:
        payload = get_json(url, {**params, "page": page})
        valid = (
            isinstance(payload, list)
            and len(payload) == 2
            and isinstance(payload[0], dict)
            and "pages" in payload[0]
        )
        if not valid:
            raise IngestionError(f"réponse inattendue : {str(payload)[:150]}")
        pages.append(payload)
        if page >= payload[0]["pages"]:
            return pages
        page += 1


def collect(indicator, config):
    """Collecte un indicateur pour tous les pays et sauvegarde le brut dans bronze."""
    countries = ";".join(config["countries"])
    url = f"{config['base_url']}/country/{countries}/indicator/{indicator}"
    params = {
        "format": "json",
        "per_page": config["per_page"],
        "date": f"{config['period']['start']}:{config['period']['end']}",
    }
    pages = fetch_pages(url, params, indicator)

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
        "pages": pages,
    }
    with open(path, "x", encoding="utf-8") as file:
        json.dump(record, file, ensure_ascii=False)

    all_rows = [row for page in pages for row in (page[1] or [])]
    missing = sum(1 for row in all_rows if row["value"] is None)
    return len(all_rows), missing, len(pages)


def main():
    config = load_config()
    started = time.perf_counter()
    failures = []
    total_rows = 0

    for indicator in config["indicators"]:
        try:
            rows, missing, n_pages = collect(indicator, config)
        except (IngestionError, OSError) as error:
            print(f"{indicator}: ÉCHEC - {error}")
            failures.append(indicator)
            continue
        total_rows += rows
        print(f"{indicator}: {rows} lignes ({n_pages} page(s)), dont {missing} sans valeur")

    elapsed = time.perf_counter() - started
    total = len(config["indicators"])
    print(f"\nTerminé : {total - len(failures)}/{total} indicateurs, {total_rows} lignes, {elapsed:.1f}s")
    if failures:
        print("Indicateurs en échec :", failures)
        sys.exit(1)


if __name__ == "__main__":
    main()
