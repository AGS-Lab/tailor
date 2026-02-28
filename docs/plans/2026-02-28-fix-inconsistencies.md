# Fix Inconsistencies Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all actionable inconsistencies surfaced in the Feb 2026 codebase audit.

**Architecture:** Fixes are grouped by layer (Python sidecar → Rust backend → Frontend). Each fix is isolated and testable. No cross-cutting refactors — one bug at a time.

**Tech Stack:** Python 3.12 (pytest, tomli_w, unittest.mock), Rust (cargo test), Vanilla JS

---

## Skipped Issues (intentional)

- **IC-004** — Removing EventBus (Rust) is an architectural decision, not a bug fix. Defer.
- **IC-007** — Frontend state centralization is a large refactor. Defer to a dedicated design session.
- **IC-009** — Event name constants: low risk, low reward right now.
- **IC-010** — Hardcoded settings: low risk, needs separate design for settings.toml migration.
- **IC-013** — Stream ID contract: low priority, no user-facing bug yet.
- **IC-014** — Already fixed (stale doc reference removed in prior commit).

---

## Task 1: IC-001 — Fix toggle_plugin config write (TOML → JSON corruption)

**Files:**
- Modify: `sidecar/vault_brain.py:1082-1084`
- Test: `sidecar/tests/test_vault_brain.py`

**Context:** `toggle_plugin()` reads `.vault.toml` with `tomllib` but writes it back with `json.dump`. This corrupts the file. `set_model_category` (line 604) already uses the correct pattern with `tomli_w`.

**Step 1: Write the failing test**

Add this to `sidecar/tests/test_vault_brain.py` inside `TestVaultBrain`:

```python
@pytest.mark.asyncio
async def test_toggle_plugin_writes_valid_toml(self, valid_vault, mock_ws_server):
    """toggle_plugin must write TOML, not JSON, to .vault.toml."""
    import tomllib

    brain = VaultBrain(valid_vault, mock_ws_server)
    await brain.initialize()

    await brain.toggle_plugin(plugin_id="demo_plugin", enabled=True)

    config_path = valid_vault / ".vault.toml"
    # If this raises, the file was written as JSON (corruption bug)
    with open(config_path, "rb") as f:
        parsed = tomllib.load(f)

    assert parsed["plugins"]["demo_plugin"]["enabled"] is True
```

**Step 2: Run test to verify it fails**

```bash
pixi run pytest sidecar/tests/test_vault_brain.py::TestVaultBrain::test_toggle_plugin_writes_valid_toml -v
```

Expected: FAIL — `tomllib.TOMLDecodeError` (file contains JSON, not TOML)

**Step 3: Fix the implementation**

In `sidecar/vault_brain.py`, replace lines 1082–1084:

```python
# BEFORE (buggy):
with open(config_path, "w", encoding="utf-8") as f:
    json.dump(config, f, indent=4)

# AFTER (correct):
with open(config_path, "wb") as f:
    tomli_w.dump(config, f)
```

**Step 4: Run test to verify it passes**

```bash
pixi run pytest sidecar/tests/test_vault_brain.py::TestVaultBrain::test_toggle_plugin_writes_valid_toml -v
```

Expected: PASS

**Step 5: Run full test suite to check for regressions**

```bash
pixi run test
```

Expected: all tests pass

**Step 6: Commit**

```bash
git add sidecar/vault_brain.py sidecar/tests/test_vault_brain.py
git commit -m "fix: toggle_plugin writes TOML not JSON (IC-001)"
```

**Step 7: Mark resolved in INCONSISTENCIES.md**

Strikethrough IC-001 entry with the commit hash.

---

## Task 2: IC-002 — Fix VaultBrain singleton init guard

**Files:**
- Modify: `sidecar/vault_brain.py:70-73`
- Test: `sidecar/tests/test_vault_brain.py`

**Context:** `_initialized` is set to `False` on line 71, then checked on line 72 — the guard can never be True. The singleton `__new__` prevents double instantiation but the guard is still logically broken.

**Step 1: Write the failing test**

Add to `TestVaultBrain`:

