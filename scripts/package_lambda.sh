#!/usr/bin/env bash
# Packages factory/ + deps into .build/bot-factory.zip for the streaming Lambda.
set -euo pipefail

BUILD_DIR=".build"
STAGE_DIR="${BUILD_DIR}/staging-embed"

echo "═══ Packaging embedding Lambda ═══"

rm -rf "$STAGE_DIR"
mkdir -p "$STAGE_DIR" "$BUILD_DIR"

# Install deps into staging-embed
pip3 install -q --target "$STAGE_DIR" boto3 pyyaml

# Copy application code
cp -r factory "$STAGE_DIR/"

# Remove unnecessary bloat
find "$STAGE_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$STAGE_DIR" -name "*.pyc" -delete 2>/dev/null || true
rm -rf "$STAGE_DIR"/boto3 "$STAGE_DIR"/botocore "$STAGE_DIR"/s3transfer \
       "$STAGE_DIR"/urllib3 "$STAGE_DIR"/*.dist-info 2>/dev/null || true

# boto3/botocore are already in Lambda runtime — removing saves ~50MB

cd "$STAGE_DIR"
zip -qr "../bot-factory.zip" .
cd - > /dev/null

SIZE=$(du -h "${BUILD_DIR}/bot-factory.zip" | cut -f1)
echo "═══ Done: ${BUILD_DIR}/bot-factory.zip (${SIZE}) ═══"
