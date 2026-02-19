"""
Keyring Service - Secure API Key Storage

Uses OS-level secure storage:
- Windows: Credential Manager
- macOS: Keychain
- Linux: Secret Service (GNOME Keyring, KWallet)
"""

from typing import Optional, List, Dict, Any
from loguru import logger

try:
    import keyring
    from keyring.errors import KeyringError

    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    KeyringError = Exception

# Service name for keyring
SERVICE_NAME = "tailor-ai"

# Supported providers with their validation endpoints
PROVIDERS = {
    "openai": {
        "name": "OpenAI",
        "env_var": "OPENAI_API_KEY",
        "validation_url": "https://api.openai.com/v1/models",
    },
    "anthropic": {
        "name": "Anthropic",
        "env_var": "ANTHROPIC_API_KEY",
        "validation_url": "https://api.anthropic.com/v1/messages",
    },
    "gemini": {
        "name": "Google Gemini",
        "env_var": "GEMINI_API_KEY",  # LiteLLM uses GEMINI_API_KEY
        "validation_url": "https://generativelanguage.googleapis.com/v1beta/models",
    },
    "mistral": {
        "name": "Mistral AI",
        "env_var": "MISTRAL_API_KEY",
        "validation_url": "https://api.mistral.ai/v1/models",
    },
    "groq": {
        "name": "Groq",
        "env_var": "GROQ_API_KEY",
        "validation_url": "https://api.groq.com/openai/v1/models",
    },
    "openrouter": {
        "name": "OpenRouter",
        "env_var": "OPENROUTER_API_KEY",
        "validation_url": "https://openrouter.ai/api/v1/models",
    },
}


