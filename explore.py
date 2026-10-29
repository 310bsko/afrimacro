import json
from collections import Counter
from pathlib import Path

folder = Path("data/bronze/worldbank/FP.CPI.TOTL.ZG")
path = sorted(folder.glob("*.json"))[-1]
record = json.loads(path.read_text(encoding="utf-8"))
rows = record["payload"][1]

years = sorted({int(row["date"]) for row in rows})
print("années :", years[0], "à", years[-1])

missing = Counter(row["countryiso3code"] for row in rows if row["value"] is None)
print(missing.most_common())
by_year = Counter(row["date"] for row in rows if row["value"] is None)
print(sorted(by_year.items()))
