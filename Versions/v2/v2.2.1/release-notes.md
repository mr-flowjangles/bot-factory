# v2.2.1 — Documentation Cleanup (2026-04-01)

## Problem

Several docs and the `make test-chat` target still referenced the removed `lambda_handler.py` (buffered handler). The `Versions/` tree in README.md showed a flat layout that didn't match the actual nested `v{major}/v{major}.{minor}.{patch}/` structure.

## Solution

Removed all stale `lambda_handler` references and aligned docs with the current streaming-only architecture.

## Fixed

- `make test-chat` now curls the running dev server instead of importing the nonexistent `factory.lambda_handler`
- CLAUDE.md architecture diagram removed the "Buffered / lambda_handler" branch
- CLAUDE.md "Two Lambda handlers" corrected to single streaming handler
- README.md `Versions/` tree fixed to show nested `v1/v1.0.0/`, `v2/v2.0.0/` layout
- `factory/README.md` and `LOCAL_DEVELOPMENT.md` updated test-chat descriptions

## Files Changed

| File | Change |
|------|--------|
| `Makefile` | `test-chat` target now curls dev server with API_KEY from .env |
| `CLAUDE.md` | Removed lambda_handler references, fixed architecture diagram |
| `README.md` | Fixed Versions/ directory tree structure |
| `factory/README.md` | Updated test-chat description |
| `factory/core/docs/LOCAL_DEVELOPMENT.md` | Updated test-chat comment |
