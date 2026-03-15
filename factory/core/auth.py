"""
API Key Authentication

Validates X-API-Key headers against the BotFactoryApiKeys DynamoDB table.
Keys are scoped to a bot_id. Validated keys are cached in-memory for warm Lambda reuse.
"""

import os
import logging
import boto3

logger = logging.getLogger(__name__)

API_KEYS_TABLE_NAME = os.getenv("API_KEYS_TABLE_NAME", "BotFactoryApiKeys")

# In-memory cache: api_key -> bot_id (survives warm Lambda invocations)
_key_cache: dict[str, str] = {}


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


def validate_api_key(api_key: str, bot_id: str) -> bool:
    """Check if api_key is valid for the given bot_id. Returns True/False."""
    if not api_key:
        return False

    # Check in-memory cache first
    cached_bot = _key_cache.get(api_key)
    if cached_bot is not None:
        return cached_bot == bot_id

    # Look up in DynamoDB
    try:
        table = _get_dynamodb_table()
        result = table.get_item(Key={"api_key": api_key})
        item = result.get("Item")

        if not item:
            logger.warning(f"[auth] invalid key for bot_id={bot_id}")
            return False

        if not item.get("enabled", True):
            logger.warning(f"[auth] disabled key for bot_id={bot_id}")
            return False

        key_bot_id = item.get("bot_id")
        # Cache the result
        _key_cache[api_key] = key_bot_id
        return key_bot_id == bot_id

    except Exception as e:
        logger.error(f"[auth] DynamoDB lookup failed: {e}")
        return False
