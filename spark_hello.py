from pyspark.sql import SparkSession

spark = SparkSession.builder.master("local[*]").appName("afrimacro").getOrCreate()

df = spark.createDataFrame(
    [("CIV", 2023, 31165654.0), ("GHA", 2023, None)],
    schema="country_code string, year int, value double",
)
df.show()
df.printSchema()

spark.stop()
