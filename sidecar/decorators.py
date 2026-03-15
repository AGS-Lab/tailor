"""
Decorators for Sidecar Command and Event System.

These decorators are used to tag methods in VaultBrain (and potentially plugins)
for automatic registration.
"""

import inspect
from typing import Optional, Callable
from functools import wraps


def command(name: str, plugin_name: Optional[str] = None) -> Callable:
    """
    Decorator to register a method as a named command.

    Args:
        name: The command ID (e.g., 'system.chat')
        plugin_name: Optional plugin name owner (defaults to Core if None)
    """

    def decorator(func: Callable) -> Callable:
        # Attach metadata to the function
        # We use a list because a single function might handle multiple aliases
        if not hasattr(func, "_command_meta"):
            func._command_meta = []

        func._command_meta.append({"id": name, "plugin": plugin_name})

        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def on_event(event_type: str) -> Callable:
    """
    Decorator to subscribe a method to an internal event.

    Args:
        event_type: The event string constant
    """

    def decorator(func: Callable) -> Callable:
        if not hasattr(func, "_event_meta"):
            func._event_meta = []

        func._event_meta.append({"event": event_type})

        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    category: str = "general",
    visible_to_ui: bool = True,
    **extra_meta,
) -> Callable:
    """
    Decorator to expose a function as an LLM tool for LangGraph.

    The decorated function's type hints and docstring are used to auto-generate
    an OpenAI-compatible JSON schema for the LLM.

    Args:
        name: Tool name (defaults to function name).
        description: Tool description for the LLM (defaults to docstring).
        category: Tool category (e.g., 'search', 'filesystem', 'general').
        visible_to_ui: Whether the UI should display this tool.
        **extra_meta: Any additional metadata (e.g., requires_auth=True).
    """

    def decorator(func: Callable) -> Callable:
        tool_meta = {
            "name": name or func.__name__,
            "description": description or func.__doc__ or "No description provided.",
            "category": category,
            "visible_to_ui": visible_to_ui,
            **extra_meta,
        }

        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def wrapper(*args, **kwargs):
                return await func(*args, **kwargs)

        else:

            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

        wrapper._tool_meta = tool_meta
        return wrapper

    return decorator
