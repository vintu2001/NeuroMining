#!/usr/bin/env python3
"""
NeuroMining — MapReduce Reducer (Python Streaming)

Receives sorted key-value pairs from the mapper:
    <user_id>\t<action>\t1

Aggregates total action counts per (user_id, action) pair and emits:
    <user_id>\t<action>\t<total_count>

Additionally computes per-user aggregate row (action="__total__") for
downstream Hive ingestion.

Hadoop sort guarantees all lines for a given user_id arrive consecutively.
"""

import sys
from collections import defaultdict


def process_stream(stream=sys.stdin):
    current_user = None
    action_counts: dict[str, int] = defaultdict(int)

    def flush(user_id: str, counts: dict):
        total = 0
        for action, count in sorted(counts.items()):
            print(f"{user_id}\t{action}\t{count}")
            total += count
        # Emit aggregate row so Hive can query total_actions directly
        print(f"{user_id}\t__total__\t{total}")

    for line in stream:
        line = line.rstrip("\n")
        if not line:
            continue

        parts = line.split("\t")
        if len(parts) != 3:
            print(f"reporter:counter:NeuroMining,reducer_malformed_input,1",
                  file=sys.stderr)
            continue

        user_id, action, count_str = parts
        try:
            count = int(count_str)
        except ValueError:
            print(f"reporter:counter:NeuroMining,reducer_bad_count,1",
                  file=sys.stderr)
            continue

        if user_id != current_user:
            if current_user is not None:
                flush(current_user, action_counts)
            current_user = user_id
            action_counts = defaultdict(int)

        action_counts[action] += count

    # Flush last user
    if current_user is not None:
        flush(current_user, action_counts)


if __name__ == "__main__":
    process_stream()
