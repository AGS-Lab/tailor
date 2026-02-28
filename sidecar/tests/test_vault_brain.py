"""
Unit tests for VaultBrain module.

Tests initialization, plugin loading, and command registration.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from pathlib import Path

from sidecar.vault_brain import VaultBrain
from sidecar import exceptions
from sidecar import constants


@pytest.mark.unit
class TestVaultBrain:
    """Test VaultBrain functionality."""

    @pytest.fixture
    def mock_ws_server(self):
        """Create a mock WebSocketServer."""
        return Mock()

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset VaultBrain singleton before and after each test."""
        VaultBrain._instance = None
        yield
        VaultBrain._instance = None

    @pytest.fixture
    def valid_vault(self, tmp_path):
        """Create a valid vault structure."""
        vault_path = tmp_path / "test_vault"
        vault_path.mkdir()
        (vault_path / ".vault.toml").write_text("")
        return vault_path

    @pytest.mark.asyncio
    async def test_init_valid_vault(self, valid_vault, mock_ws_server):
        """Test initialization with a valid vault."""

        brain = VaultBrain(valid_vault, mock_ws_server)
        await brain.initialize()

        assert brain.vault_path == valid_vault.resolve()
        assert brain.ws_server == mock_ws_server
        # Core commands are registered in initialize
        assert len(brain.commands) >= 3

    def test_init_nonexistent_vault(self, mock_ws_server):
        """Test initialization with nonexistent vault."""
        # Validation happens in __init__ (utils.validate_vault_path), so this remains sync check
        fake_path = Path("/nonexistent/path")

        with pytest.raises(exceptions.VaultNotFoundError):
            VaultBrain(fake_path, mock_ws_server)

    @pytest.mark.asyncio
    async def test_load_config_valid(self, valid_vault, mock_ws_server):
        """Test loading valid configuration."""
        brain = VaultBrain(valid_vault, mock_ws_server)
        await brain.initialize()
        assert isinstance(brain.config, dict)

    @pytest.mark.asyncio
    async def test_load_config_invalid_toml(self, valid_vault, mock_ws_server):
        """Test loading invalid TOML configuration."""
        (valid_vault / ".vault.toml").write_text("[invalid toml")

        brain = VaultBrain(valid_vault, mock_ws_server)

        brain = VaultBrain(valid_vault, mock_ws_server)

        # Should not raise, but fall back to defaults
        await brain.initialize()
        assert brain.config["name"] == valid_vault.name

    @patch("sidecar.utils.validate_plugin_structure")
    @patch("sidecar.vault_brain.importlib.util.spec_from_file_location")
    @patch("sidecar.vault_brain.importlib.util.module_from_spec")
    @pytest.mark.asyncio
    async def test_load_plugins(
        self, mock_module, mock_spec, mock_validate, valid_vault, mock_ws_server
    ):
        """Test loading plugins."""
        # Mock discovered plugin path by ensuring it exists in the valid_vault
        plugin_path = valid_vault / "plugins" / "test_plugin"
        # mock_discover.return_value = [plugin_path] -> We rely on filesystem now or need to mock get_plugins_dir if we want to isolate
        # The test actually creates the directories later, so standard discovery should work if we create files BEFORE initialize

        # Mock plugin module and class
        mock_plugin_instance = Mock()
        # PluginBase mocks
        mock_plugin_instance.register_commands = Mock()
        mock_plugin_instance.on_load = AsyncMock()

        mock_plugin_class = Mock(return_value=mock_plugin_instance)

        # Create a mock module with the plugin class
        mock_mod = MagicMock()
        setattr(mock_mod, "Plugin", mock_plugin_class)
        mock_module.return_value = mock_mod

        # Mock spec loader
        mock_spec_obj = Mock()
        mock_spec_obj.loader.exec_module = Mock()
        mock_spec.return_value = mock_spec_obj

        # Connect paths
        plugin_path.mkdir(parents=True, exist_ok=True)
        (plugin_path / "main.py").touch()
        # Create settings.json to enable plugin
        (plugin_path / "settings.json").write_text(
            '{"enabled": true, "key": "value"}'
        )  # plugin defaults still use settings.json

        brain = VaultBrain(valid_vault, mock_ws_server)
        await brain.initialize()

        # Verify plugin loaded
        assert "test_plugin" in brain.plugins
        assert brain.plugins["test_plugin"] == mock_plugin_instance

        # Verify instantiation with config
        mock_plugin_class.assert_called_once()
        call_kwargs = mock_plugin_class.call_args.kwargs
        assert call_kwargs["config"] == {"enabled": True, "key": "value"}
        mock_plugin_instance.register_commands.assert_called_once()
        mock_plugin_instance.on_load.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_commands_via_plugins(self, valid_vault, mock_ws_server):
        """Test command registration from plugins flows through initialize."""
        # This is strictly integration logic usually, but here we can test
        # specifically if register_commands is called on a mocked plugin.

        brain = VaultBrain(valid_vault, mock_ws_server)

        mock_plugin = Mock()
        mock_plugin.register_commands = Mock()
        mock_plugin.on_load = AsyncMock()

        # Inject plugin manually to simulate "loaded" state if we skip initialize() logic,
        # but here we want to test that initialize CALLS it.
        # See test_load_plugins above for that.

        # If testing Register Core Commands:
        await brain.initialize()
        assert "system.chat" in brain.commands

    @pytest.mark.asyncio
    async def test_tick_event_subscription(self, valid_vault, mock_ws_server):
        """Test that plugins are auto-subscribed to TICK event."""
        brain = VaultBrain(valid_vault, mock_ws_server)

        mock_plugin = Mock()
        mock_plugin.on_load = AsyncMock()
        mock_plugin.on_tick = AsyncMock()  # Async tick

        # Manually add plugin to verify subscription logic in _activate_plugins
        brain.plugins["test_plugin"] = mock_plugin

        # Trigger activation
        await brain._activate_plugins()

        # Verify subscription
        # Verify subscription - accessing EventBus internals
        assert constants.CoreEvents.TICK in brain.events._subscribers
        # subscribers are list of (priority, handler) tuples
        handlers = [h for p, h in brain.events._subscribers[constants.CoreEvents.TICK]]
        assert mock_plugin.on_tick in handlers

        # Verify publishing event calls the plugin
        await brain.publish(constants.CoreEvents.TICK)
        mock_plugin.on_tick.assert_called_once()

    @patch("sidecar.vault_brain.importlib.invalidate_caches")
    @patch("sidecar.vault_brain.importlib.util.spec_from_file_location")
    @patch("sidecar.vault_brain.importlib.util.module_from_spec")
    @pytest.mark.asyncio
    async def test_unload_and_reload_plugin(
        self, mock_module, mock_spec, mock_invalidate, valid_vault, mock_ws_server
    ):
        """Test unloading and reloading a plugin."""
        # 1. Setup mock plugin
        plugin_path = valid_vault / "plugins" / "test_hot_reload"
        plugin_path.mkdir(parents=True, exist_ok=True)
        (plugin_path / "main.py").touch()
        (plugin_path / "settings.json").write_text('{"enabled": true}')
        
        mock_plugin_instance = Mock()
        mock_plugin_instance.register_commands = Mock()
        mock_plugin_instance.on_load = AsyncMock()
        mock_plugin_instance.on_unload = AsyncMock()
        
        # We need a bound method mock to test unsubscribe
        async def mock_tick(): pass
        mock_plugin_instance.on_tick = mock_tick
        
        mock_plugin_class = Mock(return_value=mock_plugin_instance)
        mock_mod = MagicMock()
        setattr(mock_mod, "Plugin", mock_plugin_class)
        mock_module.return_value = mock_mod
        
        mock_spec_obj = Mock()
        mock_spec_obj.loader.exec_module = Mock()
        mock_spec.return_value = mock_spec_obj

        # Initialize Brain and load plugin
        brain = VaultBrain(valid_vault, mock_ws_server)
        await brain.initialize()

        assert "test_hot_reload" in brain.plugins
        
        # Add a mock command for this plugin
        async def dummy_cmd(): pass
        brain.register_command("test.cmd", dummy_cmd, plugin_name="test_hot_reload")
        assert "test.cmd" in brain.commands

        # ==========================================
        # Test Unload
        # ==========================================
        res_unload = await brain.unload_plugin(plugin_id="test_hot_reload")
        
        assert res_unload["status"] == "success"
        assert "test_hot_reload" not in brain.plugins
        assert "test.cmd" not in brain.commands
        mock_plugin_instance.on_unload.assert_called_once()
        
        # Check event unsubscribe 
        # (Though we used a bound method mock, we'd need to verify EventBus state cleanly)

        # ==========================================
        # Test Reload
        # ==========================================
        # Reset mocks
        mock_plugin_instance.on_load.reset_mock()
        mock_plugin_instance.register_commands.reset_mock()
        mock_invalidate.reset_mock()
        
        res_reload = await brain.reload_plugin(plugin_id="test_hot_reload")
        
        assert res_reload["status"] == "success"
        assert "test_hot_reload" in brain.plugins
        mock_invalidate.assert_called_once()
        mock_plugin_instance.on_load.assert_called_once()


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


    def test_singleton_reinit_is_guarded(self, valid_vault, mock_ws_server, tmp_path):
        """Calling VaultBrain.__init__ a second time must be a no-op."""
        brain = VaultBrain(valid_vault, mock_ws_server)
        original_path = brain.vault_path

        # Create a second distinct vault to pass to the re-init attempt
        other_vault = tmp_path / "other_vault"
        other_vault.mkdir()
        (other_vault / ".vault.toml").write_text("")

        # Simulate __init__ being called again on the same instance
        brain.__init__(other_vault, mock_ws_server)

        # vault_path must be unchanged — re-init was a no-op
        assert brain.vault_path == original_path
        assert brain._initialized is True



    @pytest.mark.asyncio
    async def test_register_command_no_override_raises(self, valid_vault, mock_ws_server):
        """Registering a duplicate command with override=False must raise."""
        brain = VaultBrain(valid_vault, mock_ws_server)
        await brain.initialize()

        async def handler_a(**kwargs): return {}
        async def handler_b(**kwargs): return {}

        brain.register_command("test.cmd", handler_a)

        with pytest.raises(exceptions.CommandRegistrationError):
            brain.register_command("test.cmd", handler_b, override=False)

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


