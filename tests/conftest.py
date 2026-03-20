"""
Shared fixtures for Bot Factory tests.

Requires LocalStack running (make up) for DynamoDB.
Bedrock calls are mocked to avoid hitting real AWS.
"""

import os
import pytest
import boto3
from decimal import Decimal
from unittest.mock import patch, MagicMock

# Force local environment before any factory imports
os.environ.setdefault("APP_ENV", "local")
os.environ.setdefault("LOCALSTACK_ENDPOINT", "http://localhost:4566")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("RAG_TABLE_NAME", "BotFactoryRAG")
os.environ.setdefault("RAG_BOT_ID_INDEX_NAME", "bot_id-index")
os.environ.setdefault("BOT_DATA_BUCKET", "bot-factory-data")

TEST_BOT_ID = "test-bot-pytest"


@pytest.fixture
def dynamodb_table():
    """Get the real LocalStack DynamoDB table."""
    dynamodb = boto3.resource(
        "dynamodb",
        endpoint_url="http://localhost:4566",
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    return dynamodb.Table("BotFactoryRAG")


@pytest.fixture(autouse=True)
def cleanup_test_embeddings(dynamodb_table):
    """Delete any test bot embeddings before and after each test."""
    def _delete_test_items():
        response = dynamodb_table.query(
            IndexName="bot_id-index",
            KeyConditionExpression=boto3.dynamodb.conditions.Key("bot_id").eq(TEST_BOT_ID),
        )
        for item in response.get("Items", []):
            dynamodb_table.delete_item(Key={"pk": item["pk"]})

    _delete_test_items()
    yield
    _delete_test_items()


def make_embedding(dimensions=1024, value=0.1):
    """Create a fake embedding vector."""
    return [Decimal(str(value))] * dimensions


def store_test_embedding(table, entry_id, text="test content", heading="Test Heading", embedding_value=0.1):
    """Store a test embedding in DynamoDB."""
    table.put_item(Item={
        "pk": f"{TEST_BOT_ID}_{entry_id}",
        "bot_id": TEST_BOT_ID,
        "text": text,
        "heading": heading,
        "category": "Test",
        "embedding": make_embedding(value=embedding_value),
    })
