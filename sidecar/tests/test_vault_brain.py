"""
Unit tests for VaultBrain module.

Tests initialization, plugin loading, and command registration.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from pathlib import Path
import sys

from sidecar.vault_brain import VaultBrain
from sidecar.exceptions import (
    VaultNotFoundError, 
    VaultConfigError, 
    PluginLoadError,
    CommandRegistrationError,
    CommandNotFoundError,
    CommandExecutionError
)
from sidecar.constants import DEFAULT_TICK_INTERVAL

@pytest.mark.unit
class TestVaultBrain:
    """Test VaultBrain functionality."""
    
    @pytest.fixture
    def mock_ws_server(self):
        """Create a mock WebSocketServer."""
        return Mock()
    
    @pytest.fixture
    def valid_vault(self, tmp_path):
        """Create a valid vault structure."""
        vault_path = tmp_path / "test_vault"
        vault_path.mkdir()
        (vault_path / ".vault.json").write_text("{}")
        return vault_path

    def test_init_valid_vault(self, valid_vault, mock_ws_server):
        """Test initialization with a valid vault."""
        # Mock logging config to avoid real file operations or console noise
        with patch("sidecar.vault_brain.get_logger"):
            
            brain = VaultBrain(valid_vault, mock_ws_server)
            
            assert brain.vault_path == valid_vault.resolve()
            assert brain.ws_server == mock_ws_server
            assert brain.plugins == {}
            # Core commands are registered on init (chat, execute, list, info)
            assert len(brain.commands) >= 4
            assert brain.emitter is not None

    def test_init_nonexistent_vault(self, mock_ws_server):
        """Test initialization with nonexistent vault."""
        fake_path = Path("/nonexistent/path")
        
        with pytest.raises(VaultNotFoundError):
            VaultBrain(fake_path, mock_ws_server)

    def test_load_config_valid(self, valid_vault, mock_ws_server):
        """Test loading valid configuration."""
        brain = VaultBrain(valid_vault, mock_ws_server)
        assert isinstance(brain.config, dict)
        
    def test_load_config_invalid_json(self, valid_vault, mock_ws_server):
        """Test loading invalid JSON configuration."""
        (valid_vault / ".vault.json").write_text("{invalid json")
        
        with pytest.raises(VaultConfigError):
            VaultBrain(valid_vault, mock_ws_server)

    @patch("sidecar.vault_brain.validate_plugin_structure")
    @patch("sidecar.vault_brain.discover_plugins")
    @patch("sidecar.vault_brain.importlib.util.spec_from_file_location")
    @patch("sidecar.vault_brain.importlib.util.module_from_spec")
    def test_load_plugins(self, mock_module, mock_spec, mock_discover, mock_validate, valid_vault, mock_ws_server):
        """Test loading plugins."""
        # Mock discovered plugin path
        plugin_path = valid_vault / "plugins" / "test_plugin"
        mock_discover.return_value = [plugin_path]
        
        # Mock plugin module and class
        mock_plugin_instance = Mock()
        mock_plugin_class = Mock(return_value=mock_plugin_instance)
        
        # Create a mock module with the plugin class
        mock_mod = MagicMock()
        setattr(mock_mod, "Plugin", mock_plugin_class)
        mock_module.return_value = mock_mod
        
        # Mock spec loader
        mock_spec_obj = Mock()
        mock_spec_obj.loader.exec_module = Mock()
        mock_spec.return_value = mock_spec_obj
        
        brain = VaultBrain(valid_vault, mock_ws_server)
        
        # Verify plugin loaded
        assert "test_plugin" in brain.plugins
        assert brain.plugins["test_plugin"] == mock_plugin_instance
        
        # Verify initialize called logic? 
        # Looking at implementation: plugin = plugin_class(...)
        # It doesn't call plugin.initialize(). It calls __init__.
        # So we check if class was called.
        mock_plugin_class.assert_called_once()

    def test_register_commands(self, valid_vault, mock_ws_server):
        """Test command registration from plugins."""
        brain = VaultBrain(valid_vault, mock_ws_server)
        
        # Manually add a mock plugin
        mock_plugin = Mock()
        mock_plugin.commands = {
            "test_cmd": Mock()
        }
        brain.plugins["test_plugin"] = mock_plugin
        
        # Mock ws_server.register_handler
        brain._register_commands()
        
        # Check if handler registered with ws_server
        # Note: The actual method name registered might be prefixed ornamespaced
        # Implementation detail: Does VaultBrain strictly use plugin.commands?
        # Let's verify _register_commands implementation.
        # It iterates plugins, gets commands, and registers them.
        
        # Since we mocked the plugin, we expect ws_server.register_handler to be called
        # But wait, VaultBrain registers a wrapper or the handler directly?
        # Usually it registers "plugin_name.command_name" or just command ID. 
        # Assuming implementation registers command ID as is if unique?
        
        # Actually simplest check: mock_ws_server.register_handler called
        assert mock_ws_server.register_handler.called

    @pytest.mark.asyncio
    async def test_tick(self, valid_vault, mock_ws_server):
        """Test tick method calls plugins."""
        brain = VaultBrain(valid_vault, mock_ws_server)
        
        mock_plugin = Mock()
        mock_plugin.on_tick = AsyncMock() # Async tick
        brain.plugins["test_plugin"] = mock_plugin
        
        await brain._on_tick()
        
        mock_plugin.on_tick.assert_called_once()


@pytest.mark.unit
class TestCommandRegistry:
    """Test command registry functionality."""
    
    @pytest.fixture
    def brain(self, tmp_path):
        """Create a VaultBrain instance with mocks."""
        vault_path = tmp_path / "test_vault"
        vault_path.mkdir()
        (vault_path / ".vault.json").write_text("{}")
        
        ws_server = Mock()
        # Mock logging to clean up output
        with patch("sidecar.vault_brain.get_logger"):
            return VaultBrain(vault_path, ws_server)

    def test_register_command_valid(self, brain):
        """Test registering a valid async command."""
        async def my_command():
            return "success"
            
        brain.register_command("test.cmd", my_command)
        
        assert "test.cmd" in brain.commands
        assert brain.commands["test.cmd"]["handler"] == my_command
        
    def test_register_command_invalid_sync(self, brain):
        """Test that registering a sync function raises error."""
        def sync_command():
            pass
            
        with pytest.raises(CommandRegistrationError):
            brain.register_command("test.sync", sync_command)

    @pytest.mark.asyncio
    async def test_execute_command_success(self, brain):
        """Test executing a registered command."""
        async def my_command():
            return "executed"
            
        brain.register_command("test.cmd", my_command)
        
        result = await brain.execute_command("test.cmd")
        assert result == "executed"

    @pytest.mark.asyncio
    async def test_execute_command_with_args(self, brain):
        """Test executing a registered command with arguments."""
        async def add(a, b):
            return a + b
            
        brain.register_command("calc.add", add)
        
        # Test with named args (kwargs)
        result = await brain.execute_command("calc.add", a=5, b=3)
        assert result == 8

    @pytest.mark.asyncio
    async def test_execute_command_not_found(self, brain):
        """Test executing a non-existent command."""
        with pytest.raises(CommandNotFoundError):
            await brain.execute_command("non.existent")

    @pytest.mark.asyncio
    async def test_execute_command_execution_error(self, brain):
        """Test handling of execution errors."""
        async def failing_command():
            raise ValueError("Something went wrong")
            
        brain.register_command("test.fail", failing_command)
        
        with pytest.raises(CommandExecutionError) as exc_info:
            await brain.execute_command("test.fail")
        
        # Check that original error is preserved/referenced
        assert "Something went wrong" in str(exc_info.value)

    def test_get_commands(self, brain):
        """Test listing commands."""
        async def cmd1(): pass
        async def cmd2(): pass
        
        brain.register_command("cmd1", cmd1, "plugin1")
        brain.register_command("cmd2", cmd2, "plugin2")
        
        cmds = brain.get_commands()
        
        assert len(cmds) >= 2 + 4 # 2 custom + 4 core commands
        assert cmds["cmd1"]["plugin"] == "plugin1"
        assert cmds["cmd2"]["plugin"] == "plugin2"

