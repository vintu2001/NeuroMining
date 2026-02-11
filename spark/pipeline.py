"""
NeuroMining — Spark MLlib Ensemble Classification Pipeline
Reads the feature_table from Hive (Parquet on HDFS), trains three classifiers
(Naïve Bayes, Linear SVM, Multilayer Perceptron), and persists model weights +
evaluation metrics to HDFS.

Submit via:
    spark-submit \
        --master spark://spark-master:7077 \
        --conf spark.sql.catalogImplementation=hive \
        --conf spark.hadoop.hive.metastore.uris=thrift://hive-metastore:9083 \
        spark/pipeline.py
"""

import json
import sys
from pathlib import Path

from pyspark.ml import Pipeline
from pyspark.ml.classification import (
    MultilayerPerceptronClassifier,
    LinearSVC,
    NaiveBayes,
)
from pyspark.ml.evaluation import MulticlassClassificationEvaluator
from pyspark.ml.feature import (
    MinMaxScaler,
    StandardScaler,
    StringIndexer,
    VectorAssembler,
)
from pyspark.ml.tuning import CrossValidator, ParamGridBuilder
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, when

# ── Constants ─────────────────────────────────────────────────────────────────

HIVE_TABLE      = "neuromining.feature_table"
HDFS_MODELS_DIR = "hdfs:///neuromining/models/"
HDFS_METRICS    = "hdfs:///neuromining/metrics/classification_metrics.json"

FEATURE_COLS = [
    "n_search", "n_click", "n_view_profile", "n_send_message",
    "n_comment", "n_save_post", "n_share", "n_follow",
    "total_actions", "total_sessions",
    "avg_session_duration_min", "avg_events_per_session",
    "avg_inter_event_sec", "total_professional_searches",
    "total_deep_clicks", "professional_ratio", "click_through_rate",
]

LABEL_COL   = "label"
TRAIN_RATIO = 0.8
SEED        = 42


# ── Spark session ─────────────────────────────────────────────────────────────

def build_spark() -> SparkSession:
    return (
        SparkSession.builder
        .appName("NeuroMining-ClassificationPipeline")
        .config("spark.sql.catalogImplementation", "hive")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
        .enableHiveSupport()
        .getOrCreate()
    )


# ── Data loading ──────────────────────────────────────────────────────────────

def load_features(spark: SparkSession):
    """
    Load feature_table from Hive. The Spark–Hive connector is configured via
    hive-site.xml mounted in the Spark container (thrift metastore URI).
    Partition pruning is leveraged automatically when dt is specified.
    """
    df = spark.table(HIVE_TABLE)

    # Cast label to double (required by all MLlib classifiers)
    df = df.withColumn(LABEL_COL, col(LABEL_COL).cast("double"))

    # Drop rows with any null feature
    df = df.dropna(subset=FEATURE_COLS + [LABEL_COL])

    print(f"[pipeline] Loaded {df.count():,} rows from {HIVE_TABLE}")
    df.groupBy(LABEL_COL).count().show()
    return df


# ── Pipeline builders ─────────────────────────────────────────────────────────

def _base_stages(scaler_type: str = "standard"):
    """
    Returns shared pre-processing stages:
      VectorAssembler → Scaler
    """
    assembler = VectorAssembler(
        inputCols=FEATURE_COLS,
        outputCol="raw_features",
        handleInvalid="skip",
    )
    if scaler_type == "minmax":
        scaler = MinMaxScaler(inputCol="raw_features", outputCol="features")
    else:
        scaler = StandardScaler(
            inputCol="raw_features", outputCol="features",
            withMean=True, withStd=True,
        )
    return [assembler, scaler]


def build_naive_bayes_pipeline() -> Pipeline:
    """
    Naïve Bayes requires non-negative features → use MinMaxScaler.
    """
    stages = _base_stages(scaler_type="minmax")
    nb = NaiveBayes(
        featuresCol="features",
        labelCol=LABEL_COL,
        smoothing=1.0,
        modelType="multinomial",
    )
    return Pipeline(stages=stages + [nb])


def build_svm_pipeline() -> Pipeline:
    """
    Linear SVM (LinearSVC) works well in high-dimensional feature spaces.
    """
    stages = _base_stages(scaler_type="standard")
    svm = LinearSVC(
        featuresCol="features",
        labelCol=LABEL_COL,
        maxIter=100,
        regParam=0.01,
    )
    return Pipeline(stages=stages + [svm])


