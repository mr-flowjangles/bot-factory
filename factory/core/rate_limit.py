"""
Rate limiting

Per-(api_key, ip) request counter backed by DynamoDB with TTL.
Fail-open on errors so an outage on the rate-limit table can't take chat down.
"""

import os
import time
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

RATE_LIMIT_TABLE_NAME = os.getenv("RATE_LIMIT_TABLE_NAME", "BotFactoryRateLimit")
DEFAULT_LIMIT_PER_HOUR = int(os.getenv("RATE_LIMIT_DEFAULT_PER_HOUR", "30"))
WINDOW_SECONDS = 3600


def _get_table():
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
    return dynamodb.Table(RATE_LIMIT_TABLE_NAME)


def check_rate_limit(api_key: str, ip: str, limit: int | None = None) -> tuple[bool, int]:
    """
    Returns (allowed, current_count). Fail-open on errors.
    Window is fixed from the first request in the window (DynamoDB TTL resets it).
    """
    if not api_key or not ip:
        return (True, 0)

    effective_limit = limit if limit is not None else DEFAULT_LIMIT_PER_HOUR
    now = int(time.time())
    pk = f"{api_key}#{ip}"

    try:
        table = _get_table()
    except Exception as e:
        logger.error(f"[rate_limit] table init failed: {e}")
        return (True, 0)

    # Atomic increment IF an unexpired record exists.
    try:
        response = table.update_item(
            Key={"pk": pk},
            UpdateExpression="ADD #count :inc",
            ConditionExpression="attribute_exists(pk) AND expires_at > :now",
            ExpressionAttributeNames={"#count": "count"},
            ExpressionAttributeValues={":inc": 1, ":now": now},
            ReturnValues="UPDATED_NEW",
        )
        count = int(response["Attributes"]["count"])
        return (count <= effective_limit, count)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code != "ConditionalCheckFailedException":
            logger.error(f"[rate_limit] update failed: {e}")
            return (True, 0)

    # No record OR window expired — start a fresh window.
    try:
        table.put_item(Item={"pk": pk, "count": 1, "expires_at": now + WINDOW_SECONDS})
        return (True, 1)
    except Exception as e:
        logger.error(f"[rate_limit] put failed: {e}")
        return (True, 0)
