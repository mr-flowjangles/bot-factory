#!/usr/bin/env bash
#
# Bot Factory — Customer Onboarding
#
# One-command onboarding for a new managed-service customer. Wraps:
#   1. Scaffold the bot structure
#   2. Import a prepared customer brief (config + prompt + knowledge files)
#   3. Deploy to S3 + generate embeddings + manifest
#   4. Generate a publishable key with the customer's allowed origins
#   5. Print an onboarding receipt with the embed snippet
#
# Usage:
#   scripts/onboard_customer.sh \
#     --bot-id acme-cleaning \
#     --customer-name "Acme Cleaning" \
#     --allowed-origins https://acmecleaning.com \
#     --brief-dir ~/customers/acme-cleaning \
#     [--rate-limit 30]
#
# A "brief dir" is a directory containing:
#     config.yml       — bot settings (model, RAG params, personality)
#     prompt.yml       — system prompt
#     data/            — knowledge base files (YAML / text / PDF)
#
# Run without --brief-dir to scaffold an empty bot and stop, so you can hand-edit
# the templates before re-running with --brief-dir.

set -euo pipefail

# ── Args ──────────────────────────────────────────────────────────────────────
BOT_ID=""
CUSTOMER_NAME=""
ALLOWED_ORIGINS=""
BRIEF_DIR=""
RATE_LIMIT=30

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bot-id)          BOT_ID="$2"; shift 2 ;;
    --customer-name)   CUSTOMER_NAME="$2"; shift 2 ;;
    --allowed-origins) ALLOWED_ORIGINS="$2"; shift 2 ;;
    --brief-dir)       BRIEF_DIR="$2"; shift 2 ;;
    --rate-limit)      RATE_LIMIT="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,/^set -/p' "$0" | sed 's/^# \{0,1\}//' | head -n -1
      exit 0 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

[[ -z "$BOT_ID" ]]          && { echo "ERROR: --bot-id is required"; exit 1; }
[[ -z "$CUSTOMER_NAME" ]]   && { echo "ERROR: --customer-name is required"; exit 1; }
[[ -z "$ALLOWED_ORIGINS" ]] && { echo "ERROR: --allowed-origins is required"; exit 1; }

if ! [[ "$BOT_ID" =~ ^[a-zA-Z0-9-]+$ ]] || [[ "$BOT_ID" == -* ]] || [[ "$BOT_ID" == *- ]]; then
  echo "ERROR: --bot-id must be alphanumeric with optional hyphens (no leading/trailing -)"
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BOT_DIR="$REPO_ROOT/scripts/bots/$BOT_ID"

# ── Step 1: Scaffold ──────────────────────────────────────────────────────────
echo "═══ [1/4] Scaffold ═══"
if [[ -d "$BOT_DIR" ]]; then
  echo "Bot directory already exists at $BOT_DIR — skipping scaffold."
else
  APP_ENV=production python3 "$REPO_ROOT/scripts/scaffold_bot.py" "$BOT_ID"
fi

# ── Step 2: Import brief ──────────────────────────────────────────────────────
if [[ -z "$BRIEF_DIR" ]]; then
  cat <<EOF

No --brief-dir provided. Empty bot scaffolded.

Next steps (manual):
  1. Edit $BOT_DIR/config.yml — name, persona, response_style
  2. Edit $BOT_DIR/prompt.yml — system prompt
  3. Add knowledge files to $BOT_DIR/data/
  4. Re-run with --brief-dir $BOT_DIR (or a separate brief dir).

EOF
  exit 0
fi

[[ ! -d "$BRIEF_DIR" ]]            && { echo "ERROR: Brief dir not found: $BRIEF_DIR"; exit 1; }
[[ ! -f "$BRIEF_DIR/config.yml" ]] && { echo "ERROR: Missing $BRIEF_DIR/config.yml"; exit 1; }
[[ ! -f "$BRIEF_DIR/prompt.yml" ]] && { echo "ERROR: Missing $BRIEF_DIR/prompt.yml"; exit 1; }
[[ ! -d "$BRIEF_DIR/data" ]]       && { echo "ERROR: Missing $BRIEF_DIR/data/"; exit 1; }

echo ""
echo "═══ [2/4] Import brief from $BRIEF_DIR ═══"
cp "$BRIEF_DIR/config.yml" "$BOT_DIR/config.yml"
cp "$BRIEF_DIR/prompt.yml" "$BOT_DIR/prompt.yml"
mkdir -p "$BOT_DIR/data"
cp -R "$BRIEF_DIR/data/." "$BOT_DIR/data/"
echo "  ✓ config.yml + prompt.yml + data/ copied"

# ── Step 3: Deploy + embed ────────────────────────────────────────────────────
echo ""
echo "═══ [3/4] Deploy to S3 + generate embeddings ═══"
cd "$REPO_ROOT"
make deploy-bot-prod bot="$BOT_ID"

# ── Step 4: Generate publishable key ──────────────────────────────────────────
echo ""
echo "═══ [4/4] Generate publishable key ═══"
KEY_NAME="prod-${BOT_ID}"
KEY_OUTPUT=$(python3 "$REPO_ROOT/scripts/gen_api_key.py" "$BOT_ID" \
  --name "$KEY_NAME" \
  --allowed-origins "$ALLOWED_ORIGINS" \
  --rate-limit "$RATE_LIMIT")
echo "$KEY_OUTPUT"

PUB_KEY=$(echo "$KEY_OUTPUT" | grep -oE 'bfk_[A-Za-z0-9_-]+' | head -1)
STREAM_URL=$(terraform -chdir="$REPO_ROOT/terraform" output -raw stream_function_url 2>/dev/null \
             | tr -d '\n' || echo "<run: terraform -chdir=terraform output stream_function_url>")

# ── Receipt ───────────────────────────────────────────────────────────────────
cat <<EOF

═══════════════════════════════════════════════════════════════════════
  Onboarding complete: $CUSTOMER_NAME ($BOT_ID)
═══════════════════════════════════════════════════════════════════════

  Publishable key:   $PUB_KEY
  Allowed origins:   $ALLOWED_ORIGINS
  Rate limit:        $RATE_LIMIT requests/hour per IP
  Stream URL:        $STREAM_URL

  Embed snippet for the customer's site:
  ────────────────────────────────────────────────────────────────────

  <script>
    window.BOT_CONFIG = {
      apiUrl:         '$STREAM_URL',
      botId:          '$BOT_ID',
      publishableKey: '$PUB_KEY',
      botName:        '$CUSTOMER_NAME',
      placeholder:    'Ask anything...'
    };
  </script>
  <script src="<chat.js host TBD — see docs/your-bot/02-build-plan.md>"></script>

  ────────────────────────────────────────────────────────────────────

  Record this in your CRM and store the publishable key with the customer's file.

═══════════════════════════════════════════════════════════════════════
EOF
