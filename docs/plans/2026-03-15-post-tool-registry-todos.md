# TODO — Post Tool Registry & Visualization

> Generated: 2026-03-15
> Context: After implementing the LangGraph Tool Registry, Pipeline Visualization, and Plugin Architecture documentation.

---

## ✅ Completed (This Session)

- [x] `@tool` decorator with rich metadata (`decorators.py`)
- [x] `ToolRegistry` class — register, schema gen, safe execute (`pipeline/tool_registry.py`)
- [x] `system.list_tools` RPC command (`vault_brain.py`)
- [x] `system.get_graph` RPC command with Mermaid serialization (`vault_brain.py`)
- [x] Pipeline visualization panel — Mermaid.js CDN rendering (`pipeline-graph.js`, `layout.js`)
- [x] Plugin Architecture doc — 4 types, taxonomy, diagrams (`docs/system/PLUGIN-ARCHITECTURE.md`)
- [x] Updated all docs: CLAUDE.md, ARCHITECTURE.md, VISION.md, PLUGIN_GUIDE.md, PLUGIN_COMMANDS.md
- [x] All tests passing: 187 passed, 0 failed

---

## 🔶 Polish (Quick Fixes)

- [ ] **P2** — Fix "OpenAI-compatible" terminology → "standard function-calling schema (LiteLLM-compatible)" across docs
- [ ] **P2** — Bundle Mermaid.js via npm instead of CDN (offline support)
- [ ] **P3** — Pipeline panel auto-refresh on plugin install/uninstall events
- [ ] **P3** — Pipeline viz sizing — test with more complex graphs, ensure responsive fit

---

## 🔴 Critical Gaps

### P0 — Pass tool schemas to LLM calls

**Status:** Not started
**Effort:** Small (1 file change)
**What:** `DefaultPipeline` doesn't include `tools=schemas` when calling LiteLLM. Without this, the LLM never knows tools exist.
**Where:** `sidecar/pipeline/nodes.py` — modify the LLM node to inject `tool_registry.get_all_schemas()` into `litellm.completion()`.

---

### P0 — Tool execution loop (agent loop)

**Status:** Not started
**Effort:** Medium
**What:** When the LLM returns a `tool_call`, nothing processes it. Need the agent loop:
```
User message → LLM → tool_call? → execute tool → feed result back → LLM → final response
```
**Where:** New node in `pipeline/nodes.py` or a conditional edge in the `StateGraph`.
**Note:** This is the difference between "LLM that knows about tools" and "LLM that can use tools."

---

### P1 — Build first real `@tool` plugin

**Status:** Not started
**Effort:** Small
**What:** Zero plugins currently use `@tool`. Need at least one to prove the system end-to-end.
**Candidates:** Web search, vault file search, URL reader.

---

### P1 — Auto-discover `@tool` methods in plugins

**Status:** Not started
**Effort:** Small
**What:** Plugins must manually call `tool_registry.register()`. Auto-scan for `_tool_meta` during plugin loading.
**Where:** `VaultBrain._load_plugins()` — after instantiating a plugin, scan its methods for `_tool_meta` and auto-register.

---

### P2 — Action tool confirmation UI

**Status:** Not started
**Effort:** Medium
**What:** `category="action"` tools (side effects) should show a confirmation dialog before execution. `category="information"` tools run freely.
**Where:** Frontend modal + backend hook in `ToolRegistry.execute()`.

---

### P3 — Implement `GraphPipeline` properly

**Status:** Stub exists, falls back to `DefaultPipeline`
**Effort:** Large
**What:** `graph.py` is a placeholder. For proper tool usage, need cyclical agent pattern with conditional edges.
**Where:** `sidecar/pipeline/graph.py`

---

## Priority Summary

| Priority | Item | Effort | Blocks |
|----------|------|--------|--------|
| **P0** | Pass tool schemas to LLM | Small | Everything tool-related |
| **P0** | Tool execution loop | Medium | Actual tool usage |
| **P1** | First `@tool` plugin | Small | End-to-end proof |
| **P1** | Auto-discover `@tool` methods | Small | DX, scale |
| **P2** | Action tool confirmation UI | Medium | Safety for write tools |
| **P2** | Fix doc terminology | Small | Clarity |
| **P2** | Bundle Mermaid.js | Small | Offline support |
| **P3** | Pipeline auto-refresh | Small | UX polish |
| **P3** | GraphPipeline implementation | Large | Advanced workflows |
