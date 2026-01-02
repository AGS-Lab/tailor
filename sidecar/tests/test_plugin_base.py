"""
Unit tests for PluginBase abstract class.

Tests plugin lifecycle, helper methods, and settings management.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from sidecar.api.plugin_base import PluginBase


class ConcretePlugin(PluginBase):
    """Concrete implementation of PluginBase for testing."""
    
    def __init__(self, emitter, brain, plugin_dir, vault_path):
        super().__init__(emitter, brain, plugin_dir, vault_path)
        self.commands_registered = False
    
    def register_commands(self) -> None:
        """Required method implementation."""
        self.commands_registered = True


@pytest.mark.unit
class TestPluginBaseInitialization:
    """Test PluginBase initialization."""
    
    def test_initialization(self, tmp_path):
        """Test basic plugin initialization."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        
        emitter = Mock()
        brain = Mock()
        
        plugin = ConcretePlugin(emitter, brain, plugin_dir, vault_path)
        
        assert plugin.emitter is emitter
        assert plugin.brain is brain
        assert plugin.plugin_dir == plugin_dir
        assert plugin.vault_path == vault_path
        assert plugin.name == "test_plugin"
        assert plugin.logger is not None
    
    def test_plugin_name_from_directory(self, tmp_path):
        """Test that plugin name is derived from directory name."""
        plugin_dir = tmp_path / "my_awesome_plugin"
        plugin_dir.mkdir()
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        
        plugin = ConcretePlugin(Mock(), Mock(), plugin_dir, vault_path)
        
        assert plugin.name == "my_awesome_plugin"
    
    def test_is_loaded_initially_false(self, tmp_path):
        """Test that is_loaded is False initially."""
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        
        plugin = ConcretePlugin(Mock(), Mock(), plugin_dir, vault_path)
        
        assert plugin.is_loaded is False


@pytest.mark.unit
class TestPluginBaseLifecycle:
    """Test plugin lifecycle hooks."""
    
    @pytest.mark.asyncio
    async def test_on_load(self, tmp_path):
        """Test on_load lifecycle hook."""
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        
        plugin = ConcretePlugin(Mock(), Mock(), plugin_dir, vault_path)
        
        # Initially not loaded
        assert plugin.is_loaded is False
        
        # Call on_load
        await plugin.on_load()
        
        # Now should be loaded
        assert plugin.is_loaded is True
    
    @pytest.mark.asyncio
    async def test_on_tick(self, tmp_path):
        """Test on_tick lifecycle hook (default implementation)."""
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        
        plugin = ConcretePlugin(Mock(), Mock(), plugin_dir, vault_path)
        emitter = Mock()
        
        # Should not raise (default implementation does nothing)
        await plugin.on_tick(emitter)
    
    @pytest.mark.asyncio
    async def test_on_unload(self, tmp_path):
        """Test on_unload lifecycle hook."""
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        
        plugin = ConcretePlugin(Mock(), Mock(), plugin_dir, vault_path)
        
        # Load then unload
        await plugin.on_load()
        assert plugin.is_loaded is True
        
        await plugin.on_unload()
        assert plugin.is_loaded is False


