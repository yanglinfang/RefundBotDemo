"""
Conversation API Router for LLM-powered interactions
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.services.conversation_service import ConversationService

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    """Schema for chat request."""
    message: str
    conversation_id: Optional[str] = None
    customer_id: str


class ChatResponse(BaseModel):
    """Schema for chat response."""
    conversation_id: str
    response: str
    refund_initiated: bool = False
    refund_id: Optional[str] = None


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Send a message to the refund bot and get a response.

    The bot uses an LLM to understand the user's request and
    can automatically process refund requests.
    """
    logger.info(f"Chat request from customer: {request.customer_id}")

    service = ConversationService(db)

    try:
        result = await service.process_message(
            customer_id=request.customer_id,
            message=request.message,
            conversation_id=request.conversation_id
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
