"""
Tests for PluginBase class.

Verifies that:
- Plugins can inherit from PluginBase
- register_commands is called during __init__
- Lifecycle hooks work correctly
- UI helper methods work correctly
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

# Use the sidecar package (conftest.py should add tailor to path)
from sidecar.api.plugin_base import PluginBase


class ConcretePlugin(PluginBase):
    """Concrete implementation for testing."""
    
    def __init__(self, emitter, brain, plugin_dir, vault_path):
        self.commands_registered = False
        super().__init__(emitter, brain, plugin_dir, vault_path)
    
    def register_commands(self) -> None:
        self.commands_registered = True
        self.brain.register_command(
            "test.hello",
            self.hello_handler,
            self.name
        )
    
    async def hello_handler(self, **kwargs):
        return {"message": "Hello from test plugin!"}


@pytest.fixture
def mock_emitter():
    """Create a mock EventEmitter."""
    emitter = MagicMock()
    emitter.emit = MagicMock()
    emitter.notify = MagicMock()
    return emitter


@pytest.fixture
def mock_brain():
    """Create a mock VaultBrain."""
    brain = MagicMock()
    brain.register_command = MagicMock()
    return brain


@pytest.fixture
def plugin_dir(tmp_path):
    """Create a temporary plugin directory."""
    plugin_path = tmp_path / "test_plugin"
    plugin_path.mkdir()
    return plugin_path


@pytest.fixture
def vault_path(tmp_path):
    """Create a temporary vault directory."""
    vault = tmp_path / "test_vault"
    vault.mkdir()
    return vault


class TestPluginBase:
    """Tests for PluginBase class."""
    
    def test_init_calls_register_commands(
        self, mock_emitter, mock_brain, plugin_dir, vault_path
    ):
        """Verify register_commands is called during __init__."""
        plugin = ConcretePlugin(mock_emitter, mock_brain, plugin_dir, vault_path)
        
        assert plugin.commands_registered is True
        mock_brain.register_command.assert_called_once()
    
    def test_plugin_name_from_directory(
        self, mock_emitter, mock_brain, plugin_dir, vault_path
    ):
        """Verify plugin name is derived from directory name."""
        plugin = ConcretePlugin(mock_emitter, mock_brain, plugin_dir, vault_path)
        
        assert plugin.name == "test_plugin"
    
    def test_plugin_paths_are_set(
        self, mock_emitter, mock_brain, plugin_dir, vault_path
    ):
        """Verify plugin and vault paths are stored correctly."""
        plugin = ConcretePlugin(mock_emitter, mock_brain, plugin_dir, vault_path)
        
        assert plugin.plugin_dir == plugin_dir
        assert plugin.vault_path == vault_path
    
    @pytest.mark.asyncio
    async def test_on_load_sets_loaded_flag(
        self, mock_emitter, mock_brain, plugin_dir, vault_path
    ):
        """Verify on_load sets _loaded to True."""
        plugin = ConcretePlugin(mock_emitter, mock_brain, plugin_dir, vault_path)
        
        assert plugin.is_loaded is False
        await plugin.on_load()
        assert plugin.is_loaded is True
    
    @pytest.mark.asyncio
    async def test_on_unload_clears_loaded_flag(
        self, mock_emitter, mock_brain, plugin_dir, vault_path
    ):
        """Verify on_unload sets _loaded to False."""
        plugin = ConcretePlugin(mock_emitter, mock_brain, plugin_dir, vault_path)
        
        await plugin.on_load()
        assert plugin.is_loaded is True
        
        await plugin.on_unload()
        assert plugin.is_loaded is False
    
    def test_get_config_path(
        self, mock_emitter, mock_brain, plugin_dir, vault_path
    ):
        """Verify get_config_path returns correct path."""
        plugin = ConcretePlugin(mock_emitter, mock_brain, plugin_dir, vault_path)
        
        config_path = plugin.get_config_path("settings.json")
        assert config_path == plugin_dir / "settings.json"
    
    def test_load_settings_returns_empty_if_no_file(
        self, mock_emitter, mock_brain, plugin_dir, vault_path
    ):
        """Verify load_settings returns empty dict if file doesn't exist."""
        plugin = ConcretePlugin(mock_emitter, mock_brain, plugin_dir, vault_path)
        
        settings = plugin.load_settings()
        assert settings == {}
    
    def test_save_and_load_settings(
        self, mock_emitter, mock_brain, plugin_dir, vault_path
    ):
        """Verify settings can be saved and loaded."""
        plugin = ConcretePlugin(mock_emitter, mock_brain, plugin_dir, vault_path)
        
        test_settings = {"api_key": "test123", "enabled": True}
        result = plugin.save_settings(test_settings)
        
        assert result is True
        
        loaded = plugin.load_settings()
        assert loaded == test_settings


class TestPluginBaseUIHelpers:
    """Tests for PluginBase UI helper methods."""
    
    @pytest.mark.asyncio
    async def test_register_sidebar_view_emits_event(
        self, mock_emitter, mock_brain, plugin_dir, vault_path
    ):
        """Verify register_sidebar_view emits correct UI_COMMAND event."""
        plugin = ConcretePlugin(mock_emitter, mock_brain, plugin_dir, vault_path)
        
        await plugin.register_sidebar_view(
            identifier="test.sidebar",
            icon_svg="folder",
            title="Test Sidebar"
        )
        
        mock_emitter.emit.assert_called_once()
        call_args = mock_emitter.emit.call_args
        
        assert call_args.kwargs["event_type"] == "UI_COMMAND"
        assert call_args.kwargs["data"]["action"] == "register_sidebar"
        assert call_args.kwargs["data"]["id"] == "test.sidebar"
        assert call_args.kwargs["data"]["icon"] == "folder"
        assert call_args.kwargs["data"]["title"] == "Test Sidebar"
    
    @pytest.mark.asyncio
    async def test_set_sidebar_content_emits_event(
        self, mock_emitter, mock_brain, plugin_dir, vault_path
    ):
        """Verify set_sidebar_content emits correct UI_COMMAND event."""
        plugin = ConcretePlugin(mock_emitter, mock_brain, plugin_dir, vault_path)
        
        await plugin.set_sidebar_content(
            identifier="test.sidebar",
            html_content="<div>Hello World</div>"
        )
        
        mock_emitter.emit.assert_called_once()
        call_args = mock_emitter.emit.call_args
        
        assert call_args.kwargs["event_type"] == "UI_COMMAND"
        assert call_args.kwargs["data"]["action"] == "set_sidebar"
        assert call_args.kwargs["data"]["id"] == "test.sidebar"
        assert call_args.kwargs["data"]["html"] == "<div>Hello World</div>"
