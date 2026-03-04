#!/usr/bin/env python3
"""
Test the chat pipeline directly (no HTTP layer).

Usage:
    python scripts/test_chat.py
    python scripts/test_chat.py --bot fret-detective --message "What is a G chord?"

Requirements:
    - LocalStack running (for S3 prompt loading)
    - AWS credentials configured (for Bedrock)
    - Run from project root
"""

import sys
import os
import argparse

# Add project root to path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set environment for local testing
os.environ.setdefault("APP_ENV", "local")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("BOT_DATA_BUCKET", "bot-factory-data")
os.environ.setdefault("LOCALSTACK_ENDPOINT", "http://localhost:4566")

from factory.core.chatbot import generate_response, generate_response_stream


def test_chat(bot_id: str, message: str, stream: bool = False):
    """Run a single chat query and print the result."""
    print(f"\n{'='*60}")
    print(f"Bot:     {bot_id}")
    print(f"Message: {message}")
    print(f"Stream:  {stream}")
    print(f"{'='*60}\n")

    try:
        if stream:
            print("Response: ", end="", flush=True)
            for chunk in generate_response_stream(
                bot_id=bot_id,
                user_message=message,
                top_k=5,
                similarity_threshold=0.3,
                conversation_history=[],
            ):
                print(chunk, end="", flush=True)
            print("\n")
        else:
            result = generate_response(
                bot_id=bot_id,
                user_message=message,
                top_k=5,
                similarity_threshold=0.3,
                conversation_history=[],
            )
            print(f"Response:\n{result['response']}\n")
            print(f"Sources: {result['sources']}")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Test the chat pipeline")
    parser.add_argument("--bot", default="fret-detective", help="Bot ID to test")
    parser.add_argument("--message", default="What is a G chord?", help="Message to send")
    parser.add_argument("--stream", action="store_true", help="Use streaming response")
    args = parser.parse_args()

    test_chat(args.bot, args.message, args.stream)


if __name__ == "__main__":
    main()