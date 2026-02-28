# Tailor — Architecture

## Overview

Three processes communicate over WebSocket (JSON-RPC 2.0):

```
Frontend (Vite/JS)
       ↕ Tauri IPC
Rust/Tauri Backend  ←→  Python Sidecar
  (per vault)           (per vault process, port 9000+)
```

The Rust backend is the process manager and IPC router. The Python sidecar is the intelligence layer. The frontend is the UI shell.

---

## Rust Backend (`src-tauri/src/`)

Three singletons initialized in `main.rs`, stored in Tauri app state:

| Singleton | File | Responsibility |
|-----------|------|----------------|
| `WindowManager` | `window_manager.rs` | Tracks window↔vault mappings, creates windows (1200×800, no decorations) |
| `SidecarManager` | `sidecar_manager.rs` | Spawns/kills Python processes, allocates ports, sends JSON-RPC commands |
| `EventBus` | `event_bus.rs` | **Currently unused** — created but never routes events in practice |

**`ipc_router.rs`** exposes 23 Tauri commands. Key groups:
- Vault ops: `open_vault`, `close_vault`, `create_vault`, `list_vaults`, `get_vault_info`
- Plugin ops: `get_installed_plugins`, `install_plugin`, `update_plugin_config`
- Settings: `get_effective_settings` (merges global defaults → AppData settings.toml → vault `.vault.toml`)
- API keys: proxied through to Python sidecar via `send_command`

**`sidecar_manager.rs`** flow:
1. Checks port availability via `TcpListener::bind`, increments from 9000
2. Spawns `python -m sidecar --vault <path> --ws-port <port>`
3. `send_command()` opens a fresh WebSocket connection per request, sends JSON-RPC, awaits response

**`dependency_checker.rs`** auto-installs plugin Python deps on vault open (reads `requirements.txt` from each plugin dir).

---

## Python Sidecar (`sidecar/`)

Entry point: `python -m sidecar --vault <path> --ws-port <port>`

### VaultBrain (`vault_brain.py`) — Singleton Orchestrator

The central object. Holds:
- **Command registry** — maps `command_id → handler function`
- **Plugin registry** — maps `plugin_name → Plugin instance`
- **Internal EventBus** (`event_bus.py`) — pub/sub with priority, for plugin↔plugin events
- **Pipeline** — `DefaultPipeline` (linear LangGraph) or `GraphPipeline`, chosen via vault config
- **LLMService** — set as module-level singleton in `services/llm_service.py`

Two-phase plugin initialization:
1. **Phase 1**: Instantiate plugin → call `register_commands()`
2. **Phase 2**: Call `on_load()` → subscribe plugin to TICK event

Built-in commands (registered by VaultBrain itself, not plugins):
`system.info`, `system.chat`, `settings.*`, `chat.send`, `chat.set_model`, `chat.get_history`, `plugins.install`, `plugins.toggle`, `plugins.reload`, `keyring.*`, and others.

### WebSocket Server (`websocket_server.py`)

- Listens on `0.0.0.0:<port>`, handles one client connection at a time
- Incoming: JSON-RPC `method` → routed to `VaultBrain.execute_command()`
- Outgoing: `send_to_rust()` queues messages if no connection yet, sends as JSON-RPC notifications

### Plugin Base (`api/plugin_base.py`)

All plugins inherit `PluginBase`. Key APIs available to plugin code:

```python
# Lifecycle
register_commands()   # Phase 1: register commands with self.brain
on_load()             # Phase 2: setup, subscribe to events
on_tick()             # Called on every tick
on_unload()           # Cleanup

# UI
self.register_sidebar_view(id, label, icon, html)
self.register_panel(id, title, html)
self.register_toolbar_button(id, label, icon, command)
self.show_modal(title, html, width, height)
self.notify(message)

# Data
self.emit(event_type, data)        # → frontend
self.publish(event_type, data)     # → internal event bus
self.subscribe(event_type, handler)
self.load_settings() / save_settings()
```

