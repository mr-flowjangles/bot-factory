#!/usr/bin/env bash
# Generates a unique bucket name and writes it to terraform.tfvars
# Run once before `terraform init && terraform apply`

set -e

ADJECTIVES=(autumn hidden misty ancient crimson silent dawn velvet amber cosmic)
NOUNS=(harbor lantern forge beacon summit archive harbor cipher prism vault)

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ADJ=${ADJECTIVES[$RANDOM % ${#ADJECTIVES[@]}]}
NOUN=${NOUNS[$RANDOM % ${#NOUNS[@]}]}
BUCKET_NAME="bot-factory-${ACCOUNT_ID}-${ADJ}-${NOUN}"

TFVARS_FILE="$(dirname "$0")/terraform.tfvars"

if [ -f "$TFVARS_FILE" ]; then
  echo "terraform.tfvars already exists. Delete it to regenerate."
  echo "Current bucket name:"
  grep bucket_name "$TFVARS_FILE"
  exit 0
fi

cat > "$TFVARS_FILE" <<EOF
bucket_name = "${BUCKET_NAME}"
EOF

echo "Generated bucket name: ${BUCKET_NAME}"
echo "Written to terraform.tfvars"
