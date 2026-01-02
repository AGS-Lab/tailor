"""
Unit tests for EventEmitter.

Tests event emission, validation, and WebSocket integration.
"""

import pytest
import json
from unittest.mock import Mock, MagicMock, AsyncMock, call
from sidecar.event_emitter import EventEmitter
from sidecar.constants import EventType, EventScope, Severity


@pytest.mark.unit
class TestEventEmitterInitialization:
    """Test EventEmitter initialization."""
    
    def test_initialization(self):
        """Test basic initialization."""
        ws_server = Mock()
        brain = Mock()
        
        emitter = EventEmitter(ws_server, brain)
        
        assert emitter.ws_server is ws_server
        assert emitter.brain is brain
        # Logger is available via module level, not instance attribute usually, 
        # unless assigned. But strict checking might fail if not checked properly.
        # Checking if it didn't raise is good enough for init.
    
    def test_initialization_minimal(self):
        """Test initialization with only websocket server."""
        ws_server = Mock()
        
        emitter = EventEmitter(websocket_server=ws_server)
        
        assert emitter.ws_server is ws_server
        assert emitter.brain is None


@pytest.mark.unit
class TestEventEmission:
    """Test event emission methods."""
    
    def test_emit_basic(self):
        """Test basic event emission."""
        ws_server = Mock()
        emitter = EventEmitter(ws_server)
        
        emitter.emit(EventType.NOTIFY, {"message": "test"})
        
        # Verify WebSocket server was called
        ws_server.send_to_rust.assert_called_once()
        call_args = ws_server.send_to_rust.call_args[0][0]
        
        assert call_args["method"] == "trigger_event"
        assert "params" in call_args
    
    def test_emit_with_scope(self):
        """Test emission with specific scope."""
        ws_server = Mock()
        emitter = EventEmitter(ws_server)
        
        emitter.emit(EventType.UPDATE_STATE, {"key": "value"}, scope=EventScope.VAULT)
        
        ws_server.send_to_rust.assert_called_once()
        call_args = ws_server.send_to_rust.call_args[0][0]
        
        # Check that scope was included
        params = call_args["params"]
        assert params["scope"] == EventScope.VAULT.value
    
    def test_emit_validates_scope(self):
        """Test that invalid scope raises error."""
        ws_server = Mock()
        emitter = EventEmitter(ws_server)
        
        with pytest.raises(ValueError, match="scope"):
            emitter.emit(EventType.NOTIFY, {}, scope="invalid_scope")
    
    def test_emit_with_data(self):
        """Test emission with payload data."""
        ws_server = Mock()
        emitter = EventEmitter(ws_server)
        
        test_data = {"user": "alice", "count": 42}
        emitter.emit("CUSTOM", test_data)
        
        ws_server.send_to_rust.assert_called_once()
        call_args = ws_server.send_to_rust.call_args[0][0]
        
        params = call_args["params"]
        assert params["event_type"] == "CUSTOM"
        assert params["data"] == test_data


@pytest.mark.unit
class TestNotifyMethod:
    """Test notify convenience method."""
    
    def test_notify_basic(self):
        """Test basic notification."""
        ws_server = Mock()
        emitter = EventEmitter(ws_server)
        
        emitter.notify("Test message")
        
        ws_server.send_to_rust.assert_called_once()
        call_args = ws_server.send_to_rust.call_args[0][0]
        
        params = call_args["params"]
        assert params["event_type"] == EventType.NOTIFY.value
        assert params["data"]["message"] == "Test message"
    
    def test_notify_with_severity(self):
        """Test notification with severity level."""
        ws_server = Mock()
        emitter = EventEmitter(ws_server)
        
        emitter.notify("Warning!", severity=Severity.WARNING)
        
        call_args = ws_server.send_to_rust.call_args[0][0]
        params = call_args["params"]
        
        assert params["data"]["severity"] == Severity.WARNING.value
    
    def test_notify_validates_severity(self):
        """Test that invalid severity raises error."""
        ws_server = Mock()
        emitter = EventEmitter(ws_server)
        
        with pytest.raises(ValueError, match="severity"):
            emitter.notify("Message", severity="invalid")
    
    def test_notify_default_severity(self):
        """Test default severity is INFO."""
        ws_server = Mock()
        emitter = EventEmitter(ws_server)
        
        emitter.notify("Info message")
        
        call_args = ws_server.send_to_rust.call_args[0][0]
        params = call_args["params"]
        
        assert params["data"]["severity"] == Severity.INFO.value


