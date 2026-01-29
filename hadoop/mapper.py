#!/usr/bin/env python3
"""
NeuroMining — MapReduce Mapper (Python Streaming)

Reads JSON-line log records from stdin (Hadoop streams raw HDFS bytes here),
validates each record, filters bots and corrupt entries, then emits:

    <user_id>\t<action>\t1

to stdout for the reducer to aggregate.

Hadoop usage:
    hadoop jar $HADOOP_HOME/share/hadoop/tools/lib/hadoop-streaming-*.jar \
        -files mapper.py,reducer.py \
        -mapper "python3 mapper.py" \
        -reducer "python3 reducer.py" \
        -input  hdfs:///neuromining/raw/clickstream/ \
        -output hdfs:///neuromining/cleaned/session_counts/

Environment variables (set via -cmdenv in the streaming job):
    NM_MIN_DWELL_MS   Minimum dwell time to consider a click valid (default 500)
    NM_BOT_UA_REGEX   Regex pattern to catch bot user agents
"""

import json
import os
import re
import sys

# ── Configuration ────────────────────────────────────────────────────────────

MIN_DWELL_MS = int(os.environ.get("NM_MIN_DWELL_MS", "500"))
BOT_UA_PATTERN = re.compile(
    os.environ.get(
        "NM_BOT_UA_REGEX",
        r"(bot|crawler|spider|scraper|curl|wget|python-requests)",
    ),
    re.IGNORECASE,
)

VALID_ACTIONS = {
    "search", "click", "view_profile", "send_message",
    "save_post", "share", "comment", "login", "logout",
    "page_view", "download", "upload", "follow", "unfollow",
}

# Counters reported via stderr for the Hadoop counters API
_counters = {
    "records_in": 0,
    "records_corrupt": 0,
    "records_bot": 0,
    "records_invalid_action": 0,
    "records_emitted": 0,
}


def _increment(counter: str, delta: int = 1):
    _counters[counter] += delta
    # Hadoop streaming reads counter updates from stderr
    print(f"reporter:counter:NeuroMining,{counter},{delta}", file=sys.stderr)


def _is_bot(record: dict) -> bool:
    """Return True if the record looks like it originated from a bot."""
    if record.get("is_bot_flag"):
        return True
    client = record.get("client", {})
    ua = client.get("user_agent", "")
    if BOT_UA_PATTERN.search(ua):
        return True
    return False


def _validate(record: dict) -> bool:
    """Basic schema validation. Returns False for records that should be dropped."""
    if not isinstance(record.get("user_id"), str):
        return False
    if not isinstance(record.get("session_id"), str):
        return False
    if record.get("action") not in VALID_ACTIONS:
        return False
    if not isinstance(record.get("timestamp"), str):
        return False
    # Payload dwell time filter for click events
    action = record["action"]
    if action in ("click", "page_view"):
        dwell = record.get("payload", {}).get("dwell_time_ms", MIN_DWELL_MS + 1)
        if dwell < MIN_DWELL_MS:
            return False
    return True


def _parse_line(line: str):
    """
    Handle both plain JSON objects and multi-line nested JSON fragments.
    Hadoop may deliver partial lines when records span HDFS block boundaries;
    we attempt to reconstruct them using a simple bracket-depth heuristic.
    Returns parsed dict or None on failure.
    """
    line = line.strip()
    if not line:
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        # Attempt to repair trailing-comma or truncated objects
        repaired = line.rstrip(",").rstrip()
        if not repaired.endswith("}"):
            repaired += "}"
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            return None


def process_stream(stream=sys.stdin):
    buffer = ""
    depth = 0

    for raw_line in stream:
        _increment("records_in")

        # Multi-line nested JSON reconstruction
        for ch in raw_line:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            buffer += ch

            if depth == 0 and buffer.strip():
                record = _parse_line(buffer)
                buffer = ""

                if record is None:
                    _increment("records_corrupt")
                    continue

                if not _validate(record):
                    _increment("records_invalid_action")
                    continue

                if _is_bot(record):
                    _increment("records_bot")
                    continue

                user_id = record["user_id"]
                action = record["action"]
                print(f"{user_id}\t{action}\t1")
                _increment("records_emitted")
                break  # processed full object from this line


if __name__ == "__main__":
    process_stream()
