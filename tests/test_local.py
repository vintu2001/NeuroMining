#!/usr/bin/env python3
"""
Run all local tests (no Docker required):
  1. MapReduce mapper → reducer pipeline
  2. data_gen logger (100k records)
  3. FastAPI backend (stub data, all endpoints)
"""
import subprocess
import sys
import os
import json
import time
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASS = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"
INFO = "\033[36m·\033[0m"

errors = []

def ok(msg):  print(f"  {PASS} {msg}")
def fail(msg): print(f"  {FAIL} {msg}"); errors.append(msg)
def info(msg): print(f"  {INFO} {msg}")


# ─────────────────────────────────────────────────────────────────────────────
# TEST 1: MapReduce pipeline
# ─────────────────────────────────────────────────────────────────────────────
print("\n[1/3] MapReduce mapper → reducer")

gen   = subprocess.run([sys.executable, os.path.join(ROOT, "tests/gen_sample.py")],
                       capture_output=True, text=True)
if gen.returncode != 0:
    fail(f"gen_sample.py failed: {gen.stderr}")
else:
    mapper  = subprocess.run([sys.executable, os.path.join(ROOT, "hadoop/mapper.py")],
                              input=gen.stdout, capture_output=True, text=True)
    if mapper.returncode != 0:
        fail(f"mapper failed: {mapper.stderr.splitlines()[-1] if mapper.stderr else 'no output'}")
    else:
        lines = sorted(mapper.stdout.splitlines())
        sorted_input = "\n".join(lines) + "\n"
        reducer = subprocess.run([sys.executable, os.path.join(ROOT, "hadoop/reducer.py")],
                                  input=sorted_input, capture_output=True, text=True)
        if reducer.returncode != 0:
            fail(f"reducer failed: {reducer.stderr}")
        else:
            output = reducer.stdout.strip().splitlines()
            counters = {l for l in mapper.stderr.splitlines() if "reporter:counter" in l}
            ok(f"Mapper emitted {len(lines)} rows (bot + corrupt filtered)")
            ok(f"Reducer output {len(output)} rows")
            info(f"Sample output:\n" + "\n".join("    " + l for l in output[:8]))
            # Validate: u_bot should NOT appear
            assert all("u_bot" not in l for l in output), "Bot user leaked into output!"
            ok("Bot filtering verified — u_bot not in reducer output")
            # u_abc should have __total__ >= 3 actions
            total_abc = next((l for l in output if "u_abc" in l and "__total__" in l), None)
            assert total_abc, "u_abc __total__ row missing"
            count = int(total_abc.split("\t")[2])
            assert count >= 3, f"Expected >=3 actions for u_abc, got {count}"
            ok(f"u_abc total actions = {count} (correct)")


# ─────────────────────────────────────────────────────────────────────────────
# TEST 2: data_gen logger
# ─────────────────────────────────────────────────────────────────────────────
print("\n[2/3] data_gen logger (100k records)")

import tempfile, gzip, pathlib

tmpdir = tempfile.mkdtemp()
result = subprocess.run(
    [sys.executable, os.path.join(ROOT, "data_gen/logger.py"),
     "--records", "100000", "--out", tmpdir, "--users", "500", "--chunk-size", "100000"],
    capture_output=True, text=True, timeout=120
)
if result.returncode != 0:
    fail(f"logger.py exited {result.returncode}: {result.stderr[-300:]}")
else:
    files = list(pathlib.Path(tmpdir).glob("*.jsonl.gz"))
    total_lines = 0
    for f in files:
        with gzip.open(f, "rt") as fh:
            total_lines += sum(1 for _ in fh)
    ok(f"Generated {len(files)} file(s), {total_lines:,} records")
    # Spot-check first record
    with gzip.open(files[0], "rt") as fh:
        first = json.loads(fh.readline())
    assert "user_id" in first and "action" in first and "timestamp" in first
    ok(f"Record schema valid: {list(first.keys())}")


# ─────────────────────────────────────────────────────────────────────────────
# TEST 3: FastAPI backend (stub data)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[3/3] FastAPI backend (stub data)")

# Install deps if needed
pip = subprocess.run(
    [sys.executable, "-m", "pip", "install", "-q",
     "fastapi==0.110.0", "uvicorn[standard]==0.29.0", "pydantic==2.6.4", "httpx"],
    capture_output=True, text=True
)
if pip.returncode != 0:
    fail(f"pip install failed: {pip.stderr[-200:]}")
else:
    ok("FastAPI dependencies installed")

    # Start uvicorn in a thread
    import importlib, sys as _sys
    _sys.path.insert(0, os.path.join(ROOT, "backend"))

    server_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app",
         "--host", "127.0.0.1", "--port", "18000", "--log-level", "error"],
        cwd=os.path.join(ROOT, "backend"),
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
    )
    time.sleep(3)  # Wait for startup

    if server_proc.poll() is not None:
        err = server_proc.stderr.read().decode()[-300:]
        fail(f"uvicorn failed to start: {err}")
    else:
        ok("uvicorn started on :18000")
        # Test endpoints using httpx
        try:
            import httpx
            base = "http://127.0.0.1:18000"

            r = httpx.get(f"{base}/health", timeout=5)
            assert r.status_code == 200, f"health returned {r.status_code}"
            ok(f"GET /health → {r.json()}")

            r = httpx.get(f"{base}/metrics", timeout=5)
            assert r.status_code == 200
            data = r.json()
            assert len(data) == 4
            ok(f"GET /metrics → {len(data)} models: {[m['model'] for m in data]}")
            for m in data:
                assert 0 < m["accuracy"] <= 1 and 0 < m["f1"] <= 1

            r = httpx.get(f"{base}/clusters?limit=50", timeout=5)
            assert r.status_code == 200
            c = r.json()
            assert len(c["metadata"]) == 5
            assert len(c["points"]) == 50
            ok(f"GET /clusters → {len(c['metadata'])} archetypes, {len(c['points'])} points")

            # Test a valid user
            sample_uid = c["points"][0]["user_id"]
            r = httpx.get(f"{base}/user/{sample_uid}", timeout=5)
            assert r.status_code == 200
            u = r.json()
            ok(f"GET /user/{{id}} → label={u['label_name']}, archetype={u['archetype']}")

            # Test 404
            r = httpx.get(f"{base}/user/nonexistent_user_xyz", timeout=5)
            assert r.status_code == 404
            ok("GET /user/nonexistent → 404 (correct)")

            # Test bad limit
            r = httpx.get(f"{base}/clusters?limit=0", timeout=5)
            assert r.status_code == 400
            ok("GET /clusters?limit=0 → 400 (validation correct)")

            r = httpx.get(f"{base}/telemetry", timeout=5)
            assert r.status_code == 200
            t = r.json()
            ok(f"GET /telemetry → {t}")

        except Exception as e:
            fail(f"API test error: {e}")
        finally:
            server_proc.terminate()
            server_proc.wait()


# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
print()
if errors:
    print(f"\033[31m  FAILED — {len(errors)} error(s):\033[0m")
    for e in errors:
        print(f"    • {e}")
    sys.exit(1)
else:
    print("\033[32m  ALL LOCAL TESTS PASSED\033[0m")
