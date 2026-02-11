"""
NeuroMining — Bisecting K-Means User Segmentation
Reads the feature_table from Hive, runs Bisecting K-Means (k=5) to identify
distinct behavioral archetypes, applies PCA for 2-D visualization coordinates,
and persists cluster assignments and model to HDFS.

Submit via:
    spark-submit \
        --master spark://spark-master:7077 \
        --conf spark.sql.catalogImplementation=hive \
        --conf spark.hadoop.hive.metastore.uris=thrift://hive-metastore:9083 \
        spark/clustering.py
"""

import json

from pyspark.ml.clustering import BisectingKMeans, BisectingKMeansModel
from pyspark.ml.evaluation import ClusteringEvaluator
from pyspark.ml.feature import PCA, StandardScaler, VectorAssembler
from pyspark.ml import Pipeline
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, udf
from pyspark.sql.types import ArrayType, DoubleType

# ── Constants ─────────────────────────────────────────────────────────────────

HIVE_TABLE           = "neuromining.feature_table"
HDFS_CLUSTER_MODEL   = "hdfs:///neuromining/models/bisecting_kmeans"
HDFS_ASSIGNMENTS     = "hdfs:///neuromining/outputs/cluster_assignments/"
HDFS_CLUSTER_META    = "hdfs:///neuromining/outputs/cluster_metadata.json"

N_CLUSTERS   = 5
PCA_DIM      = 2
SEED         = 42
MAX_ITER     = 30
MIN_DIVISIBLE = 20   # Minimum cluster size before stopping bisection

FEATURE_COLS = [
    "n_search", "n_click", "n_view_profile", "n_send_message",
    "n_comment", "n_save_post", "n_share", "n_follow",
    "total_actions", "total_sessions",
    "avg_session_duration_min", "avg_events_per_session",
    "avg_inter_event_sec", "total_professional_searches",
    "total_deep_clicks", "professional_ratio", "click_through_rate",
]

# Human-readable archetype names assigned post-hoc based on centroid analysis
ARCHETYPE_NAMES = {
    0: "Power Networkers",
    1: "Passive Browsers",
    2: "Content Creators",
    3: "Job Seekers",
    4: "Casual Observers",
}


# ── Spark session ─────────────────────────────────────────────────────────────

def build_spark() -> SparkSession:
    return (
        SparkSession.builder
        .appName("NeuroMining-Clustering")
        .config("spark.sql.catalogImplementation", "hive")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
        .enableHiveSupport()
        .getOrCreate()
    )


# ── Pipeline ──────────────────────────────────────────────────────────────────

def build_clustering_pipeline() -> Pipeline:
    assembler = VectorAssembler(
        inputCols=FEATURE_COLS,
        outputCol="raw_features",
        handleInvalid="skip",
    )
    scaler = StandardScaler(
        inputCol="raw_features",
        outputCol="scaled_features",
        withMean=True,
        withStd=True,
    )
    bkm = BisectingKMeans(
        featuresCol="scaled_features",
        predictionCol="cluster",
        k=N_CLUSTERS,
        maxIter=MAX_ITER,
        seed=SEED,
        minDivisibleClusterSize=MIN_DIVISIBLE,
    )
    return Pipeline(stages=[assembler, scaler, bkm])


def build_pca_pipeline() -> Pipeline:
    """Separate PCA pipeline applied after clustering for viz coordinates."""
    assembler = VectorAssembler(
        inputCols=FEATURE_COLS,
        outputCol="raw_features",
        handleInvalid="skip",
    )
    scaler = StandardScaler(
        inputCol="raw_features",
        outputCol="scaled_features",
        withMean=True,
        withStd=True,
    )
    pca = PCA(
        k=PCA_DIM,
        inputCol="scaled_features",
        outputCol="pca_coords",
    )
    return Pipeline(stages=[assembler, scaler, pca])


# ── Helpers ───────────────────────────────────────────────────────────────────

vector_to_array = udf(lambda v: v.toArray().tolist(), ArrayType(DoubleType()))


def compute_cluster_metadata(model, df) -> list[dict]:
    """
    Extract centroid info and compute within-cluster stats.
    """
    bkm_stage = model.stages[-1]
    centers   = bkm_stage.clusterCenters()

    evaluator = ClusteringEvaluator(
        featuresCol="scaled_features",
        predictionCol="cluster",
        metricName="silhouette",
    )
    silhouette = evaluator.evaluate(df)
    print(f"[clustering] Silhouette score: {silhouette:.4f}")

    cluster_counts = (
        df.groupBy("cluster")
        .count()
        .orderBy("cluster")
        .collect()
    )
    count_map = {row["cluster"]: row["count"] for row in cluster_counts}

    metadata = []
    for i, center in enumerate(centers):
        metadata.append({
            "cluster_id":    i,
            "archetype":     ARCHETYPE_NAMES.get(i, f"Segment-{i}"),
            "user_count":    count_map.get(i, 0),
            "centroid":      [round(float(v), 4) for v in center],
            "silhouette":    round(silhouette, 4),
        })

    return metadata


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    spark = build_spark()
    spark.sparkContext.setLogLevel("WARN")

    df = spark.table(HIVE_TABLE).dropna(subset=FEATURE_COLS)
    print(f"[clustering] Loaded {df.count():,} users for segmentation")

    # ── Train Bisecting K-Means ──────────────────────────────────────────────
    clustering_pipeline = build_clustering_pipeline()
    model = clustering_pipeline.fit(df)
    clustered = model.transform(df)

    # ── PCA for 2-D coordinates ───────────────────────────────────────────────
    pca_pipeline = build_pca_pipeline()
    pca_model    = pca_pipeline.fit(df)
    pca_result   = pca_model.transform(df)

    # Attach PCA coordinates to clustered DataFrame
    pca_coords = pca_result.select("user_id", "pca_coords")
    output = clustered.join(pca_coords, on="user_id", how="left")
    output = output.withColumn("pca_array", vector_to_array(col("pca_coords")))

    # Select and rename for clean output schema
    final = output.select(
        col("user_id"),
        col("cluster"),
        col("pca_array")[0].alias("pca_x"),
        col("pca_array")[1].alias("pca_y"),
        col("label"),
        col("professional_ratio"),
        col("total_actions"),
        col("total_sessions"),
    )

    # ── Persist model and assignments ─────────────────────────────────────────
    model.write().overwrite().save(HDFS_CLUSTER_MODEL)
    print(f"[clustering] Model saved → {HDFS_CLUSTER_MODEL}")

    final.write.mode("overwrite").parquet(HDFS_ASSIGNMENTS)
    print(f"[clustering] Assignments saved → {HDFS_ASSIGNMENTS}")

    # ── Save metadata JSON ─────────────────────────────────────────────────────
    cluster_meta = compute_cluster_metadata(model, clustered)
    meta_json = json.dumps({"clusters": cluster_meta}, indent=2)
    spark.sparkContext.parallelize([meta_json]).saveAsTextFile(HDFS_CLUSTER_META)
    print(f"[clustering] Metadata saved → {HDFS_CLUSTER_META}")
    print(meta_json)

    spark.stop()


if __name__ == "__main__":
    main()
