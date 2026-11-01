import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

CHEMIN_SILVER = "donnees/silver/indicateurs_banque_mondiale"
DOSSIER_RAPPORTS = Path("donnees/qualite")

SEUIL_COUVERTURE = 0.70          # part minimale d'années renseignées pour un couple pays-indicateur
RETARD_MAX_ANNEES = 2            # écart toléré entre l'année de collecte et la dernière année renseignée
INDICATEURS_POURCENTAGE = ["EG.ELC.ACCS.ZS", "IT.NET.USER.ZS"]


def resultat(nom, reussi, detail, bloquant=True):
    """Un contrôle bloquant qui échoue arrête le pipeline ; sinon c'est un simple avertissement."""
    if reussi:
        statut = "OK"
    else:
        statut = "ECHEC" if bloquant else "AVERTISSEMENT"
    return {"controle": nom, "bloquant": bloquant, "statut": statut, "detail": detail}


def controler_cle_unique(silver):
    total = silver.count()
    cles = silver.select("code_pays", "code_indicateur", "annee").distinct().count()
    return resultat("cle_unique", total == cles, f"{total - cles} doublon(s) sur {total} lignes")


def controler_colonnes_obligatoires(silver):
    colonnes = ["code_pays", "code_indicateur", "annee", "source"]
    condition = " OR ".join(f"{colonne} IS NULL" for colonne in colonnes)
    nb_lignes_vides = silver.filter(condition).count()
    return resultat("colonnes_obligatoires", nb_lignes_vides == 0,
                    f"{nb_lignes_vides} ligne(s) avec une valeur vide dans {colonnes}")


def controler_grille_complete(silver):
    nb_pays = silver.select("code_pays").distinct().count()
    nb_indicateurs = silver.select("code_indicateur").distinct().count()
    premiere, derniere = silver.agg(F.min("annee"), F.max("annee")).first()
    nb_annees = derniere - premiere + 1
    attendu = nb_pays * nb_indicateurs * nb_annees
    reel = silver.count()
    return resultat("grille_complete", reel == attendu,
                    f"{reel} lignes pour {attendu} attendues "
                    f"({nb_pays} pays x {nb_indicateurs} indicateurs x {nb_annees} années)")


def controler_valeurs_plausibles(silver):
    annee_collecte = silver.agg(F.max(F.year("date_collecte"))).first()[0]
    population_invalide = silver.filter(
        (F.col("code_indicateur") == "SP.POP.TOTL") & (F.col("valeur") <= 0)).count()
    pourcentage_invalide = silver.filter(
        F.col("code_indicateur").isin(INDICATEURS_POURCENTAGE)
        & ((F.col("valeur") < 0) | (F.col("valeur") > 100))).count()
    annee_future = silver.filter(
        F.col("valeur").isNotNull() & (F.col("annee") > annee_collecte)).count()
    nb_problemes = population_invalide + pourcentage_invalide + annee_future
    return resultat("valeurs_plausibles", nb_problemes == 0,
                    f"population <= 0 : {population_invalide} ; pourcentage hors 0-100 : "
                    f"{pourcentage_invalide} ; valeur pour une année future : {annee_future}")


def controler_couverture(silver):
    couverture = (silver.groupBy("code_pays", "code_indicateur")
                  .agg(F.avg(F.col("valeur").isNotNull().cast("int")).alias("couverture")))
    nb_couples = couverture.count()
    nb_insuffisants = couverture.filter(F.col("couverture") < SEUIL_COUVERTURE).count()
    return resultat("couverture_suffisante", nb_insuffisants == 0,
                    f"{nb_insuffisants} couple(s) pays-indicateur sur {nb_couples} "
                    f"sous {SEUIL_COUVERTURE:.0%} d'années renseignées", bloquant=False)


def controler_fraicheur(silver):
    derniere_annee = silver.filter(F.col("valeur").isNotNull()).agg(F.max("annee")).first()[0]
    annee_collecte = silver.agg(F.max(F.year("date_collecte"))).first()[0]
    retard = annee_collecte - derniere_annee
    return resultat("fraicheur", retard <= RETARD_MAX_ANNEES,
                    f"dernière année renseignée : {derniere_annee} ; année de collecte : {annee_collecte}",
                    bloquant=False)


CONTROLES = [
    controler_cle_unique,
    controler_colonnes_obligatoires,
    controler_grille_complete,
    controler_valeurs_plausibles,
    controler_couverture,
    controler_fraicheur,
]


def ecrire_rapport(resultats):
    """Écrit un rapport CSV horodaté. Chaque exécution crée un nouveau fichier."""
    DOSSIER_RAPPORTS.mkdir(parents=True, exist_ok=True)
    maintenant = datetime.now(timezone.utc)
    chemin = DOSSIER_RAPPORTS / f"rapport_qualite_{maintenant.strftime('%Y%m%dT%H%M%SZ')}.csv"
    with open(chemin, "x", encoding="utf-8", newline="") as fichier:
        ecrivain = csv.DictWriter(
            fichier, fieldnames=["date_execution", "controle", "bloquant", "statut", "detail"])
        ecrivain.writeheader()
        for ligne in resultats:
            ecrivain.writerow({"date_execution": maintenant.isoformat(), **ligne})
    return chemin


def principal():
    spark = SparkSession.builder.master("local[*]").appName("afrimacro-qualite").getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    silver = spark.read.parquet(CHEMIN_SILVER).cache()

    resultats = [controle(silver) for controle in CONTROLES]
    spark.stop()

    for ligne in resultats:
        print(f"[{ligne['statut']:<13}] {ligne['controle']} : {ligne['detail']}")
    chemin = ecrire_rapport(resultats)
    print(f"\nRapport : {chemin}")

    if any(ligne["statut"] == "ECHEC" for ligne in resultats):
        print("Au moins un contrôle bloquant a échoué.")
        sys.exit(1)


if __name__ == "__main__":
    principal()
