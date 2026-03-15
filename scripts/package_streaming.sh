#!/usr/bin/env bash
# Packages factory/ + deps into .build/streaming.zip for the streaming Lambda.
set -euo pipefail

BUILD_DIR=".build"
STAGE_DIR="${BUILD_DIR}/staging"

echo "═══ Packaging streaming Lambda ═══"

rm -rf "$STAGE_DIR"
mkdir -p "$STAGE_DIR" "$BUILD_DIR"

# Install deps into staging
pip3 install -q --target "$STAGE_DIR" --platform manylinux2014_x86_64 --only-binary=:all: boto3 pyyaml flask flask-cors python-dotenv numpy

# Copy application code
cp -r factory "$STAGE_DIR/"
cp dev_server.py "$STAGE_DIR/"
cp run.sh "$STAGE_DIR/"
chmod +x "$STAGE_DIR/run.sh"

# Remove unnecessary bloat
find "$STAGE_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$STAGE_DIR" -name "*.pyc" -delete 2>/dev/null || true
rm -rf "$STAGE_DIR"/boto3 "$STAGE_DIR"/botocore "$STAGE_DIR"/s3transfer \
       "$STAGE_DIR"/urllib3 2>/dev/null || true
# Keep .dist-info — werkzeug needs metadata at runtime
rm -rf "$STAGE_DIR"/boto3-*.dist-info "$STAGE_DIR"/botocore-*.dist-info \
       "$STAGE_DIR"/s3transfer-*.dist-info "$STAGE_DIR"/urllib3-*.dist-info 2>/dev/null || true

# boto3/botocore are already in Lambda runtime — removing saves ~50MB

cd "$STAGE_DIR"
zip -qr "../streaming.zip" .
cd - > /dev/null

SIZE=$(du -h "${BUILD_DIR}/streaming.zip" | cut -f1)
echo "═══ Done: ${BUILD_DIR}/streaming.zip (${SIZE}) ═══"
