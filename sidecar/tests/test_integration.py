from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from sidecar import exceptions

# Add sidecar root to path to ensure imports work
# sys.path.insert(0, str(Path(__file__).parent.parent))

from sidecar.vault_brain import VaultBrain
from sidecar.websocket_server import WebSocketServer

# ----------------------------------------------------------------------------
# Test Plugin Content
# ----------------------------------------------------------------------------

TEST_PLUGIN_CODE = """
from sidecar.api.plugin_base import PluginBase
from typing import Dict, Any

class Plugin(PluginBase):
    def register_commands(self):
        self.brain.register_command("test.echo", self.handle_echo, self.name)
        self.brain.register_command("test.emit", self.handle_emit, self.name)

    async def handle_echo(self, message: str, **kwargs) -> Dict[str, Any]:
        self.logger.info(f"Echoing: {message}")
        return {"echo": message}

    async def handle_emit(self, event_type: str, data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        # Use brain.emit_to_frontend directly or helper methods
        self.brain.emit_to_frontend(event_type, data)
        return {"emitted": True}
"""

# ----------------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------------


@pytest.fixture
def mock_ws_server():
    """Mock WebSocket server."""
    server = MagicMock(spec=WebSocketServer)
    server.send = AsyncMock()
    server.send_to_rust = MagicMock()
    server.command_handlers = {}
    return server


@pytest.fixture
def integration_vault(tmp_path):
    """Create a temporary vault with a test plugin."""
    vault_dir = tmp_path / "test_vault"
    vault_dir.mkdir()

    # Create plugins directory
    plugins_dir = vault_dir / "plugins"
    plugins_dir.mkdir()

    # Create test plugin
    plugin_dir = plugins_dir / "integration_test_plugin"
    plugin_dir.mkdir()

    (plugin_dir / "main.py").write_text(TEST_PLUGIN_CODE, encoding="utf-8")
    (plugin_dir / "settings.json").write_text('{"enabled": true}', encoding="utf-8")

    return vault_dir


# ----------------------------------------------------------------------------
# Integration Tests
# ----------------------------------------------------------------------------


@pytest.mark.asyncio
class TestIntegration:
    async def test_plugin_lifecycle_and_execution(
        self, integration_vault, mock_ws_server
    ):
        """
        Verify:
        1. Plugin is discovered and loaded.
        2. Commands are registered.
        3. Command execution works.
        4. Events are emitted to WebSocket.
        """
        # 1. Initialize logic
        # 1. Initialize logic
        brain = VaultBrain(integration_vault, mock_ws_server)
        await brain.initialize()

        # Verify plugin loaded
        assert "integration_test_plugin" in brain.plugins
        plugin = brain.plugins["integration_test_plugin"]
        assert plugin.is_loaded is True

        # Verify commands registered
        assert "test.echo" in brain.commands
        assert "test.emit" in brain.commands

        # 2. Execute Command
        result = await brain.execute_command("test.echo", message="Integration Test")
        assert result == {"echo": "Integration Test"}

        # 3. Test Event Emission flow
        # Execute command that triggers emit
        event_data = {"status": "ok", "value": 42}
        await brain.execute_command(
            "test.emit", event_type="custom.event", data=event_data
        )

        # Verify mock server received the event
        # ws_server.send_to_rust should be called with JSON-RPC notification
        assert mock_ws_server.send_to_rust.called
        call_args = mock_ws_server.send_to_rust.call_args[0][
            0
        ]  # First arg of last call

        # Check structure of sent message
        assert call_args["method"] == "trigger_event"
        assert call_args["params"]["event_type"] == "custom.event"
        assert call_args["params"]["data"] == event_data

    async def test_invalid_command_handling(self, integration_vault, mock_ws_server):
        """Test system behavior when executing non-existent command."""
        brain = VaultBrain(integration_vault, mock_ws_server)

        with pytest.raises(exceptions.CommandNotFoundError):
            await brain.execute_command("non.existent.command")

    async def test_plugin_unload(self, integration_vault, mock_ws_server):
        """Test plugin unloading."""
        brain = VaultBrain(integration_vault, mock_ws_server)
        await brain.initialize()

        plugin = brain.plugins["integration_test_plugin"]
        await plugin.on_unload()

        assert plugin.is_loaded is False

    async def test_real_example_vault(self, mock_ws_server):
        """Verify we can load the actual example-vault plugins."""
        # This assumes example-vault is at ../example-vault relative to sidecar
        real_vault_path = Path(__file__).parent.parent.parent / "example-vault"

        # We use the real path
        brain = VaultBrain(real_vault_path, mock_ws_server)
        await brain.initialize()

        # Check if demo_plugin loaded
        assert "demo_ui" in brain.plugins

        demo = brain.plugins["demo_ui"]
        assert demo.is_loaded

        # Verify commands from demo plugin
        assert "demo_ui.show_modal" in brain.commands
        assert "demo_ui.update_stage" in brain.commands

        # Verify smart_context plugin loaded
        assert "smart_context" in brain.plugins
        assert brain.plugins["smart_context"].is_loaded
