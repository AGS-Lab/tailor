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
        with patch("pathlib.Path.home", return_value=tmp_path):
            service = KeyringService()
            yield service


def test_fallback_storage(keyring_service_fallback):
    # Test storing key
    success = keyring_service_fallback.store_api_key("openai", "sk-test-123")
    assert success is True

    # Verify file content
    secret_file = keyring_service_fallback._fallback_file
    assert secret_file.exists()
    data = json.loads(secret_file.read_text())
    assert data["openai"] == "sk-test-123"

    # Test retrieving key
    key = keyring_service_fallback.get_api_key("openai")
    assert key == "sk-test-123"

    # Test deleting key
    keyring_service_fallback.delete_api_key("openai")
    data = json.loads(secret_file.read_text())
    assert "openai" not in data


def test_list_configured_providers(keyring_service_fallback):
    keyring_service_fallback.store_api_key("openai", "k1")
    keyring_service_fallback.store_api_key("anthropic", "k2")

    providers = keyring_service_fallback.list_configured_providers()
    assert "openai" in providers
    assert "anthropic" in providers


def test_set_env_vars(keyring_service_fallback):
    keyring_service_fallback.store_api_key("openai", "sk-env-test")

    with patch.dict("os.environ", {}, clear=True):
        keyring_service_fallback.set_env_vars()
        import os

        assert os.environ["OPENAI_API_KEY"] == "sk-env-test"


@pytest.mark.asyncio
async def test_verify_api_key_valid(keyring_service_fallback):
    keyring_service_fallback.store_api_key("openai", "sk-valid")

    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client_cls.return_value = mock_client

        result = await keyring_service_fallback.verify_api_key("openai")
        assert result["valid"] is True


@pytest.mark.asyncio
async def test_verify_api_key_invalid(keyring_service_fallback):
    keyring_service_fallback.store_api_key("openai", "sk-invalid")

    mock_response = MagicMock()
    mock_response.status_code = 401

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client_cls.return_value = mock_client

        result = await keyring_service_fallback.verify_api_key("openai")
        assert result["valid"] is False
        assert result["error"] == "Invalid API key"
