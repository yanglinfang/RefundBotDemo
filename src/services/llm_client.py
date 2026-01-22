"""
LLM Client - Integration with OpenAI-compatible LLM API
"""

import logging
import re
from typing import Optional

from openai import AsyncOpenAI

from src.config import settings

logger = logging.getLogger(__name__)

# System prompt for the refund bot
SYSTEM_PROMPT = """You are a helpful customer service assistant for an e-commerce platform.
Your primary role is to help customers with refund requests.

When a customer wants a refund:
1. Ask for the order ID if not provided
2. Understand the reason for the refund
3. Be empathetic and professional

If you detect a refund request, extract:
- The order ID (format: ORD-XXX)
- The reason for the refund

Respond in a friendly, professional manner. Keep responses concise."""


class LLMClient:
    """Client for interacting with OpenAI-compatible LLM APIs."""

    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=settings.llm_api_url,
            api_key=settings.llm_api_key or "dummy-key"
        )
        self.model = settings.llm_model

    async def analyze_refund_intent(
        self,
        message: str,
        conversation_history: list[dict],
        customer_id: str
    ) -> dict:
        """
        Analyze a message to determine if it's a refund request.

        Returns intent classification and extracted entities.
        """
        analysis_prompt = f"""Analyze this customer message and determine if they are requesting a refund.

Customer message: "{message}"

Respond in this exact format:
INTENT: [refund_request OR general_inquiry OR other]
ORDER_ID: [extracted order ID if mentioned, or NONE]
REASON: [brief reason for refund if mentioned, or NONE]

Only respond with the format above, nothing else."""

        try:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                *conversation_history[-5:],  # Include recent history
                {"role": "user", "content": analysis_prompt}
            ]

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,
                max_tokens=150
            )

            result_text = response.choices[0].message.content.strip()

            # Parse the response
            intent = "other"
            order_id = None
            reason = None

            if "INTENT:" in result_text:
                intent_match = re.search(r"INTENT:\s*(\w+)", result_text)
                if intent_match:
                    intent = intent_match.group(1).lower()

            if "ORDER_ID:" in result_text:
                order_match = re.search(r"ORDER_ID:\s*(ORD-\w+|NONE)", result_text)
                if order_match and order_match.group(1) != "NONE":
                    order_id = order_match.group(1)

            if "REASON:" in result_text:
                reason_match = re.search(r"REASON:\s*(.+?)(?:\n|$)", result_text)
                if reason_match and reason_match.group(1).strip() != "NONE":
                    reason = reason_match.group(1).strip()

            return {
                "intent": intent,
                "order_id": order_id,
                "reason": reason
            }

        except Exception as e:
            logger.error(f"Error analyzing intent: {e}")
            # Fallback to simple keyword matching
            return self._fallback_intent_analysis(message)

    def _fallback_intent_analysis(self, message: str) -> dict:
        """Simple keyword-based fallback for intent analysis."""
        message_lower = message.lower()

        # Check for refund keywords
        refund_keywords = ["refund", "return", "money back", "cancel order"]
        is_refund = any(kw in message_lower for kw in refund_keywords)

        # Extract order ID
        order_match = re.search(r"ORD-\w+", message, re.IGNORECASE)
        order_id = order_match.group(0).upper() if order_match else None

        return {
            "intent": "refund_request" if is_refund else "general_inquiry",
            "order_id": order_id,
            "reason": "Customer requested refund" if is_refund else None
        }

    async def generate_response(
        self,
        message: str,
        conversation_history: list[dict]
    ) -> str:
        """Generate a general conversational response."""
        try:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                *conversation_history[-10:],
                {"role": "user", "content": message}
            ]

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=300
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "I apologize, but I'm having trouble processing your request right now. Please try again or contact our support team directly."

    async def generate_refund_confirmation(
        self,
        order_id: str,
        amount: float,
        refund_id: str
    ) -> str:
        """Generate a confirmation message for a successful refund."""
        try:
            prompt = f"""Generate a brief, friendly confirmation message for a customer whose refund has been processed.
Details:
- Order ID: {order_id}
- Refund amount: ${amount:.2f}
- Refund reference: {refund_id}

Keep it concise (2-3 sentences) and professional."""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=150
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Error generating confirmation: {e}")
            return f"Great news! Your refund of ${amount:.2f} for order {order_id} has been processed. Your refund reference is {refund_id}. The amount should appear in your account within 5-10 business days."

    async def generate_refund_denial(
        self,
        order_id: str,
        reason: str
    ) -> str:
        """Generate a message explaining why a refund cannot be processed."""
        try:
            prompt = f"""Generate a polite, empathetic message explaining why a refund cannot be processed.
Details:
- Order ID: {order_id}
- Reason: {reason}

Be understanding but clear. Offer alternatives if possible. Keep it concise."""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=200
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Error generating denial: {e}")
            return f"I apologize, but I'm unable to process a refund for order {order_id}. {reason}. If you believe this is an error or need further assistance, please contact our support team."
