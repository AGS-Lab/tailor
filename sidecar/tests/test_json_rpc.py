"""
Unit tests for JSON-RPC utilities.

Tests message building, validation, and helper functions.
"""

import pytest
from sidecar.utils.json_rpc import (
    build_request,
    build_response,
    build_error,
    validate_jsonrpc_message,
    is_request,
    is_response,
    is_notification,
    get_request_id,
    get_method,
    get_params,
)
from sidecar.exceptions import JSONRPCError


@pytest.mark.unit
class TestBuildFunctions:
    """Test message building functions."""
    
    def test_build_request(self):
        """Test building a request message."""
        msg = build_request("test.method", {"arg": "value"}, request_id=1)
        
        assert msg["jsonrpc"] == "2.0"
        assert msg["method"] == "test.method"
        assert msg["params"] == {"arg": "value"}
        assert msg["id"] == 1
    
    def test_build_response(self):
        """Test building a response message."""
        msg = build_response({"result": "data"}, request_id=2)
        
        assert msg["jsonrpc"] == "2.0"
        assert msg["result"] == {"result": "data"}
        assert msg["id"] == 2
    
    def test_build_error(self):
        """Test building an error message."""
        msg = build_error(-32600, "Invalid request", {"info": "test"}, request_id=3)
        
        assert msg["jsonrpc"] == "2.0"
        assert msg["error"]["code"] == -32600
        assert msg["error"]["message"] == "Invalid request"
        assert msg["error"]["data"] == {"info": "test"}
        assert msg["id"] == 3


@pytest.mark.unit
class TestValidation:
    """Test message validation."""
    
    def test_valid_request(self):
        """Test validating a valid request."""
        msg = {"jsonrpc": "2.0", "method": "test", "id": 1}
        validate_jsonrpc_message(msg)  # Should not raise
    
    def test_valid_notification(self):
        """Test validating a valid notification (no id)."""
        msg = {"jsonrpc": "2.0", "method": "notify"}
        validate_jsonrpc_message(msg)  # Should not raise
    
    def test_invalid_version(self):
        """Test invalid JSON-RPC version."""
        msg = {"jsonrpc": "1.0", "method": "test", "id": 1}
        with pytest.raises(JSONRPCError, match="version"):
            validate_jsonrpc_message(msg)
    
    def test_missing_method(self):
        """Test missing method field."""
        msg = {"jsonrpc": "2.0", "id": 1}
        with pytest.raises(JSONRPCError):
            validate_jsonrpc_message(msg)


@pytest.mark.unit
class TestHelpers:
    """Test helper functions."""
    
    def test_is_request(self):
        """Test is_request helper."""
        request = {"jsonrpc": "2.0", "method": "test", "id": 1}
        notification = {"jsonrpc": "2.0", "method": "notify"}
        
        assert is_request(request) is True
        assert is_request(notification) is False
    
    def test_is_notification(self):
        """Test is_notification helper."""
        request = {"jsonrpc": "2.0", "method": "test", "id": 1}
        notification = {"jsonrpc": "2.0", "method": "notify"}
        
        assert is_notification(notification) is True
        assert is_notification(request) is False
    
    def test_get_method(self):
        """Test get_method helper."""
        msg = {"jsonrpc": "2.0", "method": "my.method", "id": 1}
        assert get_method(msg) == "my.method"
    
    def test_get_params(self):
        """Test get_params helper."""
        msg_with_params = {"jsonrpc": "2.0", "method": "test", "params": {"key": "val"}}
        msg_without_params = {"jsonrpc": "2.0", "method": "test"}
        
        assert get_params(msg_with_params) == {"key": "val"}
        assert get_params(msg_without_params) == {}
    
    def test_get_request_id(self):
        """Test get_request_id helper."""
        request = {"jsonrpc": "2.0", "method": "test", "id": 42}
        notification = {"jsonrpc": "2.0", "method": "notify"}
        
        assert get_request_id(request) == 42
        assert get_request_id(notification) is None
