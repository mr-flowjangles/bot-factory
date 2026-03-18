"""
Retrieval Module (Parameterized)

Performs semantic search against stored embeddings in DynamoDB,
scoped by bot_id. Each bot's embeddings are cached separately
in memory for warm Lambda reuse.

Uses a GSI on bot_id to query only that bot's items instead of
scanning the entire table.
"""

import os
import json
import time
import logging
import boto3
import numpy as np
from boto3.dynamodb.conditions import Key

logger = logging.getLogger(__name__)

BEDROCK_MODEL_ID = "amazon.titan-embed-text-v2:0"
EMBEDDING_DIMENSIONS = 1024
RAG_TABLE_NAME = os.getenv("RAG_TABLE_NAME", "BotFactoryRAG")
GSI_NAME = os.getenv("RAG_BOT_ID_INDEX_NAME", "bot_id-index")

# Per-bot embedding cache — survives across warm Lambda invocations
_embeddings_cache = {}


def get_dynamodb_connection():
    if os.getenv("APP_ENV", "local") == "production":
        return boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))
    return boto3.resource(
        "dynamodb",
        endpoint_url=os.getenv("LOCALSTACK_ENDPOINT", "http://localhost:4566"),
        region_name=os.getenv("AWS_REGION", "us-east-1"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "test"),
    )


def get_cached_embeddings(bot_id: str) -> list[dict]:
    """Load and cache embeddings for a specific bot via GSI query."""
    if bot_id in _embeddings_cache:
        logger.info(f"[retrieval:{bot_id}] cache HIT — {len(_embeddings_cache[bot_id])} items")
        return _embeddings_cache[bot_id]

    logger.info(f"[retrieval:{bot_id}] cache MISS — querying GSI...")
    t_start = time.time()

    dynamodb = get_dynamodb_connection()
    table = dynamodb.Table(RAG_TABLE_NAME)

    # Query the GSI — reads only this bot's items, not the whole table
    items = []
    response = table.query(
        IndexName=GSI_NAME,
        KeyConditionExpression=Key("bot_id").eq(bot_id),
    )
    items.extend(response.get("Items", []))
    pages = 1

    while "LastEvaluatedKey" in response:
        response = table.query(
            IndexName=GSI_NAME,
            KeyConditionExpression=Key("bot_id").eq(bot_id),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))
        pages += 1

    t_query = time.time() - t_start
    logger.info(f"[retrieval:{bot_id}] GSI query — {len(items)} items, {pages} page(s), {t_query:.3f}s")

    _embeddings_cache[bot_id] = items
    logger.info(f"[retrieval:{bot_id}] cached {len(items)} embeddings")
    return items


def invalidate_bot_cache(bot_id: str):
    """Clear cached embeddings for a bot so the next request reloads from DynamoDB."""
    if bot_id in _embeddings_cache:
        del _embeddings_cache[bot_id]
        logger.info(f"[retrieval:{bot_id}] cache INVALIDATED")
    else:
        logger.info(f"[retrieval:{bot_id}] cache invalidate — nothing cached")


# ---------------------------------------------------------------------------
# Bedrock query embedding
# ---------------------------------------------------------------------------

_bedrock_client = None


def get_bedrock_client():
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))
    return _bedrock_client


def generate_query_embedding(query: str) -> list[float]:
    """Convert a user's question to an embedding vector via Bedrock Titan V2."""
    t_start = time.time()
    client = get_bedrock_client()
    response = client.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        body=json.dumps({"inputText": query, "dimensions": EMBEDDING_DIMENSIONS, "normalize": True}),
    )
    embedding = json.loads(response["body"].read())["embedding"]
    logger.info(f"[retrieval] Bedrock embedding={time.time() - t_start:.3f}s")
    return embedding


# ---------------------------------------------------------------------------
# Similarity search
# ---------------------------------------------------------------------------


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    a = np.array(vec1)
    b = np.array(vec2)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def retrieve_relevant_chunks(bot_id: str, query: str, top_k: int, similarity_threshold: float) -> list[dict]:
    """Retrieve the most relevant chunks for a query, scoped to a bot."""
    logger.info(f"[retrieval:{bot_id}] query='{query[:60]}'")

    query_embedding = generate_query_embedding(query)
    items = get_cached_embeddings(bot_id)

    results = []
    for item in items:
        stored_embedding = [float(x) for x in item["embedding"]]
        similarity = cosine_similarity(query_embedding, stored_embedding)

        if similarity >= similarity_threshold:
            results.append(
                {
                    "id": item["pk"],
                    "category": item.get("category", "General"),
                    "heading": item.get("heading", ""),
                    "text": item["text"],
                    "similarity": float(similarity),
                }
            )

    results.sort(key=lambda x: x["similarity"], reverse=True)

    top = results[0]["similarity"] if results else "N/A"
    logger.info(
        f"[retrieval:{bot_id}] found={len(results)} above threshold={similarity_threshold} "
        f"top_score={top} returning top_{top_k}"
    )

    return results[:top_k]


def format_context_for_llm(chunks: list[dict]) -> str:
    """Format retrieved chunks into context string for Claude."""
    if not chunks:
        return "No relevant information found."

    context_parts = []
    for chunk in chunks:
        context_parts.append(f"[{chunk['category'].upper()}]\n{chunk['text']}")

    return "\n\n---\n\n".join(context_parts)
