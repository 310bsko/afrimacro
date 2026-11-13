import os
from datetime import date

import psycopg
import pyarrow.parquet as pq

CHEMIN_SILVER = "donnees/silver/indicateurs_banque_mondiale"
CODE_SOURCE = "banque_mondiale"

SQL_UPSERT_FAIT = """
    INSERT INTO fait_observation
        (id_pays, id_indicateur, id_source, annee, valeur, est_projection, source_mise_a_jour, date_collecte)
    VALUES (%s, %s, %s, %s, %s, FALSE, %s, %s)
    ON CONFLICT (id_pays, id_indicateur, id_source, annee)
    DO UPDATE SET valeur = EXCLUDED.valeur,
                  source_mise_a_jour = EXCLUDED.source_mise_a_jour,
                  date_collecte = EXCLUDED.date_collecte
"""


def se_connecter():
    """Ouvre la connexion à PostgreSQL. Les identifiants viennent de l'environnement (fichier .env)."""
    return psycopg.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=os.environ.get("POSTGRES_PORT", "5432"),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )


def lire_silver():
    """Lit le silver (Parquet) et renvoie une liste de dictionnaires, un par ligne."""
    return pq.read_table(CHEMIN_SILVER).to_pylist()


def charger_dimensions(curseur, lignes):
    """Ajoute les pays, indicateurs et années rencontrés. Renvoie les identifiants dont les faits ont besoin."""
    pays = {(ligne["code_pays"], ligne["nom_pays"]) for ligne in lignes}
    curseur.executemany(
        """INSERT INTO dim_pays (code_pays, nom_pays) VALUES (%s, %s)
           ON CONFLICT (code_pays) DO UPDATE SET nom_pays = EXCLUDED.nom_pays""",
        sorted(pays),
    )
    indicateurs = {(ligne["code_indicateur"], ligne["libelle_indicateur"]) for ligne in lignes}
    curseur.executemany(
        """INSERT INTO dim_indicateur (code_indicateur, libelle_indicateur) VALUES (%s, %s)
           ON CONFLICT (code_indicateur) DO UPDATE SET libelle_indicateur = EXCLUDED.libelle_indicateur""",
        sorted(indicateurs),
    )
    annees = sorted({ligne["annee"] for ligne in lignes})
    curseur.executemany(
        "INSERT INTO dim_annee (annee, decennie) VALUES (%s, %s) ON CONFLICT (annee) DO NOTHING",
        [(annee, annee // 10 * 10) for annee in annees],
    )

    curseur.execute("SELECT code_pays, id_pays FROM dim_pays")
    id_pays = dict(curseur.fetchall())
    curseur.execute("SELECT code_indicateur, id_indicateur FROM dim_indicateur")
    id_indicateurs = dict(curseur.fetchall())
    curseur.execute("SELECT id_source FROM dim_source WHERE code_source = %s", (CODE_SOURCE,))
    ligne_source = curseur.fetchone()
    if ligne_source is None:
        raise RuntimeError("Source introuvable : applique d'abord entrepot/schema.sql")
    return id_pays, id_indicateurs, ligne_source[0]


def charger_faits(curseur, lignes, id_pays, id_indicateurs, id_source):
    """Insère les observations. Si la clé existe déjà, la ligne est mise à jour : aucun doublon."""
    donnees = [
        (
            id_pays[ligne["code_pays"]],
            id_indicateurs[ligne["code_indicateur"]],
            id_source,
            ligne["annee"],
            ligne["valeur"],                      # None devient NULL : valeur manquante
            date.fromisoformat(ligne["source_mise_a_jour"]),
            ligne["date_collecte"],
        )
        for ligne in lignes
    ]
    curseur.executemany(SQL_UPSERT_FAIT, donnees)


def verifier(curseur):
    """Affiche les effectifs de l'entrepôt, à comparer avec ceux du silver."""
    curseur.execute("SELECT count(*), count(*) FILTER (WHERE valeur IS NULL) FROM fait_observation")
    total, sans_valeur = curseur.fetchone()
    print(f"fait_observation : {total} lignes, dont {sans_valeur} sans valeur")
    for table in ("dim_pays", "dim_indicateur", "dim_source", "dim_annee"):
        curseur.execute(f"SELECT count(*) FROM {table}")
        print(f"{table} : {curseur.fetchone()[0]} lignes")


def principal():
    lignes = lire_silver()
    print(f"silver : {len(lignes)} lignes lues")
    with se_connecter() as connexion:          # tout ou rien : validé à la fin, annulé en cas d'erreur
        with connexion.cursor() as curseur:
            id_pays, id_indicateurs, id_source = charger_dimensions(curseur, lignes)
            charger_faits(curseur, lignes, id_pays, id_indicateurs, id_source)
            verifier(curseur)


if __name__ == "__main__":
    principal()
