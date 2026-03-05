#!/bin/bash
# =============================================================================
# build_lambda.sh
#
# Packages the embedding generator Lambda and deploys to AWS.
#
# Usage:
#   ./build_lambda.sh                  # build + deploy
#   ./build_lambda.sh --build-only     # zip only, no deploy
#
# Required env vars (or set them below):
#   LAMBDA_FUNCTION_NAME   e.g. bot-factory-embed
#   AWS_REGION             e.g. us-east-1
#   BOT_DATA_BUCKET        S3 bucket where YAML files live
# =============================================================================

set -e

# ── Config ────────────────────────────────────────────────────────────────────
FUNCTION_NAME="${LAMBDA_FUNCTION_NAME:-bot-factory-embed}"
REGION="${AWS_REGION:-us-east-1}"
BUCKET="${BOT_DATA_BUCKET:-your-bot-data-bucket}"
BUILD_DIR=".lambda_build"
ZIP_FILE="embedding_lambda.zip"

echo ""
echo "======================================================"
echo "  Bot Factory — Lambda Build"
echo "  Function: $FUNCTION_NAME"
echo "  Region:   $REGION"
echo "======================================================"
echo ""

# ── Clean ─────────────────────────────────────────────────────────────────────
rm -rf "$BUILD_DIR" "$ZIP_FILE"
mkdir -p "$BUILD_DIR/factory/core"

# ── Copy source files ─────────────────────────────────────────────────────────
echo "Copying source files..."
cp factory/core/generate_embeddings.py "$BUILD_DIR/factory/core/"
cp factory/core/chunker.py             "$BUILD_DIR/factory/core/"

# __init__.py files so Python treats dirs as packages
touch "$BUILD_DIR/factory/__init__.py"
touch "$BUILD_DIR/factory/core/__init__.py"

# ── Install dependencies ───────────────────────────────────────────────────────
echo "Installing dependencies..."
pip install boto3 pyyaml --target "$BUILD_DIR" --quiet

# ── Zip it up ─────────────────────────────────────────────────────────────────
echo "Creating $ZIP_FILE..."
cd "$BUILD_DIR" && zip -r "../$ZIP_FILE" . -q && cd ..
echo "  Done — $(du -sh $ZIP_FILE | cut -f1) package"

if [[ "$1" == "--build-only" ]]; then
    echo ""
    echo "Build complete. Skipping deploy (--build-only)."
    echo "Upload $ZIP_FILE manually or run without --build-only."
    exit 0
fi

# ── Deploy ────────────────────────────────────────────────────────────────────
echo ""
echo "Deploying to Lambda..."

# Check if function exists
if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" &>/dev/null; then
    # Update existing
    aws lambda update-function-code \
        --function-name "$FUNCTION_NAME" \
        --zip-file "fileb://$ZIP_FILE" \
        --region "$REGION" \
        --output json | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  Updated: {d[\"FunctionArn\"]}')"

    # Update env vars
    aws lambda update-function-configuration \
        --function-name "$FUNCTION_NAME" \
        --region "$REGION" \
        --handler "factory.core.generate_embeddings.lambda_handler" \
        --environment "Variables={DATA_SOURCE=s3,BOT_DATA_BUCKET=$BUCKET}" \
        --timeout 300 \
        --memory-size 512 \
        --output json | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  Config updated')"
else
    echo "  Function '$FUNCTION_NAME' not found."
    echo "  Create it first in the AWS console, then re-run this script."
    echo ""
    echo "  Minimum settings when creating:"
    echo "    Runtime:  Python 3.12"
    echo "    Handler:  factory.core.generate_embeddings.lambda_handler"
    echo "    Timeout:  300s"
    echo "    Memory:   512 MB"
    exit 1
fi

echo ""
echo "======================================================"
echo "  Deploy complete!"
echo ""
echo "  Test invoke (AWS Console or CLI):"
echo "    aws lambda invoke \\"
echo "      --function-name $FUNCTION_NAME \\"
echo "      --payload '{\"bot_id\":\"guitar\",\"force\":true}' \\"
echo "      --cli-binary-format raw-in-base64-out \\"
echo "      response.json && cat response.json"
echo "======================================================"
echo ""
