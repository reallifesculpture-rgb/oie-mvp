#!/usr/bin/env bash
set -e

echo "PORT=$PORT"
exec python -m uvicorn backend.main:app --host 0.0.0.0 --port "$PORT"
