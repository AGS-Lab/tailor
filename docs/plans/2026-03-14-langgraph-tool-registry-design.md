# LangGraph Tool Registry Design

## Context
Tailor relies on a Python Sidecar for backend operations. Plugins use the `@command` decorator to register remote procedure calls (RPC) that the frontend can trigger.

We now want to expose these tools dynamically to a LangGraph-powered LLM pipeline so the LLM can decide when to trigger them autonomously.

## Requirements
1. The system must discover Python plugins and any functionality they wish to expose.
2. The exposed functions should be converted into the format LangGraph/LiteLLM expects for tool calling (JSON Schema definitions of parameters).
3. The UI needs to be aware of what tools the LLM has access to (exposing metadata).
4. Tool execution needs to be routed back to the appropriate sidecar plugin command.

## Approaches

### Approach 1: `@tool` Decorator (Recommended)
Create a new `@tool` decorator specifically for LangGraph. 
* Plugins decorate functions they want to expose to the LLM with `@tool(name, description)`.
* They use standard Python type hints and docstrings.
* `VaultBrain` reads these decorators during `_load_plugins()`, uses Python's `inspect` module to generate the JSON schemas, and registers them in a new `self.tools` registry.
* **Pros**: Clean separation of concerns. A function can be an RPC command, an LLM tool, or both. Familiar to developers used to LangChain.
* **Cons**: Requires plugin developers to add a second decorator if they want a function to be both a UI command and an LLM tool.

### Approach 2: Overload `@command` Decorator
Extend the existing `@command` decorator to accept a `expose_as_tool=True` flag.
* When registering commands, `VaultBrain` automatically generates schemas for any command with this flag.
* **Pros**: Less boilerplate for developers. One decorator rules them all.
* **Cons**: UI commands and LLM tools often need different parameter structures or descriptions. Tying them together might limit flexibility. UI commands expect `chat_id` and other internal kwargs that the LLM shouldn't see.

### Approach 3: Manifest-based Tool Definition
Plugins define their tools in a JSON or YAML manifest file (e.g., `tools.json`), mapping tool names to specific Python methods.
* **Pros**: Very explicit. Doesn't require scanning decorators. Easy to expose to the UI quickly.
* **Cons**: Duplication of effort. Developers have to write the schema manually and keep it in sync with the Python function signature.

## Recommendation
**Approach 1 (`@tool` Decorator)** is the most robust and flexible. While overloading `@command` seems easier, LLM tools specifically need very high-quality descriptions and strongly typed parameters to prevent hallucinations, whereas UI commands are usually hardcoded to exact payloads. Separating them allows developers to optimize the docstring specifically for the LLM without breaking UI behavior.

## User Review Required
Does **Approach 1** align with your mental model for how plugin developers should expose their tools to the LLM?