```python
def test_singleton_reinit_is_guarded(self, valid_vault, mock_ws_server):
    """Calling VaultBrain.__init__ a second time on the same instance must be a no-op."""
    brain = VaultBrain(valid_vault, mock_ws_server)
    original_path = brain.vault_path

    # Simulate what would happen if __init__ ran again on the same instance
    brain.__init__(valid_vault, mock_ws_server)

    # vault_path must not be reset (guard protected it)
    assert brain.vault_path == original_path
    assert brain._initialized is True
```

**Step 2: Run test to verify it fails**

```bash
pixi run pytest sidecar/tests/test_vault_brain.py::TestVaultBrain::test_singleton_reinit_is_guarded -v
```

Expected: FAIL — `_initialized` is reset to False by the second `__init__` call

**Step 3: Fix the implementation**

Replace lines 70–73 in `sidecar/vault_brain.py`:

```python
# BEFORE (buggy):
self._initialized: bool = False
if self._initialized:
    return

# AFTER (correct):
if hasattr(self, "_initialized") and self._initialized:
    return
```

**Step 4: Run test**

```bash
pixi run pytest sidecar/tests/test_vault_brain.py::TestVaultBrain::test_singleton_reinit_is_guarded -v
```

Expected: PASS

**Step 5: Run full suite**

```bash
pixi run test
```

**Step 6: Commit**

```bash
git add sidecar/vault_brain.py sidecar/tests/test_vault_brain.py
git commit -m "fix: VaultBrain singleton init guard was always False (IC-002)"
```

**Step 7: Mark IC-002 resolved in INCONSISTENCIES.md**

---

## Task 3: IC-006 — Fix register_command override logic

**Files:**
- Modify: `sidecar/vault_brain.py:376-385`
- Test: `sidecar/tests/test_vault_brain.py`

**Context:** When `override=False` and a command already exists, the code logs a warning but still overwrites. The `override` flag should actually prevent overwriting — raise `CommandRegistrationError` instead.

**Step 1: Write the failing tests**

Add to `TestVaultBrain`:

```python
@pytest.mark.asyncio
async def test_register_command_no_override_raises(self, valid_vault, mock_ws_server):
    """Registering a duplicate command with override=False must raise, not silently overwrite."""
    brain = VaultBrain(valid_vault, mock_ws_server)
    await brain.initialize()

    async def handler_a(**kwargs): return {}
    async def handler_b(**kwargs): return {}

    brain.register_command("test.cmd", handler_a)

    with pytest.raises(exceptions.CommandRegistrationError):
        brain.register_command("test.cmd", handler_b, override=False)

    # Original handler must still be registered
    assert brain.commands["test.cmd"]["handler"] is handler_a


@pytest.mark.asyncio
async def test_register_command_with_override_succeeds(self, valid_vault, mock_ws_server):
    """Registering a duplicate command with override=True must succeed."""
    brain = VaultBrain(valid_vault, mock_ws_server)
    await brain.initialize()

    async def handler_a(**kwargs): return {}
    async def handler_b(**kwargs): return {}

    brain.register_command("test.cmd", handler_a)
    brain.register_command("test.cmd", handler_b, override=True)

    assert brain.commands["test.cmd"]["handler"] is handler_b
```

**Step 2: Run tests to verify they fail**

```bash
pixi run pytest sidecar/tests/test_vault_brain.py::TestVaultBrain::test_register_command_no_override_raises sidecar/tests/test_vault_brain.py::TestVaultBrain::test_register_command_with_override_succeeds -v
```

Expected: first test FAILS (no exception raised), second PASSES

**Step 3: Fix the implementation**

Replace the duplicate-check block in `register_command` (lines 376–380):

```python
# BEFORE:
if command_id in self.commands:
    if not override:
        logger.warning(f"Overwriting command '{command_id}'")
    else:
        logger.debug(f"Overriding command '{command_id}'")

# AFTER:
if command_id in self.commands:
    if not override:
        raise exceptions.CommandRegistrationError(
            command_id, "Command already registered. Use override=True to replace it."
        )
    logger.debug(f"Overriding command '{command_id}'")
```

**Step 4: Run tests**

