"""
LLM Service - Central LLM Orchestration

Provides a unified interface to multiple LLM providers via LiteLLM.
Features:
- Category-based model selection
- Ollama auto-detection
- Streaming support
- Automatic API key injection from keyring
"""

import os
import json
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any, AsyncGenerator, Union
from dataclasses import dataclass, field

from loguru import logger

import litellm
from litellm import acompletion

# Suppress debug info (e.g. "Provider List" link) but keep errors
litellm.suppress_debug_info = True

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from .keyring_service import get_keyring_service, PROVIDERS


@dataclass
class ModelInfo:
    """Information about an available model."""
    id: str
    name: str
    provider: str
    categories: List[str]
    context_window: Optional[int] = None
    is_local: bool = False


@dataclass  
class OllamaModel:
    """Information about an Ollama model."""
    name: str
    size: str
    modified_at: str
    digest: str


@dataclass
class LLMResponse:
    """Response from an LLM completion."""
    content: str
    model: str
    usage: Dict[str, int] = field(default_factory=dict)
    finish_reason: Optional[str] = None


class LLMService:
    """
    Central LLM orchestration service.
    
    Handles:
    - Model selection by category
    - Provider authentication
    - Ollama detection
    - Streaming completions
    """
    

    
    def __init__(self, vault_path: Path, config: Dict[str, Any]):
        self._logger = logger.bind(component="LLMService")
        self.vault_path = vault_path
        self.config = config
        
        # Load models registry
        self._registry = self._load_registry()
        
        # Initialize keyring and set env vars
        self._keyring = get_keyring_service()
        self._keyring.set_env_vars()
        
        # Category configuration from vault config
        self._categories = config.get("categories", {})
        self._defaults = config.get("defaults", {
            "temperature": 0.7,
            "max_tokens": 4096
        })
        
        # Cached Ollama models
        self._ollama_models: Optional[List[OllamaModel]] = None
        self._ollama_available: Optional[bool] = None
        

    
    def _load_registry(self) -> Dict[str, Any]:
        """Load the models registry JSON."""
        registry_path = Path(__file__).parent.parent / "models_registry.json"
        try:
            with open(registry_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            self._logger.error(f"Failed to load models registry: {e}")
            return {"recommended": {}, "categories": {}}

    async def _fetch_litellm_data(self) -> Dict[str, Any]:
        """Fetch model data from LiteLLM source."""
        # Use local litellm.model_cost instead of fetching
        return litellm.model_cost
    
    # =========================================================================
    # Ollama Detection
    # =========================================================================
    
    async def detect_ollama(self, force_refresh: bool = False) -> List[OllamaModel]:
        """
        Detect if Ollama is running and list available models.
        
        Args:
            force_refresh: If True, bypass cache and re-detect
            
        Returns:
            List of available Ollama models
        """
        if not force_refresh and self._ollama_models is not None:
            return self._ollama_models
        
        if not HTTPX_AVAILABLE:
            self._ollama_available = False
            self._ollama_models = []
            return []
        
        base_url = self.config.get("providers", {}).get("ollama", {}).get(
            "base_url", "http://localhost:11434"
        )
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{base_url}/api/tags")
                
                if response.status_code == 200:
                    data = response.json()
                    models = []
                    for model in data.get("models", []):
                        models.append(OllamaModel(
                            name=model.get("name", ""),
                            size=self._format_size(model.get("size", 0)),
                            modified_at=model.get("modified_at", ""),
                            digest=model.get("digest", "")[:12]
                        ))
                    
                    self._ollama_available = True
                    self._ollama_models = models
                    self._logger.info(f"Ollama detected with {len(models)} models")
                    return models
                else:
                    self._ollama_available = False
                    self._ollama_models = []
                    return []
                    
        except Exception as e:
            self._logger.debug(f"Ollama not detected: {e}")
            self._ollama_available = False
            self._ollama_models = []
            return []
    
    def _format_size(self, size_bytes: int) -> str:
        """Format bytes to human readable size."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"
    
    def _get_ollama_categories(self, model_name: str) -> List[str]:
        """
        Determine categories for an Ollama model based on its name.
        Uses keywords defined in the registry categories.
        """
        name_lower = model_name.lower().split(":")[0]
        matched_categories = set()
        
        categories_config = self._registry.get("categories", {})
        
        for category_id, config in categories_config.items():
            keywords = config.get("ollama_keywords", [])
            for keyword in keywords:
                if keyword in name_lower:
                    matched_categories.add(category_id)
                    break # One match per category is enough

        return list(matched_categories) or ["fast"]
    
    async def is_ollama_available(self) -> bool:
        """Check if Ollama is running."""
        if self._ollama_available is None:
            await self.detect_ollama()
        return self._ollama_available or False
    
    # =========================================================================
    # Model Discovery
    # =========================================================================
    
    async def get_available_models(self) -> Dict[str, List[ModelInfo]]:
        """
        Get all models available to the user grouped by provider.
        
        Only returns models from providers that have API keys configured.
        
        Returns:
            Dict mapping provider IDs to lists of available models
        """
        available = {}
        configured_providers = self._keyring.list_configured_providers()
        
        # Fetch LiteLLM data (could be cached)
        litellm_data = await self._fetch_litellm_data()
        
        # Get recommended models by category from the new structure
        categories_config = self._registry.get("categories", {})
        
        # Invert recommended to get list of used models
        used_models = set()
        model_to_categories = {}
        
        for cat_id, config in categories_config.items():
            recs = config.get("recommended", [])
            for model_id in recs:
                used_models.add(model_id)
                if model_id not in model_to_categories:
                    model_to_categories[model_id] = []
                model_to_categories[model_id].append(cat_id)
            
        # Group by provider (parse from model ID)
        for model_id in used_models:
            provider = "unknown"
            
            # 1. Check for explicit provider prefix (preferred)
            if "/" in model_id:
                parts = model_id.split("/", 1)
                provider = parts[0]
                
                # Normalize provider names if needed (e.g. 'google' -> 'gemini' for consistency with keys)
                if provider == "google":
                    provider = "gemini"
            
            # 2. Fallback heuristics for legacy models without prefix
            elif "gpt" in model_id or "text-embedding" in model_id or "whisper" in model_id or "o1" in model_id:
                provider = "openai"
            elif "claude" in model_id:
                provider = "anthropic"
            elif "gemini" in model_id:
                provider = "gemini"
            elif "mistral" in model_id or "codestral" in model_id:
                provider = "mistral"
            elif "groq" in model_id:
                provider = "groq" 
            elif "openrouter" in model_id:
                provider = "openrouter"
            
            # FILTER: Only include models from providers with configured API keys
            if provider not in configured_providers and provider != "unknown":
                continue  # Skip this model

            # Get specs from LiteLLM data if available
            specs = litellm_data.get(model_id, {})
            
            # Prepare ModelInfo
            # Strip provider prefix from ID since it's stored separately in provider field
            # This prevents double-prefixing in frontend (e.g. 'openai/openai/gpt-4o')
            clean_id = model_id
            if "/" in model_id:
                _, rest = model_id.split("/", 1)
                clean_id = rest
            
            categories = model_to_categories.get(model_id, [])

            model_info = ModelInfo(
                id=clean_id,
                name=clean_id, # Display name (without provider prefix)
                provider=provider,
                categories=categories,
                context_window=specs.get("max_input_tokens") or specs.get("max_tokens"),
                is_local=False
            )
            
            if provider not in available:
                available[provider] = []
            available[provider].append(model_info)
        
        # Add Ollama models (always available as they are local)
        ollama_models = await self.detect_ollama()
        if ollama_models:
            ollama_list = []
            for model in ollama_models:
                ollama_list.append(ModelInfo(
                    id=model.name,
                    name=model.name,
                    provider="ollama",
                    categories=self._get_ollama_categories(model.name),
                    context_window=None,
                    is_local=True
                ))
            available["ollama"] = ollama_list
        
        return available
    
    async def get_models_for_category(self, category: str) -> List[ModelInfo]:
        """
        Get all available models that support a specific category.
        
        Args:
            category: Category ID (e.g., 'thinking', 'fast')
            
        Returns:
            List of models that support this category
        """
        all_models = await self.get_available_models()
        matching = []
        
        for provider_models in all_models.values():
            for model in provider_models:
                if category in model.categories:
                    matching.append(model)
        
        return matching
    
    def get_model_for_category(self, category: str) -> Optional[str]:
        """
        Get the configured model for a category.
        
        Args:
            category: Category ID
            
        Returns:
            Model ID in format 'provider/model' or None
        """
        # Check user configuration
        model = self._categories.get(category)
        if model:
            return model
        
        # Check for fallback
        category_info = self._registry.get("categories", {}).get(category, {})
        fallback = category_info.get("fallback")
        if fallback:
            return self.get_model_for_category(fallback)
        
        return None
    
    # =========================================================================
    # LLM Completions
    # =========================================================================
    
    async def complete(
        self,
        messages: List[Dict[str, str]],
        category: str = "fast",
        model: Optional[str] = None,
        stream: bool = False,
        **kwargs
    ) -> Union[LLMResponse, AsyncGenerator[str, None]]:
        """
        Generate a completion using the appropriate model.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            category: Model category to use (if model not specified)
            model: Specific model ID to use (overrides category)
            stream: If True, return an async generator of tokens
            **kwargs: Additional parameters passed to LiteLLM
            
        Returns:
            LLMResponse or AsyncGenerator if streaming
        """

        
        # Determine model to use
        model_id = model or self.get_model_for_category(category)
        if not model_id:
            raise ValueError(f"No model configured for category: {category}")
        
        # Format model for LiteLLM (provider/model format)
        litellm_model = self._format_model_for_litellm(model_id)
        
        # Merge defaults with kwargs
        params = {
            "temperature": self._defaults.get("temperature", 0.7),
            "max_tokens": self._defaults.get("max_tokens", 4096),
            **kwargs
        }
        
        # Apply model-specific parameter restrictions (guardrails)
        params = self._apply_model_guardrails(model_id, params)
        
        self._logger.debug(f"Completing with model: {litellm_model}, params: {params}")
        
        if stream:
            return self._stream_completion(litellm_model, messages, params)
        else:
            return await self._sync_completion(litellm_model, messages, params)
    
    def _apply_model_guardrails(self, model_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply model-specific parameter restrictions.
        
        Some models have restrictions on what parameters they accept:
        - GPT-5/o1 models only support temperature=1
        - Some models don't support certain parameters
        """
        model_lower = model_id.lower()
        
        # GPT-5 and o1 models only support temperature=1
        if any(prefix in model_lower for prefix in ['gpt-5', 'o1-', 'o1_']):
            if params.get('temperature', 1.0) != 1.0:
                self._logger.info(f"Model {model_id} only supports temperature=1, adjusting")
                params['temperature'] = 1.0
            # These models also don't support top_p, presence_penalty, frequency_penalty
            for unsupported in ['top_p', 'presence_penalty', 'frequency_penalty']:
                if unsupported in params:
                    self._logger.debug(f"Removing unsupported param {unsupported} for {model_id}")
                    del params[unsupported]
        
        return params
    
    def get_model_restrictions(self, model_id: str) -> Dict[str, Any]:
        """
        Get parameter restrictions for a model.
        
        Used by frontend to show appropriate UI controls.
        """
        model_lower = model_id.lower()
        
        restrictions = {
            "temperature": {"min": 0, "max": 2, "default": 0.7, "locked": False},
            "max_tokens": {"min": 1, "max": 128000, "default": 4096},
            "top_p": {"min": 0, "max": 1, "default": 1.0, "supported": True},
            "presence_penalty": {"min": -2, "max": 2, "default": 0, "supported": True},
            "frequency_penalty": {"min": -2, "max": 2, "default": 0, "supported": True}
        }
        
        # GPT-5 and o1 models have temperature locked to 1
        if any(prefix in model_lower for prefix in ['gpt-5', 'o1-', 'o1_']):
            restrictions["temperature"] = {"min": 1, "max": 1, "default": 1, "locked": True, "locked_reason": "This model only supports temperature=1"}
            restrictions["top_p"]["supported"] = False
            restrictions["presence_penalty"]["supported"] = False
            restrictions["frequency_penalty"]["supported"] = False
        
        return restrictions
    
    async def _sync_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        params: Dict[str, Any]
    ) -> LLMResponse:
        """Synchronous (non-streaming) completion."""
        try:
            response = await acompletion(
                model=model,
                messages=messages,
                **params
            )
            
            return LLMResponse(
                content=response.choices[0].message.content or "",
                model=model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                } if response.usage else {},
                finish_reason=response.choices[0].finish_reason
            )
        except Exception as e:
            self._logger.error(f"Completion failed: {e}")
            raise
    
    async def _stream_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        params: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """Streaming completion - yields tokens as they arrive."""
        try:
            response = await acompletion(
                model=model,
                messages=messages,
                stream=True,
                **params
            )
            
            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            self._logger.error(f"Stream completion failed: {e}")
            raise
    
    def _format_model_for_litellm(self, model_id: str) -> str:
        """
        Format a model ID for LiteLLM.
        
        LiteLLM uses specific provider prefixes:
        - openai/gpt-4o, openai/o1-preview
        - anthropic/claude-3-5-sonnet-20241022
        - gemini/gemini-1.5-pro (NOT google/)
        - mistral/mistral-large-latest
        - groq/llama-3.1-8b
        - ollama/llama3
        """
        # If already contains a provider prefix, validate/fix it
        if "/" in model_id:
            provider, model = model_id.split("/", 1)
            # Fix common mistakes
            if provider == "google":
                return f"gemini/{model}"
            return model_id
            
        # Check if it's an Ollama model
        if self._ollama_models:
            for m in self._ollama_models:
                if m.name == model_id or m.name.startswith(model_id):
                    return f"ollama/{model_id}"
        
        # Legacy heuristics for old configs without prefix
        # Can eventually be removed once all configs are updated
        model_lower = model_id.lower()
        
        if "gpt" in model_lower or "text-embedding" in model_lower or "whisper" in model_lower or "o1" in model_lower:
            return f"openai/{model_id}"
        elif "claude" in model_lower:
            return f"anthropic/{model_id}"
        elif "gemini" in model_lower:
            return f"gemini/{model_id}"
        elif "mistral" in model_lower or "codestral" in model_lower:
            return f"mistral/{model_id}"
        elif "llama" in model_lower:
            return f"groq/{model_id}"

        # Check if it's an Ollama model
        if self._ollama_models:
            for m in self._ollama_models:
                if m.name == model_id or m.name.startswith(model_id):
                    return f"ollama/{model_id}"
        
        # Return as-is and let LiteLLM figure it out
        return model_id
    
    # =========================================================================
    # Configuration
    # =========================================================================
    
    def set_category_model(self, category: str, model: str) -> None:
        """
        Set the model for a category (in memory).
        
        Note: Call save_config() to persist to .vault.json
        """
        self._categories[category] = model
    
    def get_category_config(self) -> Dict[str, str]:
        """Get current category configuration."""
        return dict(self._categories)
    
    def get_categories_info(self) -> Dict[str, Dict[str, Any]]:
        """Get metadata about all categories."""
        return self._registry.get("categories", {})
    
    async def get_model_info(self, model_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific model.
        
        Args:
            model_id: Model ID in format 'provider/model' or just 'model'
            
        Returns:
            Dictionary with model details including pricing and specs
        """
        # Normalize model ID to provider/model format
        normalized_id = self._format_model_for_litellm(model_id)
        
        # Extract provider and model name
        if "/" in normalized_id:
            provider, model_name = normalized_id.split("/", 1)
        else:
            provider = "unknown"
            model_name = normalized_id
        
        # Get pricing from litellm.model_cost
        litellm_data = litellm.model_cost.get(model_name, {})
        
        # Determine categories for this model
        categories = []
        for cat_id, cat_info in self._registry.get("categories", {}).items():
            if model_name in cat_info.get("recommended", []):
                categories.append(cat_id)
        
        # Check if it's an Ollama model
        is_local = provider == "ollama"
        if not is_local and self._ollama_models:
            for om in self._ollama_models:
                if om.name == model_name:
                    is_local = True
                    categories = self._get_ollama_categories(model_name)
                    break
        
        # Build capabilities list
        capabilities = []
        if "vision" in categories:
            capabilities.append("Vision")
        if "code" in categories:
            capabilities.append("Code")
        if "audio" in categories:
            capabilities.append("Audio")
        if not capabilities:
            capabilities.append("Text")
        
        # Extract pricing (cost per 1M tokens)
        pricing = {
            "input": None,
            "output": None
        }
        
        if litellm_data and not is_local:
            # LiteLLM stores pricing in different formats
            if "input_cost_per_token" in litellm_data:
                pricing["input"] = litellm_data["input_cost_per_token"] * 1_000_000
            elif "input_cost_per_million_tokens" in litellm_data:
                pricing["input"] = litellm_data["input_cost_per_million_tokens"]
            
            if "output_cost_per_token" in litellm_data:
                pricing["output"] = litellm_data["output_cost_per_token"] * 1_000_000
            elif "output_cost_per_million_tokens" in litellm_data:
                pricing["output"] = litellm_data["output_cost_per_million_tokens"]
        
        # Get context window
        context_window = None
        if litellm_data:
            context_window = (
                litellm_data.get("max_input_tokens") or 
                litellm_data.get("max_tokens") or
                litellm_data.get("context_window")
            )
        
        return {
            "id": model_id,
            "normalized_id": normalized_id,
            "name": model_name,
            "provider": provider,
            "categories": categories,
            "context_window": context_window,
            "pricing": pricing,
            "capabilities": capabilities,
            "is_local": is_local
        }


# Module-level singleton
_llm_service: Optional[LLMService] = None


def get_llm_service(vault_path: Optional[Path] = None, config: Optional[Dict] = None) -> LLMService:
    """Get the singleton LLMService instance."""
    global _llm_service
    if _llm_service is None:
        if vault_path is None or config is None:
            raise RuntimeError("LLMService not initialized. Provide vault_path and config.")
        _llm_service = LLMService(vault_path, config)
    return _llm_service


def reset_llm_service() -> None:
    """Reset the singleton (for testing or vault restart)."""
    global _llm_service
    _llm_service = None
