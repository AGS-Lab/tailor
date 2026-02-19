"""
Tests for Demo UI Plugin.
"""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

# Mock sys.path to include tailor root if needed, but we can just import assuming sidecar is in path
# The plugin code does sys.path insert, so we might need to simulate that or just mock the base class if we want to avoid side effects.
# However, simpler to just import the class if we can.

# We need to manually load the module because it's not a standard package structure
import importlib.util


def load_plugin_module(path):
    spec = importlib.util.spec_from_file_location("demo_ui_plugin", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Resolve plugin path relative to this test file
# sidecar/tests/test_plugin_demo_ui.py -> ... -> example-vault/plugins/demo_ui/main.py
base_dir = Path(__file__).resolve().parent.parent.parent
plugin_path = base_dir / "example-vault" / "plugins" / "demo_ui" / "main.py"

demo_ui = load_plugin_module(plugin_path)


@pytest.fixture
def mock_brain():
    brain = MagicMock()
    brain.emit_to_frontend = MagicMock()
    brain.register_command = MagicMock()
    return brain


@pytest.fixture
def plugin(mock_brain, tmp_path):
    with patch("sidecar.vault_brain.VaultBrain.get", return_value=mock_brain):
        # We need to ensure that when the plugin accesses self.brain, it gets our mock
        # The property calls VaultBrain.get()
        p = demo_ui.Plugin(tmp_path, tmp_path)
        yield p


@pytest.mark.asyncio
async def test_register_commands(plugin):
    plugin.register_commands()
    assert plugin.brain.register_command.call_count == 3
    args = [call.args[0] for call in plugin.brain.register_command.call_args_list]
    assert "demo_ui.show_modal" in args
    assert "demo_ui.update_stage" in args
    assert "demo_ui.toolbar_action" in args


@pytest.mark.asyncio
async def test_on_client_connected(plugin):
    await plugin.on_client_connected()
    # Check if UI commands were emitted
    assert plugin.brain.emit_to_frontend.call_count >= 1
    # We can check specific calls
    calls = plugin.brain.emit_to_frontend.call_args_list
    assert any(c.kwargs["data"]["action"] == "register_sidebar" for c in calls)

    # Debug prints
    print(f"DEBUG CALLS: {[c.kwargs['data']['action'] for c in calls]}")

    # register_toolbar_button emits REGISTER_TOOLBAR ("register_toolbar")
    assert any(c.kwargs["data"]["action"] == "register_toolbar" for c in calls)


@pytest.mark.asyncio
async def test_handle_show_modal(plugin):
    await plugin._handle_show_modal()
    # show_modal emits UI_COMMAND
    calls = plugin.brain.emit_to_frontend.call_args_list
    assert any(c.kwargs["data"]["action"] == "show_modal" for c in calls)


@pytest.mark.asyncio
async def test_handle_update_stage(plugin):
    await plugin._handle_update_stage()
    calls = plugin.brain.emit_to_frontend.call_args_list
    assert any(c.kwargs["data"]["action"] == "set_toolbox" for c in calls)


@pytest.mark.asyncio
async def test_handle_toolbar_action(plugin):
    await plugin._handle_toolbar_action()
    calls = plugin.brain.emit_to_frontend.call_args_list
    # notifies and updates panel
    assert any(c.kwargs["data"]["action"] == "set_panel" for c in calls)
