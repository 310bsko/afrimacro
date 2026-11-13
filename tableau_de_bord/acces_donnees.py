"""Accès aux données du tableau de bord.

Rôle dans le pipeline : le tableau de bord lit PostgreSQL quand l'entrepôt est
disponible (poste local). En ligne, il n'y a pas de base : il lit alors
l'instantané versionné dans `instantane/`, produit par `exporter_instantane.py`.

Le même code (`lire_vue_postgres`) sert à lire la base ET à écrire l'instantané,
donc les deux chemins donnent exactement les mêmes colonnes et les mêmes types.
"""

import json
import os
from decimal import Decimal
from pathlib import Path

import pandas as pd

try:  # absent de l'hébergement en ligne : volontairement non installé là-bas
    import psycopg
except ImportError:
    psycopg = None

DOSSIER_INSTANTANE = Path(__file__).parent / "instantane"
NOM_FICHIER_OBSERVATIONS = "observations.parquet"
NOM_FICHIER_META = "meta.json"
NOM_FICHIER_GROUPES = "groupes_pays.csv"
# Résultat local du regroupement (regroupement_pays.py), publié dans l'instantané par exporter_instantane.py
CHEMIN_GROUPES_LOCAL = Path(__file__).parent.parent / "donnees" / "analyse" / NOM_FICHIER_GROUPES

ERREURS_BASE = (RuntimeError,) + ((psycopg.Error,) if psycopg else ())


def _normaliser_types(donnees: pd.DataFrame) -> pd.DataFrame:
    """Convertit les NUMERIC de PostgreSQL (Decimal) en nombres décimaux classiques."""
    for colonne in donnees.columns:
        if donnees[colonne].dtype == object and donnees[colonne].map(
            lambda v: isinstance(v, Decimal)
        ).any():
            donnees[colonne] = pd.to_numeric(
                donnees[colonne].map(lambda v: None if v is None else float(v)),
                errors="coerce",
            )
    return donnees


def lire_vue_postgres() -> pd.DataFrame:
    """Lit la vue `vue_observations`. Lève une erreur si la base est injoignable."""
    if psycopg is None:
        raise RuntimeError("psycopg n'est pas installé")
    try:
        parametres = {
            "host": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
            "port": os.environ.get("POSTGRES_PORT", "5432"),
            "dbname": os.environ["POSTGRES_DB"],
            "user": os.environ["POSTGRES_USER"],
            "password": os.environ["POSTGRES_PASSWORD"],
        }
    except KeyError as erreur:
        raise RuntimeError(f"variable d'environnement absente : {erreur}") from erreur

    with psycopg.connect(**parametres, connect_timeout=3) as connexion:
        with connexion.cursor() as curseur:
            curseur.execute("SELECT * FROM vue_observations")
            colonnes = [colonne.name for colonne in curseur.description]
            lignes = curseur.fetchall()
    return _normaliser_types(pd.DataFrame(lignes, columns=colonnes))


def lire_meta_instantane() -> dict:
    chemin = DOSSIER_INSTANTANE / NOM_FICHIER_META
    return json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}


def charger_observations() -> tuple[pd.DataFrame, str]:
    """Retourne (données, origine). Base locale si possible, sinon instantané.

    L'origine est affichée dans le tableau de bord : on ne masque jamais
    le fait que l'on lit une copie figée plutôt que la base.
    """
    if os.environ.get("POSTGRES_PASSWORD"):  # sans mot de passe : pas de base, inutile d'essayer
        try:
            return lire_vue_postgres(), "base PostgreSQL (entrepôt local)"
        except ERREURS_BASE:
            pass  # base arrêtée ou injoignable : on retombe sur l'instantané

    chemin = DOSSIER_INSTANTANE / NOM_FICHIER_OBSERVATIONS
    if not chemin.exists():
        raise FileNotFoundError(
            "Aucune source de données : démarrer PostgreSQL (docker compose up -d) "
            "ou générer l'instantané avec exporter_instantane.py."
        )
    date_export = lire_meta_instantane().get("date_export", "date inconnue")
    return pd.read_parquet(chemin), f"instantané du {date_export}"


def charger_groupes() -> pd.DataFrame | None:
    """Groupes de pays issus du regroupement (CAH).

    Le fichier local, s'il existe, est lu en premier ; sinon la copie publiée avec l'instantané.
    """
    for chemin in (CHEMIN_GROUPES_LOCAL, DOSSIER_INSTANTANE / NOM_FICHIER_GROUPES):
        if chemin.exists():
            return pd.read_csv(chemin)
    return None
