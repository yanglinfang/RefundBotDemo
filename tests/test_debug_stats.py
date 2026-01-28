"""
Tests for Debug Stats Service.
"""

import json
import tempfile
import time
from pathlib import Path

import pytest

from src.services.debug_stats import (
    DebugStatsService,
    RequestRecord,
    get_debug_stats,
    initialize_debug_stats,
    cleanup_debug_stats,
)
import src.services.debug_stats as debug_stats_module


@pytest.fixture
def temp_stats_file():
    """Create a temporary stats file path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test_stats.json"


@pytest.fixture
def stats_service(temp_stats_file):
    """Create a DebugStatsService with temporary file."""
    return DebugStatsService(stats_file=temp_stats_file, max_recent=10)


class TestDebugStatsService:
    """Tests for DebugStatsService."""

    @pytest.mark.asyncio
    async def test_initialize_creates_new_file(self, stats_service, temp_stats_file):
        """Test that initialize creates a new stats file."""
        assert not temp_stats_file.exists()
        await stats_service.initialize()
        assert temp_stats_file.exists()

    @pytest.mark.asyncio
    async def test_initialize_loads_existing_file(self, temp_stats_file):
        """Test that initialize loads existing stats."""
        # Create pre-existing stats file
        existing_data = {
            "started_at": 1000.0,
            "total_requests": 5,
            "local_requests": 3,
            "cloud_requests": 2,
            "total_tokens": 100,
            "total_latency_ms": 500.0,
            "endpoints": {},
            "recent_requests": [],
            "last_request": None,
        }
        temp_stats_file.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_stats_file, "w") as f:
            json.dump(existing_data, f)

        service = DebugStatsService(stats_file=temp_stats_file)
        await service.initialize()

        stats = await service.get_stats()
        assert stats["total_requests"] == 5
        assert stats["local_requests"] == 3
        assert stats["cloud_requests"] == 2

    @pytest.mark.asyncio
    async def test_initialize_handles_corrupt_file(self, temp_stats_file):
        """Test that initialize handles corrupt stats file."""
        temp_stats_file.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_stats_file, "w") as f:
            f.write("not valid json")

        service = DebugStatsService(stats_file=temp_stats_file)
        await service.initialize()

        stats = await service.get_stats()
        # Should start fresh with 0 requests
        assert stats["total_requests"] == 0

    @pytest.mark.asyncio
    async def test_record_request_updates_totals(self, stats_service):
        """Test that record_request updates total counters."""
        await stats_service.initialize()

        await stats_service.record_request(
            endpoint_name="test-endpoint",
            endpoint_url="http://localhost:8000",
            model="test-model",
            is_local=True,
            request_type="test",
            latency_ms=100.0,
            tokens=50,
            success=True,
        )

        stats = await stats_service.get_stats()
        assert stats["total_requests"] == 1
        assert stats["local_requests"] == 1
        assert stats["cloud_requests"] == 0
        assert stats["total_tokens"] == 50
        assert stats["total_latency_ms"] == 100.0

    @pytest.mark.asyncio
    async def test_record_request_cloud_endpoint(self, stats_service):
        """Test recording a cloud endpoint request."""
        await stats_service.initialize()

        await stats_service.record_request(
            endpoint_name="cloud-endpoint",
            endpoint_url="https://api.openai.com",
            model="gpt-4",
            is_local=False,
            request_type="chat",
            latency_ms=200.0,
            tokens=100,
            success=True,
        )

        stats = await stats_service.get_stats()
        assert stats["total_requests"] == 1
        assert stats["local_requests"] == 0
        assert stats["cloud_requests"] == 1

    @pytest.mark.asyncio
    async def test_record_request_tracks_failures(self, stats_service):
        """Test that failed requests are tracked."""
        await stats_service.initialize()

        await stats_service.record_request(
            endpoint_name="test-endpoint",
            endpoint_url="http://localhost:8000",
            model="test-model",
            is_local=True,
            request_type="test",
            latency_ms=50.0,
            success=False,
            error="Connection timeout",
        )

        stats = await stats_service.get_stats()
        endpoint_stats = stats["endpoints"]["test-endpoint"]
        assert endpoint_stats["failed_requests"] == 1
        assert endpoint_stats["successful_requests"] == 0

    @pytest.mark.asyncio
    async def test_record_request_tracks_by_type(self, stats_service):
        """Test that requests are tracked by type."""
        await stats_service.initialize()

        await stats_service.record_request(
            endpoint_name="test-endpoint",
            endpoint_url="http://localhost:8000",
            model="test-model",
            is_local=True,
            request_type="refund_confirmation",
            latency_ms=100.0,
            success=True,
        )
        await stats_service.record_request(
            endpoint_name="test-endpoint",
            endpoint_url="http://localhost:8000",
            model="test-model",
            is_local=True,
            request_type="general_response",
            latency_ms=100.0,
            success=True,
        )

        stats = await stats_service.get_stats()
        endpoint_stats = stats["endpoints"]["test-endpoint"]
        assert endpoint_stats["requests_by_type"]["refund_confirmation"] == 1
        assert endpoint_stats["requests_by_type"]["general_response"] == 1

    @pytest.mark.asyncio
    async def test_record_request_limits_recent_requests(self, temp_stats_file):
        """Test that recent requests are limited to max_recent."""
        service = DebugStatsService(stats_file=temp_stats_file, max_recent=3)
        await service.initialize()

        # Record 5 requests
        for i in range(5):
            await service.record_request(
                endpoint_name="test-endpoint",
                endpoint_url="http://localhost:8000",
                model="test-model",
                is_local=True,
                request_type=f"type_{i}",
                latency_ms=100.0,
                success=True,
            )

        # Should only keep last 3
        assert len(service._stats.recent_requests) == 3
        assert service._stats.recent_requests[0]["request_type"] == "type_2"
        assert service._stats.recent_requests[2]["request_type"] == "type_4"

    @pytest.mark.asyncio
    async def test_get_stats_returns_correct_structure(self, stats_service):
        """Test that get_stats returns correct structure."""
        await stats_service.initialize()

        stats = await stats_service.get_stats()

        assert "started_at" in stats
        assert "uptime_seconds" in stats
        assert "total_requests" in stats
        assert "local_requests" in stats
        assert "cloud_requests" in stats
        assert "total_tokens" in stats
        assert "total_latency_ms" in stats
        assert "avg_latency_ms" in stats
        assert "endpoints" in stats
        assert "last_request" in stats

    @pytest.mark.asyncio
    async def test_get_stats_calculates_avg_latency(self, stats_service):
        """Test that average latency is calculated correctly."""
        await stats_service.initialize()

        await stats_service.record_request(
            endpoint_name="test",
            endpoint_url="http://localhost",
            model="model",
            is_local=True,
            request_type="test",
            latency_ms=100.0,
            success=True,
        )
        await stats_service.record_request(
            endpoint_name="test",
            endpoint_url="http://localhost",
            model="model",
            is_local=True,
            request_type="test",
            latency_ms=200.0,
            success=True,
        )

        stats = await stats_service.get_stats()
        assert stats["avg_latency_ms"] == 150.0  # (100 + 200) / 2

    @pytest.mark.asyncio
    async def test_get_last_request(self, stats_service):
        """Test get_last_request returns the most recent request."""
        await stats_service.initialize()

        await stats_service.record_request(
            endpoint_name="first",
            endpoint_url="http://localhost",
            model="model",
            is_local=True,
            request_type="test1",
            latency_ms=100.0,
            success=True,
        )
        await stats_service.record_request(
            endpoint_name="second",
            endpoint_url="http://localhost",
            model="model",
            is_local=False,
            request_type="test2",
            latency_ms=200.0,
            success=True,
        )

        last = await stats_service.get_last_request()
        assert last["endpoint_name"] == "second"
        assert last["request_type"] == "test2"

    @pytest.mark.asyncio
    async def test_reset_stats(self, stats_service):
        """Test reset_stats clears all statistics."""
        await stats_service.initialize()

        await stats_service.record_request(
            endpoint_name="test",
            endpoint_url="http://localhost",
            model="model",
            is_local=True,
            request_type="test",
            latency_ms=100.0,
            tokens=50,
            success=True,
        )

        await stats_service.reset_stats()

        stats = await stats_service.get_stats()
        assert stats["total_requests"] == 0
        assert stats["total_tokens"] == 0
        assert stats["endpoints"] == {}

    @pytest.mark.asyncio
    async def test_cleanup_removes_file(self, stats_service, temp_stats_file):
        """Test that cleanup removes the stats file."""
        await stats_service.initialize()
        assert temp_stats_file.exists()

        await stats_service.cleanup()
        assert not temp_stats_file.exists()

    @pytest.mark.asyncio
    async def test_cleanup_handles_missing_file(self, stats_service, temp_stats_file):
        """Test that cleanup handles missing file gracefully."""
        # Don't initialize, so file doesn't exist
        await stats_service.cleanup()  # Should not raise


class TestRequestRecord:
    """Tests for RequestRecord dataclass."""

    def test_request_record_defaults(self):
        """Test RequestRecord default values."""
        record = RequestRecord(
            timestamp=time.time(),
            endpoint_name="test",
            endpoint_url="http://localhost",
            model="model",
            is_local=True,
            request_type="test",
            latency_ms=100.0,
        )

        assert record.tokens is None
        assert record.success is True
        assert record.error is None

    def test_request_record_with_all_fields(self):
        """Test RequestRecord with all fields."""
        record = RequestRecord(
            timestamp=1000.0,
            endpoint_name="test",
            endpoint_url="http://localhost",
            model="model",
            is_local=False,
            request_type="chat",
            latency_ms=100.0,
            tokens=50,
            success=False,
            error="Connection error",
        )

        assert record.timestamp == 1000.0
        assert record.tokens == 50
        assert record.success is False
        assert record.error == "Connection error"


class TestSingletonFunctions:
    """Tests for singleton functions."""

    def test_get_debug_stats_returns_singleton(self):
        """Test that get_debug_stats returns a singleton."""
        # Reset the singleton
        debug_stats_module._debug_stats_instance = None

        instance1 = get_debug_stats()
        instance2 = get_debug_stats()

        assert instance1 is instance2

        # Clean up
        debug_stats_module._debug_stats_instance = None

    @pytest.mark.asyncio
    async def test_initialize_debug_stats(self):
        """Test initialize_debug_stats function."""
        debug_stats_module._debug_stats_instance = None

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a custom service with temp file
            service = DebugStatsService(stats_file=Path(tmpdir) / "stats.json")
            debug_stats_module._debug_stats_instance = service

            await initialize_debug_stats()

            assert service._initialized is True

        debug_stats_module._debug_stats_instance = None

    @pytest.mark.asyncio
    async def test_cleanup_debug_stats(self):
        """Test cleanup_debug_stats function."""
        debug_stats_module._debug_stats_instance = None

        with tempfile.TemporaryDirectory() as tmpdir:
            stats_file = Path(tmpdir) / "stats.json"
            service = DebugStatsService(stats_file=stats_file)
            debug_stats_module._debug_stats_instance = service

            await service.initialize()
            assert stats_file.exists()

            await cleanup_debug_stats()
            assert not stats_file.exists()

        debug_stats_module._debug_stats_instance = None
