# NeuroMining

A distributed data mining and machine learning pipeline built on the Hadoop ecosystem. The system ingests large volumes of semi-structured JSON clickstream logs, cleans and aggregates them through Hadoop MapReduce, engineers features in Hive, and trains ensemble classification and user-segmentation models in Apache Spark MLlib. A FastAPI backend exposes model results and cluster data, and a React dashboard provides interactive visualizations.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
  - [1. Infrastructure](#1-infrastructure)
  - [2. Data Generation](#2-data-generation)
  - [3. MapReduce Cleaning](#3-mapreduce-cleaning)
  - [4. Hive Feature Engineering](#4-hive-feature-engineering)
  - [5. Spark ML Training](#5-spark-ml-training)
  - [6. Backend API](#6-backend-api)
  - [7. Frontend Dashboard](#7-frontend-dashboard)
- [Pipeline Details](#pipeline-details)
  - [Data Generation](#data-generation)
  - [MapReduce Stage](#mapreduce-stage)
  - [Hive Feature Engineering](#hive-feature-engineering)
  - [Spark ML Models](#spark-ml-models)
  - [API and Dashboard](#api-and-dashboard)
- [Docker Services](#docker-services)
- [Configuration](#configuration)
- [Testing](#testing)

---

## Architecture Overview

```
Synthetic Logs  -->  HDFS  -->  MapReduce  -->  Hive  -->  Spark MLlib  -->  FastAPI  -->  React Dashboard
  (JSONL.gz)        Storage     (Mapper/       (Feature     (NB/SVM/MLP      (REST)       (D3.js + Tailwind)
                                 Reducer)       Eng SQL)     + K-Means)
```

Raw clickstream events are generated as gzipped JSONL files and loaded into HDFS. A Python streaming MapReduce job reads these logs, validates records, and emits per-user action counts. Hive ingests the MapReduce output alongside the raw JSON logs to build a consolidated feature table with session-level aggregates, ratio features, and a binary label. Spark MLlib then consumes the Hive-produced Parquet to train three classifiers (Naive Bayes, Linear SVM, MLP Neural Network) with an ensemble voting layer, and a Bisecting K-Means clustering model for user segmentation. The FastAPI backend serves model metrics, cluster assignments, and telemetry data. The React frontend renders an interactive cluster scatter plot, a model comparison table, and a telemetry time-series chart.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Infrastructure | Docker Compose, Hadoop HDFS 3.4.1 |
| Storage | HDFS, Apache Hive 4.0.1, PostgreSQL 17 (Hive Metastore) |
| Processing | MapReduce (Python Streaming), HiveQL |
| Machine Learning | PySpark MLlib -- Naive Bayes, Linear SVM, Multilayer Perceptron, Bisecting K-Means |
| Backend API | Python, FastAPI, Uvicorn |
| Frontend | React 19, D3.js, Tailwind CSS, Vite |

---

## Project Structure

```
NeuroMining/
|-- backend/
|   |-- app.py                   # FastAPI application with REST endpoints
|   |-- models/
|   |   |-- __init__.py
|   |   |-- loader.py            # Artifact loader (model metrics, cluster data)
|   |-- requirements.txt
|-- data_gen/
|   |-- logger.py                # Synthetic clickstream log generator
|   |-- requirements.txt
|-- docker/
|   |-- docker-compose.yml       # Full cluster definition (7 services)
|-- frontend/
|   |-- src/
|   |   |-- App.jsx              # Main dashboard with tab navigation
|   |   |-- components/
|   |   |   |-- ClusterMap.jsx   # D3 scatter plot of user clusters
|   |   |   |-- ModelComparison.jsx  # Model metrics comparison table
|   |   |   |-- TelemetryView.jsx    # Time-series telemetry chart
|   |   |-- index.css            # Tailwind CSS entry point
|   |   |-- index.jsx            # React entry point
|   |-- index.html
|   |-- package.json
|   |-- tailwind.config.js
|-- hadoop/
|   |-- mapper.py                # MapReduce mapper (Python streaming)
|   |-- reducer.py               # MapReduce reducer (Python streaming)
|   |-- run_job.sh               # Hadoop streaming job submission script
|-- hive/
|   |-- feature_eng.sql          # 6-stage HiveQL feature engineering pipeline
|-- spark/
|   |-- pipeline.py              # Ensemble classification (NB + SVM + MLP)
|   |-- clustering.py            # Bisecting K-Means user segmentation
|   |-- requirements.txt
|-- tests/
|   |-- gen_sample.py            # Sample data generator for local testing
|   |-- test_local.py            # Local integration tests
|-- .gitignore
|-- README.md
```

---

## Prerequisites

- Docker and Docker Compose
- Python 3.9+
- Node.js 18+
- At least 8 GB of available RAM for the Docker cluster

---

## Getting Started

### 1. Infrastructure

Start the Hadoop, Hive, Spark, and PostgreSQL cluster:

```bash
cd docker
docker compose up -d
```

Wait for all services to become healthy. The HDFS NameNode web UI will be available at `http://localhost:9870`.

Initialize the Hive metastore schema (first run only):

```bash
docker compose run --rm hive-metastore schematool -dbType postgres -initSchema
```

### 2. Data Generation

Generate synthetic clickstream logs and upload them to HDFS:

```bash
cd data_gen
pip install -r requirements.txt
python logger.py --size 100
```

The `--size` flag controls the approximate dataset size in megabytes. Generated logs are gzipped JSONL files. Upload them to HDFS:

```bash
docker exec namenode hdfs dfs -mkdir -p /neuromining/raw/clickstream/
docker exec namenode hdfs dfs -put /shared/clickstream_*.jsonl.gz /neuromining/raw/clickstream/
```

### 3. MapReduce Cleaning

Run the Hadoop streaming MapReduce job to clean and aggregate the raw logs:

```bash
cd hadoop
bash run_job.sh
```

This submits a streaming job that uses `mapper.py` and `reducer.py` to read the raw JSONL logs from HDFS, validate each record, and emit tab-separated `(user_id, action, count)` tuples into `/neuromining/cleaned/session_counts/`.

### 4. Hive Feature Engineering

Run the six-stage HiveQL pipeline to transform the cleaned data into a feature table:

```bash
docker exec hive-server hive -f /shared/feature_eng.sql
```

The pipeline creates the following tables in the `neuromining` database:

| Stage | Table | Description |
|---|---|---|
| 1 | `raw_action_counts` | External table over MapReduce output |
| 2 | `user_action_pivot` | Pivoted per-user action counts (ORC) |
| 3 | `raw_logs` | External table over raw JSON logs via JsonSerDe |
| 4 | `session_features` | Session-level aggregates with window functions |
| 5 | `feature_table` | Consolidated feature table with derived ratios and labels |
| 6 | -- | Exports `feature_table` to HDFS as Parquet |

### 5. Spark ML Training

Train the ensemble classification model and the clustering model:

```bash
docker exec spark-master spark-submit --master spark://spark-master:7077 /shared/pipeline.py
docker exec spark-master spark-submit --master spark://spark-master:7077 /shared/clustering.py
```

**pipeline.py** trains three classifiers on the Hive feature table:
- Naive Bayes
- Linear SVM (via LinearSVC)
- Multilayer Perceptron (Neural Network)

Each model is evaluated with AUC-ROC, accuracy, precision, recall, and F1. An ensemble voting layer combines predictions from all three. Metrics are persisted as JSON to HDFS.

**clustering.py** trains a Bisecting K-Means model for user segmentation, applies PCA for 2D projection, and saves cluster assignments and metadata as JSON to HDFS.

### 6. Backend API

Start the FastAPI server:

```bash
cd backend
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

Available endpoints:

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/metrics` | Model evaluation metrics (all classifiers + ensemble) |
| GET | `/clusters` | User cluster assignments with PCA coordinates |
| GET | `/user/{user_id}` | Individual user feature vector and cluster label |
| GET | `/telemetry` | Pipeline telemetry (stage timings, record counts) |

If no model artifacts are found on HDFS, the API automatically falls back to realistic stub data so the dashboard remains functional during development.

### 7. Frontend Dashboard

Start the React development server:

```bash
cd frontend
npm install
npm run dev
```

The dashboard opens at `http://localhost:5173` and provides three views:

- **Cluster Map** -- Interactive D3.js scatter plot showing user clusters from Bisecting K-Means. Points are colored by cluster assignment and sized by total actions. Hover tooltips display user details.
- **Model Comparison** -- Side-by-side metrics table comparing Naive Bayes, SVM, MLP, and ensemble performance across AUC, accuracy, precision, recall, and F1.
- **Telemetry** -- Time-series chart showing pipeline stage durations and record throughput.

---

## Pipeline Details

### Data Generation

The `data_gen/logger.py` module generates synthetic but realistic clickstream data. Each event contains a timestamp, user ID, session ID, action type, a structured payload (search queries, dwell times, URLs), and client metadata (IP, user agent, country). Actions include search, click, view_profile, send_message, comment, save_post, share, follow, and login. The generator produces gzipped JSONL files with configurable volume.

### MapReduce Stage

The mapper (`hadoop/mapper.py`) reads each JSON line, validates required fields (user_id, action), and emits `user_id\taction\t1` for per-action counts plus `user_id\t__total__\t1` for the grand total. Invalid records are counted via Hadoop streaming counters. The reducer (`hadoop/reducer.py`) receives sorted input, accumulates counts per user-action pair, and flushes aggregated `user_id\taction\tcount` rows.

### Hive Feature Engineering

The `hive/feature_eng.sql` script runs six stages:

1. Creates an external table over the MapReduce output.
2. Pivots action counts into one row per user with columns for each action type.
3. Creates an external table over the raw JSON logs using Hive's JsonSerDe.
4. Computes session-level aggregates: session duration, inter-event timing, professional search counts, deep click counts, and country using window functions (LAG, FIRST_VALUE).
5. Joins the pivot table with session aggregates and derives ratio features (professional_ratio, click_through_rate) and a binary label for high-value users.
6. Exports the consolidated feature table to HDFS as Snappy-compressed Parquet for Spark consumption.

### Spark ML Models

**Ensemble Classification (pipeline.py):**

The pipeline reads the Parquet feature table, assembles numeric features into a vector, and applies MinMax scaling. It trains three models using an 80/20 train-test split:

- **Naive Bayes** -- Multinomial variant, suitable for count-based features.
- **Linear SVM** -- LinearSVC with L2 regularization for binary classification.
- **MLP Neural Network** -- Three hidden layers with configurable topology.

Each model is evaluated individually. An ensemble voting classifier combines the three predictions using majority vote. All metrics (AUC, accuracy, precision, recall, F1) are persisted as a JSON array to HDFS at `/neuromining/metrics/model_metrics.json`.

**User Segmentation (clustering.py):**

Bisecting K-Means is trained with k=5 on the same scaled feature vectors. PCA reduces features to two components for visualization. Cluster assignments with PCA coordinates are saved as JSON to `/neuromining/metrics/cluster_assignments.json`, and model metadata (k, cluster sizes, within-set sum of squared errors) is saved to `/neuromining/metrics/cluster_meta.json`.

### API and Dashboard

The FastAPI backend loads model artifacts from HDFS on startup. If artifacts are unavailable, it generates plausible stub data so the dashboard works without a running cluster. The React frontend fetches data from three endpoints on mount and renders the active tab. The cluster scatter plot uses D3.js force simulation for layout, with pan/zoom support. The color scheme uses a dark theme with accent colors defined in the Tailwind configuration.

---

## Docker Services

The `docker/docker-compose.yml` defines seven services:

| Service | Image | Ports | Purpose |
|---|---|---|---|
| namenode | apache/hadoop:3.4.1 | 9870, 8020 | HDFS NameNode |
| datanode | apache/hadoop:3.4.1 | 9864 | HDFS DataNode |
| postgres | postgres:17-alpine | 5432 | Hive Metastore database |
| hive-metastore | apache/hive:4.0.1 | 9083 | Hive Metastore service |
| hive-server | apache/hive:4.0.1 | 10000, 10002 | HiveServer2 (JDBC/Thrift) |
| spark-master | apache/spark:3.5.3 | 8080, 7077 | Spark master node |
| spark-worker | apache/spark:3.5.3 | 8081 | Spark worker node |

A shared volume at `docker/volumes/shared/` is mounted into all containers at `/shared/` for exchanging scripts and data files.

---

## Configuration

Key environment variables and settings:

| Variable | Default | Description |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | Backend API URL (frontend) |
| `--size` (logger.py) | 100 | Approximate dataset size in MB |
| `HDFS_REPLICATION` | 1 | HDFS replication factor (single-node dev) |
| `HIVE_METASTORE_DB` | postgres:5432/metastore | Hive metastore JDBC URL |
| Spark master | `spark://spark-master:7077` | Spark cluster manager URL |

---

## Testing

Run local integration tests without requiring Docker:

```bash
cd tests
python gen_sample.py        # Generate sample test data
python test_local.py        # Run integration tests
```

These tests validate the mapper and reducer logic, data generation output format, and API endpoint responses using lightweight local data.
