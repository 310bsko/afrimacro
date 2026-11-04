from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F

CHEMIN_BRONZE = "donnees/bronze/banque_mondiale/*/*.json"
CHEMIN_SILVER = "donnees/silver/indicateurs_banque_mondiale"

# Ces noms viennent de l'API (données brutes) : on ne les traduit pas.
SCHEMA_META = "struct<lastupdated: string>"
SCHEMA_LIGNES = """array<struct<
    indicator: struct<id: string, value: string>,
    country: struct<id: string, value: string>,
    countryiso3code: string,
    date: string,
    value: double
>>"""

spark = SparkSession.builder.master("local[*]").appName("afrimacro-silver").getOrCreate()
spark.sparkContext.setLogLevel("ERROR")

# 1. Lire tous les fichiers bronze
brut = spark.read.json(CHEMIN_BRONZE)

# 2. Garder la collecte la plus récente de chaque indicateur
plus_recent_d_abord = Window.partitionBy("code_indicateur").orderBy(F.col("date_collecte").desc())
derniere_collecte = brut.withColumn("rang", F.dense_rank().over(plus_recent_d_abord)).filter("rang = 1")

# 3. Une ligne par page, puis une ligne par observation
pages = derniere_collecte.select("date_collecte", "libelle_indicateur", F.explode("pages").alias("page"))
lignes = pages.select(
    "date_collecte",
    "libelle_indicateur",
    F.from_json(F.col("page")[0], SCHEMA_META).alias("meta"),
    F.explode(F.from_json(F.col("page")[1], SCHEMA_LIGNES)).alias("observation"),
)

# 4. Colonnes propres, typées et nommées en français (traduction des champs de l'API)
silver = lignes.select(
    F.col("observation.countryiso3code").alias("code_pays"),
    F.col("observation.country.value").alias("nom_pays"),
    F.col("observation.indicator.id").alias("code_indicateur"),
    F.col("libelle_indicateur"),   # libellé français de la configuration, conservé dans le bronze
    F.col("observation.date").cast("int").alias("annee"),
    F.col("observation.value").alias("valeur"),
    F.lit("banque_mondiale").alias("source"),
    F.col("meta.lastupdated").alias("source_mise_a_jour"),
    F.to_timestamp("date_collecte").alias("date_collecte"),
)

# 5. Écrire le silver en Parquet (remplace la version précédente)
silver.write.mode("overwrite").parquet(CHEMIN_SILVER)

# 6. Relire ce qui a été écrit et vérifier
controle = spark.read.parquet(CHEMIN_SILVER)
controle.printSchema()
total = controle.count()
sans_valeur = controle.filter(F.col("valeur").isNull()).count()
cles_uniques = controle.select("code_pays", "code_indicateur", "annee").distinct().count()
print(f"lignes : {total}")
print(f"sans valeur : {sans_valeur}")
print(f"clés uniques : {cles_uniques} | doublons : {total - cles_uniques}")
controle.orderBy("code_indicateur", "code_pays", F.desc("annee")).show(3, truncate=False)

spark.stop()