@pytest.mark.unit
class TestCommandRegistry:
    """Test command registry functionality."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset VaultBrain singleton."""
        VaultBrain._instance = None
        yield
        VaultBrain._instance = None

    @pytest.fixture
    def brain(self, tmp_path):
        """Create a VaultBrain instance with mocks."""
        vault_path = tmp_path / "test_vault"
        vault_path.mkdir()
        (vault_path / ".vault.toml").write_text("")

        ws_server = Mock()
        ws_server.command_handlers = {}
        brain = VaultBrain(vault_path, ws_server)
        # We don't necessarily need full initialize for registry unit tests if we just use register_command directly
        return brain

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

        with pytest.raises(exceptions.CommandRegistrationError):
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
        with pytest.raises(exceptions.CommandNotFoundError):
            await brain.execute_command("non.existent")

    @pytest.mark.asyncio
    async def test_execute_command_execution_error(self, brain):
        """Test handling of execution errors."""

        async def failing_command():
            raise ValueError("Something went wrong")

        brain.register_command("test.fail", failing_command)

        with pytest.raises(exceptions.CommandExecutionError) as exc_info:
            await brain.execute_command("test.fail")

        # Check that original error is preserved/referenced
        assert "Something went wrong" in str(exc_info.value)

    def test_get_commands(self, brain):
        """Test listing commands."""

        async def cmd1():
            pass

        async def cmd2():
            pass

        brain.register_command("cmd1", cmd1, "plugin1")
        brain.register_command("cmd2", cmd2, "plugin2")

        # Direct access to commands dict since get_commands() doesn't exist
        assert "cmd1" in brain.commands
        assert "cmd2" in brain.commands
        assert brain.commands["cmd1"]["plugin"] == "plugin1"

    def test_register_command_override(self, brain):
        """Test overriding a command."""

        async def cmd1():
            return 1

        async def cmd2():
            return 2

        brain.register_command("test.cmd", cmd1)

        # Override with flag
        brain.register_command("test.cmd", cmd2, override=True)
        assert brain.commands["test.cmd"]["handler"] == cmd2

    def test_clear_subscribers(self, brain):
        """Test clearing event subscribers."""

        async def handler():
            pass

        brain.subscribe("test.evt", handler)
        # Check brain.events._subscribers
        assert len(brain.events._subscribers["test.evt"]) == 1

        brain.clear_subscribers("test.evt")
        assert len(brain.events._subscribers["test.evt"]) == 0
