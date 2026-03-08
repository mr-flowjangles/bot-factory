#!/bin/bash
# =============================================================================
# build_lambda.sh
#
# Packages the bot-factory Lambda deployment zip.
# All Lambdas share this zip, different handlers:
#   - handler.handler          (main API)
#   - streaming_handler.handler (SSE streaming)
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
cp handler.py "$BUILD_DIR/handler.py"
cp factory/streaming_handler.py "$BUILD_DIR/streaming_handler.py"
cp -r app "$BUILD_DIR/app"

# Remove __pycache__ / .pyc
find "$BUILD_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR" -name "*.pyc" -delete 2>/dev/null || true

# ── Install dependencies ───────────────────────────────────────────────────────
echo "Installing dependencies..."
pip3 install boto3 pyyaml python-dotenv -t "$BUILD_DIR" --quiet

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
