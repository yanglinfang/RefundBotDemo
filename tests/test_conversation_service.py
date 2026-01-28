"""
Tests for Conversation Service.
"""

import pytest
from datetime import datetime
from unittest.mock import patch, AsyncMock, MagicMock

from src.services.conversation_service import ConversationService
from src.models.conversation import Conversation, Message, MessageRole
from src.models.refund import RefundStatus


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    with patch("src.services.conversation_service.LLMClient") as mock:
        client = mock.return_value
        yield client


@pytest.fixture
def mock_refund_service():
    """Create a mock refund service."""
    with patch("src.services.conversation_service.RefundService") as mock:
        service = mock.return_value
        yield service


class TestConversationServiceProcessMessage:
    """Tests for ConversationService.process_message."""

    @pytest.mark.asyncio
    async def test_process_message_general_inquiry_new_conversation(
        self, mock_db, mock_llm_client, mock_refund_service
    ):
        """Test processing a general inquiry with new conversation."""
        mock_conversation = MagicMock()
        mock_conversation.id = "CONV-001"

        mock_llm_client.analyze_refund_intent = AsyncMock(return_value={
            "intent": "general_inquiry",
            "order_id": None,
            "reason": None
        })
        mock_llm_client.generate_response = AsyncMock(
            return_value="Hello! How can I help you today?"
        )
        mock_llm_client.get_last_debug.return_value = {"endpoint": "local"}

        service = ConversationService(mock_db)
        service.llm_client = mock_llm_client
        service.refund_service = mock_refund_service
        service._create_conversation = AsyncMock(return_value=mock_conversation)
        service._add_message = AsyncMock()
        service._get_message_history = AsyncMock(return_value=[])

        result = await service.process_message(
            customer_id="CUST-123",
            message="Hello"
        )

        assert result["conversation_id"] == "CONV-001"
        assert result["response"] == "Hello! How can I help you today?"
        assert result["refund_initiated"] is False
        assert result["refund_id"] is None
        service._create_conversation.assert_called_once_with("CUST-123")
        mock_llm_client.generate_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_message_existing_conversation(
        self, mock_db, mock_llm_client, mock_refund_service
    ):
        """Test processing message with existing conversation."""
        mock_conversation = MagicMock()
        mock_conversation.id = "CONV-001"

        mock_llm_client.analyze_refund_intent = AsyncMock(return_value={
            "intent": "general_inquiry",
            "order_id": None,
            "reason": None
        })
        mock_llm_client.generate_response = AsyncMock(return_value="I can help!")
        mock_llm_client.get_last_debug.return_value = None

        service = ConversationService(mock_db)
        service.llm_client = mock_llm_client
        service.refund_service = mock_refund_service
        service._get_conversation = AsyncMock(return_value=mock_conversation)
        service._add_message = AsyncMock()
        service._get_message_history = AsyncMock(return_value=[
            {"role": "user", "content": "Hello"}
        ])

        result = await service.process_message(
            customer_id="CUST-123",
            message="Can you help?",
            conversation_id="CONV-001"
        )

        assert result["conversation_id"] == "CONV-001"
        service._get_conversation.assert_called_once_with("CONV-001")

    @pytest.mark.asyncio
    async def test_process_message_conversation_not_found(
        self, mock_db, mock_llm_client, mock_refund_service
    ):
        """Test processing message when conversation not found."""
        service = ConversationService(mock_db)
        service.llm_client = mock_llm_client
        service.refund_service = mock_refund_service
        service._get_conversation = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="not found"):
            await service.process_message(
                customer_id="CUST-123",
                message="Hello",
                conversation_id="CONV-NOTFOUND"
            )

    @pytest.mark.asyncio
    async def test_process_message_refund_request_eligible(
        self, mock_db, mock_llm_client, mock_refund_service
    ):
        """Test processing a refund request when eligible."""
        mock_conversation = MagicMock()
        mock_conversation.id = "CONV-001"

        mock_refund = MagicMock()
        mock_refund.id = "RFR-001"
        mock_refund.amount = 79.99

        mock_llm_client.analyze_refund_intent = AsyncMock(return_value={
            "intent": "refund_request",
            "order_id": "ORD-001",
            "reason": "Damaged item"
        })
        mock_llm_client.generate_refund_confirmation = AsyncMock(
            return_value="Your refund of $79.99 has been processed."
        )
        mock_llm_client.get_last_debug.return_value = {"endpoint": "cloud"}

        mock_refund_service.check_refund_eligibility = AsyncMock(return_value={
            "eligible": True,
            "reason": "Order is eligible"
        })
        mock_refund_service.create_refund_request = AsyncMock(return_value=mock_refund)
        mock_refund_service.process_refund = AsyncMock()

        service = ConversationService(mock_db)
        service.llm_client = mock_llm_client
        service.refund_service = mock_refund_service
        service._create_conversation = AsyncMock(return_value=mock_conversation)
        service._add_message = AsyncMock()
        service._get_message_history = AsyncMock(return_value=[])

        result = await service.process_message(
            customer_id="CUST-123",
            message="I want a refund for ORD-001"
        )

        assert result["refund_initiated"] is True
        assert result["refund_id"] == "RFR-001"
        mock_refund_service.create_refund_request.assert_called_once()
        mock_refund_service.process_refund.assert_called_once_with("RFR-001")
        mock_llm_client.generate_refund_confirmation.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_message_refund_request_not_eligible(
        self, mock_db, mock_llm_client, mock_refund_service
    ):
        """Test processing a refund request when not eligible."""
        mock_conversation = MagicMock()
        mock_conversation.id = "CONV-001"

        mock_llm_client.analyze_refund_intent = AsyncMock(return_value={
            "intent": "refund_request",
            "order_id": "ORD-001",
            "reason": "Changed mind"
        })
        mock_llm_client.generate_refund_denial = AsyncMock(
            return_value="Sorry, your order is outside the refund window."
        )
        mock_llm_client.get_last_debug.return_value = None

        mock_refund_service.check_refund_eligibility = AsyncMock(return_value={
            "eligible": False,
            "reason": "Order is outside refund window"
        })

        service = ConversationService(mock_db)
        service.llm_client = mock_llm_client
        service.refund_service = mock_refund_service
        service._create_conversation = AsyncMock(return_value=mock_conversation)
        service._add_message = AsyncMock()
        service._get_message_history = AsyncMock(return_value=[])

        result = await service.process_message(
            customer_id="CUST-123",
            message="Refund ORD-001 please"
        )

        assert result["refund_initiated"] is False
        assert result["refund_id"] is None
        mock_llm_client.generate_refund_denial.assert_called_once()
        mock_refund_service.create_refund_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_message_refund_creation_fails(
        self, mock_db, mock_llm_client, mock_refund_service
    ):
        """Test processing when refund creation fails."""
        mock_conversation = MagicMock()
        mock_conversation.id = "CONV-001"

        mock_llm_client.analyze_refund_intent = AsyncMock(return_value={
            "intent": "refund_request",
            "order_id": "ORD-001",
            "reason": "Damaged"
        })
        mock_llm_client.generate_refund_denial = AsyncMock(
            return_value="Sorry, we couldn't process your refund."
        )
        mock_llm_client.get_last_debug.return_value = None

        mock_refund_service.check_refund_eligibility = AsyncMock(return_value={
            "eligible": True,
            "reason": "Order is eligible"
        })
        mock_refund_service.create_refund_request = AsyncMock(
            side_effect=ValueError("Payment not found")
        )

        service = ConversationService(mock_db)
        service.llm_client = mock_llm_client
        service.refund_service = mock_refund_service
        service._create_conversation = AsyncMock(return_value=mock_conversation)
        service._add_message = AsyncMock()
        service._get_message_history = AsyncMock(return_value=[])

        result = await service.process_message(
            customer_id="CUST-123",
            message="Refund ORD-001"
        )

        assert result["refund_initiated"] is False
        mock_llm_client.generate_refund_denial.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_message_refund_intent_no_order_id(
        self, mock_db, mock_llm_client, mock_refund_service
    ):
        """Test refund request without order ID triggers general response."""
        mock_conversation = MagicMock()
        mock_conversation.id = "CONV-001"

        mock_llm_client.analyze_refund_intent = AsyncMock(return_value={
            "intent": "refund_request",
            "order_id": None,  # No order ID extracted
            "reason": None
        })
        mock_llm_client.generate_response = AsyncMock(
            return_value="I'd be happy to help with your refund. What's your order number?"
        )
        mock_llm_client.get_last_debug.return_value = None

        service = ConversationService(mock_db)
        service.llm_client = mock_llm_client
        service.refund_service = mock_refund_service
        service._create_conversation = AsyncMock(return_value=mock_conversation)
        service._add_message = AsyncMock()
        service._get_message_history = AsyncMock(return_value=[])

        result = await service.process_message(
            customer_id="CUST-123",
            message="I want a refund"
        )

        assert result["refund_initiated"] is False
        mock_llm_client.generate_response.assert_called_once()
        mock_refund_service.check_refund_eligibility.assert_not_called()


