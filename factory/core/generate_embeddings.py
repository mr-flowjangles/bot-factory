"""
Embedding Generator (Universal)

Reads a bot's YAML data (local or S3), generates OpenAI embeddings,
and stores them in the ChatbotRAG DynamoDB table with a bot_id field.

Kill-and-fill scoped to bot_id — other bots are untouched.

Data source is controlled by the DATA_SOURCE env var:
  DATA_SOURCE=local  → reads from bots/{bot_id}/data/ (default for local dev)
  DATA_SOURCE=s3     → reads from S3 bucket (required for Lambda)

S3 bucket name is set via BOT_DATA_BUCKET env var.

─────────────────────────────────────────────────────────
LOCAL USAGE
─────────────────────────────────────────────────────────
    python -m ai.factory.core.generate_embeddings guitar
    python -m ai.factory.core.generate_embeddings guitar --force

─────────────────────────────────────────────────────────
LAMBDA INVOCATION (from AWS Console or CLI)
─────────────────────────────────────────────────────────
Invoke the Lambda with a JSON payload:

    { "bot_id": "guitar" }
    { "bot_id": "guitar", "force": true }

Lambda env vars required:
    DATA_SOURCE=s3
    BOT_DATA_BUCKET=your-bucket-name
    OPENAI_API_KEY=sk-...
"""
import os
import sys
import json
import yaml
from decimal import Decimal
from collections import Counter
from .connections import get_rag_table, get_openai_client


# ---------------------------------------------------------------------------
# Data loading — local or S3
# ---------------------------------------------------------------------------

def load_bot_data_local(bot_id: str) -> list[dict]:
    """Load and chunk YAML files from local bots/{bot_id}/data/ directory."""
    from .chunker import load_bot_data
    return load_bot_data(bot_id)


def load_bot_data_s3(bot_id: str, bucket: str) -> list[dict]:
    """
    Load and chunk YAML files from S3.

    Expects files at: s3://{bucket}/bots/{bot_id}/data/*.yml

    Each YAML file should have the same structure as local data files.
    Passes raw YAML content through the same chunker logic.
    """
    from .chunker import chunk_yaml_content  # see note below

    s3 = boto3.client('s3')
    prefix = f"bots/{bot_id}/data/"

    paginator = s3.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=bucket, Prefix=prefix)

    all_chunks = []
    file_count = 0

    for page in pages:
        for obj in page.get('Contents', []):
            key = obj['Key']
            if not key.endswith(('.yml', '.yaml')):
                continue

            print(f"  Loading s3://{bucket}/{key}")
            response = s3.get_object(Bucket=bucket, Key=key)
            raw = response['Body'].read().decode('utf-8')
            data = yaml.safe_load(raw)

            chunks = chunk_yaml_content(data, bot_id=bot_id)
            all_chunks.extend(chunks)
            file_count += 1

    print(f"  Loaded {file_count} files → {len(all_chunks)} chunks from S3")
    return all_chunks


def load_bot_data(bot_id: str) -> list[dict]:
    """Route to local or S3 loader based on DATA_SOURCE env var."""
    source = os.getenv('DATA_SOURCE', 'local').lower()

    if source == 's3':
        bucket = os.getenv('BOT_DATA_BUCKET')
        if not bucket:
            raise EnvironmentError("BOT_DATA_BUCKET must be set when DATA_SOURCE=s3")
        return load_bot_data_s3(bot_id, bucket)

    return load_bot_data_local(bot_id)


# ---------------------------------------------------------------------------
# Embedding generation
# ---------------------------------------------------------------------------

def generate_embedding(text: str) -> list[float]:
    client = get_openai_client()
    response = client.embeddings.create(model="text-embedding-3-small", input=text)
    return response.data[0].embedding


def generate_all_embeddings(chunks: list[dict]) -> list[dict]:
    print(f"\nGenerating embeddings ({len(chunks)} chunks)...")
    for idx, chunk in enumerate(chunks, 1):
        print(f"  [{idx}/{len(chunks)}] {chunk['category']}: {chunk['id']}")
        try:
            chunk['embedding'] = generate_embedding(chunk['text'])
        except Exception as e:
            raise RuntimeError(f"Embedding failed for '{chunk['id']}': {e}") from e
    print(f"  Done — {len(chunks)} embeddings generated")
    return chunks


# ---------------------------------------------------------------------------
# DynamoDB operations
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# DynamoDB operations
# ---------------------------------------------------------------------------

