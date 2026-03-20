#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# new-version.sh — Start a new Bot Factory version
#
# Creates:
#   1. A git branch: V{major}dot{minor}dot{patch}/{Description}
#   2. A version folder: Versions/v{major}.{minor}.{patch}/
#   3. A stubbed release-notes.md
#
# Usage:
#   ./scripts/new-version.sh
#   ./scripts/new-version.sh "My Feature Description"
# ─────────────────────────────────────────────────────────────
set -euo pipefail

VERSIONS_DIR="Versions"

# ── Find latest version from folder names ──
latest=$(ls -d "$VERSIONS_DIR"/v*.*.* 2>/dev/null \
  | sed 's|.*/v||' \
  | sort -t. -k1,1n -k2,2n -k3,3n \
  | tail -1)

if [ -z "$latest" ]; then
  echo "No existing version folders found in $VERSIONS_DIR/"
  exit 1
fi

# ── Bump patch version ──
IFS='.' read -r major minor patch <<< "$latest"
next_patch=$((patch + 1))
next_version="${major}.${minor}.${next_patch}"

echo "Latest version: v${latest}"
echo "Next version:   v${next_version}"
echo ""

# ── Get description ──
if [ -n "${1:-}" ]; then
  description="$1"
else
  read -rp "Description (e.g. 'Add Widget Support'): " description
fi

if [ -z "$description" ]; then
  echo "Description is required."
  exit 1
fi

# ── Format branch name: V{major}dot{minor}dot{patch}/{Description_With_Underscores} ──
branch_suffix=$(echo "$description" | sed 's/ /_/g')
branch_name="V${major}dot${minor}dot${next_patch}/${branch_suffix}"

# ── Create branch ──
echo ""
echo "Creating branch: $branch_name"
git checkout -b "$branch_name"

# ── Create version folder + stub ──
version_dir="${VERSIONS_DIR}/v${next_version}"
mkdir -p "$version_dir"

today=$(date +%Y-%m-%d)

cat > "${version_dir}/release-notes.md" << EOF
# v${next_version} — ${description} (${today})

<!-- TODO: Fill in after implementation -->

## Problem

## Solution

## New

## Changed

## Fixed

## Files Changed

| File | Change |
|------|--------|
EOF

echo "Created ${version_dir}/release-notes.md"
echo ""
echo "Ready to go:"
echo "  Branch:  $branch_name"
echo "  Folder:  $version_dir/"
echo "  Notes:   ${version_dir}/release-notes.md"
