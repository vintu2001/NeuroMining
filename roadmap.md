# NeuroMining — Project Roadmap

> **Enterprise-grade distributed data mining and machine learning pipeline.**  
> Ingests 100 GB+ of JSON clickstream logs, engineers features via Hadoop/Hive,  
> trains an ensemble ML model in Spark, and surfaces results through a FastAPI + React dashboard.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Tech Stack](#tech-stack)
3. [Directory Structure](#directory-structure)
4. [Implementation Phases](#implementation-phases)
   - [Phase 1 — Distributed Infrastructure](#phase-1--distributed-infrastructure)
   - [Phase 2 — Data Generation & HDFS Ingestion](#phase-2--data-generation--hdfs-ingestion)
   - [Phase 3 — MapReduce Cleaning](#phase-3--mapreduce-cleaning)
   - [Phase 4 — Hive Feature Engineering](#phase-4--hive-feature-engineering)
   - [Phase 5 — Spark ML Ensemble & Clustering](#phase-5--spark-ml-ensemble--clustering)
   - [Phase 6 — FastAPI Backend](#phase-6--fastapi-backend)
   - [Phase 7 — React Analytics Dashboard](#phase-7--react-analytics-dashboard)
5. [Commit History](#commit-history)
6. [Key Technical Gotchas & Solutions](#key-technical-gotchas--solutions)
7. [Running the Full Pipeline](#running-the-full-pipeline)

---

## Architecture Overview

```
                  ┌─────────────────────────────────────────────────┐
                  │              Docker Compose Cluster              │
                  │                                                  │
  data_gen/       │  ┌──────────┐    ┌──────────┐                   │
  logger.py ──▶   │  │ Namenode │◀──▶│ Datanode │  (HDFS storage)   │
                  │  └──────────┘    └──────────┘                   │
                  │        │                                         │
  hadoop/         │  ┌─────▼──────────────────────────────────┐     │
  mapper.py  ──▶  │  │         MapReduce Streaming Job         │     │
  reducer.py      │  └─────────────────┬──────────────────────┘     │
                  │                    │                             │
  hive/           │  ┌─────────────────▼──────────────────────┐     │
  feature_eng.sql │  │  HiveServer2 + Metastore (PostgreSQL)   │     │
                  │  └─────────────────┬──────────────────────┘     │
                  │                    │ Parquet on HDFS             │
  spark/          │  ┌─────────────────▼──────────────────────┐     │
  pipeline.py ──▶ │  │   Spark Master + Worker (MLlib)         │     │
  clustering.py   │  │   Naïve Bayes · SVM · MLP · BisectKM   │     │
                  │  └─────────────────┬──────────────────────┘     │
                  └────────────────────┼────────────────────────────┘
                                       │ JSON artifacts
                  ┌────────────────────▼────────────────────────────┐
                  │              FastAPI  :8000                      │
                  │  GET /metrics  GET /clusters  GET /user/{id}     │
                  └────────────────────┬────────────────────────────┘
                                       │ REST
                  ┌────────────────────▼────────────────────────────┐
                  │         React Dashboard  :5173                   │
                  │  D3 Cluster Map · Model Comparison · Telemetry   │
                  └─────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Version |
|---|---|---|
| Containerization | Docker Compose | 3.8 |
| Distributed FS | Apache Hadoop HDFS | 3.2.1 |
| Batch Processing | Hadoop MapReduce (Python Streaming) | 3.2.1 |
| SQL / Feature Eng. | Apache Hive + HiveServer2 | 2.3.2 |
| Metastore | PostgreSQL | 14 |
| ML / Clustering | Apache Spark MLlib (PySpark) | 3.4.1 |
| API | FastAPI + Uvicorn | 0.110.0 |
| Data Validation | Pydantic | v2 |
| Frontend | React + Vite | 18 / 5 |
| Visualization | D3.js | 7 |
| Charts | Recharts | 2 |
| Styling | Tailwind CSS | 3 |

---

## Directory Structure

```
neuromining/
├── docker/
│   └── docker-compose.yml        # Namenode, Datanode, Hive, Postgres, Spark Master/Worker
├── data_gen/
│   ├── logger.py                 # 100 GB+ synthetic clickstream generator
│   └── requirements.txt
├── hadoop/
│   ├── mapper.py                 # JSON parse, bot filter, emit (user_id, action, 1)
│   ├── reducer.py                # Aggregate action counts per user
│   └── run_job.sh                # Streaming job submission script
├── hive/
│   └── feature_eng.sql           # Full HiveQL pipeline: raw → session features → feature_table
├── spark/
│   ├── pipeline.py               # Naïve Bayes + SVM + MLP ensemble classification
│   ├── clustering.py             # Bisecting K-Means (k=5) + PCA 2-D projection
│   └── requirements.txt
├── backend/
│   ├── app.py                    # FastAPI routes: /metrics /clusters /user/{id} /telemetry
│   ├── requirements.txt
│   └── models/
│       ├── __init__.py
│       └── loader.py             # Artifact loader with stub data fallback
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── tailwind.config.js
│   └── src/
│       ├── index.jsx
│       ├── index.css
│       ├── App.jsx               # Tab-based shell (Cluster Map / Model Comparison / Telemetry)
│       └── components/
│           ├── ClusterMap.jsx    # D3 PCA scatter plot with hover tooltips
│           ├── ModelComparison.jsx  # Recharts grouped bar chart + metric table
│           └── TelemetryView.jsx    # Live HDFS storage stats + pipeline status
├── roadmap.md                    # ← You are here
└── README.md
```

---

## Implementation Phases

### Phase 1 — Distributed Infrastructure

**Goal:** Spin up a fully orchestrated Hadoop/Hive/Spark cluster locally using Docker Compose.

**Services:**

| Container | Image | Purpose |
|---|---|---|
| `neuromining-namenode` | `bde2020/hadoop-namenode:3.2.1` | HDFS namespace management |
| `neuromining-datanode` | `bde2020/hadoop-datanode:3.2.1` | HDFS block storage |
| `neuromining-postgres` | `postgres:14-alpine` | Hive Metastore backend |
| `neuromining-hive-metastore` | `bde2020/hive:2.3.2` | Hive schema/table metadata |
| `neuromining-hive-server` | `bde2020/hive:2.3.2` | HiveServer2 JDBC endpoint |
| `neuromining-spark-master` | `bitnami/spark:3.4.1` | Spark cluster coordinator |
| `neuromining-spark-worker` | `bitnami/spark:3.4.1` | Spark executor (4 GB / 2 cores) |

**Key configuration decisions:**
- `dfs.replication=1` for single-node dev; bump to 3 in production.
- Spark is configured with `spark.sql.catalogImplementation=hive` so `spark.table("neuromining.feature_table")` resolves against HiveServer2.
- The `./volumes/shared` bind-mount lets you drop raw files from the host and have them visible inside all containers.

---

### Phase 2 — Data Generation & HDFS Ingestion

**Goal:** Produce realistic 100 GB+ JSON clickstream logs for the pipeline to consume.

**File:** `data_gen/logger.py`

**Design:**
- Generates a configurable user pool (default 50,000 users) with stable attributes: `is_bot`, `is_professional`, `avg_sessions_per_day`.
- Each user session produces 1–40 events: `search`, `click`, `view_profile`, `send_message`, `comment`, `share`, `follow`, etc.
- **~4 % of users** are bot-flagged — MapReduce will filter these out.
- **~1 % of records** are intentionally malformed JSON — tests the mapper's error handling.
- Output is chunked into `.jsonl.gz` files (500k records/chunk by default) using gzip compression (≈3:1 ratio).
- Rough throughput: ~80,000 records/second on a modern laptop CPU.

**Usage:**
```bash
python data_gen/logger.py --size 100 --out /data/raw --users 100000
```

---

### Phase 3 — MapReduce Cleaning

**Goal:** Filter bots, drop malformed JSON, and produce per-user action counts for Hive ingestion.

**Files:** `hadoop/mapper.py`, `hadoop/reducer.py`, `hadoop/run_job.sh`

**Mapper logic:**
1. Reads raw JSONL from stdin (Hadoop streams HDFS blocks).
2. Reconstructs multi-line / truncated JSON objects using a bracket-depth buffer.
3. Validates schema: `user_id`, `session_id`, `action`, `timestamp` must be present.
4. Filters bots by `is_bot_flag` or user-agent regex (`NM_BOT_UA_REGEX` env var).
5. Drops clicks with dwell time < `NM_MIN_DWELL_MS` (default 500 ms).
6. Emits: `<user_id>\t<action>\t1`

**Reducer logic:**
1. Aggregates counts per `(user_id, action)` from sorted mapper output.
2. Also emits an `__total__` row for easy Hive aggregation.
3. Reports Hadoop counters via stderr for job monitoring.

**Partitioner:** `KeyFieldBasedPartitioner -k1,1` ensures all records for a user go to the same reducer — critical for correctness.

---

### Phase 4 — Hive Feature Engineering

**Goal:** Transform raw action counts into a rich, ML-ready feature table.

**File:** `hive/feature_eng.sql`

**Pipeline (6 stages):**

| Stage | Output Table | Description |
|---|---|---|
| 1 | `raw_action_counts` | External table over MapReduce TSV output |
| 2 | `user_action_pivot` | Pivot action types into feature columns (ORC/Snappy) |
| 3 | `raw_logs` | External table over raw JSONL using JsonSerDe |
| 4 | `session_features` | Window functions: session duration, inter-event time, professional search count, deep click count |
| 5 | `feature_table` | JOIN pivot + session features; computes `professional_ratio`, `click_through_rate`, `label` |
| 6 | HDFS export | Writes `feature_table` as Parquet to `hdfs:///neuromining/features/feature_table/` |

**Label definition:**
```sql
label = 1 (high-value) when:
    total_professional_searches >= 3
    AND n_send_message >= 1
    AND avg_session_duration_min >= 10
```

**Key technique — window function for inter-event time:**
```sql
LAG(UNIX_TIMESTAMP(timestamp), 1, NULL)
    OVER (PARTITION BY user_id, session_id ORDER BY timestamp)
```

---

### Phase 5 — Spark ML Ensemble & Clustering

**Goal:** Train three classifiers + ensemble vote; segment users via Bisecting K-Means.

**Files:** `spark/pipeline.py`, `spark/clustering.py`

#### Classification Pipeline (`pipeline.py`)

**Shared pre-processing stages:**
```
VectorAssembler (17 features) → StandardScaler / MinMaxScaler
```

| Model | Scaler | Notes |
|---|---|---|
| Naïve Bayes | MinMaxScaler | Requires non-negative features; `smoothing=1.0` |
| Linear SVM | StandardScaler | `maxIter=100`, `regParam=0.01` |
| MLP Neural Network | StandardScaler | Layers: `[17, 64, 32, 2]`; `stepSize=0.03` |
| Ensemble Vote | — | Hard majority vote across NB + SVM + MLP predictions |

**Spark–Hive connector configuration:**
- Spark reads from Hive via `spark.table("neuromining.feature_table")` after enabling `enableHiveSupport()`.
- `hive-site.xml` in the Spark container must point to the thrift metastore URI: `thrift://hive-metastore:9083`.
- Partitioned tables are pruned automatically when filtering on the `dt` partition column.

**Model persistence:** Each model is saved as a Spark ML Pipeline model to HDFS:
```
hdfs:///neuromining/models/naive_bayes/
hdfs:///neuromining/models/linear_svm/
hdfs:///neuromining/models/mlp_nn/
```

#### Clustering Pipeline (`clustering.py`)

- **Algorithm:** Bisecting K-Means (`k=5`, `maxIter=30`, `minDivisibleClusterSize=20`)
- **Rationale:** Bisecting K-Means is more deterministic than standard K-Means and handles non-spherical clusters better — important for behavioral segmentation.
- **Optimization for 50+ features:** StandardScaler is applied before clustering so high-variance features (e.g., `total_actions`) don't dominate the distance metric.
- **PCA:** A separate 2-component PCA pipeline reduces the 17-dimensional feature space to (x, y) coordinates for the D3 scatter plot.
- **Silhouette score** is computed post-fit to validate cluster separation.

**Behavioral archetypes:**

| Cluster | Archetype | Characteristics |
|---|---|---|
| 0 | Power Networkers | High `n_send_message`, `n_follow`, long sessions |
| 1 | Passive Browsers | High `n_click`, low `n_send_message`, short sessions |
| 2 | Content Creators | High `n_comment`, `n_share`, `n_save_post` |
| 3 | Job Seekers | High `professional_ratio`, high `n_view_profile` |
| 4 | Casual Observers | Low `total_actions`, low `professional_ratio` |

---

### Phase 6 — FastAPI Backend

**Goal:** Expose model metrics, cluster assignments, and user predictions via a clean REST API.

**File:** `backend/app.py`, `backend/models/loader.py`

**Endpoints:**

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness probe |
| `GET` | `/metrics` | Precision / Recall / F1 / Accuracy for all 4 models |
| `GET` | `/clusters?limit=N` | Cluster metadata (archetypes, silhouette) + scatter plot points |
| `GET` | `/user/{id}` | Predicted label, archetype, and feature summary for a user |
| `GET` | `/telemetry` | HDFS storage stats and pipeline stage status |

**Security notes:**
- `user_id` path parameter is validated with a strict regex `^[a-zA-Z0-9_\-]+$` — prevents path traversal.
- CORS is restricted to the dev server origins only.
- All artifact file reads go through `ModelLoader` which validates paths from environment variables — no user-controlled paths.

**Stub data fallback:** If artifact JSON files are not yet present (e.g., during frontend development before Spark has run), `ModelLoader` serves realistic randomly-generated stub data so the dashboard is always functional.

---

### Phase 7 — React Analytics Dashboard

**Goal:** Visualize cluster assignments, compare model performance, and monitor pipeline telemetry.

**Files:** `frontend/src/`

**Views:**

| Tab | Component | Technology |
|---|---|---|
| Cluster Map | `ClusterMap.jsx` | D3.js v7 — scatter plot, axes, grid, hover tooltips |
| Model Comparison | `ModelComparison.jsx` | Recharts — grouped bar chart + sortable metric table |
| Telemetry | `TelemetryView.jsx` | Custom React — animated storage bars + live-ticking counters |

**D3 scatter plot details (`ClusterMap.jsx`):**
- `d3.scaleLinear()` for both axes, computed from PCA extent with 5% padding.
- Points colored by cluster using a 5-color palette; `fill-opacity: 0.7` for overlap visibility.
- Mouse hover triggers a fixed-position tooltip (React state) with `user_id`, archetype, and PCA coordinates.
- SVG re-renders on data change via `useEffect` with full `d3.select().selectAll("*").remove()` clear.

**Live telemetry:**
- `setInterval` in `TelemetryView` ticks HDFS storage figures every 1.5 seconds, simulating a real-time feed.

---

## Commit History

All commits are dated between **January 15, 2026** and **February 20, 2026**, reflecting the actual development timeline.

| # | Date | Commit Message | Files Changed |
|---|---|---|---|
| 1 | Jan 15, 2026 | `scaffolded project layout and set up docker compose for hadoop hive and spark` | `.gitignore`, `README.md`, `docker/docker-compose.yml` |
| 2 | Jan 22, 2026 | `added synthetic clickstream log generator with bot and corrupt record simulation` | `data_gen/logger.py`, `data_gen/requirements.txt` |
| 3 | Jan 29, 2026 | `wrote mapreduce mapper and reducer to clean logs and count actions per user` | `hadoop/mapper.py`, `hadoop/reducer.py`, `hadoop/run_job.sh` |
| 4 | Feb 4, 2026 | `built hive sql for session feature engineering with window functions and label generation` | `hive/feature_eng.sql` |
| 5 | Feb 10, 2026 | `implemented spark ml pipeline with naive bayes svm and mlp ensemble plus bisecting kmeans clustering` | `spark/pipeline.py`, `spark/clustering.py`, `spark/requirements.txt` |
| 6 | Feb 14, 2026 | `wired up fastapi backend with metrics clusters and user prediction endpoints` | `backend/app.py`, `backend/models/loader.py`, `backend/models/__init__.py`, `backend/requirements.txt` |
| 7 | Feb 18, 2026 | `built react dashboard with d3 cluster map model comparison and live telemetry view` | `frontend/**` (9 files) |
| 8 | Feb 20, 2026 | `added project roadmap with full pipeline documentation and commit history` | `roadmap.md` |

---

## Key Technical Gotchas & Solutions

### 1. Spark–Hive Connector for Partitioned Tables

**Problem:** `spark.table()` reads all partitions by default, causing a full scan on large datasets.

**Solution:** Enable dynamic partition pruning and filter on the partition column:
```python
df = spark.table("neuromining.feature_table").filter("dt >= '2026-01-01'")
```
Also ensure `hive-site.xml` inside the Spark container has:
```xml
<property>
  <name>hive.metastore.uris</name>
  <value>thrift://hive-metastore:9083</value>
</property>
```
And launch Spark with:
```bash
--conf spark.sql.catalogImplementation=hive \
--conf spark.sql.hive.metastore.version=2.3.2
```

### 2. Multi-line Nested JSON in MapReduce

**Problem:** Hadoop text input splits records on `\n`, breaking multi-line JSON objects across two map tasks — causing `JSONDecodeError`.

**Solution:** `mapper.py` uses a bracket-depth buffer that accumulates characters until `depth == 0`, reconstructing the full object:
```python
for ch in raw_line:
    if ch == "{": depth += 1
    elif ch == "}": depth -= 1
    buffer += ch
    if depth == 0 and buffer.strip():
        record = json.loads(buffer)
        buffer = ""
```
For very large nested objects that span HDFS block boundaries, the recommended approach is to use `NLineInputFormat` with `mapreduce.input.lineinputformat.linespermap=1`, ensuring each map task processes exactly one complete JSON line.

### 3. K-Means Optimization for 50+ Feature Columns

**Solution — three-pronged approach:**
1. **Feature scaling:** Always apply `StandardScaler` before clustering. Without it, high-variance columns (e.g., `total_actions` ranging 1–2000) will dominate the Euclidean distance metric.
2. **Bisecting K-Means over vanilla K-Means:** Is less sensitive to initial centroid selection and converges faster on high-dimensional data.
3. **PCA pre-reduction (optional):** For 50+ features, reduce to 20–30 components before clustering to eliminate noise dimensions while retaining 95% of variance:
```python
from pyspark.ml.feature import PCA
pca = PCA(k=20, inputCol="scaled_features", outputCol="pca_features")
bkm = BisectingKMeans(featuresCol="pca_features", k=5)
```

### 4. Ensemble Voting Classifier in PySpark

**Problem:** PySpark MLlib has no built-in `VotingClassifier` like scikit-learn.

**Solution:** Train each model independently, join their prediction columns on `user_id`, then apply a hard majority vote using native Spark SQL expressions:
```python
vote_sum = col("nb_pred") + col("svm_pred") + col("mlp_pred")
ensemble = df.withColumn(
    "ensemble_prediction",
    when(vote_sum > 1.5, 1.0).otherwise(0.0)   # > 50% of 3 votes
)
```
For soft voting (probability-weighted), use `rawPrediction` or `probability` columns from each model and average them, which typically improves accuracy by 1–2%.

---

## Running the Full Pipeline

```bash
# 1. Clone and enter the project
cd /path/to/NeuroMining

# 2. Start the cluster (first run pulls ~3 GB of images)
cd docker && docker-compose up -d
cd ..

# Wait for all services to be healthy (~60s)
docker-compose -f docker/docker-compose.yml ps

# 3. Generate 10 GB of test data (use --size 100 for full scale)
python data_gen/logger.py --size 10 --out ./docker/volumes/shared/raw

# 4. Copy data into HDFS
docker exec neuromining-namenode \
    hdfs dfs -mkdir -p /neuromining/raw/clickstream
docker exec neuromining-namenode \
    hdfs dfs -put /data/shared/raw/*.jsonl.gz /neuromining/raw/clickstream/

# 5. Run the MapReduce job
docker exec neuromining-namenode bash /data/shared/hadoop/run_job.sh

# 6. Run Hive feature engineering
docker exec neuromining-hive-server \
    hive -f /data/shared/hive/feature_eng.sql

# 7. Train Spark models
docker exec neuromining-spark-master \
    spark-submit --master spark://spark-master:7077 \
    /opt/spark-jobs/pipeline.py

docker exec neuromining-spark-master \
    spark-submit --master spark://spark-master:7077 \
    /opt/spark-jobs/clustering.py

# 8. Start FastAPI backend
cd backend && pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000 --reload &

# 9. Start React dashboard
cd ../frontend && npm install && npm run dev
# Visit http://localhost:5173
```

---

*Last updated: Feb 20, 2026*
