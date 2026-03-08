# -*- coding: utf-8 -*-
"""
Embedding Generator (Universal)

Reads a bot's data via the chunker, generates embeddings via AWS Bedrock
(Amazon Titan Text Embeddings V2), and stores them in the BotFactoryRAG
DynamoDB table with a bot_id field.

Uses kill-and-fill scoped to the bot_id -- only deletes and rewrites
embeddings for the specified bot. Other bots are untouched.

Behavior:
  - First run:      No embeddings found, generates automatically
  - Already exist:  Prompts "Regenerate? (y/n)" before proceeding
  - --force flag:   Skips the prompt, regenerates without asking

Usage:
    # Local (S3 + DynamoDB via LocalStack, Bedrock via real AWS)
    python -m factory.core.generate_embeddings guitar

    # Production (everything via real AWS)
    APP_ENV=production python -m factory.core.generate_embeddings guitar
    APP_ENV=production python -m factory.core.generate_embeddings guitar --force
"""

import os
import sys
import json
import boto3
from decimal import Decimal
from .chunker import load_bot_data
from dotenv import load_dotenv

BEDROCK_MODEL_ID = "amazon.titan-embed-text-v2:0"
EMBEDDING_DIMENSIONS = 1024
RAG_TABLE_NAME = os.getenv("RAG_TABLE_NAME", "BotFactoryRAG")


# ---------------------------------------------------------------------------
# Connections
# ---------------------------------------------------------------------------


def get_dynamodb_connection():
    """Get DynamoDB connection. Uses LocalStack for local, real AWS for production."""
    if os.getenv("APP_ENV", "local") == "production":
        return boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))

    return boto3.resource(
        "dynamodb",
        endpoint_url=os.getenv("LOCALSTACK_ENDPOINT", "http://localhost:4566"),
        region_name=os.getenv("AWS_REGION", "us-east-1"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "test"),
    )


def get_bedrock_client():
    """Bedrock always calls real AWS regardless of APP_ENV."""
    return boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))


# ---------------------------------------------------------------------------
# Embedding generation
# ---------------------------------------------------------------------------


def generate_embedding(client, text: str) -> list:
    """Generate a single embedding vector via Bedrock Titan V2."""
    response = client.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        body=json.dumps({"inputText": text, "dimensions": EMBEDDING_DIMENSIONS, "normalize": True}),
    )
    return json.loads(response["body"].read())["embedding"]


def generate_all_embeddings(client, chunks: list) -> list:
    """Generate embeddings for all chunks. Adds 'embedding' key to each chunk."""
    print("\nGenerating embeddings with Bedrock Titan V2 ({} chunks)...".format(len(chunks)))

    for idx, chunk in enumerate(chunks, 1):
        print("  [{}/{}] {}: {}".format(idx, len(chunks), chunk["category"], chunk["id"]))
        try:
            chunk["embedding"] = generate_embedding(client, chunk["text"])
        except Exception as e:
            print("  Error generating embedding for '{}': {}".format(chunk["id"], e))
            sys.exit(1)

    print("  Done -- {} embeddings generated".format(len(chunks)))
    return chunks


# ---------------------------------------------------------------------------
# DynamoDB storage
# ---------------------------------------------------------------------------


def clear_bot_embeddings(table, bot_id: str):
    """Delete all existing embeddings for this bot_id only."""
    print("\nClearing existing embeddings for bot '{}'...".format(bot_id))

    response = table.scan()
    items = response.get("Items", [])
    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))

    bot_items = [item for item in items if item.get("bot_id") == bot_id]

    if not bot_items:
        print("  No existing embeddings found for '{}'".format(bot_id))
        return

    with table.batch_writer() as batch:
        for item in bot_items:
            batch.delete_item(Key={"pk": item["pk"]})

    print("  Deleted {} existing embeddings".format(len(bot_items)))


def store_embeddings(table, chunks: list):
    """Write chunks with embeddings to DynamoDB."""
    print("\nStoring {} embeddings in BotFactoryRAG...".format(len(chunks)))

    with table.batch_writer() as batch:
        for chunk in chunks:
            item = {
                "pk": "{}_{}".format(chunk["bot_id"], chunk["id"]),
                "bot_id": chunk["bot_id"],
                "category": chunk["category"],
                "heading": chunk["heading"],
                "text": chunk["text"],
                "embedding": [Decimal(str(x)) for x in chunk["embedding"]],
            }
            batch.put_item(Item=item)

    print("  Done -- {} embeddings stored".format(len(chunks)))


def bot_embeddings_exist(table, bot_id: str) -> bool:
    """Check if this bot already has embeddings in the table."""
    response = table.scan()
    items = response.get("Items", [])
    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))
    return any(item.get("bot_id") == bot_id for item in items)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def generate_bot_embeddings(bot_id: str, force: bool = False):
    """Full pipeline: chunker -> Bedrock Titan V2 -> DynamoDB for a given bot."""
    env = os.getenv("APP_ENV", "local")

    print("\n" + "=" * 60)
    print("  Bot Factory -- Embedding Generator")
    print("  Bot: {}".format(bot_id))
    print("  Model: {} ({}d)".format(BEDROCK_MODEL_ID, EMBEDDING_DIMENSIONS))
    print("  Environment: {}".format(env))
    print("=" * 60 + "\n")

    # Step 1: Connect to DynamoDB
    dynamodb = get_dynamodb_connection()
    table = dynamodb.Table(RAG_TABLE_NAME)

    # Step 2: Check if embeddings already exist
    if not force and bot_embeddings_exist(table, bot_id):
        answer = input("Embeddings already exist for '{}'. Regenerate? (y/n): ".format(bot_id))
        if answer.strip().lower() != "y":
            print("Skipping.")
            return

    # Step 3: Load and chunk the bot's data
    chunks = load_bot_data(bot_id)
    if not chunks:
        print("No data found for bot '{}'. Check s3://bot-factory-data/bots/{}/data/".format(bot_id, bot_id))
        sys.exit(1)

    # Step 4: Generate embeddings via Bedrock
    bedrock_client = get_bedrock_client()
    chunks = generate_all_embeddings(bedrock_client, chunks)

    # Step 5: Clear old embeddings for this bot
    clear_bot_embeddings(table, bot_id)

    # Step 6: Store new embeddings
    store_embeddings(table, chunks)

    # Summary
    from collections import Counter
    cats = Counter(c["category"] for c in chunks)

    print("\n" + "=" * 60)
    print("  Embeddings generation complete!")
    print("=" * 60)
    print("\n  Bot:        {}".format(bot_id))
    print("  Env:        {}".format(env))
    print("  Model:      {}".format(BEDROCK_MODEL_ID))
    print("  Dimensions: {}".format(EMBEDDING_DIMENSIONS))
    print("  Total:      {} embeddings".format(len(chunks)))
    for cat, count in cats.most_common():
        print("    {}: {}".format(cat, count))
    print("  Table:      {} (bot_id='{}')".format(RAG_TABLE_NAME, bot_id))
    print()


def main():
    """CLI entry point."""
    load_dotenv()
    
    if len(sys.argv) < 2:
        print("Usage: python -m factory.core.generate_embeddings <bot_id> [--force]")
        print("Example: python -m factory.core.generate_embeddings guitar")
        sys.exit(1)

    bot_id = sys.argv[1]
    force = "--force" in sys.argv
    generate_bot_embeddings(bot_id, force=force)


if __name__ == "__main__":
    main()