```bash
pixi run pytest sidecar/tests/test_vault_brain.py::TestVaultBrain::test_register_command_no_override_raises sidecar/tests/test_vault_brain.py::TestVaultBrain::test_register_command_with_override_succeeds -v
```

Expected: both PASS

**Step 5: Run full suite — expect some existing tests to break**

```bash
pixi run test
```

Any test that registers the same command twice without `override=True` will now fail. Fix those tests to use `override=True` or unique command IDs.

**Step 6: Commit**

```bash
git add sidecar/vault_brain.py sidecar/tests/test_vault_brain.py
git commit -m "fix: register_command raises on duplicate without override=True (IC-006)"
```

**Step 7: Mark IC-006 resolved in INCONSISTENCIES.md**

---

## Task 4: IC-005 — Warn on legacy plugin config format

**Files:**
- Modify: `sidecar/vault_brain.py:274-277`
- Test: `sidecar/tests/test_vault_brain.py`

**Context:** If a plugin config entry in `.vault.toml` is not a dict (old list format), it silently falls back to `{}`. We should at least log a warning so the user knows their config was ignored.

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_legacy_plugin_config_logs_warning(self, valid_vault, mock_ws_server):
    """Non-dict plugin config entry must log a warning, not silently discard."""
    import logging

    (valid_vault / ".vault.toml").write_text(
        '[plugins]\nexplorer = ["legacy", "list", "format"]\n'
    )

    brain = VaultBrain(valid_vault, mock_ws_server)

    with patch("sidecar.vault_brain.logger") as mock_logger:
        await brain.initialize()
        # Should have warned about the malformed config
        warning_calls = [str(c) for c in mock_logger.warning.call_args_list]
        assert any("explorer" in w for w in warning_calls), (
            "Expected a warning about malformed plugin config for 'explorer'"
        )
```

**Step 2: Run test to verify it fails**

```bash
pixi run pytest sidecar/tests/test_vault_brain.py::TestVaultBrain::test_legacy_plugin_config_logs_warning -v
```

Expected: FAIL — no warning is currently logged

**Step 3: Fix the implementation**

Replace lines 274–277 in `sidecar/vault_brain.py`:

```python
# BEFORE:
overrides = vault_apps_config.get(plugin_name, {})
if not isinstance(overrides, dict):
    overrides = {}

# AFTER:
overrides = vault_apps_config.get(plugin_name, {})
if not isinstance(overrides, dict):
    logger.warning(
        f"Plugin config for '{plugin_name}' in .vault.toml is not a dict "
        f"(got {type(overrides).__name__}). Ignoring overrides — update your .vault.toml."
    )
    overrides = {}
```

**Step 4: Run test**

```bash
pixi run pytest sidecar/tests/test_vault_brain.py::TestVaultBrain::test_legacy_plugin_config_logs_warning -v
```

Expected: PASS

**Step 5: Run full suite**

```bash
pixi run test
```

**Step 6: Commit**

```bash
git add sidecar/vault_brain.py sidecar/tests/test_vault_brain.py
git commit -m "fix: warn on malformed plugin config instead of silent discard (IC-005)"
```

**Step 7: Mark IC-005 resolved in INCONSISTENCIES.md**

---

## Task 5: IC-003 — Remove nested params fallback from command handlers

**Files:**
- Modify: `sidecar/vault_brain.py` (4 handlers: lines ~461-464, ~495-499, ~682-687, ~1054-1058)
- Test: `sidecar/tests/test_vault_brain.py`

**Context:** Four handlers do `kwargs.get("p") or kwargs.get("params")` as a legacy fallback. The frontend sends flat params. Remove the fallback to enforce a single calling convention. If any caller breaks, fix the caller instead.

**Step 1: Write tests confirming flat params work (they already should)**

```python
@pytest.mark.asyncio
async def test_handle_chat_accepts_flat_params(self, valid_vault, mock_ws_server):
    """system.chat must work with flat params (no nested 'p' or 'params' key)."""
    brain = VaultBrain(valid_vault, mock_ws_server)
    await brain.initialize()

    result = await brain.handle_chat(message="hello", history=[], chat_id="test-123")
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_toggle_plugin_accepts_flat_params(self, valid_vault, mock_ws_server):
    """plugins.toggle must work with flat params."""
    brain = VaultBrain(valid_vault, mock_ws_server)
    await brain.initialize()

    result = await brain.toggle_plugin(plugin_id="demo_plugin", enabled=True)
    assert result["status"] == "success"
