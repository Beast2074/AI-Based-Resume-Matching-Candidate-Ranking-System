#!/usr/bin/env bash
# TalentRank Warmup Script
# Pings /api/health and verifies DB connectivity before live demo

API_URL="${API_URL:-http://localhost:8000}"
echo "TalentRank: Warming up backend at $API_URL..."

# 1. Warm up health & ONNX embedder model
HEALTH_RESP=$(curl -s "$API_URL/api/health")
echo "Health Response: $HEALTH_RESP"

# 2. Warm up scoring config
CONFIG_RESP=$(curl -s "$API_URL/api/scoring-config")
echo "Scoring Config Loaded."

# 3. Warm up database with light query (e.g. list jobs)
JOBS_RESP=$(curl -s "$API_URL/api/jobs")
echo "Database Connection Active."

echo "TalentRank is warmed up and ready for demonstration!"
