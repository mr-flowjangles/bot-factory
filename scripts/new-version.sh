#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# new-version.sh — Start a new Bot Factory version
#
# Creates:
#   1. A git branch: V{major}dot{minor}dot{patch}/{Description}
#   2. A version folder: Versions/v{major}/v{major}.{minor}.{patch}/
#   3. A stubbed release-notes.md
#
# Usage:
#   ./scripts/new-version.sh                          # patch bump (interactive)
#   ./scripts/new-version.sh "My Feature"             # patch bump
#   ./scripts/new-version.sh --minor "My Feature"     # minor bump (resets patch)
#   ./scripts/new-version.sh --major "My Feature"     # major bump (resets minor+patch)
# ─────────────────────────────────────────────────────────────
set -euo pipefail

VERSIONS_DIR="Versions"
BUMP="patch"

# ── Parse flags ──
while [[ "${1:-}" == --* ]]; do
  case "$1" in
    --minor) BUMP="minor"; shift ;;
    --major) BUMP="major"; shift ;;
    *) echo "Unknown flag: $1"; exit 1 ;;
  esac
done

# ── Find latest version from folder names (supports nested v{major}/ layout) ──
latest=$(find "$VERSIONS_DIR" -type d -name 'v*.*.*' 2>/dev/null \
  | sed 's|.*/v||' \
  | sort -t. -k1,1n -k2,2n -k3,3n \
  | tail -1)

if [ -z "$latest" ]; then
  echo "No existing version folders found in $VERSIONS_DIR/"
  exit 1
fi

# ── Bump version ──
IFS='.' read -r major minor patch <<< "$latest"

case "$BUMP" in
  patch) next_major=$major; next_minor=$minor; next_patch=$((patch + 1)) ;;
  minor) next_major=$major; next_minor=$((minor + 1)); next_patch=0 ;;
  major) next_major=$((major + 1)); next_minor=0; next_patch=0 ;;
esac

next_version="${next_major}.${next_minor}.${next_patch}"

echo "Latest version: v${latest}"
echo "Next version:   v${next_version} (${BUMP} bump)"
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
branch_name="V${next_major}dot${next_minor}dot${next_patch}/${branch_suffix}"

# ── Create branch ──
echo ""
echo "Creating branch: $branch_name"
git checkout -b "$branch_name"

# ── Create version folder + stub ──
version_dir="${VERSIONS_DIR}/v${next_major}/v${next_version}"
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
