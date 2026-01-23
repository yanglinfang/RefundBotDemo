"""
Conversation Service - LLM-powered chat interactions
"""

import uuid
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.conversation import Conversation, Message, MessageRole
from src.services.llm_client import LLMClient
from src.services.refund_service import RefundService

logger = logging.getLogger(__name__)


class ConversationService:
    """Service for handling LLM-powered conversations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm_client = LLMClient()
        self.refund_service = RefundService(db)

    async def process_message(
        self,
        customer_id: str,
        message: str,
        conversation_id: Optional[str] = None
    ) -> dict:
        """
        Process a user message and generate a response.

        The LLM analyzes the message to determine intent and
        can trigger refund operations when appropriate.
        """
        # Get or create conversation
        if conversation_id:
            conversation = await self._get_conversation(conversation_id)
            if not conversation:
                raise ValueError(f"Conversation {conversation_id} not found")
        else:
            conversation = await self._create_conversation(customer_id)

        # Store user message
        await self._add_message(conversation.id, MessageRole.USER, message)

        # Get conversation history for context
        history = await self._get_message_history(conversation.id)

        # Analyze intent with LLM
        intent_result = await self.llm_client.analyze_refund_intent(
            message=message,
            conversation_history=history,
            customer_id=customer_id
        )

        # Handle refund intent
        refund_initiated = False
        refund_id = None

        if intent_result.get("intent") == "refund_request" and intent_result.get("order_id"):
            order_id = intent_result["order_id"]

            # Check eligibility
            eligibility = await self.refund_service.check_refund_eligibility(
                order_id=order_id,
                customer_id=customer_id
            )

            if eligibility["eligible"]:
                try:
                    # Create and process refund
                    refund = await self.refund_service.create_refund_request(
                        order_id=order_id,
                        customer_id=customer_id,
                        reason=intent_result.get("reason", "Customer requested refund")
                    )
                    await self.refund_service.process_refund(refund.id)
                    refund_initiated = True
                    refund_id = refund.id

                    response = await self.llm_client.generate_refund_confirmation(
                        order_id=order_id,
                        amount=refund.amount,
                        refund_id=refund.id,
                        original_message=message,
                    )
                except ValueError as e:
                    response = await self.llm_client.generate_refund_denial(
                        order_id=order_id,
                        reason=str(e),
                        original_message=message,
                    )
            else:
                response = await self.llm_client.generate_refund_denial(
                    order_id=order_id,
                    reason=eligibility["reason"],
                    original_message=message,
                )
        else:
            # Generate general response
            response = await self.llm_client.generate_response(
                message=message,
                conversation_history=history
            )

        # Store assistant response
        await self._add_message(conversation.id, MessageRole.ASSISTANT, response)

        return {
            "conversation_id": conversation.id,
            "response": response,
            "refund_initiated": refund_initiated,
            "refund_id": refund_id,
            "llm_debug": self.llm_client.get_last_debug(),
        }

    async def get_conversation(self, conversation_id: str) -> Optional[dict]:
        """Get conversation with messages."""
        conversation = await self._get_conversation(conversation_id)
        if not conversation:
            return None

        messages = await self._get_message_history(conversation_id)

        return {
            "id": conversation.id,
            "customer_id": conversation.customer_id,
            "created_at": conversation.created_at.isoformat(),
            "messages": messages
        }

    async def _get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get conversation by ID."""
        result = await self.db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        return result.scalar_one_or_none()

    async def _create_conversation(self, customer_id: str) -> Conversation:
        """Create a new conversation."""
        conversation = Conversation(
            id=f"CONV-{uuid.uuid4().hex[:8].upper()}",
            customer_id=customer_id
        )
        self.db.add(conversation)
        await self.db.commit()
        await self.db.refresh(conversation)

        logger.info(f"Created conversation {conversation.id} for customer {customer_id}")

        return conversation

    async def _add_message(
        self,
        conversation_id: str,
        role: MessageRole,
        content: str
    ) -> Message:
        """Add a message to a conversation."""
        message = Message(
            id=f"MSG-{uuid.uuid4().hex[:8].upper()}",
            conversation_id=conversation_id,
            role=role,
            content=content
        )
        self.db.add(message)
        await self.db.commit()
        return message

    async def _get_message_history(self, conversation_id: str) -> list[dict]:
        """Get message history for a conversation."""
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        messages = result.scalars().all()

        return [
            {
                "role": msg.role.value,
                "content": msg.content
            }
            for msg in messages
        ]
