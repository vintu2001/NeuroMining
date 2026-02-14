"""
NeuroMining — FastAPI Backend
Serves model metrics and cluster data from HDFS/local cache for the dashboard.

Run with:
    uvicorn app:app --host 0.0.0.0 --port 8000 --reload
"""

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Path as FPath
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from models.loader import ModelLoader

app = FastAPI(
    title="NeuroMining API",
    description="Model metrics, cluster assignments, and user predictions for NeuroMining.",
    version="1.0.0",
)

# ── CORS (allow React dev server) ─────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ── Singleton loader ──────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def get_loader() -> ModelLoader:
    return ModelLoader()


# ── Response schemas ──────────────────────────────────────────────────────────

class ModelMetrics(BaseModel):
    model: str
    accuracy: float
    weightedPrecision: float
    weightedRecall: float
    f1: float


class ClusterInfo(BaseModel):
    cluster_id: int
    archetype: str
    user_count: int
    silhouette: float
    centroid: list[float]


class ClusterPoint(BaseModel):
    user_id: str
    cluster: int
    pca_x: float
    pca_y: float
    archetype: str


class UserPrediction(BaseModel):
    user_id: str
    predicted_label: int
    label_name: str
    cluster: int
    archetype: str
    professional_ratio: float
    total_actions: int


class ClustersResponse(BaseModel):
    metadata: list[ClusterInfo]
    points: list[ClusterPoint]


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "neuromining-api"}


@app.get("/metrics", response_model=list[ModelMetrics])
def get_metrics():
    """
    Returns precision/recall/F1/accuracy for each classifier:
    Naïve Bayes, Linear SVM, MLP Neural Network, and Ensemble Vote.
    """
    try:
        return get_loader().get_metrics()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/clusters", response_model=ClustersResponse)
def get_clusters(limit: int = 2000):
    """
    Returns cluster metadata (archetypes, silhouette score, centroids)
    and a sample of PCA-reduced scatter plot points for the dashboard.
    Limit controls how many data points are returned (default 2000).
    """
    if limit < 1 or limit > 50_000:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 50000")
    try:
        return get_loader().get_clusters(limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/user/{user_id}", response_model=UserPrediction)
def get_user(user_id: str = FPath(..., min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_\-]+$")):
    """
    Returns the predicted interaction value and behavioral segment for
    a specific user. Returns 404 if the user is not in the dataset.
    """
    try:
        result = get_loader().get_user(user_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")
    return result


@app.get("/telemetry")
def get_telemetry():
    """
    Returns HDFS storage metrics and record counts for the telemetry view.
    In production this would query the Hadoop NameNode REST API.
    """
    try:
        return get_loader().get_telemetry()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
