from pyspark.sql.types import *
from pyspark.sql.functions import *
import os

class DustData():

    def __init__(self, df):
        self.df = df
        self.dust_schema = StructType(
            [
                StructField("value", IntegerType(), True),
                StructField("voltage", FloatType(), True),
                StructField("density", DoubleType(), True),
                StructField("timestamp", DoubleType(), True),
            ]
        )

    def write_jdbc(self, df, epoch_id):
        # Transform and write batchDF
        df.persist()
        # df = df.withColumn(
        #     "id", monotonically_increasing_id()
        # )  # adding a db identifier
        df.write.format("jdbc").mode("append").options(
            url=os.getenv("CX_DB_URL"),
            dbtable="dust",
            driver=os.getenv("CX_DB_DRIVER"),
            user=os.getenv("CX_DB_USER"),
            password=os.getenv("CX_DB_PWD"),
        ).save()
        df.unpersist()

    def start_working(self):
        sensor = self.df.filter("topic == 'dust'")
        sensor = sensor.select(from_json(sensor.value, self.dust_schema).alias("data")).select(
            "data.*"
        )

        # converting timestamp column to Timestamp type, somehow the conversion doesn't work from the start.
        sensor = sensor.withColumn(
            "timestamp", sensor["timestamp"].cast(TimestampType()))

        sensor = (
            sensor.withWatermark("timestamp", "5 minutes")
            .groupBy(window("timestamp", "1 minutes"))
            .avg()
        )

        sensor = (
            sensor.withColumn("startdate", sensor["window"]["start"])
            .withColumn("window", sensor["window"]["end"])
            .withColumnRenamed("window", "enddate")
            .withColumnRenamed("avg(value)", "value")
            .withColumnRenamed("avg(voltage)", "voltage")
            .withColumnRenamed("avg(density)", "density")
        )

        ds = sensor.writeStream.foreachBatch(self.write_jdbc).start()
        return ds

# Backup code
# ###########
# sensor.printSchema()
# def process_row(row):
#     print(f'{row["startdate"]} -> {row["enddate"]} = {row["value"]}')

# sensor.writeStream.foreach(process_row).start().awaitTermination()
# sensor.writeStream.format("console").outputMode("append").start().awaitTermination()
