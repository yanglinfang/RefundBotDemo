import time
from unittest.mock import patch, AsyncMock

import pytest

from src.config import LLMEndpoint
from src.services.llm_router import (
    LLMRouter,
    EndpointStats,
    RoutingStrategy,
    get_llm_router,
    _router_instance,
)


def _endpoints():
    return [
        LLMEndpoint(
            name="local",
            url="http://localhost:11434/v1",
            api_key="",
            model="llama",
            priority=1,
            is_local=True,
            cost_per_1k_tokens=0.0,
        ),
        LLMEndpoint(
            name="cloud",
            url="https://api.openai.com/v1",
            api_key="sk-test",
            model="gpt-4o-mini",
            priority=2,
            is_local=False,
            cost_per_1k_tokens=0.2,
        ),
    ]


def test_routing_plan_fallback_orders_by_priority():
    router = LLMRouter(endpoints=_endpoints(), strategy="fallback")
    plan = router.get_routing_plan()
    assert [endpoint.name for endpoint in plan] == ["local", "cloud"]


def test_routing_plan_cost_orders_by_cost():
    router = LLMRouter(endpoints=_endpoints(), strategy="cost")
    plan = router.get_routing_plan()
    assert [endpoint.name for endpoint in plan] == ["local", "cloud"]


def test_routing_plan_latency_orders_by_latency():
    router = LLMRouter(endpoints=_endpoints(), strategy="latency")
    router.endpoint_stats["local"].avg_latency_ms = 150.0
    router.endpoint_stats["cloud"].avg_latency_ms = 50.0
    plan = router.get_routing_plan()
    assert [endpoint.name for endpoint in plan] == ["cloud", "local"]


def test_routing_plan_load_orders_by_inflight():
    router = LLMRouter(endpoints=_endpoints(), strategy="load")
    router.endpoint_stats["local"].inflight = 5
    router.endpoint_stats["cloud"].inflight = 1
    plan = router.get_routing_plan()
    assert [endpoint.name for endpoint in plan] == ["cloud", "local"]


def test_routing_plan_single_selects_primary():
    router = LLMRouter(endpoints=_endpoints(), strategy="single")
    plan = router.get_routing_plan()
    assert [endpoint.name for endpoint in plan] == ["local"]


def test_routing_plan_complexity_prefers_cloud():
    router = LLMRouter(
        endpoints=_endpoints(),
        strategy="fallback",
        complexity_threshold=3,
        complexity_char_threshold=9999,
    )
    plan = router.get_routing_plan(context={"complexity_score": 5})
    assert [endpoint.name for endpoint in plan] == ["cloud", "local"]


@pytest.mark.asyncio
async def test_record_success_updates_stats():
    router = LLMRouter(endpoints=_endpoints(), strategy="fallback")
    await router.mark_request_start("local")
    await router.record_success("local", latency_ms=120.0)
    stats = router.endpoint_stats["local"]
    assert stats.requests == 1
    assert stats.inflight == 0
    assert stats.healthy is True
    assert stats.last_latency_ms == 120.0


@pytest.mark.asyncio
async def test_record_failure_sets_cooldown_and_skips():
    router = LLMRouter(endpoints=_endpoints(), strategy="fallback", cooldown_seconds=60.0)
    await router.mark_request_start("local")
    await router.record_failure("local", latency_ms=50.0, error_message="boom")
    stats = router.endpoint_stats["local"]
    assert stats.healthy is False
    assert stats.cooldown_until is not None
    assert stats.cooldown_until > time.time()
    plan = router.get_routing_plan()
    assert plan[0].name == "cloud"


# Tests for _is_complex_message with different inputs


def test_is_complex_message_with_unique_words():
    router = LLMRouter(
        endpoints=_endpoints(),
        strategy="fallback",
        complexity_threshold=10,
        complexity_char_threshold=9999,
    )
    assert router._is_complex_message({"unique_words": 15}) is True
    assert router._is_complex_message({"unique_words": 5}) is False


def test_is_complex_message_with_message_chars():
    router = LLMRouter(
        endpoints=_endpoints(),
        strategy="fallback",
        complexity_threshold=9999,
        complexity_char_threshold=100,
    )
    assert router._is_complex_message({"message_chars": 150}) is True
    assert router._is_complex_message({"message_chars": 50}) is False