class KeyringService:
    """
    Secure API key storage service using OS keyring.
    """

    def __init__(self):
        self._logger = logger.bind(component="KeyringService")
        self._fallback_file = None

        if not KEYRING_AVAILABLE:
            self._logger.warning(
                "keyring package not available. Using local file fallback."
            )
            self._setup_fallback()

    def _setup_fallback(self):
        """Setup fallback storage file."""
        import pathlib

        try:
            # unique path for fallback
            self._fallback_file = pathlib.Path.home() / ".tailor" / "secrets.json"
            self._fallback_file.parent.mkdir(parents=True, exist_ok=True)
            if not self._fallback_file.exists():
                self._fallback_file.write_text("{}")
        except Exception as e:
            self._logger.error(f"Failed to setup fallback storage: {e}")

    def _load_fallback(self) -> Dict[str, str]:
        """Load secrets from fallback file."""
        import json

        if not self._fallback_file or not self._fallback_file.exists():
            return {}
        try:
            return json.loads(self._fallback_file.read_text())
        except Exception as e:
            self._logger.error(f"Failed to load fallback secrets: {e}")
            return {}

    def _save_fallback(self, data: Dict[str, str]) -> bool:
        """Save secrets to fallback file."""
        import json

        if not self._fallback_file:
            return False
        try:
            self._fallback_file.write_text(json.dumps(data, indent=2))
            return True
        except Exception as e:
            self._logger.error(f"Failed to save fallback secrets: {e}")
            return False

    def is_available(self) -> bool:
        """Check if storage service is available."""
        return KEYRING_AVAILABLE or (self._fallback_file is not None)

    def store_api_key(self, provider: str, api_key: str) -> bool:
        """
        Store an API key securely.
        """
        if provider not in PROVIDERS:
            self._logger.error(f"Unknown provider: {provider}")
            return False

        if KEYRING_AVAILABLE:
            try:
                keyring.set_password(SERVICE_NAME, provider, api_key)
                self._logger.info(f"Stored API key for provider: {provider}")
                return True
            except KeyringError as e:
                self._logger.error(f"Failed to store API key using keyring: {e}")
                return False
        else:
            # Fallback
            secrets = self._load_fallback()
            secrets[provider] = api_key
            if self._save_fallback(secrets):
                self._logger.info(f"Stored API key for provider: {provider} (fallback)")
                return True
            return False

    def get_api_key(self, provider: str) -> Optional[str]:
        """
        Retrieve an API key.
        """
        if KEYRING_AVAILABLE:
            try:
                return keyring.get_password(SERVICE_NAME, provider)
            except KeyringError as e:
                self._logger.error(f"Failed to get API key using keyring: {e}")
                return None
        else:
            # Fallback
            secrets = self._load_fallback()
            return secrets.get(provider)

    def delete_api_key(self, provider: str) -> bool:
        """
        Delete an API key.
        """
        if KEYRING_AVAILABLE:
            try:
                keyring.delete_password(SERVICE_NAME, provider)
                self._logger.info(f"Deleted API key for provider: {provider}")
                return True
            except KeyringError as e:
                self._logger.error(f"Failed to delete API key using keyring: {e}")
                return False
        else:
            # Fallback
            secrets = self._load_fallback()
            if provider in secrets:
                del secrets[provider]
                if self._save_fallback(secrets):
                    self._logger.info(
                        f"Deleted API key for provider: {provider} (fallback)"
                    )
                    return True
            return False

    def list_configured_providers(self) -> List[str]:
        """
        List all providers with stored API keys.
        """
        configured = []
        if KEYRING_AVAILABLE:
            for provider in PROVIDERS.keys():
                try:
                    if keyring.get_password(SERVICE_NAME, provider):
                        configured.append(provider)
                except KeyringError:
                    pass
        else:
            # Fallback
            secrets = self._load_fallback()
            configured = list(secrets.keys())

        return configured

    def get_provider_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all supported providers.
        """
        status = {}
        configured = self.list_configured_providers()

        for provider_id, info in PROVIDERS.items():
            status[provider_id] = {
                "name": info["name"],
                "configured": provider_id in configured,
            }

        return status

    async def verify_api_key(self, provider: str) -> Dict[str, Any]:
        """
        Verify that a stored API key is valid by making a test request.
        """
        api_key = self.get_api_key(provider)
        if not api_key:
            return {"valid": False, "error": "No API key stored"}

        if provider not in PROVIDERS:
            return {"valid": False, "error": "Unknown provider"}

        try:
            import httpx

            provider_info = PROVIDERS[provider]
            headers = self._get_auth_headers(provider, api_key)

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    provider_info["validation_url"], headers=headers
                )

                if response.status_code in (200, 201):
                    return {"valid": True}
                elif response.status_code == 401:
                    return {"valid": False, "error": "Invalid API key"}
                else:
                    return {"valid": False, "error": f"HTTP {response.status_code}"}

        except Exception as e:
            self._logger.error(f"Verification failed for {provider}: {e}")
            return {"valid": False, "error": str(e)}

    def _get_auth_headers(self, provider: str, api_key: str) -> Dict[str, str]:
        """Get provider-specific authentication headers."""
        if provider == "openai":
            return {"Authorization": f"Bearer {api_key}"}
        elif provider == "anthropic":
            return {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
        elif provider == "google":
            return {"x-goog-api-key": api_key}
        elif provider == "mistral":
            return {"Authorization": f"Bearer {api_key}"}
        elif provider == "groq":
            return {"Authorization": f"Bearer {api_key}"}
        else:
            return {"Authorization": f"Bearer {api_key}"}

    def set_env_vars(self) -> None:
        """
        Set environment variables for all stored API keys.
        """
        import os

        # Load from storage (keyring or fallback)
        for provider_id, info in PROVIDERS.items():
            api_key = self.get_api_key(provider_id)
            if api_key:
                os.environ[info["env_var"]] = api_key
                self._logger.debug(f"Set env var {info['env_var']}")


# Module-level singleton
_keyring_service: Optional[KeyringService] = None


def get_keyring_service() -> KeyringService:
    """Get the singleton KeyringService instance."""
    global _keyring_service
    if _keyring_service is None:
        _keyring_service = KeyringService()
    return _keyring_service
