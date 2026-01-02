"""
Unit tests for constants module.

Tests that all enums and constants are properly defined.
"""

import pytest
from sidecar.constants import (
    EventType,
    EventScope,
    Severity,
    JSONRPC_VERSION,
    DEFAULT_TICK_INTERVAL,
    VAULT_CONFIG_FILE,
)


@pytest.mark.unit
class TestEnums:
    """Test enum definitions."""
    
    def test_event_type_enum(self):
        """Test EventType enum has expected values."""
        assert EventType.NOTIFY == "NOTIFY"
        assert EventType.PROGRESS == "PROGRESS"
        assert EventType.UPDATE_STATE == "UPDATE_STATE"
        assert EventType.LLM_RESPONSE == "LLM_RESPONSE"
    
    def test_event_scope_enum(self):
        """Test EventScope enum has expected values."""
        assert EventScope.WINDOW == "window"
        assert EventScope.VAULT == "vault"
        assert EventScope.GLOBAL == "global"
    
    def test_severity_enum(self):
        """Test Severity enum has expected values."""
        assert Severity.INFO == "info"
        assert Severity.SUCCESS == "success"
        assert Severity.WARNING == "warning"
        assert Severity.ERROR == "error"


@pytest.mark.unit
class TestConstants:
    """Test constant values."""
    
    def test_jsonrpc_version(self):
        """Test JSON-RPC version constant."""
        assert JSONRPC_VERSION == "2.0"
    
    def test_default_tick_interval(self):
        """Test default tick interval."""
        assert DEFAULT_TICK_INTERVAL == 5.0
        assert isinstance(DEFAULT_TICK_INTERVAL, (int, float))
    
    def test_vault_config_file(self):
        """Test vault config filename."""
        assert VAULT_CONFIG_FILE == ".vault.json"
        assert isinstance(VAULT_CONFIG_FILE, str)
