"""
Shared Connections

Central place for all client initialization.
Used by retriever.py, generate_embeddings.py, responder.py, and chatbot.py.

Clients are lazy-initialized and reused across warm Lambda invocations.
"""
import os
import boto3
from openai import OpenAI


# ---------------------------------------------------------------------------
# DynamoDB
# ---------------------------------------------------------------------------

_dynamodb = None


def get_dynamodb():
    """Lazy-init DynamoDB resource. Works with LocalStack or AWS."""
    global _dynamodb
    if _dynamodb is not None:
        return _dynamodb

    endpoint_url = os.getenv('AWS_ENDPOINT_URL', '')
    if endpoint_url:
        _dynamodb = boto3.resource(
            'dynamodb',
            endpoint_url=endpoint_url,
            region_name=os.getenv('AWS_REGION', 'us-east-1'),
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID', 'test'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY', 'test'),
        )
    else:
        _dynamodb = boto3.resource(
            'dynamodb',
            region_name=os.getenv('AWS_REGION', 'us-east-1'),
        )

    return _dynamodb


def get_rag_table():
    """Return the ChatbotRAG DynamoDB table."""
    return get_dynamodb().Table('ChatbotRAG')


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------

_openai_client = None


def get_openai_client() -> OpenAI:
    """Lazy-init OpenAI client."""
    global _openai_client
    if _openai_client is None:
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise EnvironmentError("OPENAI_API_KEY environment variable not set")
        _openai_client = OpenAI(api_key=api_key)
    return _openai_client


# ---------------------------------------------------------------------------
# Bedrock
# ---------------------------------------------------------------------------

_bedrock_client = None


def get_bedrock_client():
    """
    Lazy-init Bedrock runtime client.
    Local dev: credentials come from env vars (mounted via docker-compose).
    Lambda:    IAM role provides credentials automatically.
    """
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = boto3.client(
            'bedrock-runtime',
            region_name=os.getenv('AWS_REGION', 'us-east-1'),
        )
    return _bedrock_client


# ---------------------------------------------------------------------------
# S3
# ---------------------------------------------------------------------------

_s3_client = None


def get_s3_client():
    """Lazy-init S3 client."""
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client('s3', region_name=os.getenv('AWS_REGION', 'us-east-1'))
    return _s3_client
