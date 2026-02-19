"""
Tests for Decorators.
"""

import pytest
from sidecar.decorators import command, on_event


def test_command_decorator():
    """Test command decorator attached metadata."""

    @command("test.cmd", plugin_name="MyPlugin")
    async def my_func():
        pass

    assert hasattr(my_func, "_command_meta")
    meta = my_func._command_meta[0]
    assert meta["id"] == "test.cmd"
    assert meta["plugin"] == "MyPlugin"


def test_command_decorator_default_plugin():
    """Test command decorator with default plugin."""

    @command("test.cmd")
    async def my_func():
        pass

    assert my_func._command_meta[0]["plugin"] is None


def test_on_event_decorator():
    """Test on_event decorator attached metadata."""

    @on_event("system.ready")
    async def my_handler():
        pass

    assert hasattr(my_handler, "_event_meta")
    assert my_handler._event_meta[0]["event"] == "system.ready"


@pytest.mark.asyncio
async def test_decorators_preserve_behavior():
    """Test that decorators don't break function execution."""

    @command("test")
    async def echo(msg):
        return msg

    result = await echo("hello")
    assert result == "hello"
