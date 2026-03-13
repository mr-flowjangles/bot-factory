#!/bin/bash
# =============================================================================
# build_lambda.sh
#
# Packages the bot-factory Lambda deployment zip.
# Three Lambdas share this zip, different handlers:
#   - run.sh (LWA streaming via Flask/dev_server.py)
#   - factory.streaming_handler.handler              (legacy fallback)
#   - factory.core.generate_embeddings.lambda_handler (embeddings)
#
# Usage:  ./scripts/build_lambda.sh
# Output: .build/bot-factory.zip
# =============================================================================

set -e

BUILD_DIR=".build/package"
ZIP_FILE=".build/bot-factory.zip"

echo ""
echo "======================================================"
echo "  Bot Factory — Lambda Build"
echo "======================================================"
echo ""

# ── Clean ─────────────────────────────────────────────────────────────────────
rm -rf "$BUILD_DIR" "$ZIP_FILE"
mkdir -p "$BUILD_DIR"

# ── Copy source ───────────────────────────────────────────────────────────────
echo "Copying source files..."
cp -r factory "$BUILD_DIR/factory"
cp dev_server.py "$BUILD_DIR/dev_server.py"
cp run.sh "$BUILD_DIR/run.sh"
chmod +x "$BUILD_DIR/run.sh"

# Copy static assets (chat HTML)
if [ -d "app" ]; then
  cp -r app "$BUILD_DIR/app"
fi

# Remove __pycache__ / .pyc
find "$BUILD_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR" -name "*.pyc" -delete 2>/dev/null || true

# ── Install dependencies ───────────────────────────────────────────────────────
echo "Installing dependencies..."
pip3 install boto3 pyyaml python-dotenv flask flask-cors numpy \
  -t "$BUILD_DIR" --quiet \
  --platform manylinux2014_x86_64 \
  --implementation cp \
  --python-version 3.12 \
  --only-binary=:all: \
  --upgrade

# ── Zip ───────────────────────────────────────────────────────────────────────
echo "Creating $ZIP_FILE..."
cd "$BUILD_DIR" && zip -r "../../$ZIP_FILE" . -q && cd ../..
echo "  Done — $(du -sh $ZIP_FILE | cut -f1)"

echo ""
echo "======================================================"
echo "  Build complete: $ZIP_FILE"
echo ""
echo "  Deploy with:"
echo "    cd terraform && terraform apply"
echo "======================================================"
echo ""