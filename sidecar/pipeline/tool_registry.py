"""
Tool Registry - LangGraph Tool Management Layer

Provides schema generation, registration, and safe execution of LLM tools.
Independent from VaultBrain — the Brain holds a reference to ToolRegistry,
but this module has no dependency on VaultBrain.
"""

import inspect
import json
from typing import Callable, Dict, Any, List, Optional

from loguru import logger


# =========================================================================
# Schema Generation
# =========================================================================

_TYPE_MAP = {
    str: {"type": "string"},
    int: {"type": "integer"},
    float: {"type": "number"},
    bool: {"type": "boolean"},
}


def _type_to_json_schema(py_type: Any) -> Dict[str, Any]:
    """Map a Python type annotation to a JSON Schema fragment."""
    # Direct match
    if py_type in _TYPE_MAP:
        return _TYPE_MAP[py_type].copy()

    # Handle Optional[T] (Union[T, None])
    origin = getattr(py_type, "__origin__", None)
    args = getattr(py_type, "__args__", None)

    if origin is type(None):
        return {"type": "string"}

    # typing.Union — check for Optional pattern (Union[X, None])
    import typing
    if origin is typing.Union and args:
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return _type_to_json_schema(non_none[0])

    # List[T]
    if origin is list and args:
        return {"type": "array", "items": _type_to_json_schema(args[0])}

    # Dict[K, V]
    if origin is dict:
        return {"type": "object"}

    # Fallback
    return {"type": "string"}


def _is_optional_type(py_type: Any) -> bool:
    """Return True if the type is Optional[T] (i.e. Union[T, None])."""
    import typing
    origin = getattr(py_type, "__origin__", None)
    args = getattr(py_type, "__args__", None)
    if origin is typing.Union and args:
        return type(None) in args
    return False


def generate_tool_schema(func: Callable) -> Dict[str, Any]:
    """
    Generate an OpenAI-compatible tool schema from a @tool-decorated function.

    Returns a dict in the format:
    {
        "type": "function",
        "function": {
            "name": "...",
            "description": "...",
            "parameters": { "type": "object", "properties": {...}, "required": [...] }
        }
    }
    """
    if not hasattr(func, "_tool_meta"):
        raise ValueError(
            f"Function '{func.__name__}' must be decorated with @tool"
        )

    meta = func._tool_meta
    sig = inspect.signature(func)

    properties: Dict[str, Any] = {}
    required: List[str] = []

    for param_name, param in sig.parameters.items():
        if param_name == "self":
            continue

        annotation = (
            param.annotation
            if param.annotation != inspect.Parameter.empty
            else str
        )

        is_optional = _is_optional_type(annotation)
        properties[param_name] = _type_to_json_schema(annotation)

        # A parameter is required if it has no default AND is not Optional[T]
        if param.default is inspect.Parameter.empty and not is_optional:
            required.append(param_name)

    return {
        "type": "function",
        "function": {
            "name": meta["name"],
            "description": meta["description"],
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


# =========================================================================
# Tool Registry
# =========================================================================


class ToolRegistry:
    """
    Independent layer for managing LLM tools.

    Responsibilities:
    - Store registered tool functions and their schemas
    - Generate OpenAI-compatible tool definitions
    - Safely wrap and execute tool calls, handling errors gracefully
    - Expose metadata to the UI
    """

    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._schemas: Dict[str, Dict[str, Any]] = {}
        self._logger = logger.bind(component="ToolRegistry")

    # --- Registration ---

    def register(self, func: Callable) -> None:
        """Register a @tool-decorated function."""
        if not hasattr(func, "_tool_meta"):
            raise ValueError(
                f"Function '{func.__name__}' must be decorated with @tool"
            )

        name = func._tool_meta["name"]

        if name in self._tools:
            self._logger.warning(
                f"Overwriting already-registered tool: {name}"
            )

        self._tools[name] = func
        self._schemas[name] = generate_tool_schema(func)
        self._logger.debug(f"Registered tool: {name}")

    def unregister(self, name: str) -> bool:
        """Unregister a tool. Returns True if it existed."""
        if name in self._tools:
            del self._tools[name]
            del self._schemas[name]
            self._logger.debug(f"Unregistered tool: {name}")
            return True
        return False

    # --- Schema Queries ---

    def get_schema(self, name: str) -> Optional[Dict[str, Any]]:
        """Get the OpenAI-compatible schema for a single tool."""
        return self._schemas.get(name)

    def get_all_schemas(self) -> List[Dict[str, Any]]:
        """Get schemas for all registered tools (for passing to the LLM)."""
        return list(self._schemas.values())

    def get_all_metadata(self) -> List[Dict[str, Any]]:
        """Get the rich metadata dicts (for the UI, not for the LLM)."""
        return [func._tool_meta for func in self._tools.values()]

    @property
    def tool_names(self) -> List[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def __len__(self) -> int:
        return len(self._tools)

    # --- Execution ---

    async def execute(self, name: str, arguments: Dict[str, Any]) -> str:
        """
        Safely execute a tool and return a string result.

        This is the ONLY way tool functions should be called by the pipeline.
        Never call plugin functions directly.

        - Handles sync and async functions
        - Catches and formats exceptions
        - Always returns a string (LLM-friendly)
        """
        if name not in self._tools:
            return f"Error: Tool '{name}' not found."

        func = self._tools[name]
        self._logger.info(f"Executing tool '{name}' with args {arguments}")

        try:
            if inspect.iscoroutinefunction(func):
                result = await func(**arguments)
            else:
                result = func(**arguments)

            # Convert result to string for the LLM
            if isinstance(result, (dict, list)):
                return json.dumps(result)
            return str(result)

        except Exception as e:
            self._logger.exception(f"Tool execution failed: {name}")
            return f"Error executing tool {name}: {str(e)}"
