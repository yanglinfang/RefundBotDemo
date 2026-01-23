"""
Debug Stats Service - Tracks LLM usage statistics for debugging.

Stores stats in a local JSON file that is created on startup and
can be cleaned up on shutdown.
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Stats file location
STATS_FILE = Path("./data/debug_stats.json")


@dataclass
class RequestRecord:
    """Record of a single LLM request."""
    timestamp: float
    endpoint_name: str
    endpoint_url: str
    model: str
    is_local: bool
    request_type: str
    latency_ms: float
    tokens: Optional[int] = None
    success: bool = True
    error: Optional[str] = None


@dataclass
class EndpointStats:
    """Aggregated stats for an endpoint."""
    name: str
    url: str
    model: str
    is_local: bool
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_latency_ms: float = 0.0
    total_tokens: int = 0
    requests_by_type: Dict[str, int] = field(default_factory=dict)


@dataclass
class DebugStats:
    """Overall debug statistics."""
    started_at: float = field(default_factory=time.time)
    total_requests: int = 0
    local_requests: int = 0
    cloud_requests: int = 0
    total_tokens: int = 0
    total_latency_ms: float = 0.0
    endpoints: Dict[str, dict] = field(default_factory=dict)
    recent_requests: List[dict] = field(default_factory=list)
    last_request: Optional[dict] = None


class DebugStatsService:
    """Service to track and persist debug statistics."""

    def __init__(self, stats_file: Path = STATS_FILE, max_recent: int = 50):
        self.stats_file = stats_file
        self.max_recent = max_recent
        self._stats = DebugStats()
        self._lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the stats file."""
        async with self._lock:
            # Ensure data directory exists
            self.stats_file.parent.mkdir(parents=True, exist_ok=True)

            # Load existing stats if file exists, otherwise start fresh
            if self.stats_file.exists():
                try:
                    with open(self.stats_file, 'r') as f:
                        data = json.load(f)
                        self._stats = DebugStats(
                            started_at=data.get('started_at', time.time()),
                            total_requests=data.get('total_requests', 0),
                            local_requests=data.get('local_requests', 0),
                            cloud_requests=data.get('cloud_requests', 0),
                            total_tokens=data.get('total_tokens', 0),
                            total_latency_ms=data.get('total_latency_ms', 0.0),
                            endpoints=data.get('endpoints', {}),
                            recent_requests=data.get('recent_requests', [])[-self.max_recent:],
                            last_request=data.get('last_request'),
                        )
                    logger.info("Loaded existing debug stats from %s", self.stats_file)
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning("Failed to load stats file, starting fresh: %s", e)
                    self._stats = DebugStats()
            else:
                self._stats = DebugStats()
                logger.info("Created new debug stats file at %s", self.stats_file)

            await self._persist()
            self._initialized = True

    async def cleanup(self) -> None:
        """Clean up the stats file on shutdown."""
        async with self._lock:
            if self.stats_file.exists():
                try:
                    os.remove(self.stats_file)
                    logger.info("Removed debug stats file: %s", self.stats_file)
                except OSError as e:
                    logger.warning("Failed to remove stats file: %s", e)

    async def record_request(
        self,
        endpoint_name: str,
        endpoint_url: str,
        model: str,
        is_local: bool,
        request_type: str,
        latency_ms: float,
        tokens: Optional[int] = None,
        success: bool = True,
        error: Optional[str] = None,
    ) -> RequestRecord:
        """Record a new LLM request."""
        record = RequestRecord(
            timestamp=time.time(),
            endpoint_name=endpoint_name,
            endpoint_url=endpoint_url,
            model=model,
            is_local=is_local,
            request_type=request_type,
            latency_ms=latency_ms,
            tokens=tokens,
            success=success,
            error=error,
        )

        async with self._lock:
            # Update totals
            self._stats.total_requests += 1
            if is_local:
                self._stats.local_requests += 1
            else:
                self._stats.cloud_requests += 1

            self._stats.total_latency_ms += latency_ms
            if tokens:
                self._stats.total_tokens += tokens

            # Update endpoint stats
            if endpoint_name not in self._stats.endpoints:
                self._stats.endpoints[endpoint_name] = {
                    'name': endpoint_name,
                    'url': endpoint_url,
                    'model': model,
                    'is_local': is_local,
                    'total_requests': 0,
                    'successful_requests': 0,
                    'failed_requests': 0,
                    'total_latency_ms': 0.0,
                    'total_tokens': 0,
                    'requests_by_type': {},
                }

            ep_stats = self._stats.endpoints[endpoint_name]
            ep_stats['total_requests'] += 1
            if success:
                ep_stats['successful_requests'] += 1
            else:
                ep_stats['failed_requests'] += 1
            ep_stats['total_latency_ms'] += latency_ms
            if tokens:
                ep_stats['total_tokens'] += tokens

            # Track by request type
            if request_type not in ep_stats['requests_by_type']:
                ep_stats['requests_by_type'][request_type] = 0
            ep_stats['requests_by_type'][request_type] += 1

            # Store recent requests
            record_dict = asdict(record)
            self._stats.recent_requests.append(record_dict)
            if len(self._stats.recent_requests) > self.max_recent:
                self._stats.recent_requests = self._stats.recent_requests[-self.max_recent:]

            self._stats.last_request = record_dict

            await self._persist()

        return record

    async def get_stats(self) -> dict:
        """Get current debug statistics."""
        async with self._lock:
            return {
                'started_at': self._stats.started_at,
                'uptime_seconds': time.time() - self._stats.started_at,
                'total_requests': self._stats.total_requests,
                'local_requests': self._stats.local_requests,
                'cloud_requests': self._stats.cloud_requests,
                'total_tokens': self._stats.total_tokens,
                'total_latency_ms': self._stats.total_latency_ms,
                'avg_latency_ms': (
                    self._stats.total_latency_ms / self._stats.total_requests
                    if self._stats.total_requests > 0 else 0
                ),
                'endpoints': self._stats.endpoints,
                'last_request': self._stats.last_request,
            }

    async def get_last_request(self) -> Optional[dict]:
        """Get the last request record."""
        async with self._lock:
            return self._stats.last_request

    async def reset_stats(self) -> None:
        """Reset all statistics."""
        async with self._lock:
            self._stats = DebugStats()
            await self._persist()
            logger.info("Debug stats reset")

    async def _persist(self) -> None:
        """Persist stats to file."""
        try:
            data = {
                'started_at': self._stats.started_at,
                'total_requests': self._stats.total_requests,
                'local_requests': self._stats.local_requests,
                'cloud_requests': self._stats.cloud_requests,
                'total_tokens': self._stats.total_tokens,
                'total_latency_ms': self._stats.total_latency_ms,
                'endpoints': self._stats.endpoints,
                'recent_requests': self._stats.recent_requests,
                'last_request': self._stats.last_request,
            }
            with open(self.stats_file, 'w') as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            logger.error("Failed to persist debug stats: %s", e)


# Singleton instance
_debug_stats_instance: Optional[DebugStatsService] = None


def get_debug_stats() -> DebugStatsService:
    """Return the singleton debug stats service."""
    global _debug_stats_instance
    if _debug_stats_instance is None:
        _debug_stats_instance = DebugStatsService()
    return _debug_stats_instance


async def initialize_debug_stats() -> None:
    """Initialize the debug stats service."""
    service = get_debug_stats()
    await service.initialize()


async def cleanup_debug_stats() -> None:
    """Clean up the debug stats service."""
    service = get_debug_stats()
    await service.cleanup()
