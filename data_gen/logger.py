#!/usr/bin/env python3
"""
NeuroMining — Synthetic Clickstream Log Generator
Produces JSON-line log files simulating user clickstreams, search queries,
and session metadata at scale (configurable up to 100 GB+).

Usage:
    python logger.py --size 100          # target ~100 GB output
    python logger.py --records 5000000   # explicit record count
    python logger.py --out /data/raw     # custom output directory
"""

import argparse
import gzip
import json
import os
import random
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Domain constants ────────────────────────────────────────────────────────

ACTIONS = [
    "search", "click", "view_profile", "send_message",
    "save_post", "share", "comment", "login", "logout",
    "page_view", "download", "upload", "follow", "unfollow",
]

PROFESSIONAL_KEYWORDS = [
    "machine learning", "data engineering", "distributed systems",
    "kubernetes", "spark", "hadoop", "MLOps", "feature store",
    "neural network", "LLM fine-tuning", "data pipeline",
    "microservices", "REST API", "CI/CD", "Docker", "Terraform",
    "system design", "database sharding", "stream processing",
    "real-time analytics", "recommendation engine",
]

CASUAL_KEYWORDS = [
    "funny cat videos", "weekend recipes", "travel tips",
    "movie reviews", "celebrity news", "sports highlights",
    "home decor ideas", "DIY hacks", "fitness motivation",
    "fashion trends", "gaming tips", "food delivery",
]

DOMAINS = ["linkedin.com", "github.com", "medium.com", "dev.to",
           "stackoverflow.com", "reddit.com", "youtube.com",
           "twitter.com", "instagram.com", "facebook.com"]

BOT_USER_FRACTION = 0.04   # ~4 % of user IDs will be bot-like
CORRUPT_RECORD_FRACTION = 0.01  # ~1 % records are intentionally malformed


def _iso_ts(base: datetime, jitter_seconds: int = 3600) -> str:
    delta = timedelta(seconds=random.randint(0, jitter_seconds))
    return (base + delta).isoformat()


def _weighted_action() -> str:
    weights = [15, 20, 10, 8, 5, 6, 7, 3, 2, 12, 4, 2, 4, 2]
    return random.choices(ACTIONS, weights=weights, k=1)[0]


def _payload(action: str, is_professional: bool) -> dict:
    keyword_pool = PROFESSIONAL_KEYWORDS if is_professional else CASUAL_KEYWORDS
    if action == "search":
        return {
            "query": random.choice(keyword_pool),
            "results_count": random.randint(1, 200),
            "page": random.randint(1, 5),
        }
    if action in ("click", "view_profile", "page_view"):
        return {
            "url": f"https://{random.choice(DOMAINS)}/{uuid.uuid4().hex[:8]}",
            "referrer": random.choice(DOMAINS),
            "dwell_time_ms": random.randint(500, 120_000),
        }
    if action in ("send_message", "comment"):
        return {
            "content_snippet": " ".join(random.choices(keyword_pool, k=random.randint(3, 12))),
            "recipient_id": f"u_{uuid.uuid4().hex[:10]}",
        }
    return {"meta": f"{action}_event", "value": random.random()}


def _make_record(user_id: str, session_id: str, ts: str,
                 is_bot: bool, is_professional: bool) -> dict:
    action = _weighted_action()
    rec = {
        "timestamp": ts,
        "user_id": user_id,
        "session_id": session_id,
        "action": action,
        "payload": _payload(action, is_professional),
        "client": {
            "ip": f"{random.randint(1,254)}.{random.randint(0,254)}.{random.randint(0,254)}.{random.randint(1,254)}",
            "user_agent": random.choice([
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                "python-requests/2.28.0",    # bot indicator
                "curl/7.68.0",               # bot indicator
            ]) if not is_bot else "bot-crawler/1.0",
            "country": random.choice(["US", "IN", "DE", "BR", "GB", "CA", "AU", "SG"]),
        },
        "is_bot_flag": is_bot,
        "schema_version": "1.2",
    }
    return rec


