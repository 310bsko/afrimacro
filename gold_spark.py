import yaml
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

CHEMIN_SILVER = "donnees/silver/indicateurs_banque_mondiale"
CHEMIN_GOLD_MOYENNES = "donnees/gold/moyennes_recentes"
CHEMIN_GOLD_PROFIL = "donnees/gold/profil_pays"

with open("config/pipeline.yml", encoding="utf-8") as fichier:
    parametres = yaml.safe_load(fichier)["gold"]
FENETRE_DEBUT = parametres["fenetre_debut"]
FENETRE_FIN = parametres["fenetre_fin"]
SEUIL_COUVERTURE = parametres["seuil_couverture"]
NB_ANNEES_FENETRE = FENETRE_FIN - FENETRE_DEBUT + 1

spark = SparkSession.builder.master("local[*]").appName("afrimacro-gold").getOrCreate()
spark.sparkContext.setLogLevel("ERROR")

silver = spark.read.parquet(CHEMIN_SILVER)

# 1. Ne garder que la fenêtre d'analyse
fenetre = silver.filter(F.col("annee").between(FENETRE_DEBUT, FENETRE_FIN))

# 2. Pour chaque pays et chaque indicateur : moyenne, nombre d'années renseignées, fiabilité
moyennes = (
    fenetre.groupBy("code_pays", "nom_pays", "code_indicateur", "libelle_indicateur")
    .agg(
        F.avg("valeur").alias("moyenne"),                     # ignore les valeurs vides
        F.count("valeur").alias("nb_annees_renseignees"),     # compte seulement les valeurs présentes
    )
    .withColumn("couverture", F.col("nb_annees_renseignees") / NB_ANNEES_FENETRE)
    .withColumn("fiable", F.col("couverture") >= SEUIL_COUVERTURE)
    .withColumn("annee_debut", F.lit(FENETRE_DEBUT))
    .withColumn("annee_fin", F.lit(FENETRE_FIN))
)
moyennes.write.mode("overwrite").parquet(CHEMIN_GOLD_MOYENNES)

# 3. Un profil par pays : une ligne par pays, une colonne par indicateur (moyennes fiables seulement)
profil = (
    moyennes
    .withColumn("colonne", F.lower(F.regexp_replace("code_indicateur", r"\.", "_")))
    .withColumn("moyenne_fiable", F.when(F.col("fiable"), F.col("moyenne")))
    .groupBy("code_pays", "nom_pays")
    .pivot("colonne")
    .agg(F.first("moyenne_fiable"))
)
profil.write.mode("overwrite").parquet(CHEMIN_GOLD_PROFIL)

# 4. Relire et vérifier
moyennes_lues = spark.read.parquet(CHEMIN_GOLD_MOYENNES)
profil_lu = spark.read.parquet(CHEMIN_GOLD_PROFIL)
print(f"fenêtre : {FENETRE_DEBUT} à {FENETRE_FIN} ({NB_ANNEES_FENETRE} années)")
print(f"moyennes : {moyennes_lues.count()} lignes, dont {moyennes_lues.filter(~F.col('fiable')).count()} non fiables")
print(f"profil : {profil_lu.count()} pays, {len(profil_lu.columns)} colonnes")
profil_lu.select("code_pays", "sp_pop_totl", "ny_gdp_pcap_cd", "fp_cpi_totl_zg").orderBy("code_pays").show(15)
moyennes_lues.filter(~F.col("fiable")).select(
    "code_pays", "code_indicateur", "nb_annees_renseignees"
).orderBy("code_indicateur", "code_pays").show(30, truncate=False)
spark.stop()
