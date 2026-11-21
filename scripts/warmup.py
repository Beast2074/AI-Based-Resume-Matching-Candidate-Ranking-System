"""
TalentRank Warmup Utility
Pings backend endpoints to preload local ONNX model and wake up DB connection.
"""

import sys
import urllib.request
import json
import time

def warmup(api_base: str = "http://localhost:8000"):
    print(f"TalentRank: Warming up backend services at {api_base}...")
    endpoints = [
        ("/api/health", "Preloading ONNX embedding model and engine status"),
        ("/api/scoring-config", "Loading calibrated scoring parameters"),
        ("/api/jobs", "Waking up database connection pool"),
    ]

    for ep, desc in endpoints:
        url = f"{api_base.rstrip('/')}{ep}"
        t0 = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "TalentRank-Warmup/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
                elapsed = (time.time() - t0) * 1000.0
                print(f"  [OK] {ep:20s} ({elapsed:.1f} ms) - {desc}")
        except Exception as e:
            print(f"  [WARN] {ep:20s} - {e}")

    print("\nWarmup complete. Backend is hot and ready for live recruiter demo!")

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    warmup(url)