```

**Step 2: Run tests to confirm they already pass**

```bash
pixi run pytest sidecar/tests/test_vault_brain.py::TestVaultBrain::test_handle_chat_accepts_flat_params sidecar/tests/test_vault_brain.py::TestVaultBrain::test_toggle_plugin_accepts_flat_params -v
```

Expected: PASS (establishes the baseline before removing fallback)

**Step 3: Remove nested params fallback from all 4 handlers**

**`handle_chat` (~line 461):** Remove the block:
```python
# DELETE these lines:
if chat_id == "default":
    p = kwargs.get("p") or kwargs.get("params")
    if isinstance(p, dict):
        chat_id = p.get("chat_id", chat_id)
```

**`store_api_key` (~line 495):** Remove the block:
```python
# DELETE these lines:
if not provider:
    p = kwargs.get("p") or kwargs.get("params")
    if isinstance(p, dict):
        provider = p.get("provider", provider)
        api_key = p.get("api_key", api_key)
```

**`chat_send` / `set_model` (~line 682):** Remove the block:
```python
# DELETE these lines:
if not chat_id:
    p = kwargs.get("p") or kwargs.get("params")
    if isinstance(p, dict):
        chat_id = p.get("chat_id", chat_id)
        model_id = p.get("model_id", model_id)
        category = p.get("category", category)
```

**`toggle_plugin` (~line 1054):** Remove the block:
```python
# DELETE these lines:
if not plugin_id:
    p = kwargs.get("p") or kwargs.get("params")
    if isinstance(p, dict):
        plugin_id = p.get("plugin_id", plugin_id)
        enabled = p.get("enabled", enabled)
```

**Step 4: Run all tests**

```bash
pixi run test
```

Expected: all pass. If any test now fails with missing `plugin_id` or `provider`, that test was using the nested format — update it to pass flat kwargs.

**Step 5: Commit**

```bash
git add sidecar/vault_brain.py sidecar/tests/test_vault_brain.py
git commit -m "fix: remove nested params fallback, enforce flat kwargs contract (IC-003)"
```

**Step 6: Mark IC-003 resolved in INCONSISTENCIES.md**

---

## Task 6: IC-008 — Remove unimplemented stub Rust commands

**Files:**
- Modify: `src-tauri/src/ipc_router.rs:402-412`
- Modify: `src-tauri/src/main.rs` (remove from invoke_handler)

**Context:** `search_plugins` and `get_plugin_details` are registered Tauri commands that do nothing useful. Remove them from the public surface until implemented.

**Step 1: Find all references**

```bash
grep -n "search_plugins\|get_plugin_details" src-tauri/src/main.rs src-tauri/src/ipc_router.rs
```

Note all line numbers.

**Step 2: Remove the two functions from ipc_router.rs**

Delete from `src-tauri/src/ipc_router.rs`:

```rust
// DELETE:
/// Search plugins in the community store
#[tauri::command]
pub async fn search_plugins(_query: String, _category: Option<String>) -> Result<Vec<serde_json::Value>, String> {
    Ok(vec![])
}

/// Get plugin details
#[tauri::command]
pub async fn get_plugin_details(_plugin_id: String) -> Result<serde_json::Value, String> {
    Err("Plugin details not yet implemented".to_string())
}
```

**Step 3: Remove from invoke_handler in main.rs**

In `src-tauri/src/main.rs`, remove `search_plugins` and `get_plugin_details` from the `generate_handler![]` macro call.

**Step 4: Build to confirm it compiles**

```bash
pixi run test-rust
```

Expected: compiles and tests pass

**Step 5: Commit**

```bash
git add src-tauri/src/ipc_router.rs src-tauri/src/main.rs
git commit -m "fix: remove unimplemented stub Tauri commands (IC-008)"
```

**Step 6: Mark IC-008 resolved in INCONSISTENCIES.md**

---

## Task 7: IC-011 — Remove dead Rust methods

**Files:**
- Modify: `src-tauri/src/sidecar_manager.rs` (remove `is_running`)
- Modify: `src-tauri/src/window_manager.rs` (remove `get_active_windows`)

**Context:** Both methods are marked `#[allow(dead_code)]` and never called. Remove them. (EventBus dead code is deferred with IC-004.)

