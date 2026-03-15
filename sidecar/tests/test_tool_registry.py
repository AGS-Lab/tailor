"""Tests for Tool Schema Generator and ToolRegistry."""

import pytest
from typing import Optional, List, Dict

from sidecar.decorators import tool
from sidecar.pipeline.tool_registry import generate_tool_schema, ToolRegistry


# =========================================================================
# generate_tool_schema Tests
# =========================================================================


def test_generate_tool_schema_basic():
    @tool(name="weather", description="Get weather")
    def get_weather(location: str, unit: Optional[str] = "celsius") -> str:
        """Fetch the weather."""
        pass

    schema = generate_tool_schema(get_weather)

    assert schema["type"] == "function"
    assert schema["function"]["name"] == "weather"
    assert "Get weather" in schema["function"]["description"]
    assert "location" in schema["function"]["parameters"]["properties"]
    assert "unit" in schema["function"]["parameters"]["properties"]
    assert "location" in schema["function"]["parameters"]["required"]
    assert "unit" not in schema["function"]["parameters"]["required"]


def test_generate_tool_schema_no_decorator():
    def plain_function():
        pass

    with pytest.raises(ValueError, match="must be decorated with @tool"):
        generate_tool_schema(plain_function)


def test_generate_tool_schema_type_mapping():
    @tool(name="types_test")
    def func(a: str, b: int, c: float, d: bool) -> str:
        pass

    schema = generate_tool_schema(func)
    props = schema["function"]["parameters"]["properties"]

    assert props["a"]["type"] == "string"
    assert props["b"]["type"] == "integer"
    assert props["c"]["type"] == "number"
    assert props["d"]["type"] == "boolean"


def test_generate_tool_schema_all_required_when_no_defaults():
    @tool(name="all_required")
    def func(x: str, y: int) -> str:
        pass

    schema = generate_tool_schema(func)
    assert schema["function"]["parameters"]["required"] == ["x", "y"]


def test_generate_tool_schema_skips_self():
    """Ensure 'self' parameter is excluded from schema."""

    @tool(name="method_tool")
    def method(self, query: str) -> str:
        pass

    schema = generate_tool_schema(method)
    assert "self" not in schema["function"]["parameters"]["properties"]
    assert "query" in schema["function"]["parameters"]["properties"]


# =========================================================================
# ToolRegistry Tests
# =========================================================================


@pytest.mark.asyncio
async def test_registry_register_and_list():
    registry = ToolRegistry()

    @tool(name="calc", description="Add two numbers")
    def calculate(a: int, b: int) -> int:
        return a + b

    registry.register(calculate)

    assert len(registry) == 1
    assert "calc" in registry.tool_names
    schemas = registry.get_all_schemas()
    assert len(schemas) == 1
    assert schemas[0]["function"]["name"] == "calc"


@pytest.mark.asyncio
async def test_registry_execution_success():
    registry = ToolRegistry()

    @tool(name="calc")
    def calculate(a: int, b: int) -> int:
        return a + b

    registry.register(calculate)

    result = await registry.execute("calc", {"a": 5, "b": 3})
    assert result == "8"  # Always returns string


@pytest.mark.asyncio
async def test_registry_execution_dict_result():
    registry = ToolRegistry()

    @tool(name="info")
    def get_info() -> dict:
        return {"status": "ok", "count": 42}

    registry.register(get_info)

    result = await registry.execute("info", {})
    assert '"status": "ok"' in result
    assert '"count": 42' in result


@pytest.mark.asyncio
async def test_registry_execution_error_capture():
    registry = ToolRegistry()

    @tool(name="crash")
    def crashing_tool():
        raise ValueError("Boom")

    registry.register(crashing_tool)

    error_result = await registry.execute("crash", {})
    assert "Error executing tool crash" in error_result
    assert "Boom" in error_result


@pytest.mark.asyncio
async def test_registry_execution_not_found():
    registry = ToolRegistry()

    result = await registry.execute("nonexistent", {})
    assert "not found" in result


@pytest.mark.asyncio
async def test_registry_async_tool():
    registry = ToolRegistry()

    @tool(name="async_search")
    async def search(query: str) -> str:
        return f"Results for {query}"

    registry.register(search)

    result = await registry.execute("async_search", {"query": "hello"})
    assert result == "Results for hello"


@pytest.mark.asyncio
async def test_registry_unregister():
    registry = ToolRegistry()

    @tool(name="temp")
    def temp_tool():
        return "hi"

    registry.register(temp_tool)
    assert len(registry) == 1

    removed = registry.unregister("temp")
    assert removed is True
    assert len(registry) == 0

    not_removed = registry.unregister("temp")
    assert not_removed is False


def test_registry_metadata():
    registry = ToolRegistry()

    @tool(name="search", category="search", visible_to_ui=True)
    def search_files(query: str) -> str:
        """Search files in the vault."""
        return query

    registry.register(search_files)

    metadata = registry.get_all_metadata()
    assert len(metadata) == 1
    assert metadata[0]["name"] == "search"
    assert metadata[0]["category"] == "search"
    assert metadata[0]["visible_to_ui"] is True


def test_registry_rejects_undecorated():
    registry = ToolRegistry()

    def plain_func():
        pass

    with pytest.raises(ValueError, match="must be decorated with @tool"):
        registry.register(plain_func)