def build_mlp_pipeline(input_dim: int) -> Pipeline:
    """
    Multi-layer Perceptron (MLP) with 2 hidden layers.
    Layer sizes: [input_dim, 64, 32, 2]
    """
    stages = _base_stages(scaler_type="standard")
    mlp = MultilayerPerceptronClassifier(
        featuresCol="features",
        labelCol=LABEL_COL,
        layers=[input_dim, 64, 32, 2],
        maxIter=100,
        blockSize=128,
        seed=SEED,
        stepSize=0.03,
    )
    return Pipeline(stages=stages + [mlp])


# ── Evaluation ────────────────────────────────────────────────────────────────

def evaluate(predictions, model_name: str) -> dict:
    evaluator_base = MulticlassClassificationEvaluator(
        labelCol=LABEL_COL,
        predictionCol="prediction",
    )
    metrics = {"model": model_name}
    for metric in ("accuracy", "weightedPrecision", "weightedRecall", "f1"):
        evaluator_base.setMetricName(metric)
        metrics[metric] = round(evaluator_base.evaluate(predictions), 4)
    print(f"[pipeline] {model_name:30s}  acc={metrics['accuracy']:.4f}  "
          f"f1={metrics['f1']:.4f}")
    return metrics


# ── Ensemble voting ───────────────────────────────────────────────────────────

def majority_vote(df, pred_cols: list[str]):
    """
    Hard majority vote across N binary classifiers.
    Outputs 'ensemble_prediction' column (0 or 1).
    """
    vote_sum = sum(col(c) for c in pred_cols)
    threshold = len(pred_cols) / 2.0
    return df.withColumn(
        "ensemble_prediction",
        when(vote_sum > threshold, 1.0).otherwise(0.0),
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    spark = build_spark()
    spark.sparkContext.setLogLevel("WARN")

    df = load_features(spark)
    train_df, test_df = df.randomSplit([TRAIN_RATIO, 1 - TRAIN_RATIO], seed=SEED)
    train_df.cache()

    input_dim = len(FEATURE_COLS)
    all_metrics = []

    # ── Naïve Bayes ──────────────────────────────────────────────────────────
    print("[pipeline] Training Naïve Bayes …")
    nb_pipeline = build_naive_bayes_pipeline()
    nb_model = nb_pipeline.fit(train_df)
    nb_preds = nb_model.transform(test_df).withColumnRenamed("prediction", "nb_pred")
    all_metrics.append(evaluate(nb_preds.withColumnRenamed("nb_pred", "prediction"), "NaiveBayes"))
    nb_model.write().overwrite().save(HDFS_MODELS_DIR + "naive_bayes")

    # ── Linear SVM ───────────────────────────────────────────────────────────
    print("[pipeline] Training Linear SVM …")
    svm_pipeline = build_svm_pipeline()
    svm_model = svm_pipeline.fit(train_df)
    svm_preds = svm_model.transform(test_df).withColumnRenamed("prediction", "svm_pred")
    all_metrics.append(evaluate(svm_preds.withColumnRenamed("svm_pred", "prediction"), "LinearSVM"))
    svm_model.write().overwrite().save(HDFS_MODELS_DIR + "linear_svm")

    # ── MLP Neural Network ───────────────────────────────────────────────────
    print("[pipeline] Training MLP Neural Network …")
    mlp_pipeline = build_mlp_pipeline(input_dim)
    mlp_model = mlp_pipeline.fit(train_df)
    mlp_preds = mlp_model.transform(test_df).withColumnRenamed("prediction", "mlp_pred")
    all_metrics.append(evaluate(mlp_preds.withColumnRenamed("mlp_pred", "prediction"), "MLP-NN"))
    mlp_model.write().overwrite().save(HDFS_MODELS_DIR + "mlp_nn")

    # ── Ensemble Voting ───────────────────────────────────────────────────────
    print("[pipeline] Evaluating ensemble majority vote …")
    combined = (
        test_df
        .join(nb_preds.select("user_id", "nb_pred"),   on="user_id")
        .join(svm_preds.select("user_id", "svm_pred"),  on="user_id")
        .join(mlp_preds.select("user_id", "mlp_pred"),  on="user_id")
    )
    combined = majority_vote(combined, ["nb_pred", "svm_pred", "mlp_pred"])
    ensemble_eval = combined.withColumnRenamed("ensemble_prediction", "prediction")
    all_metrics.append(evaluate(ensemble_eval, "Ensemble-Vote"))

    # ── Persist metrics to HDFS ───────────────────────────────────────────────
    metrics_json = json.dumps(all_metrics, indent=2)
    spark.sparkContext.parallelize([metrics_json]).saveAsTextFile(HDFS_METRICS)
    print(f"[pipeline] Metrics saved → {HDFS_METRICS}")
    print(json.dumps(all_metrics, indent=2))

    spark.stop()


if __name__ == "__main__":
    main()
