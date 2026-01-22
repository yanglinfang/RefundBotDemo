"""
Routing logic for selecting between multiple LLM endpoints.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

import httpx

from src.config import LLMEndpoint, settings

logger = logging.getLogger(__name__)


class RoutingStrategy(str, Enum):
    """Supported routing strategies."""

    SINGLE = "single"
    FALLBACK = "fallback"
    COST = "cost"
    LATENCY = "latency"
    LOAD = "load"


@dataclass
class EndpointStats:
    """Track health and performance metrics for an endpoint."""

    healthy: bool = True
    inflight: int = 0
    requests: int = 0
    failures: int = 0
    health_checks: int = 0
    last_latency_ms: Optional[float] = None
    avg_latency_ms: Optional[float] = None
    last_error: Optional[str] = None
    last_checked: Optional[float] = None
    cooldown_until: Optional[float] = None

    def as_dict(self) -> dict:
        """Return a serializable snapshot."""
        return {
            "healthy": self.healthy,
            "inflight": self.inflight,
            "requests": self.requests,
            "failures": self.failures,
            "health_checks": self.health_checks,
            "last_latency_ms": self.last_latency_ms,
            "avg_latency_ms": self.avg_latency_ms,
            "last_error": self.last_error,
            "last_checked": self.last_checked,
            "cooldown_until": self.cooldown_until,
        }


class LLMRouter:
    """Coordinate routing decisions across multiple LLM endpoints."""

    def __init__(
        self,
        endpoints: Optional[List[LLMEndpoint]] = None,
        strategy: Optional[str] = None,
        health_timeout: float = 5.0,
        cooldown_seconds: float = 30.0,
        complexity_threshold: Optional[int] = None,
        complexity_char_threshold: Optional[int] = None,
    ) -> None:
        self.endpoints: List[LLMEndpoint] = endpoints or settings.get_llm_endpoints()
        if not self.endpoints:
            raise ValueError("At least one LLM endpoint must be configured")

        self.strategy = self._normalize_strategy(strategy or settings.llm_router_strategy)
        self.health_timeout = health_timeout
        self.cooldown_seconds = cooldown_seconds
        self.complexity_threshold = (
            complexity_threshold
            if complexity_threshold is not None
            else settings.llm_complexity_threshold
        )
        self.complexity_char_threshold = (
            complexity_char_threshold
            if complexity_char_threshold is not None
            else settings.llm_complexity_char_threshold
        )
        self.endpoint_stats: Dict[str, EndpointStats] = {
            endpoint.name: EndpointStats() for endpoint in self.endpoints
        }
        self._lock = asyncio.Lock()

    def _normalize_strategy(self, value: str) -> RoutingStrategy:
        """Map arbitrary strings to supported strategies."""
        try:
            return RoutingStrategy(value.lower())
        except ValueError:
            logger.warning("Unknown router strategy '%s', defaulting to FALLBACK", value)
            return RoutingStrategy.FALLBACK

    def get_routing_plan(self, context: Optional[dict] = None) -> List[LLMEndpoint]:
        """
        Return a prioritized list of endpoints to try for a request.

        Context can include hints such as complexity or latency sensitivity.
        """
        context = context or {}
        available = self._filter_available_endpoints()
        candidates = available if available else list(self.endpoints)
        candidates = self._apply_complexity_routing(candidates, context)

        if self.strategy == RoutingStrategy.SINGLE:
            endpoint = self._select_primary(candidates)
            return [endpoint]

        if self.strategy == RoutingStrategy.COST:
            sorted_eps = sorted(
                candidates,
                key=lambda ep: (
                    ep.cost_per_1k_tokens
                    if ep.cost_per_1k_tokens is not None
                    else float("inf"),
                    ep.priority,
                ),
            )
            return sorted_eps or candidates

        if self.strategy == RoutingStrategy.LATENCY:
            sorted_eps = sorted(
                candidates,
                key=lambda ep: (
                    self.endpoint_stats[ep.name].avg_latency_ms
                    if self.endpoint_stats[ep.name].avg_latency_ms is not None
                    else float("inf"),
                    ep.priority,
                ),
            )
            return sorted_eps or candidates

        if self.strategy == RoutingStrategy.LOAD:
            sorted_eps = sorted(
                candidates,
                key=lambda ep: (
                    self.endpoint_stats[ep.name].inflight,
                    ep.priority,
                ),
            )
            return sorted_eps or candidates

        # Default fallback strategy prefers higher priority (lower number) endpoints.
        sorted_eps = sorted(
            candidates,
            key=lambda ep: (ep.priority, not ep.is_local),
        )
        return sorted_eps or candidates

    def _select_primary(self, candidates: List[LLMEndpoint]) -> LLMEndpoint:
        """Select a single endpoint for the SINGLE strategy."""
        return min(candidates, key=lambda ep: (ep.priority, not ep.is_local))

    def _apply_complexity_routing(
        self,
        candidates: List[LLMEndpoint],
        context: dict,
    ) -> List[LLMEndpoint]:
        """
        Prefer cloud endpoints when message complexity exceeds thresholds.
        """
        if not candidates:
            return candidates

        complexity_score = context.get("complexity_score")
        message_chars = context.get("message_chars")
        unique_words = context.get("unique_words")

        is_complex = False
        if isinstance(complexity_score, int) and complexity_score >= self.complexity_threshold:
            is_complex = True
        if isinstance(unique_words, int) and unique_words >= self.complexity_threshold:
            is_complex = True
        if isinstance(message_chars, int) and message_chars >= self.complexity_char_threshold:
            is_complex = True

        if not is_complex:
            return candidates

        non_local = [ep for ep in candidates if not ep.is_local]
        local = [ep for ep in candidates if ep.is_local]
        return non_local + local if non_local else candidates

    def _filter_available_endpoints(self) -> List[LLMEndpoint]:
        """Filter endpoints that are currently considered healthy."""
        now = time.time()
        available: List[LLMEndpoint] = []

        for endpoint in self.endpoints:
            stats = self.endpoint_stats.setdefault(endpoint.name, EndpointStats())
            cooldown = stats.cooldown_until or 0
            if cooldown and cooldown > now:
                continue
            if stats.healthy:
                available.append(endpoint)

        return available

    async def mark_request_start(self, endpoint_name: str) -> None:
        """Increment inflight counter when a request begins."""
        async with self._lock:
            stats = self.endpoint_stats.setdefault(endpoint_name, EndpointStats())
            stats.inflight += 1

    async def record_success(self, endpoint_name: str, latency_ms: float) -> None:
        """Record successful completion for an endpoint request."""
        async with self._lock:
            stats = self.endpoint_stats.setdefault(endpoint_name, EndpointStats())
            stats.inflight = max(0, stats.inflight - 1)
            stats.requests += 1
            stats.healthy = True
            stats.last_error = None
            stats.cooldown_until = None
            stats.last_latency_ms = latency_ms
            stats.avg_latency_ms = (
                latency_ms
                if stats.avg_latency_ms is None
                else stats.avg_latency_ms * 0.8 + latency_ms * 0.2
            )
            stats.last_checked = time.time()

    async def record_failure(
        self,
        endpoint_name: str,
        latency_ms: float,
        error_message: str,
    ) -> None:
        """Record a failed attempt against an endpoint."""
        async with self._lock:
            stats = self.endpoint_stats.setdefault(endpoint_name, EndpointStats())
            stats.inflight = max(0, stats.inflight - 1)
            stats.failures += 1
            stats.last_error = error_message
            stats.last_latency_ms = latency_ms or stats.last_latency_ms
            stats.last_checked = time.time()
            stats.healthy = False
            stats.cooldown_until = time.time() + self.cooldown_seconds

    async def refresh_health(self) -> Dict[str, bool]:
        """Actively ping each endpoint to refresh health data."""
        results: Dict[str, bool] = {}
        tasks = [self._probe_endpoint(endpoint) for endpoint in self.endpoints]
        probes = await asyncio.gather(*tasks, return_exceptions=True)

        for endpoint, probe_result in zip(self.endpoints, probes):
            if isinstance(probe_result, Exception):
                logger.error(
                    "Health probe failed for %s: %s", endpoint.name, probe_result
                )
                results[endpoint.name] = False
            else:
                results[endpoint.name] = probe_result

        return results

    async def get_health_report(self, refresh: bool = False) -> dict:
        """Return current router metrics."""
        if refresh:
            await self.refresh_health()

        async with self._lock:
            snapshot = {
                endpoint: stats.as_dict()
                for endpoint, stats in self.endpoint_stats.items()
            }

        return {
            "strategy": self.strategy.value,
            "endpoints": snapshot,
        }

    async def _probe_endpoint(self, endpoint: LLMEndpoint) -> bool:
        """Hit the /models endpoint (and fall back to /api/tags) to gauge health."""
        base_url = endpoint.url.rstrip("/")
        headers = {}
        if endpoint.api_key:
            headers["Authorization"] = f"Bearer {endpoint.api_key}"

        last_error: Optional[Exception] = None
        for suffix in ("/models", "/api/tags"):
            url = base_url + suffix
            start = time.perf_counter()
            try:
                async with httpx.AsyncClient(timeout=self.health_timeout) as client:
                    response = await client.get(url, headers=headers)
                    response.raise_for_status()
                latency_ms = (time.perf_counter() - start) * 1000
                await self._update_health(
                    endpoint.name,
                    healthy=True,
                    latency_ms=latency_ms,
                )
                return True
            except Exception as exc:  # noqa: BLE001 - log/capture all errors
                last_error = exc

        await self._update_health(
            endpoint.name,
            healthy=False,
            error=str(last_error) if last_error else "unknown error",
        )
        return False

    async def _update_health(
        self,
        endpoint_name: str,
        *,
        healthy: bool,
        latency_ms: Optional[float] = None,
        error: Optional[str] = None,
    ) -> None:
        """Update health info outside of request flow (e.g., probes)."""
        async with self._lock:
            stats = self.endpoint_stats.setdefault(endpoint_name, EndpointStats())
            stats.health_checks += 1
            stats.last_checked = time.time()
            stats.last_latency_ms = latency_ms or stats.last_latency_ms
            stats.healthy = healthy
            if healthy:
                stats.last_error = None
                stats.cooldown_until = None
                stats.avg_latency_ms = (
                    latency_ms
                    if latency_ms is not None
                    else stats.avg_latency_ms
                )
            else:
                stats.last_error = error
                stats.cooldown_until = time.time() + self.cooldown_seconds


_router_instance: Optional[LLMRouter] = None


def get_llm_router() -> LLMRouter:
    """Return a singleton router instance."""
    global _router_instance
    if _router_instance is None:
        _router_instance = LLMRouter()
    return _router_instance