def test_is_complex_message_with_non_int_values():
    router = LLMRouter(
        endpoints=_endpoints(),
        strategy="fallback",
        complexity_threshold=10,
        complexity_char_threshold=100,
    )
    # Non-integer values should not trigger complexity
    assert router._is_complex_message({"complexity_score": "high"}) is False
    assert router._is_complex_message({"unique_words": None}) is False
    assert router._is_complex_message({"message_chars": 15.5}) is False


def test_is_complex_message_empty_context():
    router = LLMRouter(
        endpoints=_endpoints(),
        strategy="fallback",
        complexity_threshold=10,
        complexity_char_threshold=100,
    )
    assert router._is_complex_message({}) is False


# Tests for _normalize_strategy


def test_normalize_strategy_unknown_defaults_to_fallback():
    router = LLMRouter(endpoints=_endpoints(), strategy="unknown_strategy")
    assert router.strategy == RoutingStrategy.FALLBACK


def test_normalize_strategy_case_insensitive():
    router = LLMRouter(endpoints=_endpoints(), strategy="COST")
    assert router.strategy == RoutingStrategy.COST


# Tests for _filter_available_endpoints


def test_filter_available_endpoints_excludes_in_cooldown():
    router = LLMRouter(endpoints=_endpoints(), strategy="fallback", cooldown_seconds=60.0)
    router.endpoint_stats["local"].cooldown_until = time.time() + 30
    available = router._filter_available_endpoints()
    assert [ep.name for ep in available] == ["cloud"]


def test_filter_available_endpoints_excludes_unhealthy():
    router = LLMRouter(endpoints=_endpoints(), strategy="fallback")
    router.endpoint_stats["local"].healthy = False
    available = router._filter_available_endpoints()
    assert [ep.name for ep in available] == ["cloud"]


def test_filter_available_endpoints_expired_cooldown_included():
    router = LLMRouter(endpoints=_endpoints(), strategy="fallback")
    router.endpoint_stats["local"].cooldown_until = time.time() - 10  # expired
    available = router._filter_available_endpoints()
    assert len(available) == 2


# Tests for get_health_report


@pytest.mark.asyncio
async def test_get_health_report_without_refresh():
    router = LLMRouter(endpoints=_endpoints(), strategy="fallback")
    report = await router.get_health_report(refresh=False)
    assert report["strategy"] == "fallback"
    assert "local" in report["endpoints"]
    assert "cloud" in report["endpoints"]
    assert report["endpoints"]["local"]["healthy"] is True


@pytest.mark.asyncio
async def test_get_health_report_with_refresh():
    router = LLMRouter(endpoints=_endpoints(), strategy="fallback")
    with patch.object(router, "refresh_health", new_callable=AsyncMock) as mock_refresh:
        mock_refresh.return_value = {"local": True, "cloud": True}
        report = await router.get_health_report(refresh=True)
        mock_refresh.assert_called_once()
        assert "strategy" in report


# Tests for EndpointStats.as_dict


def test_endpoint_stats_as_dict():
    stats = EndpointStats(
        healthy=True,
        inflight=2,
        requests=10,
        failures=1,
        health_checks=5,
        last_latency_ms=100.0,
        avg_latency_ms=95.0,
        last_error=None,
        last_checked=1234567890.0,
        cooldown_until=None,
    )
    result = stats.as_dict()
    assert result["healthy"] is True
    assert result["inflight"] == 2
    assert result["requests"] == 10
    assert result["failures"] == 1
    assert result["health_checks"] == 5
    assert result["last_latency_ms"] == 100.0
    assert result["avg_latency_ms"] == 95.0
    assert result["last_error"] is None
    assert result["last_checked"] == 1234567890.0
    assert result["cooldown_until"] is None


# Tests for get_llm_router singleton


def test_get_llm_router_returns_singleton():
    import src.services.llm_router as llm_router_module

    # Reset the singleton
    llm_router_module._router_instance = None

    with patch("src.services.llm_router.settings") as mock_settings:
        mock_settings.get_llm_endpoints.return_value = _endpoints()
        mock_settings.llm_router_strategy = "fallback"
        mock_settings.llm_complexity_threshold = 10
        mock_settings.llm_complexity_char_threshold = 500
        router1 = get_llm_router()
        router2 = get_llm_router()
        assert router1 is router2

    # Clean up
    llm_router_module._router_instance = None


# Tests for edge cases in record_success and record_failure