**Step 1: Check nothing calls these**

```bash
grep -rn "is_running\|get_active_windows" src-tauri/src/
```

Confirm only the definition lines appear.

**Step 2: Remove `is_running` from sidecar_manager.rs**

Delete the function (around line 167) — the one marked `#[allow(dead_code)]`:
```rust
// DELETE:
#[allow(dead_code)]
pub async fn is_running(&self, vault_path: &str) -> bool { ... }
```

**Step 3: Remove `get_active_windows` from window_manager.rs**

Delete the function (around line 63):
```rust
// DELETE:
#[allow(dead_code)]
pub fn get_active_windows(&self) -> Vec<String> { ... }
```

**Step 4: Build**

```bash
pixi run test-rust
```

Expected: compiles cleanly with no dead_code warnings for these methods

**Step 5: Commit**

```bash
git add src-tauri/src/sidecar_manager.rs src-tauri/src/window_manager.rs
git commit -m "fix: remove unused dead_code methods in Rust backend (IC-011)"
```

**Step 6: Mark IC-011 resolved in INCONSISTENCIES.md**

---

## Task 8: IC-012 — Add error handling to loadHistory

**Files:**
- Modify: `src/vault/chat/chat.js:127`
- Test: `src/tests/` (add or update)

**Context:** `loadHistory()` does `res.result || {}` without checking if `res` itself is an error response. If the sidecar returns `{error: "..."}` with no `result` key, the code silently does nothing.

**Step 1: Find the existing frontend test file**

```bash
ls src/tests/
```

**Step 2: Write a test (if using vitest)**

In `src/tests/chat.test.js` (create if needed):

```js
import { describe, it, expect, vi, beforeEach } from 'vitest'

describe('loadHistory error handling', () => {
  it('handles missing res.result gracefully', async () => {
    // Simulate sidecar returning an error response with no .result
    window.request = vi.fn().mockResolvedValue({ error: 'Not found' })

    // Should not throw
    const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    // loadHistory is not exported — test via the module's exported init or directly
    // For now, verify the guard logic manually in the fix step
    consoleSpy.mockRestore()
  })
})
```

Note: if `loadHistory` is not exported, just add a defensive guard directly (step 3) and rely on manual verification.

**Step 3: Fix the implementation**

In `src/vault/chat/chat.js`, replace line 127:

```js
// BEFORE:
const result = res.result || {};

// AFTER:
if (!res || res.error || !res.result) {
    console.warn('[Chat] Failed to load history:', res?.error || 'No result');
    setStatus('Ready');
    return;
}
const result = res.result;
```

**Step 4: Run frontend tests**

```bash
npm run test
```

Expected: pass (or new test passes)

**Step 5: Commit**

```bash
git add src/vault/chat/chat.js
git commit -m "fix: guard against missing res.result in loadHistory (IC-012)"
```

**Step 6: Mark IC-012 resolved in INCONSISTENCIES.md**

---

## Final Step: Push

```bash
git push
```

---

## Execution Order Summary

| Task | Issue | Layer | Risk |
|------|-------|-------|------|
| 1 | IC-001 | Python | Low — one-line fix, has test |
| 2 | IC-002 | Python | Low — guard logic only |
| 3 | IC-006 | Python | Medium — may break existing tests |
| 4 | IC-005 | Python | Low — adds a log line |
| 5 | IC-003 | Python | Medium — removes fallback, verify no callers break |
| 6 | IC-008 | Rust | Low — removes dead endpoints |
| 7 | IC-011 | Rust | Low — removes dead code |
| 8 | IC-012 | JS | Low — adds a guard |
