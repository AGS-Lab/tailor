"""
Tests for Keyring Service.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import json

from sidecar.services.keyring_service import KeyringService


@pytest.fixture
def mock_keyring_lib():
    with patch("sidecar.services.keyring_service.keyring") as mock:
        yield mock


@pytest.fixture
def keyring_service_fallback(tmp_path):
    # Force fallback mode by mocking KEYRING_AVAILABLE = False
    with patch("sidecar.services.keyring_service.KEYRING_AVAILABLE", False):
        service = KeyringService()
        yield service


def test_fallback_storage(keyring_service_fallback):
    # Test storing key when keyring is unavailable
    success = keyring_service_fallback.store_api_key("openai", "sk-test-123")
    assert success is False

    # Test retrieving key
    key = keyring_service_fallback.get_api_key("openai")
    assert key is None

    # Test deleting key
    success = keyring_service_fallback.delete_api_key("openai")
    assert success is False


def test_list_configured_providers(keyring_service_fallback):
    providers = keyring_service_fallback.list_configured_providers()
    assert len(providers) == 0


def test_set_env_vars(keyring_service_fallback):
    with patch.dict("os.environ", {}, clear=True):
        keyring_service_fallback.set_env_vars()
        import os
        
        # When keyring is unavailable, no keys are loaded
        assert "OPENAI_API_KEY" not in os.environ


@pytest.mark.asyncio
async def test_verify_api_key_valid(keyring_service_fallback):
    # Without keyring, no keys are stored
    result = await keyring_service_fallback.verify_api_key("openai")
    assert result["valid"] is False
    assert result["error"] == "No API key stored"


@pytest.mark.asyncio
async def test_verify_api_key_invalid(keyring_service_fallback):
    # Without keyring, no keys are stored
    result = await keyring_service_fallback.verify_api_key("openai")
    assert result["valid"] is False
    assert result["error"] == "No API key stored"