class TestConversationServiceGetConversation:
    """Tests for ConversationService.get_conversation."""

    @pytest.mark.asyncio
    async def test_get_conversation_success(self, mock_db):
        """Test successful conversation retrieval."""
        mock_conversation = MagicMock()
        mock_conversation.id = "CONV-001"
        mock_conversation.customer_id = "CUST-123"
        mock_conversation.created_at = datetime(2024, 1, 1, 12, 0, 0)

        service = ConversationService(mock_db)
        service._get_conversation = AsyncMock(return_value=mock_conversation)
        service._get_message_history = AsyncMock(return_value=[
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ])

        result = await service.get_conversation("CONV-001")

        assert result["id"] == "CONV-001"
        assert result["customer_id"] == "CUST-123"
        assert len(result["messages"]) == 2

    @pytest.mark.asyncio
    async def test_get_conversation_not_found(self, mock_db):
        """Test conversation retrieval when not found."""
        service = ConversationService(mock_db)
        service._get_conversation = AsyncMock(return_value=None)

        result = await service.get_conversation("CONV-NOTFOUND")

        assert result is None


class TestConversationServiceHelpers:
    """Tests for ConversationService helper methods."""

    @pytest.mark.asyncio
    async def test_get_conversation_by_id(self, mock_db):
        """Test _get_conversation method."""
        mock_conversation = Conversation(id="CONV-001", customer_id="CUST-123")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_conversation
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = ConversationService(mock_db)
        # Bypass LLM client init
        service.llm_client = MagicMock()
        service.refund_service = MagicMock()

        result = await service._get_conversation("CONV-001")

        assert result == mock_conversation

    @pytest.mark.asyncio
    async def test_create_conversation(self, mock_db):
        """Test _create_conversation method."""
        service = ConversationService(mock_db)
        service.llm_client = MagicMock()
        service.refund_service = MagicMock()

        result = await service._create_conversation("CUST-123")

        assert result.customer_id == "CUST-123"
        assert result.id.startswith("CONV-")
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_add_message(self, mock_db):
        """Test _add_message method."""
        service = ConversationService(mock_db)
        service.llm_client = MagicMock()
        service.refund_service = MagicMock()

        result = await service._add_message(
            conversation_id="CONV-001",
            role=MessageRole.USER,
            content="Hello"
        )

        assert result.conversation_id == "CONV-001"
        assert result.role == MessageRole.USER
        assert result.content == "Hello"
        assert result.id.startswith("MSG-")
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_message_history(self, mock_db):
        """Test _get_message_history method."""
        mock_messages = [
            MagicMock(role=MessageRole.USER, content="Hello"),
            MagicMock(role=MessageRole.ASSISTANT, content="Hi there!")
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_messages
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = ConversationService(mock_db)
        service.llm_client = MagicMock()
        service.refund_service = MagicMock()

        result = await service._get_message_history("CONV-001")

        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Hello"
        assert result[1]["role"] == "assistant"
