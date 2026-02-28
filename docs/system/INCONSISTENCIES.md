# Tailor — Known Inconsistencies

Surfaced during codebase audit (Feb 2026). Add new findings here; mark resolved items with ~~strikethrough~~ and the fixing commit.

---

## Critical

### IC-001 — Config write uses JSON instead of TOML
**Component**: Python Sidecar
**File**: `sidecar/vault_brain.py:1084`
**Severity**: Critical — causes data corruption

`toggle_plugin()` reads config with `tomllib` (TOML) but writes it back with `json.dump`. This corrupts `.vault.toml`. The next read will fail because TOML parser can't read JSON.

Correct pattern (already used in `set_model_category` at line 604):
```python
with open(config_path, "wb") as f:
    tomli_w.dump(config, f)
```

---

## High

### IC-002 — VaultBrain singleton init check is backwards
**Component**: Python Sidecar
**File**: `sidecar/vault_brain.py:70-73`
**Severity**: High — silent logic error

`_initialized` is set to `False` immediately before the guard check, so the guard never fires. Should use `hasattr(self, '_initialized') and self._initialized`.

### IC-003 — Inconsistent parameter format between layers
**Component**: Cross-layer (Frontend → Sidecar)
**Files**: `sidecar/vault_brain.py` (multiple), `src/vault/connection.js`
**Severity**: High — implicit coupling, fragile

Some command handlers look for params nested under `p` or `params` key (`kwargs.get("p") or kwargs.get("params")`), while others expect flat kwargs. The frontend sends flat params. Works via fallback, but the contract is implicit and breaks silently when a new command is added.

Affected handlers: `handle_chat` (line 452), `store_api_key` (line 495), `chat_send` (line 686), `toggle_plugin` (line 1057).

---

## Medium

### IC-004 — EventBus (Rust) is created but never used
**Component**: Rust Backend
**Files**: `src-tauri/src/event_bus.rs`, `src-tauri/src/main.rs:22-23`
**Severity**: Medium — dead abstraction, misleading

`EventBus` is initialized and stored in app state but event routing happens directly via Tauri's `Emitter` trait in `ipc_router.rs`. Almost all methods in `event_bus.rs` are marked `#[allow(dead_code)]`. Either wire it up or remove it.

### IC-005 — Plugin config legacy format fallback is incomplete
**Component**: Python Sidecar
**File**: `sidecar/vault_brain.py:268-278`
**Severity**: Medium — silent data loss

Code comments mention "list style legacy" plugin config format, but if `plugins.plugin_name` is a list, it falls back to `{}` (empty dict) instead of migrating or logging. Old-format vaults silently lose plugin config.

### IC-006 — `register_command` override logic is inverted
**Component**: Python Sidecar
**File**: `sidecar/vault_brain.py:363-387`
**Severity**: Medium — confusing API

If a command already exists and `override=False`, the code logs a warning but still overwrites. The `override` flag only controls log level, not behavior. Should either raise on non-override collision or actually skip the overwrite.

### IC-007 — Frontend state is module-local, no centralized store
**Component**: Frontend
**Files**: `src/vault/chat/chat.js`, `src/vault/connection.js`
**Severity**: Medium — scaling problem

Each module holds its own state (`conversationHistory`, `isWaitingForResponse`, `ws`, `pending`, etc.). No shared state layer. Cross-module state queries rely on `window.request()` behavior rather than explicit state access. Will become a problem as features grow.

---

## Low

### IC-008 — Stub commands not implemented
**Component**: Rust Backend
**File**: `src-tauri/src/ipc_router.rs:404-411`
**Severity**: Low — misleading surface area

`search_plugins()` returns empty vec. `get_plugin_details()` returns `NotImplemented` error. Should be removed from the IPC surface until implemented.

### IC-009 — Event type names are inconsistent across layers
**Component**: Cross-layer
**Files**: `sidecar/websocket_server.py`, `src-tauri/src/event_bus.rs`, `src/vault/chat/chat.js`
**Severity**: Low — cognitive overhead

- WebSocket method: `"trigger_event"` (hardcoded string in websocket_server.py)
- Tauri event name: `"sidecar-event"` (hardcoded in event_bus.rs)
- Frontend custom events: `chat:token`, `chat:historyLoaded` (camelCase colons)

No unified constant. Should centralize at least the cross-process names.

### IC-010 — Default settings hardcoded in ipc_router.rs
**Component**: Rust Backend
**File**: `src-tauri/src/ipc_router.rs:485-518`
**Severity**: Low — maintenance burden

Default settings are embedded as a `serde_json::json!` macro literal. A `settings.toml` exists at the project root but is not consistently used as the source of truth.

### IC-011 — Unused Rust methods with dead_code suppression
**Component**: Rust Backend
**Files**: `sidecar_manager.rs:167`, `window_manager.rs:63`, `event_bus.rs` (pervasive)
**Severity**: Low — noise

`is_running()`, `get_active_windows()`, and most of `EventBus` are suppressed with `#[allow(dead_code)]`. Either exercise them or remove them.

### IC-012 — Missing error handling in chat history fetch
**Component**: Frontend
**File**: `src/vault/chat/chat.js:117-150`
**Severity**: Low

`loadHistory()` accesses `res.result` without checking if the response is an error. Malformed or error responses will fail silently or throw uncaught exceptions.

### IC-013 — Streaming stream_id contract is undocumented
**Component**: Cross-layer
**Files**: `sidecar/vault_brain.py:814`, `src/vault/chat/chat.js`
**Severity**: Low

Backend generates `stream_id` via `utils.generate_id("stream_")` and emits it. Frontend doesn't validate or match it. If multiple streams run concurrently, there's no deduplication logic on the frontend.

### IC-014 — `event_emitter.py` referenced in docs but does not exist
**Component**: Python Sidecar
**File**: `CLAUDE.md` (stale reference), original docs
**Severity**: Low — documentation error, no runtime impact

The old `CLAUDE.md` listed `event_emitter.py` as "Plugin API for emitting events to the UI." This file does not exist. Event emission is handled via `PluginBase.emit()` / `brain.emit_to_frontend()` in `api/plugin_base.py` and `vault_brain.py`. Reference has been removed from CLAUDE.md.
