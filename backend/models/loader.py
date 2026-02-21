"""Model and data artifact loader for the FastAPI backend."""

import json
import os
import random
from pathlib import Path
from typing import Dict, List, Optional

_BASE = Path(__file__).resolve().parent.parent
METRICS_PATH  = Path(os.environ.get("NM_METRICS_PATH",  _BASE / "artifacts" / "classification_metrics.json"))
CLUSTERS_PATH = Path(os.environ.get("NM_CLUSTERS_PATH", _BASE / "artifacts" / "cluster_metadata.json"))
ASSIGNMENTS_PATH = Path(os.environ.get("NM_ASSIGNMENTS_PATH", _BASE / "artifacts" / "cluster_assignments.json"))

ARCHETYPE_NAMES = {
    0: "Power Networkers",
    1: "Passive Browsers",
    2: "Content Creators",
    3: "Job Seekers",
    4: "Casual Observers",
}

LABEL_NAMES = {0: "low-value", 1: "high-value"}


class ModelLoader:

    def __init__(self):
        self._metrics: Optional[List[Dict]] = None
        self._cluster_meta: Optional[List[Dict]] = None
        self._assignments: Optional[List[Dict]] = None

    def _load_metrics(self) -> List[Dict]:
        if self._metrics is None:
            if not METRICS_PATH.exists():
                self._metrics = _stub_metrics()
            else:
                self._metrics = json.loads(METRICS_PATH.read_text())
        return self._metrics

    def _load_cluster_meta(self) -> List[Dict]:
        if self._cluster_meta is None:
            if not CLUSTERS_PATH.exists():
                self._cluster_meta = _stub_cluster_meta()
            else:
                data = json.loads(CLUSTERS_PATH.read_text())
                self._cluster_meta = data.get("clusters", data)
        return self._cluster_meta

    def _load_assignments(self) -> List[Dict]:
        if self._assignments is None:
            if not ASSIGNMENTS_PATH.exists():
                self._assignments = _stub_assignments()
            else:
                self._assignments = json.loads(ASSIGNMENTS_PATH.read_text())
        return self._assignments

    def get_metrics(self) -> List[Dict]:
        return self._load_metrics()

    def get_clusters(self, limit: int = 2000) -> Dict:
        meta   = self._load_cluster_meta()
        points = self._load_assignments()[:limit]
        enriched_points = [
            {**p, "archetype": ARCHETYPE_NAMES.get(p["cluster"], f"Segment-{p['cluster']}")}
            for p in points
        ]
        return {"metadata": meta, "points": enriched_points}

    def get_user(self, user_id: str) -> Optional[dict]:
        assignments = self._load_assignments()
        for row in assignments:
            if row.get("user_id") == user_id:
                cluster = row.get("cluster", 0)
                label   = int(row.get("label", 0))
                return {
                    "user_id":           user_id,
                    "predicted_label":   label,
                    "label_name":        LABEL_NAMES.get(label, "unknown"),
                    "cluster":           cluster,
                    "archetype":         ARCHETYPE_NAMES.get(cluster, f"Segment-{cluster}"),
                    "professional_ratio": round(float(row.get("professional_ratio", 0.0)), 4),
                    "total_actions":     int(row.get("total_actions", 0)),
                }
        return None

    def get_telemetry(self) -> dict:
        assignments = self._load_assignments()
        return {
            "total_users":          len(assignments),
            "hdfs_raw_gb":          round(random.uniform(90, 110), 2),   # stub
            "hdfs_processed_gb":    round(random.uniform(8, 12), 2),
            "hdfs_features_gb":     round(random.uniform(1.2, 2.4), 2),
            "mapreduce_output_rows": len(assignments) * 14,
        }


def _stub_metrics() -> list[dict]:
    return [
        {"model": "NaiveBayes",    "accuracy": 0.7812, "weightedPrecision": 0.7834, "weightedRecall": 0.7812, "f1": 0.7803},
        {"model": "LinearSVM",     "accuracy": 0.8541, "weightedPrecision": 0.8563, "weightedRecall": 0.8541, "f1": 0.8537},
        {"model": "MLP-NN",        "accuracy": 0.8897, "weightedPrecision": 0.8912, "weightedRecall": 0.8897, "f1": 0.8894},
        {"model": "Ensemble-Vote", "accuracy": 0.9023, "weightedPrecision": 0.9034, "weightedRecall": 0.9023, "f1": 0.9021},
    ]


def _stub_cluster_meta() -> list[dict]:
    return [
        {"cluster_id": i, "archetype": ARCHETYPE_NAMES[i],
         "user_count": random.randint(2000, 12000),
         "silhouette": 0.6412,
         "centroid": [round(random.uniform(-2, 2), 4) for _ in range(17)]}
        for i in range(5)
    ]


def _stub_assignments(n: int = 5000) -> list[dict]:
    rng = __import__("random").Random(42)
    return [
        {
            "user_id":           f"u_{i:010x}",
            "cluster":           rng.randint(0, 4),
            "pca_x":             round(rng.gauss(0, 2.5), 4),
            "pca_y":             round(rng.gauss(0, 2.5), 4),
            "label":             rng.randint(0, 1),
            "professional_ratio": round(rng.random(), 4),
            "total_actions":     rng.randint(5, 2000),
            "total_sessions":    rng.randint(1, 120),
        }
        for i in range(n)
    ]
