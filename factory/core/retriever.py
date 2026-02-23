"""
Retriever

Performs semantic search against stored embeddings in DynamoDB,
scoped by bot_id. Embeddings are cached per bot for warm Lambda reuse.
"""
import numpy as np
from boto3.dynamodb.conditions import Attr
from .connections import get_rag_table, get_openai_client


# ---------------------------------------------------------------------------
# Per-bot embedding cache — survives warm Lambda invocations
# ---------------------------------------------------------------------------

_embeddings_cache: dict[str, list[dict]] = {}


def get_cached_embeddings(bot_id: str) -> list[dict]:
    """Load and cache embeddings for a specific bot from DynamoDB."""
    if bot_id in _embeddings_cache:
        return _embeddings_cache[bot_id]

    print(f"Loading embeddings for '{bot_id}' from DynamoDB...")
    table = get_rag_table()

    items = []
    response = table.scan(FilterExpression=Attr('bot_id').eq(bot_id))
    items.extend(response.get('Items', []))

    while 'LastEvaluatedKey' in response:
        response = table.scan(
            FilterExpression=Attr('bot_id').eq(bot_id),
            ExclusiveStartKey=response['LastEvaluatedKey'],
        )
        items.extend(response.get('Items', []))

    _embeddings_cache[bot_id] = items
    print(f"Cached {len(items)} embeddings for '{bot_id}'")
    return items


def invalidate_cache(bot_id: str):
    """Force a cache reload on next request — call after re-embedding a bot."""
    _embeddings_cache.pop(bot_id, None)


# ---------------------------------------------------------------------------
# Similarity search
# ---------------------------------------------------------------------------

def generate_query_embedding(query: str) -> list[float]:
    """Convert a user query to an embedding vector."""
    client = get_openai_client()
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=query,
    )
    return response.data[0].embedding


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    a = np.array(vec1)
    b = np.array(vec2)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def retrieve_relevant_chunks(
    bot_id: str,
    query: str,
    top_k: int = 5,
    similarity_threshold: float = 0.5,
) -> list[dict]:
    """
    Retrieve the most relevant chunks for a query, scoped to a bot.

    Args:
        bot_id:               Which bot's embeddings to search
        query:                The user's message
        top_k:                Max number of results to return
        similarity_threshold: Minimum similarity score (0-1)

    Returns:
        List of chunk dicts sorted by similarity (highest first):
        [{id, category, heading, text, similarity}, ...]
    """
    query_embedding = generate_query_embedding(query)
    items = get_cached_embeddings(bot_id)

    results = []
    for item in items:
        stored = [float(x) for x in item['embedding']]
        score = cosine_similarity(query_embedding, stored)
        if score >= similarity_threshold:
            results.append({
                'id':         item['id'],
                'category':   item.get('category', 'General'),
                'heading':    item.get('heading', ''),
                'text':       item['text'],
                'similarity': score,
            })

    results.sort(key=lambda x: x['similarity'], reverse=True)
    top = results[:top_k]

    print(f"Retrieval: {len(top)}/{len(results)} chunks returned for '{bot_id}' (threshold={similarity_threshold})")
    return top


# ---------------------------------------------------------------------------
# Format for LLM
# ---------------------------------------------------------------------------

def format_context(chunks: list[dict]) -> str:
    """Format retrieved chunks into a context block for the prompt."""
    if not chunks:
        return "No relevant information found."

    parts = [f"[{c['category'].upper()}]\n{c['text']}" for c in chunks]
    return "\n\n---\n\n".join(parts)
