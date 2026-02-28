# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is Tailor

Tailor is a modular AI assistant desktop framework built with Tauri. Users open "vaults" (project directories), each running an isolated Python sidecar process. Plugins are self-contained Python directories inside the vault that can register commands, emit UI events, and participate in LLM pipelines.

## Commands

**Primary tool: `pixi`** — manages Python, Node.js, and Rust environments together.

```bash
pixi run dev           # Start Vite dev server + Tauri window
pixi run build         # Production build
pixi run test          # Run Python (sidecar) tests
pixi run test-rust     # Run Rust tests
pixi run lint          # Check Python with ruff
pixi run format        # Format Python with ruff
pixi run sidecar       # Run sidecar standalone (for debugging)
pixi run install-frontend  # Install npm deps
```

**Running a single Python test:**
```bash
pixi run pytest sidecar/tests/test_vault_brain.py
pixi run pytest sidecar/tests/test_vault_brain.py::test_function_name
```

**Frontend tests (via npm):**
```bash
npm run test
```

## Architecture

Three processes communicate over WebSocket (JSON-RPC 2.0):

```
Frontend (Vite/JS)  ←→  Rust/Tauri Backend  ←→  Python Sidecar
                         (per vault)              (per vault process)
```

### Rust Backend (`src-tauri/src/`)

- `main.rs` — Initializes three singletons: `WindowManager`, `SidecarManager`, `EventBus`
- `sidecar_manager.rs` — Spawns/kills isolated Python processes per vault; allocates ports starting at 9000
- `window_manager.rs` — Tracks vault window lifecycle
- `event_bus.rs` — Routes events with three scopes: `window` (one window), `vault` (all windows sharing a vault), `global` (all windows)
- `ipc_router.rs` — Tauri command handlers (open vault, close vault, get info, etc.)
- `dependency_checker.rs` — Auto-installs plugin Python dependencies on vault open

### Python Sidecar (`sidecar/`)

- `main.py` — CLI entry point, logging setup
- `websocket_server.py` — JSON-RPC 2.0 server; bridges Rust ↔ Python
- `vault_brain.py` — Singleton orchestrator: loads plugins, manages command registry, event bus, LLM pipelines
- `api/plugin_base.py` — Abstract base class all plugins must inherit from
- `pipeline/` — LLM processing (DefaultPipeline, GraphPipeline using LangGraph + LiteLLM)
- `services/` — LLM service, keyring, memory

### Plugin System

Plugins live at `vault/plugins/<name>/main.py`. The Plugin class inherits `PluginBase` and implements:
- `register_commands()` — register callable commands (VSCode-style command palette)
- `on_load()`, `on_tick()`, `on_unload()` — lifecycle hooks

See `example-vault/plugins/` for working examples and `docs/PLUGIN_GUIDE.md` for the full API.

### Frontend (`src/`)

Vanilla JavaScript with Vite. Uses Golden Layout for panel management. Key managers: `PanelManager`, `ToolbarManager`, `SidebarManager`, `ModalManager`. Talks to Rust via Tauri IPC (`@tauri-apps/api`).

### Vault Configuration (`.vault.toml`)

Each vault has a `.vault.toml` defining LLM providers, model categories (thinking, fast, vision, code, embedding), and which plugins are enabled.

## System Documentation

| Doc | Purpose |
|-----|---------|
| `docs/system/VISION.md` | What Tailor is, core principles, direction, settled decisions |
| `docs/system/ARCHITECTURE.md` | Accurate current state of all three layers and their interactions |
| `docs/system/INCONSISTENCIES.md` | Known issues surfaced during audit, prioritized |

**Update protocol:**
- After touching a component → update the relevant section in `ARCHITECTURE.md`
- After a design decision is made → add it to `VISION.md` Settled Decisions
- If you find an inconsistency → add it to `INCONSISTENCIES.md`
- After fixing an inconsistency → strikethrough the entry with the commit reference
- `CLAUDE.md` only changes when commands or conventions change

## Key Dependencies

- **Tauri 2** — desktop app shell
- **tokio + tokio-tungstenite** — async Rust runtime and WebSocket
- **LangGraph + LiteLLM** — LLM pipeline orchestration, multi-provider support
- **loguru** — Python logging
- **ruff** — Python linter/formatter
- **pixi** — reproducible multi-language environment (Python 3.12+, Node 20+, Rust 1.70+)
