# LangGraph Tool Registry Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Implement a LangGraph Tool Registry that allows Python plugins to expose functions as LLM tools, separate from `VaultBrain`, with metadata support and safe execution wrapping.

**Architecture:**
- Create `@tool` decorator in `sidecar.decorators` with metadata support (`category`, `visible_to_ui`, etc).
- Create `ToolRegistry` class in `sidecar.pipeline.tool_registry` to discover, parse, and store tool schemas.
- Create `ToolExecutor` class to safely wrap function calls, handle exceptions, and format outputs for the LLM.
- Connect the registry to `VaultBrain` so plugins can register tools during initialization, and the UI can fetch tool metadata.

**Tech Stack:** Python 3.12, Pydantic (for schema generation), `inspect` module (for signature parsing).

---

### Task 1: Create `@tool` Decorator

**Files:**
- Modify: `e:/tailor/sidecar/decorators.py`
- Create: `e:/tailor/sidecar/tests/test_tool_decorator.py`

**Step 1: Write the failing test**

```python
# e:/tailor/sidecar/tests/test_tool_decorator.py
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
```

**Step 2: Run test to verify it fails**

Run: `pixi run pytest sidecar/tests/test_tool_decorator.py -v`
Expected: FAIL (ImportError: cannot import name 'tool' from 'sidecar.decorators')

**Step 3: Write minimal implementation**

```python
# In e:/tailor/sidecar/decorators.py (add to existing file)
from typing import Optional, Callable
from functools import wraps
import inspect

def tool(
    name: Optional[str] = None, 
    description: Optional[str] = None, 
    category: str = "general",
    visible_to_ui: bool = True,
    **kwargs
) -> Callable:
    """
    Decorator to expose a function as an LLM tool for LangGraph.
    """
    def decorator(func: Callable) -> Callable:
        if not hasattr(func, "_tool_meta"):
            func._tool_meta = {
                "name": name or func.__name__,
                "description": description or func.__doc__ or "No description provided.",
                "category": category,
                "visible_to_ui": visible_to_ui,
                **kwargs
            }
        
        @wraps(func)
        async def async_wrapper(*args, **async_kwargs):
            return await func(*args, **async_kwargs)
            
        @wraps(func)
        def sync_wrapper(*args, **sync_kwargs):
            return func(*args, **sync_kwargs)
            
        if inspect.iscoroutinefunction(func):
            wrapper = async_wrapper
        else:
            wrapper = sync_wrapper
            
        # Copy the meta to the wrapper
        wrapper._tool_meta = func._tool_meta
        return wrapper
        
    return decorator
```

**Step 4: Run test to verify it passes**

Run: `pixi run pytest sidecar/tests/test_tool_decorator.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add sidecar/decorators.py sidecar/tests/test_tool_decorator.py
git commit -m "feat(pipeline): add @tool decorator with metadata support"
```

---

### Task 2: Create Tool Schema Generator

**Files:**
- Create: `e:/tailor/sidecar/pipeline/tool_registry.py`
- Create: `e:/tailor/sidecar/tests/test_tool_registry.py`

**Step 1: Write the failing test**

```python
# e:/tailor/sidecar/tests/test_tool_registry.py
from typing import Optional
from sidecar.decorators import tool
from sidecar.pipeline.tool_registry import generate_tool_schema

def test_generate_tool_schema():
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
```

**Step 2: Run test to verify it fails**

Run: `pixi run pytest sidecar/tests/test_tool_registry.py -v`
Expected: FAIL (ModuleNotFoundError or ImportError)

**Step 3: Write minimal implementation**

```python
# In e:/tailor/sidecar/pipeline/tool_registry.py
import inspect
from typing import Callable, Dict, Any, get_type_hints, List

def _type_to_json_schema(py_type: Any) -> Dict[str, Any]:
    """Map python types to JSON schema types."""
    if py_type == str: return {"type": "string"}
    if py_type == int: return {"type": "integer"}
    if py_type == float: return {"type": "number"}
    if py_type == bool: return {"type": "boolean"}
    # Simplified fallback if type is unknown or None
    return {"type": "string"}

def generate_tool_schema(func: Callable) -> Dict[str, Any]:
    """Generate OpenAI-compatible tool schema from a decorated function."""
    if not hasattr(func, "_tool_meta"):
        raise ValueError("Function must be decorated with @tool")
        
    meta = func._tool_meta
    sig = inspect.signature(func)
    
    properties = {}
    required = []
    
    for name, param in sig.parameters.items():
        if name == "self":
            continue
            
        param_type = param.annotation if param.annotation != inspect.Parameter.empty else str
        
        # Handle simple Optional[T] gracefully for the schema
        is_optional = False
        if getattr(param_type, "__origin__", None) is getattr(type(None), "__origin__", None):
            is_optional = True
            
        properties[name] = _type_to_json_schema(param_type)
        
        if param.default == inspect.Parameter.empty and not is_optional:
            required.append(name)
            
    return {
        "type": "function",
        "function": {
            "name": meta["name"],
            "description": meta["description"],
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }
    }
```

**Step 4: Run test to verify it passes**