`self.brain` lazy-loads the VaultBrain singleton.

### Pipeline (`pipeline/`)

`DefaultPipeline` uses LangGraph `StateGraph`:
```
input → context → prompt → llm → post_process → output
```

`stream_run()` is an async generator yielding tokens. VaultBrain emits:
- `CHAT_STREAM_START` → `CHAT_TOKEN` (per token) → `CHAT_STREAM_END`

LiteLLM handles multi-provider model access. Model selection is category-based (fast, thinking, vision, code, embedding) configured in `.vault.toml`.

### Pipeline (`pipeline/`) — internals

| File | Purpose |
|------|---------|
| `default.py` | `DefaultPipeline` — linear LangGraph StateGraph |
| `graph.py` | `GraphPipeline` — placeholder for power-user LangGraph workflows; falls back to DefaultPipeline |
| `types.py` | `PipelineConfig` (Pydantic: category, temperature, max_tokens, streaming) and `PipelineContext` (mutable state object passed through nodes) |
| `nodes.py` | `PipelineNodes` — actual node implementations: input, context, prompt. Publishes to brain event bus at each phase. |
| `events.py` | `PipelineEvents` constants: START, END, ERROR, INPUT, CONTEXT, PROMPT, LLM, POST_PROCESS, OUTPUT |
| `studio_entrypoint.py` | Exports compiled graph for LangGraph Studio visualization (dev tool) |

### Services (`services/`)

| Service | Purpose |
|---------|---------|
| `llm_service.py` | LiteLLM wrapper, category-based model selection, Ollama auto-detection |
| `keyring_service.py` | Secure API key storage, injects keys as env vars for LiteLLM |
| `memory/` | Conversation memory, chat history |

### Sidecar Infrastructure

| File | Purpose |
|------|---------|
| `constants.py` | JSON-RPC error codes, timing constants (tick interval, WS timeout/ping), env var names, `EventType` + `Severity` enums |
| `exceptions.py` | `TailorError` base with `.to_dict()` for JSON-RPC. Subclasses: `VaultError`, `PluginError`, `PipelineError`, `WebSocketError`, `ConfigError`, etc. |
| `utils.py` | Loguru setup, JSON-RPC helpers, path utilities, `generate_id()`, env var handling |
| `decorators.py` | `@command(name, plugin_name)` and `@on_event(event_type)` — declarative registration of methods as commands/handlers |
| `plugin_installer.py` | Full plugin package manager: install from HTTP URL (zip) or git, validate, check deps, update, remove. `InstallStatus` enum + `InstallResult`/`ValidationResult` dataclasses. |

---

## Frontend (`src/`)

Vanilla JavaScript, bundled with Vite. Two entry points:

- **Dashboard** (`src/index.html`) — vault launcher, settings, themes
- **Vault window** (`src/vault/main.js`) — chat + plugin UI

### Dashboard Pages (`src/pages/`)

| Page | File | Purpose |
|------|------|---------|
| Dashboard | `dashboard.js` | Vault list with filter, quick actions, vault creation/opening |
| Settings | `settings.js` | Global settings — theme toggle, API keys, appearance |
| Themes | `themes.js` | Theme store; loads `/theme-registry.json`, applies CSS variables, persists to localStorage + backend |
| Vault Settings | `vault-settings.js` | Per-vault config tabs: General, AI Models, API Keys, Plugins (with hot-reload signals) |

### Vault Window Architecture

```
main.js
  ├── connection.js        WebSocket client (JSON-RPC 2.0, auto-reconnect)
  ├── layout.js            GoldenLayout workspace config (chat, toolbox, log, inspector, stage panels)
  ├── plugins.js           Plugin event handler — translates backend events into UI actions
  ├── settings.js          Dynamic settings UI generator (TOML → form elements)
  ├── chat/chat.js         Chat UI with streaming support
  ├── managers/
  │   ├── SidebarManager.js   Activity bar + content panels
  │   ├── PanelManager.js     GoldenLayout panel management
  │   ├── ToolbarManager.js   Top toolbar buttons
  │   ├── ModalManager.js     Dialog overlays
  │   └── ToolboxManager.js   Stage/toolbox area
  └── plugin-store.js      Plugin install/update UI
```

