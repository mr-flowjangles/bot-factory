"""
API Key Authentication

Validates publishable keys (X-Publishable-Key, also accepted as X-API-Key) against the
BotFactoryApiKeys DynamoDB table. Keys are scoped to a bot_id and carry an `allowed_origins`
list — hard-enforced. Keys without `allowed_origins` are rejected.

Validated lookups are cached in-memory for warm Lambda reuse.
"""

import os
import logging
import boto3

logger = logging.getLogger(__name__)

API_KEYS_TABLE_NAME = os.getenv("API_KEYS_TABLE_NAME", "BotFactoryApiKeys")

# In-memory cache: api_key -> record dict (survives warm Lambda invocations)
_key_cache: dict[str, dict] = {}


def _get_dynamodb_table():
    if os.getenv("APP_ENV", "local") == "production":
        dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))
    else:
        dynamodb = boto3.resource(
            "dynamodb",
            endpoint_url=os.getenv("LOCALSTACK_ENDPOINT", "http://localhost:4566"),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "test"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "test"),
        )
    return dynamodb.Table(API_KEYS_TABLE_NAME)


def lookup_api_key(api_key: str) -> dict | None:
    """Return the full key record (bot_id, allowed_origins, rate_limit_per_hour, ...) or None."""
    if not api_key:
        return None

    cached = _key_cache.get(api_key)
    if cached is not None:
        return cached

    try:
        table = _get_dynamodb_table()
        result = table.get_item(Key={"api_key": api_key})
        item = result.get("Item")
        if not item:
            return None
        if not item.get("enabled", True):
            logger.warning("[auth] disabled key presented")
            return None
        _key_cache[api_key] = item
        return item
    except Exception as e:
        logger.error(f"[auth] DynamoDB lookup failed: {e}")
        return None


def authorize_request(api_key: str, bot_id: str, origin: str) -> tuple[bool, str, dict | None]:
    """
    Hard-enforce three checks: key valid, bot_id matches, origin in allowlist.
    Returns (allowed, reason_if_rejected, key_record_if_allowed).
    """
    record = lookup_api_key(api_key)
    if record is None:
        return (False, "invalid or disabled key", None)

    if record.get("bot_id") != bot_id:
        return (False, "key not authorized for this bot", None)

    allowed_origins = record.get("allowed_origins") or []
    if not allowed_origins:
        logger.warning(f"[auth] key for bot_id={bot_id} has no allowed_origins — rejecting")
        return (False, "key has no configured origins", None)

    if origin not in allowed_origins:
        logger.warning(f"[auth] origin={origin!r} not in allowlist for bot_id={bot_id}")
        return (False, "origin not allowed", None)

    return (True, "", record)
