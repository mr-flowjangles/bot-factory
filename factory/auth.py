"""
API key authentication for Bot Factory.

Keys are stored as SHA-256 hashes in BotFactoryApiKeys DynamoDB table.
Incoming keys are hashed and looked up to verify access.

Usage:
    from factory.core.auth import validate_api_key

    # Returns bot_id if valid, None if not
    bot_id = validate_api_key("bf_live_abc123...")

    # Or use the decorator in Flask routes
    @require_auth
    def my_route():
        ...
"""

import hashlib
import logging
import os
import time
from functools import wraps

import boto3

logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────

API_KEYS_TABLE = os.getenv("API_KEYS_TABLE", "BotFactoryApiKeys")
APP_ENV = os.getenv("APP_ENV", "local")

# Cache validated keys for 5 minutes to reduce DynamoDB reads
_key_cache = {}
_CACHE_TTL = 300  # seconds


def _get_table():
    """Get the DynamoDB table resource."""
    if APP_ENV == "local":
        endpoint = os.getenv("LOCALSTACK_ENDPOINT", "http://localhost:4566")
        dynamodb = boto3.resource("dynamodb", endpoint_url=endpoint, region_name="us-east-1")
    else:
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    return dynamodb.Table(API_KEYS_TABLE)


def hash_key(raw_key: str) -> str:
    """SHA-256 hash a raw API key."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def validate_api_key(raw_key: str) -> dict | None:
    """
    Validate an API key against DynamoDB.

    Returns:
        dict with 'bot_id', 'key_name' if valid
        None if invalid or revoked
    """
    if not raw_key:
        return None

    # Strip "Bearer " prefix if present
    if raw_key.startswith("Bearer "):
        raw_key = raw_key[7:]

    key_hash = hash_key(raw_key)

    # Check cache first
    cached = _key_cache.get(key_hash)
    if cached and (time.time() - cached["cached_at"]) < _CACHE_TTL:
        logger.debug(f"[auth] cache hit for key ending ...{raw_key[-6:]}")
        return cached["result"]

    # Look up in DynamoDB
    try:
        table = _get_table()
        response = table.get_item(Key={"pk": key_hash})
        item = response.get("Item")

        if not item:
            logger.warning(f"[auth] unknown key ending ...{raw_key[-6:]}")
            return None

        # Check if revoked
        if item.get("revoked_at"):
            logger.warning(f"[auth] revoked key ending ...{raw_key[-6:]}")
            return None

        result = {
            "bot_id": item["bot_id"],
            "key_name": item.get("key_name", "unknown"),
        }

        # Cache the result
        _key_cache[key_hash] = {"result": result, "cached_at": time.time()}

        logger.info(f"[auth] valid key for bot_id={result['bot_id']}")
        return result

    except Exception as e:
        logger.error(f"[auth] DynamoDB error: {e}")
        return None


def extract_api_key(event_or_request) -> str | None:
    """
    Extract API key from various request formats.
    Supports: Authorization header, x-api-key header, query param.
    Works with Flask request objects and Lambda event dicts.
    """
    # Flask request object
    if hasattr(event_or_request, "headers"):
        auth = event_or_request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:]
        api_key = event_or_request.headers.get("x-api-key", "")
        if api_key:
            return api_key
        return event_or_request.args.get("api_key")

    # Lambda event dict
    if isinstance(event_or_request, dict):
        headers = event_or_request.get("headers", {})
        # Headers can be mixed case in Lambda events
        for k, v in headers.items():
            if k.lower() == "authorization" and v.startswith("Bearer "):
                return v[7:]
            if k.lower() == "x-api-key":
                return v
        # Query string params
        params = event_or_request.get("queryStringParameters") or {}
        return params.get("api_key")

    return None


def require_auth(f):
    """
    Flask route decorator that enforces API key auth.
    Sets request.auth_info with bot_id and key_name on success.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        from flask import request, jsonify

        raw_key = extract_api_key(request)
        if not raw_key:
            return jsonify({"error": "Missing API key. Use Authorization: Bearer <key> header."}), 401

        auth_info = validate_api_key(raw_key)
        if not auth_info:
            return jsonify({"error": "Invalid or revoked API key."}), 403

        # Attach auth info to request context
        request.auth_info = auth_info
        return f(*args, **kwargs)

    return decorated


def check_bot_access(auth_info: dict, requested_bot_id: str) -> bool:
    """
    Verify the authenticated key has access to the requested bot.
    A key with bot_id='*' has access to all bots.
    """
    allowed = auth_info.get("bot_id", "")
    return allowed == "*" or allowed == requested_bot_id
