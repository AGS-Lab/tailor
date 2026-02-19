import pytest
from unittest.mock import MagicMock
from sidecar.vault_brain import VaultBrain


@pytest.mark.asyncio
async def test_event_priority():
    # Mock VaultBrain dependencies
    brain = VaultBrain.__new__(VaultBrain)
    # Manually initialize events since we skipped __init__
    from sidecar.event_bus import EventBus

    brain.events = EventBus()

    brain.ws_server = MagicMock()

    execution_order = []

    async def handler_high():
        execution_order.append("high")

    async def handler_medium():
        execution_order.append("medium")

    async def handler_low():
        execution_order.append("low")

    # Subscribe in random order (delegates to brain.events)
    brain.subscribe("test.event", handler_medium, priority=10)
    brain.subscribe("test.event", handler_low, priority=1)
    brain.subscribe("test.event", handler_high, priority=20)

    # Publish sequential
    await brain.publish("test.event", sequential=True)

    assert execution_order == ["high", "medium", "low"]

    # Clean up
    brain.clear_subscribers("test.event")
