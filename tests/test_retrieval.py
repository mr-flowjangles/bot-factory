"""
Tests for retrieval module — proves embeddings are always fresh from DynamoDB.

Requires: LocalStack running (make up).
"""

from unittest.mock import patch
from tests.conftest import TEST_BOT_ID, store_test_embedding
from factory.core.retrieval import get_embeddings, retrieve_relevant_chunks


class TestGetEmbeddings:
    """Verify get_embeddings always reads fresh from DynamoDB (no stale cache)."""

    def test_returns_stored_items(self, dynamodb_table):
        store_test_embedding(dynamodb_table, "item-1", text="guitar basics")
        store_test_embedding(dynamodb_table, "item-2", text="chord theory")

        items = get_embeddings(TEST_BOT_ID)
        pks = {item["pk"] for item in items}

        assert f"{TEST_BOT_ID}_item-1" in pks
        assert f"{TEST_BOT_ID}_item-2" in pks

    def test_returns_empty_for_unknown_bot(self):
        items = get_embeddings("nonexistent-bot-xyz")
        assert items == []

    def test_immediately_sees_new_embeddings(self, dynamodb_table):
        """The key test: new items are visible on the very next call with no cache busting."""
        store_test_embedding(dynamodb_table, "item-1")
        first_call = get_embeddings(TEST_BOT_ID)
        assert len(first_call) == 1

        # Add another embedding (simulates what self-heal does)
        store_test_embedding(dynamodb_table, "item-2")
        second_call = get_embeddings(TEST_BOT_ID)
        assert len(second_call) == 2

    def test_immediately_sees_deleted_embeddings(self, dynamodb_table):
        """Deletions are also visible immediately (kill-and-fill re-embed)."""
        store_test_embedding(dynamodb_table, "item-1")
        store_test_embedding(dynamodb_table, "item-2")
        assert len(get_embeddings(TEST_BOT_ID)) == 2

        dynamodb_table.delete_item(Key={"pk": f"{TEST_BOT_ID}_item-1"})
        assert len(get_embeddings(TEST_BOT_ID)) == 1


class TestRetrieveRelevantChunks:
    """Verify similarity search filtering and ranking."""

    @patch("factory.core.retrieval.generate_query_embedding")
    def test_filters_below_threshold(self, mock_embed, dynamodb_table):
        # Store two items with known embedding values
        store_test_embedding(dynamodb_table, "item-1", text="relevant", embedding_value=0.9)
        store_test_embedding(dynamodb_table, "item-2", text="irrelevant", embedding_value=0.1)

        # Query embedding that's similar to item-1 (all 0.9s)
        mock_embed.return_value = [0.9] * 1024

        results = retrieve_relevant_chunks(
            bot_id=TEST_BOT_ID,
            query="test query",
            top_k=10,
            similarity_threshold=0.5,
        )

        # item-1 (0.9 vs 0.9 = high similarity) should pass
        # item-2 (0.1 vs 0.9 = low similarity) should be filtered out
        headings = [r["heading"] for r in results]
        assert len(results) >= 1
        assert results[0]["similarity"] >= 0.5

    @patch("factory.core.retrieval.generate_query_embedding")
    def test_respects_top_k(self, mock_embed, dynamodb_table):
        # Store 5 items all with same embedding
        for i in range(5):
            store_test_embedding(dynamodb_table, f"item-{i}", embedding_value=0.5)

        mock_embed.return_value = [0.5] * 1024

        results = retrieve_relevant_chunks(
            bot_id=TEST_BOT_ID,
            query="test",
            top_k=2,
            similarity_threshold=0.0,
        )
        assert len(results) == 2

    @patch("factory.core.retrieval.generate_query_embedding")
    def test_results_sorted_by_similarity_descending(self, mock_embed, dynamodb_table):
        store_test_embedding(dynamodb_table, "low", embedding_value=0.1)
        store_test_embedding(dynamodb_table, "mid", embedding_value=0.5)
        store_test_embedding(dynamodb_table, "high", embedding_value=0.9)

        mock_embed.return_value = [0.9] * 1024

        results = retrieve_relevant_chunks(
            bot_id=TEST_BOT_ID,
            query="test",
            top_k=10,
            similarity_threshold=0.0,
        )

        similarities = [r["similarity"] for r in results]
        assert similarities == sorted(similarities, reverse=True)
