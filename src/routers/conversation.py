"""
Conversation API Router for LLM-powered interactions
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.services.conversation_service import ConversationService
from src.limiter import limiter
from src.utils.customer_identity import is_customer_id, is_email

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    """Schema for chat request."""
    message: str = Field(..., max_length=10000)
    conversation_id: Optional[str] = None
    customer_id: str = Field(..., min_length=3, max_length=255)

    @field_validator("customer_id")
    @classmethod
    def validate_customer_identifier(cls, value: str) -> str:
        if is_customer_id(value) or is_email(value):
            return value
        raise ValueError("Customer ID must be a CUST- identifier or a valid email address")


class ChatResponse(BaseModel):
    """Schema for chat response."""
    conversation_id: str
    response: str
    refund_initiated: bool = False
    refund_id: Optional[str] = None
    llm_debug: Optional[dict] = None


@router.post("/chat", response_model=ChatResponse)
@limiter.limit("10/minute")
async def chat(
    chat_request: ChatRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Send a message to the refund bot and get a response.

    The bot uses an LLM to understand the user's request and
    can automatically process refund requests.
    """
    logger.info(f"Chat request from customer: {chat_request.customer_id}")

    service = ConversationService(db)

    try:
        result = await service.process_message(
            customer_id=chat_request.customer_id,
            message=chat_request.message,
            conversation_id=chat_request.conversation_id
        )
        return ChatResponse(**result)
    except Exception as e:
        logger.error(f"Error processing chat: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get conversation history."""
    service = ConversationService(db)
    conversation = await service.get_conversation(conversation_id)

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return conversation