@pytest.mark.asyncio
async def test_record_success_updates_avg_latency():
    router = LLMRouter(endpoints=_endpoints(), strategy="fallback")
    # First request establishes baseline
    await router.mark_request_start("local")
    await router.record_success("local", latency_ms=100.0)
    assert router.endpoint_stats["local"].avg_latency_ms == 100.0

    # Second request uses exponential moving average (0.8 * old + 0.2 * new)
    await router.mark_request_start("local")
    await router.record_success("local", latency_ms=200.0)
    expected_avg = 100.0 * 0.8 + 200.0 * 0.2  # 120.0
    assert router.endpoint_stats["local"].avg_latency_ms == expected_avg


@pytest.mark.asyncio
async def test_record_failure_preserves_last_latency_when_zero():
    router = LLMRouter(endpoints=_endpoints(), strategy="fallback")
    # Set an initial latency
    router.endpoint_stats["local"].last_latency_ms = 50.0
    await router.mark_request_start("local")
    # Pass 0 latency (falsy value)
    await router.record_failure("local", latency_ms=0, error_message="timeout")
    # Should preserve the previous latency
    assert router.endpoint_stats["local"].last_latency_ms == 50.0


@pytest.mark.asyncio
async def test_record_success_clears_error_state():
    router = LLMRouter(endpoints=_endpoints(), strategy="fallback")
    router.endpoint_stats["local"].healthy = False
    router.endpoint_stats["local"].last_error = "previous error"
    router.endpoint_stats["local"].cooldown_until = time.time() + 100

    await router.mark_request_start("local")
    await router.record_success("local", latency_ms=50.0)

    stats = router.endpoint_stats["local"]
    assert stats.healthy is True
    assert stats.last_error is None
    assert stats.cooldown_until is None


@pytest.mark.asyncio
async def test_mark_request_start_increments_inflight():
    router = LLMRouter(endpoints=_endpoints(), strategy="fallback")
    assert router.endpoint_stats["local"].inflight == 0
    await router.mark_request_start("local")
    assert router.endpoint_stats["local"].inflight == 1
    await router.mark_request_start("local")
    assert router.endpoint_stats["local"].inflight == 2


# Tests for complexity routing edge cases


def test_complexity_routing_with_unique_words_prefers_cloud():
    router = LLMRouter(
        endpoints=_endpoints(),
        strategy="fallback",
        complexity_threshold=10,
        complexity_char_threshold=9999,
    )
    plan = router.get_routing_plan(context={"unique_words": 15})
    assert plan[0].name == "cloud"


def test_complexity_routing_with_message_chars_prefers_cloud():
    router = LLMRouter(
        endpoints=_endpoints(),
        strategy="fallback",
        complexity_threshold=9999,
        complexity_char_threshold=100,
    )
    plan = router.get_routing_plan(context={"message_chars": 150})
    assert plan[0].name == "cloud"


def test_apply_complexity_routing_with_empty_candidates():
    router = LLMRouter(
        endpoints=_endpoints(),
        strategy="fallback",
        complexity_threshold=3,
    )
    result = router._apply_complexity_routing([], {"complexity_score": 5})
    assert result == []


def test_apply_complexity_routing_no_non_local_endpoints():
    local_only = [
        LLMEndpoint(
            name="local1",
            url="http://localhost:11434/v1",
            api_key="",
            model="llama",
            priority=1,
            is_local=True,
        ),
        LLMEndpoint(
            name="local2",
            url="http://localhost:11435/v1",
            api_key="",
            model="llama2",
            priority=2,
            is_local=True,
        ),
    ]
    router = LLMRouter(
        endpoints=local_only,
        strategy="fallback",
        complexity_threshold=3,
    )
    plan = router.get_routing_plan(context={"complexity_score": 5})
    # When no non-local endpoints exist, should return all candidates
    assert len(plan) == 2


# Tests for routing plan edge cases


def test_routing_plan_with_no_context():
    router = LLMRouter(endpoints=_endpoints(), strategy="fallback")
    plan = router.get_routing_plan(context=None)
    assert len(plan) == 2


def test_routing_plan_all_endpoints_unhealthy_uses_all():
    router = LLMRouter(endpoints=_endpoints(), strategy="fallback")
    router.endpoint_stats["local"].healthy = False
    router.endpoint_stats["cloud"].healthy = False
    plan = router.get_routing_plan()
    # When all are unhealthy, should still return all endpoints
    assert len(plan) == 2


# Tests for LLMRouter initialization


def test_router_raises_without_endpoints():
    # Need to patch settings since empty list is falsy and triggers fallback to settings
    with patch("src.services.llm_router.settings") as mock_settings:
        mock_settings.get_llm_endpoints.return_value = []
        mock_settings.llm_router_strategy = "fallback"
        with pytest.raises(ValueError, match="At least one LLM endpoint must be configured"):
            LLMRouter(endpoints=None)