@pytest.mark.unit
class TestPluginBaseSettings:
    """Test settings management."""
    
    def test_get_config_path(self, tmp_path):
        """Test getting config file path."""
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        
        plugin = ConcretePlugin(Mock(), Mock(), plugin_dir, vault_path)
        
        config_path = plugin.get_config_path("settings.json")
        
        assert config_path == plugin_dir / "settings.json"
    
    def test_get_config_path_custom_filename(self, tmp_path):
        """Test getting config path with custom filename."""
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        
        plugin = ConcretePlugin(Mock(), Mock(), plugin_dir, vault_path)
        
        config_path = plugin.get_config_path("custom.json")
        
        assert config_path == plugin_dir / "custom.json"
    
    def test_load_settings_existing_file(self, tmp_path):
        """Test loading settings from existing file."""
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        
        # Create settings file
        settings_file = plugin_dir / "settings.json"
        test_settings = {"key": "value", "count": 42}
        settings_file.write_text(json.dumps(test_settings))
        
        plugin = ConcretePlugin(Mock(), Mock(), plugin_dir, vault_path)
        
        loaded = plugin.load_settings()
        
        assert loaded == test_settings
    
    def test_load_settings_nonexistent_file(self, tmp_path):
        """Test loading settings when file doesn't exist."""
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        
        plugin = ConcretePlugin(Mock(), Mock(), plugin_dir, vault_path)
        
        loaded = plugin.load_settings()
        
        assert loaded == {}
    
    def test_load_settings_invalid_json(self, tmp_path):
        """Test loading settings with invalid JSON."""
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        
        # Create invalid JSON file
        settings_file = plugin_dir / "settings.json"
        settings_file.write_text("not valid json{")
        
        plugin = ConcretePlugin(Mock(), Mock(), plugin_dir, vault_path)
        
        loaded = plugin.load_settings()
        
        # Should return empty dict on error
        assert loaded == {}
    
    def test_save_settings(self, tmp_path):
        """Test saving settings to file."""
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        
        plugin = ConcretePlugin(Mock(), Mock(), plugin_dir, vault_path)
        
        test_settings = {"key": "value", "number": 123}
        result = plugin.save_settings(test_settings)
        
        assert result is True
        
        # Verify file was created
        settings_file = plugin_dir / "settings.json"
        assert settings_file.exists()
        
        # Verify content
        saved = json.loads(settings_file.read_text())
        assert saved == test_settings
    
    def test_save_settings_custom_filename(self, tmp_path):
        """Test saving settings with custom filename."""
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        
        plugin = ConcretePlugin(Mock(), Mock(), plugin_dir, vault_path)
        
        test_settings = {"data": "test"}
        result = plugin.save_settings(test_settings, "custom.json")
        
        assert result is True
        
        # Verify correct file was created
        settings_file = plugin_dir / "custom.json"
        assert settings_file.exists()


@pytest.mark.unit
class TestPluginBaseProperties:
    """Test plugin properties."""
    
    def test_repr(self, tmp_path):
        """Test string representation."""
        plugin_dir = tmp_path / "my_plugin"
        plugin_dir.mkdir()
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        
        plugin = ConcretePlugin(Mock(), Mock(), plugin_dir, vault_path)
        
        repr_str = repr(plugin)
        
        assert "ConcretePlugin" in repr_str
        assert "my_plugin" in repr_str
        assert "loaded" in repr_str.lower()


@pytest.mark.unit
class TestPluginBaseAbstract:
    """Test abstract class enforcement."""
    
    def test_cannot_instantiate_base_class(self, tmp_path):
        """Test that PluginBase cannot be instantiated directly."""
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        
        with pytest.raises(TypeError):
            # Should fail because register_commands is abstract
            plugin = PluginBase(Mock(), Mock(), plugin_dir, vault_path)
    
    def test_must_implement_register_commands(self, tmp_path):
        """Test that subclasses must implement register_commands."""
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        
        # Create subclass without register_commands
        class IncompletePlugin(PluginBase):
            pass
        
        with pytest.raises(TypeError):
            plugin = IncompletePlugin(Mock(), Mock(), plugin_dir, vault_path)


@pytest.mark.unit
class TestPluginBaseIntegration:
    """Integration tests for PluginBase."""
    
    def test_full_lifecycle(self, tmp_path):
        """Test complete plugin lifecycle."""
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        
        # Create plugin with settings
        settings_file = plugin_dir / "settings.json"
        settings_file.write_text(json.dumps({"initialized": True}))
        
        plugin = ConcretePlugin(Mock(), Mock(), plugin_dir, vault_path)
        
        # Load settings
        settings = plugin.load_settings()
        assert settings["initialized"] is True
        
        # Lifecycle
        assert not plugin.is_loaded
        
        # Would be called by VaultBrain
        import asyncio
        asyncio.run(plugin.on_load())
        assert plugin.is_loaded
        
        # Save modified settings
        settings["count"] = 1
        plugin.save_settings(settings)
        
        # Unload
        asyncio.run(plugin.on_unload())
        assert not plugin.is_loaded
        
        # Verify settings persisted
        reloaded = plugin.load_settings()
        assert reloaded["count"] == 1
