"""FastAPI backend serving model metrics, cluster data, and telemetry."""

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "http://localhost:5176"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

@lru_cache(maxsize=1)
def get_loader() -> ModelLoader:
    return ModelLoader()


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
    centroid: list


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
    metadata: list
    points: list


@app.get("/health")
def health():
    return {"status": "ok", "service": "neuromining-api"}


@app.get("/metrics", response_model=list[ModelMetrics])
def get_metrics():
    try:
        return get_loader().get_metrics()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/clusters", response_model=ClustersResponse)
def get_clusters(limit: int = 2000):
    if limit < 1 or limit > 50_000:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 50000")
    try:
        return get_loader().get_clusters(limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/user/{user_id}", response_model=UserPrediction)
def get_user(user_id: str = FPath(..., min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_\-]+$")):
    try:
        result = get_loader().get_user(user_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")
    return result


@app.get("/telemetry")
def get_telemetry():
    try:
        return get_loader().get_telemetry()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
