#!/usr/bin/env python3
"""Quick local test: generate sample records and pipe through mapper → reducer."""
import json

records = [
    {"timestamp": "2026-01-01T10:00:00", "user_id": "u_abc", "session_id": "s_1",
     "action": "search", "payload": {"query": "machine learning", "results_count": 10, "page": 1},
     "client": {"ip": "1.2.3.4", "user_agent": "Mozilla/5.0", "country": "US"},
     "is_bot_flag": False, "schema_version": "1.2"},
    {"timestamp": "2026-01-01T10:01:00", "user_id": "u_bot", "session_id": "s_2",
     "action": "click", "payload": {"url": "https://example.com", "dwell_time_ms": 1000},
     "client": {"ip": "5.6.7.8", "user_agent": "bot-crawler/1.0", "country": "CN"},
     "is_bot_flag": True, "schema_version": "1.2"},
    {"timestamp": "2026-01-01T10:02:00", "user_id": "u_abc", "session_id": "s_1",
     "action": "follow", "payload": {},
     "client": {"ip": "1.2.3.4", "user_agent": "Mozilla/5.0", "country": "US"},
     "is_bot_flag": False, "schema_version": "1.2"},
    {"raw": "}{broken_json"},  # intentionally corrupt
    {"timestamp": "2026-01-01T10:03:00", "user_id": "u_xyz", "session_id": "s_3",
     "action": "comment", "payload": {"content_snippet": "spark tutorial"},
     "client": {"ip": "9.0.1.2", "user_agent": "Chrome/120", "country": "IN"},
     "is_bot_flag": False, "schema_version": "1.2"},
    {"timestamp": "2026-01-01T10:04:00", "user_id": "u_abc", "session_id": "s_1",
     "action": "save_post", "payload": {},
     "client": {"ip": "1.2.3.4", "user_agent": "Mozilla/5.0", "country": "US"},
     "is_bot_flag": False, "schema_version": "1.2"},
]

for r in records:
    print(json.dumps(r))
