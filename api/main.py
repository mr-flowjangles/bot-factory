"""
Bot Factory API

Thin FastAPI layer. Auto-discovers bots from factory/bots/ and mounts
a router for each one. No business logic lives here — all chat handling
is delegated to the chat Lambda via router.py.

Endpoints auto-mounted per bot:
  POST /api/{bot_id}/chat
  GET  /api/{bot_id}/suggestions
  GET  /api/{bot_id}/warmup

Meta endpoints:
  GET  /health
  GET  /bots
"""
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from factory.core.router import create_bot_router


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Bot Factory API",
    description="Multi-bot RAG chatbot platform",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv('CORS_ORIGINS', '*').split(','),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Bot auto-discovery
# ---------------------------------------------------------------------------

def discover_bots() -> list[str]:
    bots_path = Path(__file__).parent.parent / 'factory' / 'bots'

    if not bots_path.exists():
        print(f"Warning: bots directory not found at {bots_path}")
        return []

    EXCLUDED = {'TEMPLATE', 'testbot'}  # add any non-production bots here

    bots = []
    for path in sorted(bots_path.iterdir()):
        if path.is_dir() and (path / 'config.yml').exists() and path.name not in EXCLUDED:
            bots.append(path.name)

    return bots


def mount_bots(bot_ids: list[str]):
    """Mount a router for each discovered bot under /api."""
    for bot_id in bot_ids:
        router = create_bot_router(bot_id)
        app.include_router(router, prefix="/api")
        print(f"  Mounted bot: /api/{bot_id}")


# ---------------------------------------------------------------------------
# Meta endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/bots")
async def list_bots():
    """Return all active bot IDs."""
    return {"bots": discover_bots()}


# ---------------------------------------------------------------------------
# Mount bots at import time so routes are registered before the app starts
# ---------------------------------------------------------------------------

_bot_ids = discover_bots()
mount_bots(_bot_ids)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup():
    print("\nBot Factory starting up...")
    bot_ids = discover_bots()

    if not bot_ids:
        print("  Warning: no bots found in factory/bots/")
    else:
        print(f"\n  {len(bot_ids)} bot(s) active: {', '.join(bot_ids)}")

    print()