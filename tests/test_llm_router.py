import time

import pytest

from src.config import LLMEndpoint
from src.services.llm_router import LLMRouter


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
