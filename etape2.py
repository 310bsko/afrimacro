import json
from datetime import datetime, timezone
from pathlib import Path

import requests

url = "https://api.worldbank.org/v2/country/CIV/indicator/SP.POP.TOTL"
params = {"format": "json", "date": "2020:2023"}

response = requests.get(url, params=params, timeout=30)
response.raise_for_status()
payload = response.json()

collected_at = datetime.now(timezone.utc)
stamp = collected_at.strftime("%Y%m%dT%H%M%SZ")

path = Path("data/bronze/worldbank/SP.POP.TOTL") / f"{stamp}.json"
path.parent.mkdir(parents=True, exist_ok=True)

record = {
    "source": "worldbank_indicators_v2",
    "indicator": "SP.POP.TOTL",
    "collected_at": collected_at.isoformat(),
    "request": {"url": url, "params": params},
    "payload": payload,
}

with open(path, "w", encoding="utf-8") as file:
    json.dump(record, file, ensure_ascii=False)

print("Écrit :", path)
