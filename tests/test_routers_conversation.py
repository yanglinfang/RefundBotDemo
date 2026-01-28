"""
Tests for Conversation Router.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.routers.conversation import router, ChatRequest, ChatResponse


@pytest.fixture
def app():
    """Create a FastAPI app with the conversation router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


class TestChatRequestValidation:
    """Tests for ChatRequest validation."""

    def test_valid_customer_id(self):
        """Test valid customer ID format."""
        request = ChatRequest(
            message="Hello",
            customer_id="CUST-123"
        )
        assert request.customer_id == "CUST-123"

    def test_valid_email_as_customer_id(self):
        """Test valid email as customer identifier."""
        request = ChatRequest(
            message="Hello",
            customer_id="user@example.com"
        )
        assert request.customer_id == "user@example.com"

    def test_invalid_customer_id_raises_error(self):
        """Test that invalid customer ID raises validation error."""
        with pytest.raises(ValueError):
            ChatRequest(
                message="Hello",
                customer_id="invalid-format"
            )

    def test_message_max_length(self):
        """Test message max length validation."""
        # Should succeed with message under 10000 chars
        request = ChatRequest(
            message="A" * 9999,
            customer_id="CUST-123"
        )
        assert len(request.message) == 9999


class TestChatEndpoint:
    """Tests for /chat endpoint."""

    def test_chat_success(self, client):
        """Test successful chat request."""
        mock_db = AsyncMock()
        mock_service = MagicMock()
        mock_service.process_message = AsyncMock(return_value={
            "conversation_id": "CONV-001",
            "response": "Hello! How can I help you?",
            "refund_initiated": False,
            "refund_id": None,
            "llm_debug": None
        })

        with patch("src.routers.conversation.get_db", return_value=mock_db), \
             patch("src.routers.conversation.ConversationService", return_value=mock_service), \
             patch("src.routers.conversation.limiter.limit", lambda x: lambda f: f):

            response = client.post("/chat", json={
                "message": "Hello",
                "customer_id": "CUST-123"
            })

            assert response.status_code == 200
            data = response.json()
            assert data["conversation_id"] == "CONV-001"
            assert data["response"] == "Hello! How can I help you?"
            assert data["refund_initiated"] is False

    def test_chat_with_conversation_id(self, client):
        """Test chat request with existing conversation."""
        mock_db = AsyncMock()
        mock_service = MagicMock()
        mock_service.process_message = AsyncMock(return_value={
            "conversation_id": "CONV-001",
            "response": "I can help with that.",
            "refund_initiated": False,
            "refund_id": None,
            "llm_debug": None
        })

        with patch("src.routers.conversation.get_db", return_value=mock_db), \
             patch("src.routers.conversation.ConversationService", return_value=mock_service), \
             patch("src.routers.conversation.limiter.limit", lambda x: lambda f: f):

            response = client.post("/chat", json={
                "message": "Can you help?",
                "customer_id": "CUST-123",
                "conversation_id": "CONV-001"
            })

            assert response.status_code == 200
            mock_service.process_message.assert_called_once_with(
                customer_id="CUST-123",
                message="Can you help?",
                conversation_id="CONV-001"
            )

    def test_chat_with_refund_initiated(self, client):
        """Test chat request that initiates a refund."""
        mock_db = AsyncMock()
        mock_service = MagicMock()
        mock_service.process_message = AsyncMock(return_value={
            "conversation_id": "CONV-001",
            "response": "Your refund has been processed.",
            "refund_initiated": True,
            "refund_id": "RFR-001",
            "llm_debug": {"endpoint": "local"}
        })

        with patch("src.routers.conversation.get_db", return_value=mock_db), \
             patch("src.routers.conversation.ConversationService", return_value=mock_service), \
             patch("src.routers.conversation.limiter.limit", lambda x: lambda f: f):

            response = client.post("/chat", json={
                "message": "I want a refund for ORD-001",
                "customer_id": "CUST-123"
            })

            assert response.status_code == 200
            data = response.json()
            assert data["refund_initiated"] is True
            assert data["refund_id"] == "RFR-001"

    def test_chat_service_error(self, client):
        """Test chat request with service error."""
        mock_db = AsyncMock()
        mock_service = MagicMock()
        mock_service.process_message = AsyncMock(
            side_effect=Exception("Service error")
        )

        with patch("src.routers.conversation.get_db", return_value=mock_db), \
             patch("src.routers.conversation.ConversationService", return_value=mock_service), \
             patch("src.routers.conversation.limiter.limit", lambda x: lambda f: f):

            response = client.post("/chat", json={
                "message": "Hello",
                "customer_id": "CUST-123"
            })

            assert response.status_code == 500
            assert "Internal server error" in response.json()["detail"]

    def test_chat_invalid_customer_id(self, client):
        """Test chat request with invalid customer ID."""
        with patch("src.routers.conversation.limiter.limit", lambda x: lambda f: f):
            response = client.post("/chat", json={
                "message": "Hello",
                "customer_id": "invalid"
            })

            assert response.status_code == 422  # Validation error


class TestGetConversationEndpoint:
    """Tests for /conversations/{conversation_id} endpoint."""

    def test_get_conversation_success(self, client):
        """Test successful conversation retrieval."""
        mock_db = AsyncMock()
        mock_service = MagicMock()
        mock_service.get_conversation = AsyncMock(return_value={
            "id": "CONV-001",
            "customer_id": "CUST-123",
            "created_at": "2024-01-01T00:00:00",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"}
            ]
        })

        with patch("src.routers.conversation.get_db", return_value=mock_db), \
             patch("src.routers.conversation.ConversationService", return_value=mock_service):

            response = client.get("/conversations/CONV-001")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "CONV-001"
            assert len(data["messages"]) == 2

    def test_get_conversation_not_found(self, client):
        """Test conversation retrieval when not found."""
        mock_db = AsyncMock()
        mock_service = MagicMock()
        mock_service.get_conversation = AsyncMock(return_value=None)

        with patch("src.routers.conversation.get_db", return_value=mock_db), \
             patch("src.routers.conversation.ConversationService", return_value=mock_service):

            response = client.get("/conversations/CONV-NOTFOUND")

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