# Tests for refresh_health, _probe_endpoint, _update_health


@pytest.mark.asyncio
async def test_refresh_health_returns_results():
    router = LLMRouter(endpoints=_endpoints(), strategy="fallback")
    with patch.object(router, "_probe_endpoint", new_callable=AsyncMock) as mock_probe:
        mock_probe.side_effect = [True, False]
        results = await router.refresh_health()
        assert results["local"] is True
        assert results["cloud"] is False


@pytest.mark.asyncio
async def test_refresh_health_handles_exceptions():
    router = LLMRouter(endpoints=_endpoints(), strategy="fallback")
    with patch.object(router, "_probe_endpoint", new_callable=AsyncMock) as mock_probe:
        mock_probe.side_effect = [Exception("Connection error"), True]
        results = await router.refresh_health()
        assert results["local"] is False
        assert results["cloud"] is True


@pytest.mark.asyncio
async def test_probe_endpoint_success():
    router = LLMRouter(endpoints=_endpoints(), strategy="fallback", health_timeout=5.0)
    endpoint = _endpoints()[0]  # local endpoint

    with patch("src.services.llm_router.httpx.AsyncClient") as mock_client:
        mock_response = AsyncMock()
        mock_response.raise_for_status = AsyncMock()
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_response
        )

        result = await router._probe_endpoint(endpoint)

        assert result is True
        assert router.endpoint_stats["local"].healthy is True


@pytest.mark.asyncio
async def test_probe_endpoint_failure_marks_unhealthy():
    router = LLMRouter(endpoints=_endpoints(), strategy="fallback", health_timeout=5.0)
    endpoint = _endpoints()[0]  # local endpoint

    with patch("src.services.llm_router.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=Exception("Connection refused")
        )

        result = await router._probe_endpoint(endpoint)

        assert result is False
        assert router.endpoint_stats["local"].healthy is False
        assert router.endpoint_stats["local"].cooldown_until is not None


@pytest.mark.asyncio
async def test_update_health_sets_healthy_state():
    router = LLMRouter(endpoints=_endpoints(), strategy="fallback")
    await router._update_health("local", healthy=True, latency_ms=50.0)

    stats = router.endpoint_stats["local"]
    assert stats.healthy is True
    assert stats.health_checks == 1
    assert stats.last_latency_ms == 50.0
    assert stats.last_error is None
    assert stats.cooldown_until is None


@pytest.mark.asyncio
async def test_update_health_sets_unhealthy_state():
    router = LLMRouter(endpoints=_endpoints(), strategy="fallback", cooldown_seconds=60.0)
    await router._update_health("local", healthy=False, error="Connection timeout")

    stats = router.endpoint_stats["local"]
    assert stats.healthy is False
    assert stats.health_checks == 1
    assert stats.last_error == "Connection timeout"
    assert stats.cooldown_until is not None
    assert stats.cooldown_until > time.time()


@pytest.mark.asyncio
async def test_update_health_updates_avg_latency_on_healthy():
    router = LLMRouter(endpoints=_endpoints(), strategy="fallback")
    # First health check
    await router._update_health("local", healthy=True, latency_ms=100.0)
    assert router.endpoint_stats["local"].avg_latency_ms == 100.0

    # Second health check - should update avg latency
    await router._update_health("local", healthy=True, latency_ms=200.0)
    # avg_latency is just set to the latency_ms when healthy (not exponential moving avg in _update_health)
    assert router.endpoint_stats["local"].avg_latency_ms == 200.0


@pytest.mark.asyncio
async def test_probe_endpoint_with_api_key():
    endpoints_with_key = [
        LLMEndpoint(
            name="cloud",
            url="https://api.openai.com/v1",
            api_key="sk-secret-key",
            model="gpt-4o-mini",
            priority=1,
            is_local=False,
        ),
    ]
    router = LLMRouter(endpoints=endpoints_with_key, strategy="fallback")
    endpoint = endpoints_with_key[0]

    with patch("src.services.llm_router.httpx.AsyncClient") as mock_client:
        mock_response = AsyncMock()
        mock_response.raise_for_status = AsyncMock()
        mock_get = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value.get = mock_get

        result = await router._probe_endpoint(endpoint)

        assert result is True
        # Verify the Authorization header was set
        mock_get.assert_called()
        call_kwargs = mock_get.call_args[1]
        assert "Authorization" in call_kwargs["headers"]
        assert call_kwargs["headers"]["Authorization"] == "Bearer sk-secret-key"
