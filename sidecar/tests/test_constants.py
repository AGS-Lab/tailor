"""
Unit tests for constants module.

Tests that all enums and constants are properly defined.
"""

import pytest
from sidecar import constants


@pytest.mark.unit
class TestEnums:
    """Test enum definitions."""

    def test_event_type_enum(self):
        """Test EventType enum has expected values."""
        assert constants.EventType.NOTIFY == "NOTIFY"
        assert constants.EventType.PROGRESS == "PROGRESS"
        assert constants.EventType.UPDATE_STATE == "UPDATE_STATE"
        assert constants.EventType.LLM_RESPONSE == "LLM_RESPONSE"

    def test_event_scope_enum(self):
        """Test EventScope enum has expected values."""
        assert constants.EventScope.WINDOW == "window"
        assert constants.EventScope.VAULT == "vault"
        assert constants.EventScope.GLOBAL == "global"

    def test_severity_enum(self):
        """Test Severity enum has expected values."""
        assert constants.Severity.INFO == "info"
        assert constants.Severity.SUCCESS == "success"
        assert constants.Severity.WARNING == "warning"
        assert constants.Severity.ERROR == "error"


@pytest.mark.unit
class TestConstants:
    """Test constant values."""

    def test_jsonrpc_version(self):
        """Test JSON-RPC version constant."""
        assert constants.JSONRPC_VERSION == "2.0"

    def test_default_tick_interval(self):
        """Test default tick interval."""
        assert constants.DEFAULT_TICK_INTERVAL == 5.0
        assert isinstance(constants.DEFAULT_TICK_INTERVAL, (int, float))

    def test_vault_config_file(self):
        """Test vault config filename."""
        assert constants.VAULT_CONFIG_FILE == ".vault.toml"
        assert isinstance(constants.VAULT_CONFIG_FILE, str)
