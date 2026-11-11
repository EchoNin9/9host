#!/usr/bin/env bash
# Builds the API Lambda bundle at infra/.build/api_lambda (run before `tofu plan/apply`).
# Third-party deps are installed as Linux wheels for the Lambda runtime
# (python3.12, x86_64 — keep in sync with infra/lambda.tf).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/infra/.build/api_lambda"
PY_VERSION="3.12"
PLATFORM="manylinux2014_x86_64"

rm -rf "$OUT"
mkdir -p "$OUT"

python3 -m pip install -r "$ROOT/api/requirements.txt" --target "$OUT" \
  --platform "$PLATFORM" --implementation cp --python-version "$PY_VERSION" \
  --only-binary=:all: --upgrade --no-compile

cp "$ROOT"/api/*.py "$OUT"/
cp -R "$ROOT/api/templates" "$OUT/templates"
find "$OUT/templates" -name __pycache__ -type d -prune -exec rm -rf {} +

echo "Built $OUT ($(du -sh "$OUT" | cut -f1))"
