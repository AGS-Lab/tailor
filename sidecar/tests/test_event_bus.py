"""
Tests for EventBus.
"""

import pytest
from unittest.mock import AsyncMock
from sidecar.event_bus import EventBus


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.mark.asyncio
async def test_subscribe_validation(event_bus):
    """Test validation of async handlers."""

    def sync_handler():
        pass

    with pytest.raises(ValueError, match="Handler must be async"):
        event_bus.subscribe("test", sync_handler)


@pytest.mark.asyncio
async def test_subscribe_priority(event_bus):
    """Test that handlers are sorted by priority."""
    call_order = []

    async def handler_low(**kwargs):
        call_order.append("low")

    async def handler_high(**kwargs):
        call_order.append("high")

    async def handler_mid(**kwargs):
        call_order.append("mid")

    event_bus.subscribe("test", handler_low, priority=0)
    event_bus.subscribe("test", handler_high, priority=100)
    event_bus.subscribe("test", handler_mid, priority=50)

    await event_bus.publish("test", sequential=True)

    assert call_order == ["high", "mid", "low"]


@pytest.mark.asyncio
async def test_unsubscribe(event_bus):
    """Test unsubscribing handlers."""
    mock_handler = AsyncMock()

    event_bus.subscribe("test", mock_handler)

    # Should find and remove
    assert event_bus.unsubscribe("test", mock_handler) is True

    # Should not find again
    assert event_bus.unsubscribe("test", mock_handler) is False

    await event_bus.publish("test")
    mock_handler.assert_not_called()


@pytest.mark.asyncio
async def test_clear_subscribers(event_bus):
    """Test clearing all subscribers."""
    mock_handler = AsyncMock()
    event_bus.subscribe("test", mock_handler)

    event_bus.clear_subscribers("test")

    await event_bus.publish("test")
    mock_handler.assert_not_called()


@pytest.mark.asyncio
async def test_publish_sequential(event_bus):
    """Test sequential execution (await one by one)."""
    # We can verify sequential by having the first handler add a delay
    # and checking timestamps, or simply trusting the implementation iterating.
    # Here we just check they all run.
    h1 = AsyncMock()
    h2 = AsyncMock()

    event_bus.subscribe("test", h1)
    event_bus.subscribe("test", h2)

    await event_bus.publish("test", sequential=True, arg="value")

    h1.assert_called_with(arg="value")
    h2.assert_called_with(arg="value")


@pytest.mark.asyncio
async def test_publish_parallel(event_bus):
    """Test parallel execution (gather)."""
    h1 = AsyncMock()
    h2 = AsyncMock()

    event_bus.subscribe("test", h1)
    event_bus.subscribe("test", h2)

    await event_bus.publish("test", sequential=False, arg="parallel")

    h1.assert_called_with(arg="parallel")
    h2.assert_called_with(arg="parallel")


@pytest.mark.asyncio
async def test_handler_error_safety(event_bus):
    """Test that one handler failing doesn't stop others."""

    async def failing_handler(**kwargs):
        raise RuntimeError("Oops")

    working_handler = AsyncMock()

    event_bus.subscribe("test", failing_handler, priority=10)
    event_bus.subscribe("test", working_handler, priority=0)

    # Should not raise exception
    await event_bus.publish("test", sequential=True)

    working_handler.assert_called()
