# NeuroMining

An enterprise-grade distributed data mining and machine learning pipeline that ingests 100GB+ of semi-structured JSON logs, performs distributed feature engineering via Hadoop/Hive, and executes ensemble classification and clustering using Apache Spark.

## Tech Stack

| Layer | Technology |
|---|---|
| Infrastructure | Docker Compose, Hadoop HDFS, YARN |
| Storage | HDFS, Hive, PostgreSQL |
| Processing | MapReduce (Python Streaming), HiveQL |
| ML | PySpark MLlib (Naïve Bayes, SVM, MLP, Bisecting K-Means) |
| Backend | FastAPI |
| Frontend | React, D3.js, Tailwind CSS |

## Quick Start

```bash
# 1. Spin up the cluster
cd docker && docker-compose up -d

# 2. Generate synthetic data
cd data_gen && python logger.py --size 100

# 3. Run MapReduce cleaning job
cd hadoop && bash run_job.sh

# 4. Run Hive feature engineering
hive -f hive/feature_eng.sql

# 5. Train Spark ML models
spark-submit spark/pipeline.py
spark-submit spark/clustering.py

# 6. Start API
cd backend && uvicorn app:app --reload

# 7. Start frontend
cd frontend && npm install && npm run dev
```

## Phases

See [roadmap.md](roadmap.md) for the full implementation roadmap.
