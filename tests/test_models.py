"""
Tests for database models.
"""

import pytest

from src.models.refund import RefundRequest, RefundStatus
from src.models.customer import CustomerProfile
from src.models.conversation import Conversation, Message, MessageRole


class TestRefundRequest:
    """Tests for RefundRequest model."""

    def test_refund_request_repr(self):
        """Test RefundRequest __repr__ method."""
        refund = RefundRequest(
            id="RFR-001",
            order_id="ORD-001",
            customer_id="CUST-123",
            amount=50.0,
            status=RefundStatus.PENDING
        )

        repr_str = repr(refund)

        assert "RefundRequest" in repr_str
        assert "RFR-001" in repr_str
        assert "ORD-001" in repr_str
        assert "pending" in repr_str.lower()

    def test_refund_status_enum_values(self):
        """Test RefundStatus enum values."""
        assert RefundStatus.PENDING == "pending"
        assert RefundStatus.APPROVED == "approved"
        assert RefundStatus.REJECTED == "rejected"
        assert RefundStatus.PROCESSING == "processing"
        assert RefundStatus.COMPLETED == "completed"
        assert RefundStatus.FAILED == "failed"


class TestCustomerProfile:
    """Tests for CustomerProfile model."""

    def test_customer_profile_repr(self):
        """Test CustomerProfile __repr__ method."""
        customer = CustomerProfile(
            id="CUST-123",
            email="user@example.com"
        )

        repr_str = repr(customer)

        assert "CustomerProfile" in repr_str
        assert "CUST-123" in repr_str
        assert "user@example.com" in repr_str


class TestConversation:
    """Tests for Conversation model."""

    def test_conversation_repr(self):
        """Test Conversation __repr__ method."""
        conversation = Conversation(
            id="CONV-001",
            customer_id="CUST-123"
        )

        repr_str = repr(conversation)

        assert "Conversation" in repr_str
        assert "CONV-001" in repr_str
        assert "CUST-123" in repr_str


class TestMessage:
    """Tests for Message model."""

    def test_message_repr(self):
        """Test Message __repr__ method."""
        message = Message(
            id="MSG-001",
            conversation_id="CONV-001",
            role=MessageRole.USER,
            content="Hello"
        )

        repr_str = repr(message)

        assert "Message" in repr_str
        assert "MSG-001" in repr_str
        assert "user" in repr_str.lower()

    def test_message_role_enum_values(self):
        """Test MessageRole enum values."""
        assert MessageRole.USER == "user"
        assert MessageRole.ASSISTANT == "assistant"
        assert MessageRole.SYSTEM == "system"