from boto3.dynamodb.conditions import Attr


def bot_embeddings_exist(bot_id: str) -> bool:
    """Check if this bot already has any embeddings stored."""
    table = get_rag_table()
    response = table.scan(FilterExpression=Attr('bot_id').eq(bot_id), Limit=1)
    return bool(response.get('Items'))


def clear_bot_embeddings(bot_id: str):
    """Delete all existing embeddings for this bot. Other bots untouched."""
    print(f"\nClearing existing embeddings for bot '{bot_id}'...")
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

    if not items:
        print(f"  No existing embeddings found for '{bot_id}'")
        return

    with table.batch_writer() as batch:
        for item in items:
            batch.delete_item(Key={'id': item['id']})

    print(f"  Deleted {len(items)} existing embeddings")


def store_embeddings(chunks: list[dict]):
    """Write chunks with embeddings to DynamoDB."""
    print(f"\nStoring {len(chunks)} embeddings in ChatbotRAG...")
    table = get_rag_table()
    with table.batch_writer() as batch:
        for chunk in chunks:
            batch.put_item(Item={
                'id':        f"{chunk['bot_id']}_{chunk['id']}",
                'bot_id':    chunk['bot_id'],
                'category':  chunk['category'],
                'heading':   chunk['heading'],
                'text':      chunk['text'],
                'embedding': [Decimal(str(x)) for x in chunk['embedding']],
            })
    print(f"  Done — {len(chunks)} embeddings stored")


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------

def run_pipeline(bot_id: str, force: bool = False) -> dict:
    """
    Full pipeline: load data → generate embeddings → store in DynamoDB.

    Returns a summary dict (used by both CLI and Lambda handler).
    """
    print("\n" + "=" * 60)
    print(f"  Bot Factory — Embedding Generator")
    print(f"  Bot:    {bot_id}")
    print(f"  Source: {os.getenv('DATA_SOURCE', 'local').upper()}")
    print("=" * 60 + "\n")

    # Check for existing embeddings
    if bot_embeddings_exist(bot_id) and not force:
        # In Lambda context there's no stdin — force must be explicit
        if not sys.stdin.isatty():
            return {
                'status': 'skipped',
                'message': f"Embeddings already exist for '{bot_id}'. Pass force=true to regenerate.",
            }
        answer = input(f"Embeddings already exist for '{bot_id}'. Regenerate? (y/n): ").strip().lower()
        if answer != 'y':
            print("  Skipping — existing embeddings unchanged.")
            return {'status': 'skipped', 'message': 'User declined regeneration'}

    # Load data
    chunks = load_bot_data(bot_id)
    if not chunks:
        raise ValueError(f"No data found for bot '{bot_id}'")

    # Generate embeddings
    chunks = generate_all_embeddings(chunks)

    # Kill and fill
    clear_bot_embeddings(bot_id)
    store_embeddings(chunks)

    # Summary
    cats = Counter(c['category'] for c in chunks)
    summary = {
        'status': 'success',
        'bot_id': bot_id,
        'total_embeddings': len(chunks),
        'by_category': dict(cats),
    }

    print("\n" + "=" * 60)
    print(f"  Complete! {len(chunks)} embeddings stored for '{bot_id}'")
    for cat, count in cats.most_common():
        print(f"    {cat}: {count}")
    print("=" * 60 + "\n")

    return summary


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------

def lambda_handler(event, context):
    """
    AWS Lambda entry point.

    Expected event payload:
        { "bot_id": "guitar" }
        { "bot_id": "guitar", "force": true }

    Required Lambda env vars:
        DATA_SOURCE=s3
        BOT_DATA_BUCKET=your-s3-bucket
        OPENAI_API_KEY=sk-...
    """
    try:
        bot_id = event.get('bot_id')
        if not bot_id:
            return {'statusCode': 400, 'body': json.dumps({'error': 'bot_id is required'})}

        force = bool(event.get('force', False))
        result = run_pipeline(bot_id, force=force)

        return {'statusCode': 200, 'body': json.dumps(result)}

    except Exception as e:
        print(f"ERROR: {e}")
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python -m ai.factory.core.generate_embeddings <bot_id> [--force]")
        print("Example: python -m ai.factory.core.generate_embeddings guitar --force")
        sys.exit(1)

    bot_id = sys.argv[1]
    force = '--force' in sys.argv

    try:
        run_pipeline(bot_id, force=force)
    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
