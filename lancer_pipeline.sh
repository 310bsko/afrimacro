#!/usr/bin/env bash
# Lance tout le pipeline, dans l'ordre. Il s'arrête à la première erreur.
set -euo pipefail

uv run ingestion_bronze.py
uv run silver_spark.py
uv run controles_qualite.py
uv run gold_spark.py
uv run --env-file .env chargement_entrepot.py
uv run --env-file .env exporter_instantane.py
