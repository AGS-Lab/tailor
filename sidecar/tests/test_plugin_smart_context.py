"""
Tests for Smart Context Plugin.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from sidecar import constants

# Import the plugin module dynamically since it's not in the main package
import importlib.util


def load_plugin_module(plugin_path):
    spec = importlib.util.spec_from_file_location(
        "smart_context_main", plugin_path / "main.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def smart_context_plugin_cls(tmp_path):
    """Load the Smart Context plugin class."""
    # We need to point to the actual plugin location
    # Assuming test is run from project root, locate the plugin
    base_dir = Path(__file__).resolve().parent.parent.parent
    plugin_path = base_dir / "example-vault" / "plugins" / "smart_context"

    module = load_plugin_module(plugin_path)
    return module.Plugin


@pytest.fixture
def mock_brain():
    """Create a mock VaultBrain."""
    brain = MagicMock()
    brain.emit_to_frontend = MagicMock()
    brain.notify_frontend = MagicMock()
    return brain


@pytest.fixture
def plugin_instance(smart_context_plugin_cls, tmp_path, mock_brain):
    """Create an instance of the Smart Context plugin."""
    plugin_dir = tmp_path / "plugins" / "smart_context"
    plugin_dir.mkdir(parents=True)
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    with patch("sidecar.vault_brain.VaultBrain.get", return_value=mock_brain):
        plugin = smart_context_plugin_cls(plugin_dir, vault_path)
    return plugin


@pytest.mark.asyncio
class TestSmartContextPlugin:
    async def test_init(self, plugin_instance):
        """Test plugin initialization."""
        assert plugin_instance.name == "smart_context"
        assert plugin_instance.panel_id == "smart-context-panel"

    async def test_on_client_connected_registers_panel(
        self, plugin_instance, mock_brain
    ):
        """Test that panel is registered when client connects."""

        with patch("sidecar.vault_brain.VaultBrain.get", return_value=mock_brain):
            await plugin_instance.on_client_connected()

            # Check register_panel call (which emits UI_COMMAND)
            # We check the calls to brain.emit_to_frontend

            # Should have registered panel
            register_call = None
            set_content_call = None

            for call in mock_brain.emit_to_frontend.call_args_list:
                args, kwargs = call
                data = kwargs.get("data", {})
                if data.get("action") == constants.UIAction.REGISTER_PANEL.value:
                    register_call = data
                elif data.get("action") == constants.UIAction.SET_PANEL.value:
                    set_content_call = data

            assert register_call is not None
            assert register_call["id"] == "smart-context-panel"
            assert register_call["title"] == "Smart Context"

            # Should have set initial content
            assert set_content_call is not None
            assert set_content_call["id"] == "smart-context-panel"
            assert "Waiting for context" in set_content_call["html"]

    async def test_on_unload_removes_panel(self, plugin_instance, mock_brain):
        """Test that panel is removed when plugin unloads."""

        with patch("sidecar.vault_brain.VaultBrain.get", return_value=mock_brain):
            await plugin_instance.on_unload()

            # Check remove_panel call
            remove_call = None
            for call in mock_brain.emit_to_frontend.call_args_list:
                args, kwargs = call
                data = kwargs.get("data", {})
                if data.get("action") == constants.UIAction.REMOVE_PANEL.value:
                    remove_call = data

            assert remove_call is not None
            assert remove_call["id"] == "smart-context-panel"


def _load_embedding_cache():
    base = Path(__file__).resolve().parent.parent.parent
    spec = importlib.util.spec_from_file_location(
        "embedding_cache",
        base / "example-vault/plugins/smart_context/embedding_cache.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.EmbeddingCache

def test_embedding_cache_miss_returns_none(tmp_path):
    EmbeddingCache = _load_embedding_cache()
    cache = EmbeddingCache(tmp_path, "chat_abc")
    assert cache.get("msg1", "hello world") is None

def test_embedding_cache_stores_and_retrieves(tmp_path):
    EmbeddingCache = _load_embedding_cache()
    cache = EmbeddingCache(tmp_path, "chat_abc")
    cache.set("msg1", "hello world", [0.1, 0.2, 0.3])
    assert cache.get("msg1", "hello world") == [0.1, 0.2, 0.3]

def test_embedding_cache_persists_across_instances(tmp_path):
    EmbeddingCache = _load_embedding_cache()
    EmbeddingCache(tmp_path, "chat_abc").set("msg1", "text", [1.0, 2.0])
    assert EmbeddingCache(tmp_path, "chat_abc").get("msg1", "text") == [1.0, 2.0]

def test_embedding_cache_content_change_is_cache_miss(tmp_path):
    EmbeddingCache = _load_embedding_cache()
    cache = EmbeddingCache(tmp_path, "chat_abc")
    cache.set("msg1", "original", [0.1, 0.2])
    assert cache.get("msg1", "modified") is None
