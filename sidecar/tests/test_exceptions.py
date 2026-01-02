"""
Unit tests for exceptions module.

Tests custom exception classes and hierarchy.
"""

import pytest
from sidecar.exceptions import (
    TailorError,
    VaultError,
    VaultNotFoundError,
    PluginError,
    PluginLoadError,
    CommandError,
    CommandNotFoundError,
    JSONRPCError,
)


@pytest.mark.unit
class TestTailorError:
    """Test base TailorError exception."""
    
    def test_basic_error(self):
        """Test creating basic error."""
        error = TailorError("Test message")
        assert str(error) == "Test message"
        assert error.message == "Test message"
        assert error.details == {}
    
    def test_error_with_details(self):
        """Test error with details dict."""
        details = {"key": "value", "count": 42}
        error = TailorError("Test message", details)
        assert error.details == details
    
    def test_to_dict(self):
        """Test to_dict serialization."""
        error = TailorError("Test", {"info": "data"})
        result = error.to_dict()
        
        assert result["type"] == "TailorError"
        assert result["message"] == "Test"
        assert result["details"] == {"info": "data"}


@pytest.mark.unit
class TestVaultErrors:
    """Test vault-related exceptions."""
    
    def test_vault_not_found(self):
        """Test VaultNotFoundError."""
        error = VaultNotFoundError("/path/to/vault")
        assert "not found" in str(error)
        assert error.details["vault_path"] == "/path/to/vault"
    
    def test_vault_error_hierarchy(self):
        """Test exception hierarchy."""
        error = VaultNotFoundError("/test")
        assert isinstance(error, VaultError)
        assert isinstance(error, TailorError)
        assert isinstance(error, Exception)


@pytest.mark.unit
class TestPluginErrors:
    """Test plugin-related exceptions."""
    
    def test_plugin_load_error(self):
        """Test PluginLoadError."""
        error = PluginLoadError("my_plugin", "Failed to import")
        assert "my_plugin" in str(error)
        assert "Failed to import" in str(error)
        assert error.details["plugin_name"] == "my_plugin"
        assert error.details["reason"] == "Failed to import"
    
    def test_plugin_error_hierarchy(self):
        """Test exception hierarchy."""
        error = PluginLoadError("test", "reason")
        assert isinstance(error, PluginError)
        assert isinstance(error, TailorError)


@pytest.mark.unit
class TestCommandErrors:
    """Test command-related exceptions."""
    
    def test_command_not_found(self):
        """Test CommandNotFoundError."""
        available = ["cmd1", "cmd2", "cmd3"]
        error = CommandNotFoundError("missing.cmd", available)
        
        assert "missing.cmd" in str(error)
        assert error.details["command_id"] == "missing.cmd"
        assert "available_commands" in error.details
    
    def test_command_not_found_without_list(self):
        """Test CommandNotFoundError without available list."""
        error = CommandNotFoundError("test.cmd")
        assert error.details["command_id"] == "test.cmd"
        assert "available_commands" not in error.details


@pytest.mark.unit
class TestJSONRPCError:
    """Test JSON-RPC specific errors."""
    
    def test_jsonrpc_error(self):
        """Test JSONRPCError with code."""
        error = JSONRPCError("Parse error", code=-32700)
        assert error.code == -32700
        assert "JSON-RPC error: Parse error" in str(error)
        assert isinstance(error, TailorError)
    
    def test_jsonrpc_error_to_dict(self):
        """Test JSON-RPC error serialization."""
        error = JSONRPCError("Invalid request", code=-32600)
        result = error.to_dict()
        
        assert result["type"] == "JSONRPCError"
        assert result["details"]["code"] == -32600
        assert "JSON-RPC error: Invalid request" in result["message"]