def generate_users(n: int):
    """Pre-generate a user pool with stable attributes."""
    users = {}
    for _ in range(n):
        uid = f"u_{uuid.uuid4().hex[:12]}"
        users[uid] = {
            "is_bot": random.random() < BOT_USER_FRACTION,
            "is_professional": random.random() < 0.45,
            "avg_sessions_per_day": random.randint(1, 30),
        }
    return users


def write_chunk(path: Path, records: list[dict], compress: bool = True) -> int:
    """Write a list of records to a .jsonl.gz file. Returns bytes written."""
    opener = gzip.open if compress else open
    mode = "wt" if compress else "w"
    with opener(path, mode, encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")
    return path.stat().st_size


def main():
    parser = argparse.ArgumentParser(description="NeuroMining log generator")
    parser.add_argument("--size", type=float, default=1.0,
                        help="Target output size in GB (approximate)")
    parser.add_argument("--records", type=int, default=0,
                        help="Override: exact number of records to generate")
    parser.add_argument("--out", type=str, default="./data/raw",
                        help="Output directory")
    parser.add_argument("--chunk-size", type=int, default=500_000,
                        help="Records per output file chunk")
    parser.add_argument("--no-compress", action="store_true",
                        help="Disable gzip compression")
    parser.add_argument("--users", type=int, default=50_000,
                        help="Number of simulated unique users")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Rough size estimate: ~380 bytes/record uncompressed, ~3:1 gzip ratio
    bytes_per_record_compressed = 130
    target_bytes = int(args.size * 1024 ** 3)
    total_records = args.records if args.records > 0 else max(
        1_000, target_bytes // bytes_per_record_compressed
    )

    compress = not args.no_compress
    ext = ".jsonl.gz" if compress else ".jsonl"

    print(f"[logger] Target: {total_records:,} records  →  {args.out}")
    print(f"[logger] Building user pool ({args.users:,} users) …")
    users = generate_users(args.users)
    user_ids = list(users.keys())

    base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    chunk_idx = 0
    generated = 0
    total_bytes = 0
    chunk: list[dict] = []
    t0 = time.monotonic()

    while generated < total_records:
        uid = random.choice(user_ids)
        uinfo = users[uid]
        session_id = f"s_{uuid.uuid4().hex[:16]}"
        session_length = random.randint(1, 40)
        session_start = base_time + timedelta(
            seconds=random.randint(0, 30 * 24 * 3600)
        )

        for event_idx in range(session_length):
            if generated >= total_records:
                break
            ts = _iso_ts(session_start, jitter_seconds=event_idx * 120)
            if random.random() < CORRUPT_RECORD_FRACTION:
                # Intentionally malformed record for MapReduce to filter
                chunk.append({"_corrupt": True, "raw": "}{invalid_json_fragment"})
            else:
                chunk.append(_make_record(
                    uid, session_id, ts,
                    uinfo["is_bot"], uinfo["is_professional"]
                ))
            generated += 1

        if len(chunk) >= args.chunk_size:
            fname = out_dir / f"clickstream_{chunk_idx:05d}{ext}"
            total_bytes += write_chunk(fname, chunk, compress)
            pct = generated / total_records * 100
            elapsed = time.monotonic() - t0
            rate = generated / max(elapsed, 1)
            print(f"[logger] Chunk {chunk_idx:04d} written | "
                  f"{generated:>12,} / {total_records:,} records "
                  f"({pct:5.1f}%) | {total_bytes / 1024**3:.2f} GB | "
                  f"{rate:,.0f} rec/s",
                  end="\r", flush=True)
            chunk = []
            chunk_idx += 1

    # Flush remaining
    if chunk:
        fname = out_dir / f"clickstream_{chunk_idx:05d}{ext}"
        total_bytes += write_chunk(fname, chunk, compress)
        chunk_idx += 1

    elapsed = time.monotonic() - t0
    print(f"\n[logger] Done. {generated:,} records across {chunk_idx} files "
          f"→ {total_bytes / 1024**3:.3f} GB in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