**`plugins.js`** is the glue layer — it listens for `sidecar-event` notifications and dispatches them to the right manager (`registerSidebarView`, `registerPanel`, `setContent`, CSS/HTML injection). This is how backend plugins become frontend UI.

**`layout.js`** defines the GoldenLayout workspace with five registered component types: `chat`, `toolbox`, `log`, `controls` (Inspector), and `stage`. Also handles the sidebar resize interaction.

**`settings.js`** (vault window) auto-generates form UI from `.vault.toml` sections: booleans → toggles, numbers → number inputs, objects → nested subsections. Fixed tabs: API Keys, Model Categories, Themes.

`window.request(method, params)` — global function for sending JSON-RPC commands to sidecar. Plugins call this to invoke commands.

`window.ui` — global API exposing manager methods for plugin use (`registerSidebarView`, `registerPanel`, `showModal`, etc.).

### Connection (`connection.js`)

- Single WebSocket connection per vault window
- Auto-reconnect: exponential backoff, 500ms → 5s max, 10 attempts
- Port resolution order: explicit param → URL param → Tauri IPC → default 9002
- Incoming `trigger_event` notifications dispatched as `CustomEvent` on `document`

### Chat (`chat/chat.js`)

- Streaming: listens for `chat:token` events, appends tokens to active message
- Chat ID per conversation (for memory integration)
- Model selector reads from `settings.get_available_models`

---

## Example Vault Plugins (`example-vault/plugins/`)

Working reference implementations. Read these before writing a new plugin.

| Plugin | What it demonstrates |
|--------|---------------------|
| `demo_plugin` | Minimal PluginBase usage — commands, notify, basic lifecycle |
| `demo_ui` | Full UI API showcase — sidebar, panels, toolbar, modal |
| `explorer` | Sidebar with chat history list (reads from Memory plugin) |
| `memory` | JSON persistence layer for chat history; shows cross-plugin data sharing |
| `chat_branches` | Branch management for multi-path conversations |
| `summarizer` | Runs LLM call inside a plugin, stores result, shows TL;DR in toolbar |
| `prompt_refiner` | Intercepts user message, improves it via LLM before sending |
| `event_test` | Exercises the event system for debugging |
| `smart_context` | Early-stage context panel (shows wiring, not feature-complete) |

---

## Data Flow: Open Vault → First Chat Message

```
1. User picks vault in dashboard
2. Frontend → Tauri IPC: open_vault(path)
3. Rust: SidecarManager.spawn_sidecar(path) → allocates port, spawns Python
4. Rust: WindowManager creates vault window, passes port via URL param
5. Vault window loads, connection.js connects to ws://localhost:<port>
6. Plugin Phase 1+2 init runs in VaultBrain
7. User types message → window.request('chat.send', {message, stream: true})
8. WebSocket → VaultBrain.handle_chat()
9. Pipeline.stream_run() → LiteLLM → tokens streamed back
10. VaultBrain emits CHAT_TOKEN events → websocket_server.send_to_rust()
11. Frontend receives trigger_event → chat.js appends token to UI
```

---

## Plugin Config: How It's Loaded

```
settings.json (plugin defaults)
    ↓ merged with
.vault.toml [plugins.plugin_name] (vault overrides)
    ↓ = effective plugin config
```

Config is TOML. Reading uses `tomllib`. Writing must use `tomli_w`. See `INCONSISTENCIES.md` for a bug where one write path uses `json.dump` instead.

---

## Update Protocol

After touching a component, update the relevant section here. If a new module is added, add it to the appropriate table or list. Keep file paths and line number references accurate — stale references are worse than no references.
