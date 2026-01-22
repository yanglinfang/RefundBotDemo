"""
LLM Client - Integration with OpenAI-compatible LLM API
"""

import asyncio
import logging
import re
import time
from typing import Dict, List, Optional

from openai import AsyncOpenAI

from src.config import LLMEndpoint, settings
from src.services.llm_router import get_llm_router

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
    """Client for interacting with OpenAI-compatible LLM APIs via a router."""

    def __init__(self):
        self.router = get_llm_router()
        self._clients: Dict[str, AsyncOpenAI] = {}

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

            response = await self._chat_completion(
                messages=messages,
                temperature=0.1,
                max_tokens=150,
                request_type="intent_analysis",
                context={
                    "customer_id": customer_id,
                    "message_chars": len(message),
                    "message": message,
                },
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
            logger.error("Error analyzing intent via LLM: %s", e)
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

            response = await self._chat_completion(
                messages=messages,
                temperature=0.7,
                max_tokens=300,
                request_type="general_response",
                context={
                    "history_count": len(conversation_history),
                    "message": message,
                    "message_chars": len(message),
                },
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error("Error generating response: %s", e)
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

            response = await self._chat_completion(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=150,
                request_type="refund_confirmation",
                context={"order_id": order_id, "message": prompt, "message_chars": len(prompt)},
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error("Error generating confirmation: %s", e)
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

            response = await self._chat_completion(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=200,
                request_type="refund_denial",
                context={"order_id": order_id, "message": prompt, "message_chars": len(prompt)},
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error("Error generating denial: %s", e)
            return f"I apologize, but I'm unable to process a refund for order {order_id}. {reason}. If you believe this is an error or need further assistance, please contact our support team."

    async def _chat_completion(
        self,
        *,
        messages: List[dict],
        temperature: float,
        max_tokens: int,
        request_type: str,
        context: Optional[dict] = None,
    ):
        """
        Execute a chat completion request using the router for endpoint selection.
        """
        context = {**(context or {})}
        if "complexity_score" not in context:
            text = context.get("message") or self._latest_user_message(messages)
            if text:
                context["complexity_score"] = self._compute_complexity_score(text)
                context.setdefault("unique_words", context["complexity_score"])
                context.setdefault("message_chars", len(text))

        plan = self.router.get_routing_plan(
            context={
                "request_type": request_type,
                **context,
            }
        )
        last_error: Optional[Exception] = None
        failure_messages: List[str] = []

        for endpoint in plan:
            client = self._get_client(endpoint)
            await self.router.mark_request_start(endpoint.name)
            start = time.perf_counter()
            timeout_seconds = (
                endpoint.request_timeout_seconds
                if endpoint.request_timeout_seconds is not None
                else settings.llm_request_timeout_seconds
            )

            try:
                logger.info("LLM request using endpoint %s for %s", endpoint.name, request_type)
                response = await asyncio.wait_for(
                    client.chat.completions.create(
                        model=endpoint.model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens
                    ),
                    timeout=timeout_seconds,
                )
                latency_ms = (time.perf_counter() - start) * 1000
                await self.router.record_success(endpoint.name, latency_ms)
                return response
            except Exception as exc:  # noqa: BLE001 - surface LLM failures
                latency_ms = (time.perf_counter() - start) * 1000
                await self.router.record_failure(endpoint.name, latency_ms, str(exc))
                last_error = exc
                failure_messages.append(f"{endpoint.name}: {exc}")
                logger.warning("LLM request failed via %s: %s", endpoint.name, exc)

        error_text = "; ".join(failure_messages) or "unknown error"
        raise RuntimeError(f"All LLM endpoints failed ({error_text})") from last_error

    def _get_client(self, endpoint: LLMEndpoint) -> AsyncOpenAI:
        """Return/reuse an AsyncOpenAI client for the given endpoint."""
        if endpoint.name not in self._clients:
            self._clients[endpoint.name] = AsyncOpenAI(
                base_url=endpoint.url,
                api_key=endpoint.api_key or "dummy-key"
            )
        return self._clients[endpoint.name]

    @staticmethod
    def _compute_complexity_score(text: str) -> int:
        """Return a simple complexity score based on unique word count."""
        words = re.findall(r"\b\w+\b", text.lower())
        return len(set(words))

    @staticmethod
    def _latest_user_message(messages: List[dict]) -> Optional[str]:
        """Return the most recent user message content."""
        for message in reversed(messages):
            if message.get("role") == "user":
                return message.get("content")
        return None
