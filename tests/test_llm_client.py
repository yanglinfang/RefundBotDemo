"""
Tests for LLM Client business logic.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from src.services.llm_client import LLMClient


class TestLocalIntentAnalysis:
    """Tests for _local_intent_analysis method."""

    def test_refund_intent_with_order_id(self):
        """Test detection of refund intent with order ID."""
        with patch("src.services.llm_client.get_llm_router"):
            client = LLMClient()

        result = client._local_intent_analysis("I want a refund for ORD-ABC123")

        assert result["intent"] == "refund_request"
        assert result["order_id"] == "ORD-ABC123"
        assert result["reason"] is not None

    def test_refund_intent_various_keywords(self):
        """Test detection with various refund keywords."""
        with patch("src.services.llm_client.get_llm_router"):
            client = LLMClient()

        keywords_messages = [
            ("I want to return this item", "return"),
            ("Can I get my money back?", "money back"),
            ("Please cancel order ORD-001", "cancel order"),
            ("I need a refund", "refund"),
        ]

        for message, _ in keywords_messages:
            result = client._local_intent_analysis(message)
            assert result["intent"] == "refund_request", f"Failed for: {message}"

    def test_general_inquiry_no_refund_keywords(self):
        """Test detection of general inquiry without refund keywords."""
        with patch("src.services.llm_client.get_llm_router"):
            client = LLMClient()

        result = client._local_intent_analysis("What is your shipping policy?")

        assert result["intent"] == "general_inquiry"
        assert result["order_id"] is None
        assert result["reason"] is None

    def test_order_id_extraction_case_insensitive(self):
        """Test order ID extraction is case insensitive."""
        with patch("src.services.llm_client.get_llm_router"):
            client = LLMClient()

        result = client._local_intent_analysis("Refund for ord-abc123 please")

        assert result["order_id"] == "ORD-ABC123"

    def test_reason_extraction_because(self):
        """Test reason extraction with 'because' pattern."""
        with patch("src.services.llm_client.get_llm_router"):
            client = LLMClient()

        result = client._local_intent_analysis(
            "I want a refund because the item was damaged"
        )

        assert result["intent"] == "refund_request"
        assert "damaged" in result["reason"].lower()

    def test_reason_extraction_due_to(self):
        """Test reason extraction with 'due to' pattern."""
        with patch("src.services.llm_client.get_llm_router"):
            client = LLMClient()

        result = client._local_intent_analysis(
            "Refund due to wrong size received"
        )

        assert result["intent"] == "refund_request"
        assert "wrong size" in result["reason"].lower()

    def test_default_reason_when_not_specified(self):
        """Test default reason when no specific reason given."""
        with patch("src.services.llm_client.get_llm_router"):
            client = LLMClient()

        result = client._local_intent_analysis("I want a refund")

        assert result["intent"] == "refund_request"
        assert result["reason"] == "Customer requested refund"

    def test_no_order_id_in_message(self):
        """Test when no order ID is present."""
        with patch("src.services.llm_client.get_llm_router"):
            client = LLMClient()

        result = client._local_intent_analysis("I need a refund for my recent order")

        assert result["intent"] == "refund_request"
        assert result["order_id"] is None


class TestCleanResponse:
    """Tests for _clean_response static method."""

    def test_removes_here_is_prefix(self):
        """Test removal of 'here is' prefix."""
        result = LLMClient._clean_response(
            "Here's a response: Your refund has been processed."
        )
        assert result == "Your refund has been processed."

    def test_removes_here_is_the_prefix(self):
        """Test removal of 'here is the' prefix with 'response' keyword."""
        result = LLMClient._clean_response(
            "Here is the response: Your order is complete."
        )
        assert result == "Your order is complete."

    def test_removes_dear_salutation(self):
        """Test removal of 'Dear' salutation."""
        result = LLMClient._clean_response(
            "Dear Customer, Your refund is ready."
        )
        assert result == "Your refund is ready."

    def test_removes_your_name_placeholder(self):
        """Test removal of [Your Name] placeholder."""
        result = LLMClient._clean_response(
            "Thank you for contacting us. [Your Name]"
        )
        assert result == "Thank you for contacting us."

    def test_clean_normal_response(self):
        """Test that normal responses are not modified."""
        original = "Your refund of $50.00 has been processed."
        result = LLMClient._clean_response(original)
        assert result == original

    def test_combines_multiple_cleanups(self):
        """Test that multiple patterns are cleaned."""
        result = LLMClient._clean_response(
            "Here's a response: Dear Customer: Your order is ready. [Your Name]"
        )
        assert "[Your Name]" not in result
        assert "Dear Customer" not in result
        assert "Here's" not in result


class TestComputeComplexityScore:
    """Tests for _compute_complexity_score static method."""

    def test_simple_message(self):
        """Test complexity score for simple message."""
        result = LLMClient._compute_complexity_score("Hello world")
        assert result == 2  # 2 unique words

    def test_repeated_words(self):
        """Test that repeated words don't increase score."""
        result = LLMClient._compute_complexity_score("hello hello hello world world")
        assert result == 2  # 2 unique words

    def test_complex_message(self):
        """Test complexity score for complex message."""
        result = LLMClient._compute_complexity_score(
            "I would like to request a full refund for my recent purchase"
        )
        # Words: i, would, like, to, request, a, full, refund, for, my, recent, purchase
        assert result == 12  # 12 unique words

    def test_empty_message(self):
        """Test complexity score for empty message."""
        result = LLMClient._compute_complexity_score("")
        assert result == 0

    def test_case_insensitive(self):
        """Test that complexity score is case insensitive."""
        result = LLMClient._compute_complexity_score("Hello HELLO hello World WORLD")
        assert result == 2  # 2 unique words (hello, world)