Run: `pixi run pytest sidecar/tests/test_tool_registry.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add sidecar/pipeline/tool_registry.py sidecar/tests/test_tool_registry.py
git commit -m "feat(pipeline): implement tool schema generation"
```

---

### Task 3: Create ToolRegistry and Execution Wrapper

**Files:**
- Modify: `e:/tailor/sidecar/pipeline/tool_registry.py`
- Modify: `e:/tailor/sidecar/tests/test_tool_registry.py`

**Step 1: Write the failing test**

```python
# Append to e:/tailor/sidecar/tests/test_tool_registry.py
import pytest
from sidecar.pipeline.tool_registry import ToolRegistry

@pytest.mark.asyncio
async def test_registry_registration_and_execution():
    registry = ToolRegistry()
    
    @tool(name="calc")
    def calculate(a: int, b: int) -> int:
        return a + b
        
    @tool(name="crash")
    def crashing_tool():
        raise ValueError("Boom")
        
    registry.register(calculate)
    registry.register(crashing_tool)
    
    # Test Metadata
    schemas = registry.get_all_schemas()
    assert len(schemas) == 2
    
    # Test Execution Wrapper (Success)
    result = await registry.execute("calc", {"a": 5, "b": 3})
    assert result == "8" # Returns string for LLM
    
    # Test Execution Wrapper (Exception Capture)
    error_result = await registry.execute("crash", {})
    assert "Error executing tool crash" in error_result
    assert "Boom" in error_result
```

**Step 2: Run test to verify it fails**

Run: `pixi run pytest sidecar/tests/test_tool_registry.py::test_registry_registration_and_execution -v`
Expected: FAIL (ImportError ToolRegistry)

**Step 3: Write minimal implementation**

```python
# Append to e:/tailor/sidecar/pipeline/tool_registry.py
import json
from loguru import logger

class ToolRegistry:
    """Independent layer for managing LLM tools."""
    
    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._schemas: Dict[str, Dict[str, Any]] = {}
        self._logger = logger.bind(component="ToolRegistry")
        
    def register(self, func: Callable) -> None:
        """Register a @tool decorated function."""
        if not hasattr(func, "_tool_meta"):
            raise ValueError(f"Function {func.__name__} must be decorated with @tool")
            
        name = func._tool_meta["name"]
        self._tools[name] = func
        self._schemas[name] = generate_tool_schema(func)
        self._logger.debug(f"Registered tool: {name}")
        
    def get_schema(self, name: str) -> Optional[Dict[str, Any]]:
        return self._schemas.get(name)
        
    def get_all_schemas(self) -> List[Dict[str, Any]]:
        return list(self._schemas.values())
        
    def get_all_metadata(self) -> List[Dict[str, Any]]:
        """Return the rich plugin metadata for the UI (not just the LLM schema)"""
        return [func._tool_meta for func in self._tools.values()]
        
    async def execute(self, name: str, arguments: Dict[str, Any]) -> str:
        """
        Safely wrap and execute a tool function.
        Always returns a string (the format expected by LLMs).
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
```

**Step 4: Run test to verify it passes**

Run: `pixi run pytest sidecar/tests/test_tool_registry.py::test_registry_registration_and_execution -v`
Expected: PASS

**Step 5: Commit**

```bash
git add sidecar/pipeline/tool_registry.py sidecar/tests/test_tool_registry.py
git commit -m "feat(pipeline): implement ToolRegistry layer with safe execution wrapper"
```

---

### Task 4: Integrate ToolRegistry with VaultBrain

**Files:**
- Modify: `e:/tailor/sidecar/vault_brain.py`

**Step 1: Write the failing test**

*(We will rely on existing integration pipelines and test via manual startup/typing since injecting tools inside a mock VaultBrain structure is complex and brittle for a unit test.)*

**Step 2: Write minimal implementation**

```python
# In e:/tailor/sidecar/vault_brain.py
# 1. Add import around line 27:
from .pipeline.tool_registry import ToolRegistry

# 2. In __init__ around line 95:
def __init__(self, ...):
    ...
    # active stream tracking for cancellation
    self._active_streams: Dict[str, bool] = {}
    
    # LangGraph Tool Registry (Independent Layer)
    self.tool_registry = ToolRegistry()
    ...

# 3. Add a new command at the bottom of the file to expose tool metadata and schemas to UI
@command("system.list_tools", constants.CORE_PLUGIN_NAME)
async def list_tools(self) -> Dict[str, Any]:
    """List all registered LangGraph tools and their schemas."""
    schemas = self.tool_registry.get_all_schemas()
    metadata = self.tool_registry.get_all_metadata()
    return {
        "status": "success", 
        "tools": schemas,
        "metadata": metadata
    }
```

**Step 3: Run test to verify integration**

Run: `pixi run pytest sidecar/tests -v`
(Ensure nothing broke by modifying `VaultBrain`)

**Step 4: Commit**

```bash
git add sidecar/vault_brain.py
git commit -m "feat(core): integrate ToolRegistry with VaultBrain and expose system.list_tools command"
```

---

Plan complete and saved to `docs/plans/2026-03-14-langgraph-tool-registry.md`.
**Next step: run `.agent/workflows/execute-plan.md` to execute this plan task-by-task in single-flow mode.**
