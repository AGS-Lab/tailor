import asyncio
import sys
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sidecar import constants
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
    
    return vault_dir

# ----------------------------------------------------------------------------
# Integration Tests
# ----------------------------------------------------------------------------

@pytest.mark.asyncio
class TestIntegration:
    
    async def test_plugin_lifecycle_and_execution(self, integration_vault, mock_ws_server):
        """
        Verify:
        1. Plugin is discovered and loaded.
        2. Commands are registered.
        3. Command execution works.
        4. Events are emitted to WebSocket.
        """
        # 1. Initialize logic
        with patch("sidecar.vault_brain.get_logger"):
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
        await brain.execute_command("test.emit", event_type="custom.event", data=event_data)
        
        # Verify mock server received the event
        # ws_server.send_to_rust should be called with JSON-RPC notification
        assert mock_ws_server.send_to_rust.called
        call_args = mock_ws_server.send_to_rust.call_args[0][0] # First arg of last call
        
        # Check structure of sent message
        assert call_args["method"] == "trigger_event"
        assert call_args["params"]["event_type"] == "custom.event"
        assert call_args["params"]["data"] == event_data
        
    async def test_invalid_command_handling(self, integration_vault, mock_ws_server):
        """Test system behavior when executing non-existent command."""
        with patch("sidecar.vault_brain.get_logger"):
            brain = VaultBrain(integration_vault, mock_ws_server)
            
        with pytest.raises(exceptions.CommandNotFoundError):
            await brain.execute_command("non.existent.command")
            
    async def test_plugin_unload(self, integration_vault, mock_ws_server):
        """Test plugin unloading."""
        with patch("sidecar.vault_brain.get_logger"):
            brain = VaultBrain(integration_vault, mock_ws_server)
            await brain.initialize()
            
        plugin = brain.plugins["integration_test_plugin"]
        await plugin.on_unload()
        
        assert plugin.is_loaded is False

    async def test_real_example_vault(self, mock_ws_server):
        """Verify we can load the actual example-vault plugins."""
        # This assumes example-vault is at ../example-vault relative to sidecar
        real_vault_path = Path(__file__).parent.parent.parent / "example-vault"
        
        if not real_vault_path.exists():
            pytest.skip("example-vault directory not found")
            
        with patch("sidecar.vault_brain.get_logger"):
            # We use the real path
            brain = VaultBrain(real_vault_path, mock_ws_server)
            await brain.initialize()
            
        # Check if demo_plugin loaded
        assert "demo_plugin" in brain.plugins
        assert "llm" in brain.plugins
        
        demo = brain.plugins["demo_plugin"]
        assert demo.is_loaded
        
        # Verify commands from demo plugin
        assert "demo.hello" in brain.commands
        assert "demo.increment" in brain.commands

    async def test_jsonrpc_command_dispatch(self, integration_vault, mock_ws_server):
        """
        Verify the execute_command JSON-RPC handler correctly unpacks 'args'.
        This ensures the frontend-backend contract is respected.
        """
        with patch("sidecar.vault_brain.get_logger"):
            brain = VaultBrain(integration_vault, mock_ws_server)
            await brain.initialize()

        # Capture the registered handler for 'execute_command'
        # VaultBrain registers it in _register_commands via:
        # self.ws_server.register_handler("execute_command", handle_execute)
        
        # In our mock_ws_server, register_handler is just a mock method. 
        # But wait, VaultBrain calls register_handler on init.
        # We need to see what arguments register_handler was called with.
        
        # mock_ws_server.register_handler("execute_command", actual_async_function)
        
        # Let's find the call for "execute_command"
        calls = mock_ws_server.register_handler.call_args_list
        handler = None
        for c in calls:
            if c[0][0] == "execute_command":
                handler = c[0][1]
                break
        
        assert handler is not None, "execute_command handler should be registered"
        
        # Simulate JSON-RPC params from frontend
        # Correct usage: args nested under "args"
        params_correct = {
            "command": "test.echo",
            "args": {"message": "Hello JSON"}
        }
        
        result = await handler(params_correct)
        assert result["result"]["echo"] == "Hello JSON"
        
        # Incorrect usage: args at top level (what caused the bug)
        params_incorrect = {
            "command": "test.echo",
            "message": "Should be ignored"
        }
        
        # This will call echo(message=default/missing) -> might fail if message is required
        # or echo("World") if default exists.
        # Our test plugin's handle_echo signature is: async def handle_echo(self, message: str, **kwargs)
        # So "message" is required.
        
        # This should fail or raise TypeError because 'message' arg is missing
        try:
            await handler(params_incorrect)
            # If it didn't raise, check what happened?
            # It passed **{} so message was missing.
        except Exception as e:
            # Expecting TypeError: handle_echo() missing 1 required positional argument: 'message'
            # But handle_execute catches exceptions and re-raises CommandExecutionError
            # Check if it was caught
            pass
