"""Tests for the @tool decorator."""

from sidecar.decorators import tool


def test_tool_decorator_adds_metadata():
    @tool(name="my_tool", description="Does something", category="search", visible_to_ui=True)
    def my_function(query: str):
        return f"Result for {query}"

    assert hasattr(my_function, "_tool_meta")
    assert my_function._tool_meta["name"] == "my_tool"
    assert my_function._tool_meta["description"] == "Does something"
    assert my_function._tool_meta["category"] == "search"
    assert my_function._tool_meta["visible_to_ui"] is True


def test_tool_decorator_defaults():
    """Test that decorator uses function name and docstring as defaults."""

    @tool()
    def search_files(query: str):
        """Search for files in the vault."""
        return query

    assert search_files._tool_meta["name"] == "search_files"
    assert search_files._tool_meta["description"] == "Search for files in the vault."
    assert search_files._tool_meta["category"] == "general"
    assert search_files._tool_meta["visible_to_ui"] is True


def test_tool_decorator_preserves_function_behavior():
    """Decorated function should still work normally."""

    @tool(name="add")
    def add(a: int, b: int) -> int:
        return a + b

    assert add(2, 3) == 5


def test_tool_decorator_extra_kwargs():
    """Extra metadata should be stored."""

    @tool(name="my_tool", requires_auth=True, version="1.0")
    def my_function():
        pass

    assert my_function._tool_meta["requires_auth"] is True
    assert my_function._tool_meta["version"] == "1.0"
