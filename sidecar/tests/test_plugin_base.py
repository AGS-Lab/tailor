"""
Tests for PluginBase class.

Verifies that:
- Plugins can inherit from PluginBase
- Lifecycle hooks work correctly
- UI helper methods delegate to brain correctly
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from sidecar.api.plugin_base import PluginBase
from sidecar import constants


class ConcretePlugin(PluginBase):
    """Concrete implementation for testing."""

    def register_commands(self) -> None:
        pass


@pytest.fixture
def mock_brain():
    """Create a mock VaultBrain."""
    brain = MagicMock()
    brain.emit_to_frontend = MagicMock()
    brain.notify_frontend = MagicMock()
    brain.update_state = MagicMock()
    brain.subscribe_internal = MagicMock()
    brain.publish = AsyncMock()
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

    def test_init(self, plugin_dir, vault_path):
        """Verify initialization."""
        plugin = ConcretePlugin(plugin_dir, vault_path)

        assert plugin.name == "test_plugin"
        assert plugin.plugin_dir == plugin_dir
        assert plugin.vault_path == vault_path
        assert plugin.config == {}
        assert plugin.is_loaded is False

    def test_init_with_config(self, plugin_dir, vault_path):
        """Verify initialization with config."""
        config = {"enabled": True, "foo": "bar"}
        plugin = ConcretePlugin(plugin_dir, vault_path, config=config)

        assert plugin.config == config

    def test_brain_property_access(self, plugin_dir, vault_path, mock_brain):
        """Verify brain property retrieves singleton."""
        plugin = ConcretePlugin(plugin_dir, vault_path)

        # Mock VaultBrain.get() to return our mock_brain
        with patch("sidecar.vault_brain.VaultBrain.get", return_value=mock_brain):
            assert plugin.brain == mock_brain

    @pytest.mark.asyncio
    async def test_lifecycle_flags(self, plugin_dir, vault_path):
        """Verify on_load/on_unload update flags."""
        plugin = ConcretePlugin(plugin_dir, vault_path)

        assert not plugin.is_loaded
        await plugin.on_load()
        assert plugin.is_loaded

        await plugin.on_unload()
        assert not plugin.is_loaded

    def test_notify_delegates_to_brain(self, plugin_dir, vault_path, mock_brain):
        """Verify notify calls brain.notify_frontend."""
        plugin = ConcretePlugin(plugin_dir, vault_path)

        with patch("sidecar.vault_brain.VaultBrain.get", return_value=mock_brain):
            plugin.notify("Hello", "success")

            mock_brain.notify_frontend.assert_called_with("Hello", "success")

    def test_progress_delegates_to_brain(self, plugin_dir, vault_path, mock_brain):
        """Verify progress calls brain.emit_to_frontend."""
        plugin = ConcretePlugin(plugin_dir, vault_path)

        with patch("sidecar.vault_brain.VaultBrain.get", return_value=mock_brain):
            plugin.progress(50, "Loading")

            mock_brain.emit_to_frontend.assert_called_with(
                constants.EventType.PROGRESS, {"percentage": 50, "message": "Loading"}
            )

    def test_update_state_delegates_to_brain(self, plugin_dir, vault_path, mock_brain):
        """Verify update_state calls brain.update_state."""
        plugin = ConcretePlugin(plugin_dir, vault_path)

        with patch("sidecar.vault_brain.VaultBrain.get", return_value=mock_brain):
            plugin.update_state("key", "value")

            mock_brain.update_state.assert_called_with("key", "value")

    @pytest.mark.asyncio
    async def test_publish_delegates_to_brain(self, plugin_dir, vault_path, mock_brain):
        """Verify publish calls brain.publish."""
        plugin = ConcretePlugin(plugin_dir, vault_path)

        with patch("sidecar.vault_brain.VaultBrain.get", return_value=mock_brain):
            await plugin.publish("my.event", data=123)

            mock_brain.publish.assert_called_with("my.event", data=123)

    @pytest.mark.asyncio
    async def test_register_sidebar_view(self, plugin_dir, vault_path, mock_brain):
        """Verify register_sidebar_view emits UI_COMMAND."""
        plugin = ConcretePlugin(plugin_dir, vault_path)

        with patch("sidecar.vault_brain.VaultBrain.get", return_value=mock_brain):
            await plugin.register_sidebar_view("id", "icon", "Title")

            mock_brain.emit_to_frontend.assert_called()
            call_args = mock_brain.emit_to_frontend.call_args

            assert call_args.kwargs["event_type"] == constants.EventType.UI_COMMAND
            assert call_args.kwargs["data"]["action"] == "register_sidebar"
            assert call_args.kwargs["scope"] == constants.EventScope.WINDOW

    @pytest.mark.asyncio
    async def test_set_sidebar_content(self, plugin_dir, vault_path, mock_brain):
        """Verify set_sidebar_content emits UI_COMMAND."""
        plugin = ConcretePlugin(plugin_dir, vault_path)

        with patch("sidecar.vault_brain.VaultBrain.get", return_value=mock_brain):
            await plugin.set_sidebar_content("id", "<html>")

            mock_brain.emit_to_frontend.assert_called()
            call_args = mock_brain.emit_to_frontend.call_args

            assert call_args.kwargs["event_type"] == constants.EventType.UI_COMMAND
            assert call_args.kwargs["data"]["action"] == "set_sidebar"
