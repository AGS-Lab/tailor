"""
Tests for sidecar decorators.
"""
import pytest
import asyncio
from unittest.mock import Mock, MagicMock, AsyncMock
from sidecar.decorators import command, on_event
from sidecar.vault_brain import VaultBrain

@pytest.mark.unit
class TestDecorators:
    """Test standard decorators."""
    
    def test_command_decorator_metadata(self):
        """Test that @command attaches correct metadata."""
        
        @command("test.cmd", "test_plugin")
        async def my_handler():
            pass
            
        assert hasattr(my_handler, "_command_meta")
        assert len(my_handler._command_meta) == 1
        meta = my_handler._command_meta[0]
        assert meta["id"] == "test.cmd"
        assert meta["plugin"] == "test_plugin"

    def test_on_event_decorator_metadata(self):
        """Test that @on_event attaches correct metadata."""
        
        @on_event("test_event")
        async def my_listener():
            pass
            
        assert hasattr(my_listener, "_event_meta")
        assert len(my_listener._event_meta) == 1
        meta = my_listener._event_meta[0]
        assert meta["event"] == "test_event"

@pytest.mark.unit
class TestVaultBrainIntegration:
    """Test VaultBrain integration with decorators."""
    
    @pytest.fixture
    def mock_brain(self):
        """Create a partial mock of VaultBrain."""
        # We don't want to init full VaultBrain, just test registration
        brain = Mock(spec=VaultBrain)
        brain.commands = {}
        brain.subscribers = {}
        brain.register_command = VaultBrain.register_command.__get__(brain, VaultBrain)
        brain.subscribe = VaultBrain.subscribe.__get__(brain, VaultBrain)
        brain._register_decorated_handlers = VaultBrain._register_decorated_handlers.__get__(brain, VaultBrain)
        return brain

    def test_register_decorated_handlers(self):
        """Test scanning and registration."""
        
        class MockBrain(VaultBrain):
            def __init__(self):
                self.commands = {}
                self.subscribers = {} # Using dict/list for mock simplifiction? VaultBrain uses defaultdict(list)
                from collections import defaultdict
                self.subscribers = defaultdict(list)
                
            @command("test.cmd", "core")
            async def cmd_handler(self):
                pass
                
            @on_event("test_event")
            async def evt_handler(self):
                pass

        brain = MockBrain()
        brain._register_decorated_handlers()
        
        # Verify Command
        assert "test.cmd" in brain.commands
        assert brain.commands["test.cmd"]["handler"] == brain.cmd_handler
        assert brain.commands["test.cmd"]["plugin"] == "core"
        
        # Verify Event
        assert "test_event" in brain.subscribers
        assert brain.evt_handler in brain.subscribers["test_event"]

    @pytest.mark.asyncio
    async def test_plugin_install_arg_handling(self):
        """Test flexibility of install_plugin args."""
        # Use a real VaultBrain instance (mocked deps) to test the method logic
        # We need to mock PluginInstaller
        
        brain = MagicMock(spec=VaultBrain)
        brain.plugin_installer = Mock()
        brain.plugin_installer.install_from_url = AsyncMock(return_value=Mock(status=Mock(value="success"), plugin_id="pid", message="msg", manifest={}))
        
        # Bind the method
        install_method = VaultBrain.install_plugin.__get__(brain, VaultBrain)
        
        # from unittest.mock import AsyncMock # Removed inner import

        
        # Case 1: Direct kwargs (What we expect generally)
        await install_method(download_url="http://url", plugin_id="pid")
        brain.plugin_installer.install_from_url.assert_called_with("http://url", "pid")
        
        brain.plugin_installer.install_from_url.reset_mock()
        
        # Case 2: 'p' dict (Possible legacy format from Frontend?)
        # If the frontend passes {"p": {"download_url": "...", "plugin_id": "..."}}
        # Then kwargs will contain 'p'
        p_dict = {"download_url": "http://url2", "plugin_id": "pid2"}
        
        await install_method(p=p_dict)
        brain.plugin_installer.install_from_url.assert_called_with("http://url2", "pid2")
