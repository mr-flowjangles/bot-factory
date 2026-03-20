"""
Tests for self-heal pipeline — proves healed content is immediately retrievable.

Requires: LocalStack running (make up).
Bedrock calls are mocked.
"""

from unittest.mock import patch, MagicMock
from decimal import Decimal
from tests.conftest import TEST_BOT_ID, store_test_embedding, make_embedding
from factory.core.retrieval import get_embeddings, retrieve_relevant_chunks
from factory.core.self_heal import _duplicate_check, _slugify


TEST_CONFIG = {
    "bot": {
        "id": TEST_BOT_ID,
        "name": "Test Bot",
        "personality": "helpful",
        "boundaries": {"discuss_testing": True},
        "agentic": {
            "self_heal": True,
            "boundary_check": True,
            "confidence_threshold": 0.5,
        },
    }
}


class TestSelfHealIntegration:
    """End-to-end: self-heal stores embedding, next retrieval sees it immediately."""

    @patch("factory.core.self_heal._s3_key_exists", return_value=False)
    @patch("factory.core.self_heal._upload_to_s3")
    @patch("factory.core.self_heal._llm_call")
    @patch("factory.core.self_heal.generate_query_embedding")
    def test_healed_content_immediately_retrievable(
        self, mock_query_embed, mock_llm, mock_upload, mock_s3_exists, dynamodb_table
    ):
        """The critical test: after self-heal runs, the very next get_embeddings call sees the new item."""
        from factory.core.self_heal import run_self_heal

        # Before self-heal: no embeddings for test bot
        assert len(get_embeddings(TEST_BOT_ID)) == 0

        # Mock boundary check → in bounds
        # Mock YML generation → valid YML
        # Mock validation → pass
        mock_llm.side_effect = [
            "yes — this is within the testing domain",  # boundary check
            (  # YML generation
                "entries:\n"
                "  - id: self-heal-test-question\n"
                "    category: Test\n"
                "    heading: Test Answer\n"
                "    content: This is the answer to the test question.\n"
                "    search_terms: test question answer\n"
            ),
            "pass — content is accurate and relevant",  # validation
        ]
        # Mock duplicate check embedding (returns no match)
        mock_query_embed.return_value = [0.0] * 1024

        # Mock the Bedrock embedding call in generate_embeddings
        with patch("factory.core.generate_embeddings.generate_embedding") as mock_gen_embed:
            mock_gen_embed.return_value = [0.5] * 1024

            run_self_heal(TEST_BOT_ID, "what is a test question?", TEST_CONFIG)

        # After self-heal: embedding is immediately visible
        items = get_embeddings(TEST_BOT_ID)
        assert len(items) == 1
        assert items[0]["heading"] == "Test Answer"

    @patch("factory.core.self_heal._s3_key_exists", return_value=False)
    @patch("factory.core.self_heal._upload_to_s3")
    @patch("factory.core.self_heal._llm_call")
    @patch("factory.core.self_heal.generate_query_embedding")
    @patch("factory.core.generate_embeddings.generate_embedding")
    def test_healed_content_found_by_similarity_search(
        self, mock_gen_embed, mock_query_embed, mock_llm, mock_upload, mock_s3_exists, dynamodb_table
    ):
        """After self-heal, retrieve_relevant_chunks finds the new content."""
        from factory.core.self_heal import run_self_heal

        mock_llm.side_effect = [
            "yes — in bounds",
            (
                "entries:\n"
                "  - id: self-heal-drop-d\n"
                "    category: Guitar\n"
                "    heading: Drop D Tuning\n"
                "    content: Drop D tuning lowers the 6th string to D.\n"
                "    search_terms: drop d tuning alternate\n"
            ),
            "pass — accurate",
        ]
        # Duplicate check: no similar content
        mock_query_embed.return_value = [0.0] * 1024
        # Self-heal stores embedding as [0.8, 0.8, ...]
        mock_gen_embed.return_value = [0.8] * 1024

        run_self_heal(TEST_BOT_ID, "what is drop d tuning?", TEST_CONFIG)

        # Now search with a similar embedding
        with patch("factory.core.retrieval.generate_query_embedding") as mock_search_embed:
            mock_search_embed.return_value = [0.8] * 1024

            results = retrieve_relevant_chunks(
                bot_id=TEST_BOT_ID,
                query="drop d tuning",
                top_k=5,
                similarity_threshold=0.3,
            )

        assert len(results) == 1
        assert results[0]["heading"] == "Drop D Tuning"
        assert results[0]["similarity"] > 0.9


class TestDuplicateCheck:
    """Verify duplicate detection prevents redundant self-heal."""

    def test_detects_duplicate_when_similar_exists(self, dynamodb_table):
        store_test_embedding(dynamodb_table, "existing-item", embedding_value=0.8)

        with patch("factory.core.self_heal.generate_query_embedding") as mock_embed:
            # Query embedding very similar to stored one
            mock_embed.return_value = [0.8] * 1024
            assert _duplicate_check(TEST_BOT_ID, "similar question") is True

    def test_no_duplicate_when_content_differs(self, dynamodb_table):
        # Store embedding that's mostly zeros with a spike at the start
        from decimal import Decimal
        embedding_a = [Decimal("1.0")] + [Decimal("0.0")] * 1023
        dynamodb_table.put_item(Item={
            "pk": f"{TEST_BOT_ID}_existing-item",
            "bot_id": TEST_BOT_ID,
            "text": "existing content",
            "heading": "Existing",
            "category": "Test",
            "embedding": embedding_a,
        })

        with patch("factory.core.self_heal.generate_query_embedding") as mock_embed:
            # Query embedding orthogonal to stored one (spike at the end)
            mock_embed.return_value = [0.0] * 1023 + [1.0]
            assert _duplicate_check(TEST_BOT_ID, "completely different") is False


class TestSlugify:
    def test_basic_slugify(self):
        assert _slugify("What is Drop D tuning?") == "what-is-drop-d-tuning"

    def test_truncates_long_slugs(self):
        long_q = "a" * 100
        assert len(_slugify(long_q)) <= 60

    def test_strips_special_characters(self):
        assert _slugify("How do I play C#/Db?") == "how-do-i-play-cdb"
