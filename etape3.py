import json
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE_URL = "https://api.worldbank.org/v2"
COUNTRIES = ["CIV", "GHA", "NGA", "SEN", "MLI", "BFA", "NER", "BEN",
             "TGO", "GIN", "SLE", "LBR", "GMB", "GNB", "CPV"]
INDICATORS = [
    "NY.GDP.MKTP.CD", "NY.GDP.MKTP.KD.ZG", "NY.GDP.PCAP.CD", "FP.CPI.TOTL.ZG",
    "SL.UEM.TOTL.ZS", "NE.EXP.GNFS.ZS", "NE.IMP.GNFS.ZS", "BN.CAB.XOKA.GD.ZS",
    "BX.KLT.DINV.WD.GD.ZS", "DT.DOD.DECT.GN.ZS", "FS.AST.PRVT.GD.ZS",
    "SP.POP.TOTL", "SP.DYN.LE00.IN", "EG.ELC.ACCS.ZS", "IT.NET.USER.ZS",
]
START_YEAR = 1990
END_YEAR = 2026


def collect(indicator):
    """Collecte un indicateur pour tous les pays et sauvegarde le brut dans bronze."""
    url = f"{BASE_URL}/country/{';'.join(COUNTRIES)}/indicator/{indicator}"
    params = {"format": "json", "per_page": 1000, "date": f"{START_YEAR}:{END_YEAR}"}

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()

    pages = payload[0]["pages"]
    if pages > 1:
        print(f"  ATTENTION : {indicator} a {pages} pages, seule la première est récupérée")

    collected_at = datetime.now(timezone.utc)
    stamp = collected_at.strftime("%Y%m%dT%H%M%S%fZ")
    path = Path("data/bronze/worldbank") / indicator / f"{stamp}.json"
    path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "source": "worldbank_indicators_v2",
        "indicator": indicator,
        "collected_at": collected_at.isoformat(),
        "request": {"url": url, "params": params},
        "payload": payload,
    }
    with open(path, "x", encoding="utf-8") as file:
        json.dump(record, file, ensure_ascii=False)

    rows = payload[1]
    missing = sum(1 for row in rows if row["value"] is None)
    return path, len(rows), missing


for indicator in INDICATORS:
    path, rows, missing = collect(indicator)
    print(f"{indicator}: {rows} lignes, dont {missing} sans valeur")
    print(f"  -> {path}")
