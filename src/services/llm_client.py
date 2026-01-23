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
from src.services.debug_stats import get_debug_stats

logger = logging.getLogger(__name__)

PREFIX_CLEANUP_RE = re.compile(
    r"^(?:here(?:'s| is)\s+(?:an?|the)\s+[a-z\s]{0,80}?response:)\s*",
    re.IGNORECASE
)
SALUTATION_RE = re.compile(r"^dear\s+[^\n,:]+[:,]?\s*", re.IGNORECASE)

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

Respond in a friendly, professional manner. Keep responses concise and conversational.
Do not include formal salutations or closings (like "Dear ___" or "Sincerely") and avoid
placeholder text such as "[Your Name]". Provide the core information only."""


class LLMClient:
    """Client for interacting with OpenAI-compatible LLM APIs via a router."""

    def __init__(self):
        self.router = get_llm_router()
        self._clients: Dict[str, AsyncOpenAI] = {}
        self._last_debug: Optional[dict] = None

    async def analyze_refund_intent(
        self,
        message: str,
        conversation_history: list[dict],
        customer_id: str
    ) -> dict:
        """
        Analyze a message to determine if it's a refund request.

        Uses local keyword matching - no LLM call needed for intent detection.
        Returns intent classification and extracted entities.
        """
        # Use simple local keyword matching - fast and reliable
        return self._local_intent_analysis(message)

    def _local_intent_analysis(self, message: str) -> dict:
        """
        Local keyword-based intent analysis - no LLM call needed.

        Detects refund intent and extracts order ID using simple pattern matching.
        """
        message_lower = message.lower()

        # Check for refund keywords
        refund_keywords = ["refund", "return", "money back", "cancel order", "get my money"]
        is_refund = any(kw in message_lower for kw in refund_keywords)

        # Extract order ID
        order_match = re.search(r"ORD-[A-Z0-9]+", message, re.IGNORECASE)
        order_id = order_match.group(0).upper() if order_match else None

        # Try to extract reason from common patterns
        reason = None
        if is_refund:
            reason_patterns = [
                r"because\s+(.+?)(?:\.|$)",
                r"reason[:\s]+(.+?)(?:\.|$)",
                r"due to\s+(.+?)(?:\.|$)",
            ]
            for pattern in reason_patterns:
                reason_match = re.search(pattern, message_lower)
                if reason_match:
                    reason = reason_match.group(1).strip()
                    break
            if not reason:
                reason = "Customer requested refund"

        logger.debug(
            "Local intent analysis: intent=%s, order_id=%s",
            "refund_request" if is_refund else "general_inquiry",
            order_id,
        )

        return {
            "intent": "refund_request" if is_refund else "general_inquiry",
            "order_id": order_id,
            "reason": reason
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

            return self._clean_response(response.choices[0].message.content.strip())

        except Exception as e:
            logger.error("Error generating response: %s", e)
            return "I apologize, but I'm having trouble processing your request right now. Please try again or contact our support team directly."

    async def generate_refund_confirmation(
        self,
        order_id: str,
        amount: float,
        refund_id: str,
        original_message: Optional[str] = None,
    ) -> str:
        """Generate a confirmation message for a successful refund."""
        try:
            prompt = f"""Generate a brief, friendly confirmation message for a customer whose refund has been processed.
Details:
- Order ID: {order_id}
- Refund amount: ${amount:.2f}
- Refund reference: {refund_id}

Keep it concise (2-3 sentences) and professional. Respond with the final confirmation text only.
Do not preface the message with explanations like "Here is the confirmation" or include surrounding quotes."""

            # Use original customer message for complexity routing if provided
            routing_message = original_message or prompt
            response = await self._chat_completion(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=150,
                request_type="refund_confirmation",
                context={"order_id": order_id, "message": routing_message, "message_chars": len(routing_message)},
            )

            return self._clean_response(response.choices[0].message.content.strip())

        except Exception as e:
            logger.error("Error generating confirmation: %s", e)
            return f"Great news! Your refund of ${amount:.2f} for order {order_id} has been processed. Your refund reference is {refund_id}. The amount should appear in your account within 5-10 business days."

    async def generate_refund_denial(
        self,
        order_id: str,
        reason: str,
        original_message: Optional[str] = None,
    ) -> str:
        """Generate a message explaining why a refund cannot be processed."""
        try:
            prompt = f"""Generate a polite, empathetic message explaining why a refund cannot be processed.
Details:
- Order ID: {order_id}
- Reason: {reason}

Be understanding but clear. Offer alternatives if possible. Keep it concise."""

            # Use original customer message for complexity routing if provided
            routing_message = original_message or prompt
            response = await self._chat_completion(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=200,
                request_type="refund_denial",
                context={"order_id": order_id, "message": routing_message, "message_chars": len(routing_message)},
            )

            return self._clean_response(response.choices[0].message.content.strip())

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

        logger.info(
            "Routing context: complexity_score=%s, message_chars=%s, threshold=%s, char_threshold=%s",
            context.get("complexity_score"),
            context.get("message_chars"),
            self.router.complexity_threshold,
            self.router.complexity_char_threshold,
        )

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

                tokens = getattr(getattr(response, "usage", None), "total_tokens", None)
                self._last_debug = {
                    "endpoint": endpoint.name,
                    "endpoint_url": endpoint.url,
                    "is_local": endpoint.is_local,
                    "model": endpoint.model,
                    "latency_ms": round(latency_ms, 2),
                    "tokens": tokens,
                    "request_type": request_type,
                }

                # Record to debug stats service
                debug_stats = get_debug_stats()
                await debug_stats.record_request(
                    endpoint_name=endpoint.name,
                    endpoint_url=endpoint.url,
                    model=endpoint.model,
                    is_local=endpoint.is_local,
                    request_type=request_type,
                    latency_ms=latency_ms,
                    tokens=tokens,
                    success=True,
                )

                return response
            except Exception as exc:  # noqa: BLE001 - surface LLM failures
                latency_ms = (time.perf_counter() - start) * 1000
                await self.router.record_failure(endpoint.name, latency_ms, str(exc))

                # Record failure to debug stats
                debug_stats = get_debug_stats()
                await debug_stats.record_request(
                    endpoint_name=endpoint.name,
                    endpoint_url=endpoint.url,
                    model=endpoint.model,
                    is_local=endpoint.is_local,
                    request_type=request_type,
                    latency_ms=latency_ms,
                    success=False,
                    error=str(exc),
                )

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

    def get_last_debug(self) -> Optional[dict]:
        """Return the most recent LLM request metadata."""
        return self._last_debug

    @staticmethod
    def _clean_response(text: str) -> str:
        """Remove common boilerplate prefixes some models add."""
        cleaned = PREFIX_CLEANUP_RE.sub("", text)
        cleaned = SALUTATION_RE.sub("", cleaned).strip()
        cleaned = cleaned.replace("[Your Name]", "").strip()
        return cleaned

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