class TestLatestUserMessage:
    """Tests for _latest_user_message static method."""

    def test_finds_latest_user_message(self):
        """Test finding the latest user message."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "First message"},
            {"role": "assistant", "content": "First response"},
            {"role": "user", "content": "Second message"},
        ]
        result = LLMClient._latest_user_message(messages)
        assert result == "Second message"

    def test_no_user_messages(self):
        """Test when there are no user messages."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "assistant", "content": "Hello!"},
        ]
        result = LLMClient._latest_user_message(messages)
        assert result is None

    def test_empty_messages(self):
        """Test with empty message list."""
        result = LLMClient._latest_user_message([])
        assert result is None

    def test_single_user_message(self):
        """Test with single user message."""
        messages = [
            {"role": "user", "content": "Only message"},
        ]
        result = LLMClient._latest_user_message(messages)
        assert result == "Only message"


class TestAnalyzeRefundIntent:
    """Tests for analyze_refund_intent async method."""

    @pytest.mark.asyncio
    async def test_analyze_refund_intent_calls_local_analysis(self):
        """Test that analyze_refund_intent uses local analysis."""
        with patch("src.services.llm_client.get_llm_router"):
            client = LLMClient()

        result = await client.analyze_refund_intent(
            message="I want a refund for ORD-123",
            conversation_history=[],
            customer_id="CUST-001"
        )

        assert result["intent"] == "refund_request"
        assert result["order_id"] == "ORD-123"


class TestGetLastDebug:
    """Tests for get_last_debug method."""

    def test_get_last_debug_initially_none(self):
        """Test that last debug is None initially."""
        with patch("src.services.llm_client.get_llm_router"):
            client = LLMClient()

        assert client.get_last_debug() is None

    def test_get_last_debug_returns_stored_value(self):
        """Test that get_last_debug returns stored debug info."""
        with patch("src.services.llm_client.get_llm_router"):
            client = LLMClient()

        client._last_debug = {"endpoint": "test", "latency_ms": 100}
        result = client.get_last_debug()

        assert result["endpoint"] == "test"
        assert result["latency_ms"] == 100
