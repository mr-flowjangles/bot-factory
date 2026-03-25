"""
Bot Utilities

Pure Python helpers shared by both Lambda and ECS implementations.
No FastAPI dependencies — safe to import anywhere.
"""

import uuid
import os
import logging
import yaml
from datetime import datetime
from decimal import Decimal

logger = logging.getLogger(__name__)

LOGS_TABLE_NAME = os.getenv("LOGS_TABLE_NAME", "BotFactoryLogs")


def load_bot_config(bot_id: str) -> dict:
    """Load a bot's config.yml from S3. Always reads fresh so config changes
    (like threshold tuning) take effect without a cold start."""
    from .chatbot import get_s3_client, S3_BUCKET

    s3_key = f"bots/{bot_id}/config.yml"
    logger.info(f"[bot_utils:{bot_id}] Loading config from s3://{S3_BUCKET}/{s3_key}")

    s3 = get_s3_client()
    obj = s3.get_object(Bucket=S3_BUCKET, Key=s3_key)
    return yaml.safe_load(obj["Body"].read().decode("utf-8"))


def log_chat_interaction(bot_id: str, question: str, response: str, sources: list[dict]):
    """Log chat interaction to DynamoDB BotFactoryLogs table."""
    try:
        from .retrieval import get_dynamodb_connection

        dynamodb = get_dynamodb_connection()
        table = dynamodb.Table(LOGS_TABLE_NAME)

        clean_sources = [
            {
                "category": s.get("category", "unknown"),
                "similarity": Decimal(str(s.get("similarity", 0))),
            }
            for s in sources
        ]

        table.put_item(
            Item={
                "id": f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}",
                "bot_id": bot_id,
                "timestamp": datetime.utcnow().isoformat(),
                "question": question,
                "response": response,
                "sources": clean_sources,
                "source_count": len(sources),
            }
        )
    except Exception as e:
        logger.warning(f"Failed to log chat interaction for '{bot_id}': {e}")


def log_visit(bot_id: str, user_agent: str = "", referrer: str = ""):
    """Log a site visit to DynamoDB BotFactoryLogs table."""
    try:
        from .retrieval import get_dynamodb_connection

        dynamodb = get_dynamodb_connection()
        table = dynamodb.Table(LOGS_TABLE_NAME)

        table.put_item(
            Item={
                "id": f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}",
                "bot_id": bot_id,
                "type": "visit",
                "timestamp": datetime.utcnow().isoformat(),
                "user_agent": user_agent,
                "referrer": referrer,
            }
        )
    except Exception as e:
        logger.warning(f"Failed to log visit for '{bot_id}': {e}")