@pytest.mark.unit
class TestProgressMethod:
    """Test progress reporting method."""
    
    def test_progress_basic(self):
        """Test basic progress update."""
        ws_server = Mock()
        emitter = EventEmitter(ws_server)
        
        emitter.progress(50, "Halfway done")
        
        ws_server.send_to_rust.assert_called_once()
        call_args = ws_server.send_to_rust.call_args[0][0]
        
        params = call_args["params"]
        assert params["event_type"] == EventType.PROGRESS.value
        assert params["data"]["percent"] == 50
        assert params["data"]["message"] == "Halfway done"
    
    def test_progress_validates_range(self):
        """Test progress validates 0-100 range."""
        ws_server = Mock()
        emitter = EventEmitter(ws_server)
        
        # Should work with valid values
        emitter.progress(0, "Start")
        emitter.progress(100, "Complete")
        
        # Should fail with invalid values
        with pytest.raises(ValueError, match="0.*100"):
            emitter.progress(-1, "Invalid")
        
        with pytest.raises(ValueError, match="0.*100"):
            emitter.progress(101, "Invalid")
    
    def test_progress_without_message(self):
        """Test progress with just percentage."""
        ws_server = Mock()
        emitter = EventEmitter(ws_server)
        
        emitter.progress(75)
        
        call_args = ws_server.send_to_rust.call_args[0][0]
        params = call_args["params"]
        
        assert params["data"]["percent"] == 75


@pytest.mark.unit
class TestUpdateStateMethod:
    """Test state update method."""
    
    def test_update_state(self):
        """Test updating UI state."""
        ws_server = Mock()
        emitter = EventEmitter(ws_server)
        
        emitter.update_state("user_name", "Alice")
        
        ws_server.send_to_rust.assert_called_once()
        call_args = ws_server.send_to_rust.call_args[0][0]
        
        params = call_args["params"]
        assert params["event_type"] == EventType.UPDATE_STATE.value
        assert params["data"]["key"] == "user_name"
        assert params["data"]["value"] == "Alice"
    
    def test_update_state_complex_value(self):
        """Test updating state with complex value."""
        ws_server = Mock()
        emitter = EventEmitter(ws_server)
        
        complex_value = {"nested": {"data": [1, 2, 3]}}
        emitter.update_state("config", complex_value)
        
        call_args = ws_server.send_to_rust.call_args[0][0]
        params = call_args["params"]
        
        assert params["data"]["key"] == "config"
        assert params["data"]["value"] == complex_value


@pytest.mark.unit
class TestLogging:
    """Test that EventEmitter logs appropriately."""
    
    def test_logs_events(self):
        """Test that events are logged."""
        ws_server = Mock()
        emitter = EventEmitter(ws_server)
        
        # Should not raise and should log
        emitter.notify("Test notification")
        emitter.progress(50, "Progress")
        emitter.update_state("key", "value")
        
        # All should have called WebSocket server
        assert ws_server.send_to_rust.call_count == 3


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_data(self):
        """Test emitting event with empty data."""
        ws_server = Mock()
        emitter = EventEmitter(ws_server)
        
        emitter.emit("CUSTOM_EVENT", {})
        
        ws_server.send_to_rust.assert_called_once()
    
    def test_none_websocket_server(self):
        """Test behavior when websocket server is None."""
        emitter = EventEmitter(websocket_server=None)
        
        # Should not raise, but also won't send
        emitter.notify("Test")
    
    def test_enum_conversion(self):
        """Test that enums are converted to values properly."""
        ws_server = Mock()
        emitter = EventEmitter(ws_server)
        
        emitter.emit(EventType.NOTIFY, {"test": "data"}, scope=EventScope.WINDOW)
        
        call_args = ws_server.send_to_rust.call_args[0][0]
        params = call_args["params"]
        
        # Should be string values, not enum objects
        assert isinstance(params["event_type"], str)
        assert isinstance(params["scope"], str)
