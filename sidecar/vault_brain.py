"""
Vault Brain - Singleton Orchestrator for Sidecar Operations

Manages plugins, commands, and communication with the frontend.
Acts as the central Event/Command hub.
"""

import asyncio
import json
import importlib.util
import time
import inspect
from pathlib import Path
from typing import Dict, Any, Optional, Callable, Awaitable, List
from collections import defaultdict

from . import utils
from . import constants
from . import exceptions
from .decorators import command, on_event

from .pipeline import DefaultPipeline, GraphPipeline, PipelineConfig
from .plugin_installer import PluginInstaller
from .services.keyring_service import get_keyring_service, KeyringService, PROVIDERS
from .services.llm_service import get_llm_service, LLMService, reset_llm_service
from .event_bus import EventBus

# Local import avoids circular dependency in type checking if used carefully
# from .api.plugin_base import PluginBase

from loguru import logger

logger = logger.bind(name=__name__)

# Type aliases
CommandHandler = Callable[..., Awaitable[Any]]
EventHandler = Callable[..., Awaitable[None]]


class VaultBrain:
    """
    Singleton Orchestrator.
    
    Responsibilities:
    1.  Command Registry (RPC)
    2.  Event System (Frontend Notification + Internal Pub/Sub)
    3.  Plugin Lifecycle Management
    """
    
    _instance: Optional['VaultBrain'] = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(VaultBrain, cls).__new__(cls)
        return cls._instance

    @classmethod
    def get(cls) -> 'VaultBrain':
        """Get the singleton instance. Raises error if not initialized."""
        if cls._instance is None:
            raise RuntimeError("VaultBrain has not been initialized yet.")
        return cls._instance

    def __init__(self, vault_path: Path, ws_server: Any):
        """
        Initialize VaultBrain instance.
        
        Note: Heavy initialization happens in self.initialize()
        """
        # Prevent re-initialization if already initialized
        self._initialized: bool = False
        if self._initialized:
            return
            
        self.vault_path = utils.validate_vault_path(vault_path)
        
        self.plugins: Dict[str, Any] = {}
        self.commands: Dict[str, Dict[str, Any]] = {}
        
        # Internal Event Bus
        self.events = EventBus()
        # Deprecated: direct access to subscribers, kept for safety if needed but ideally unused
        # self.subscribers is now managed by self.events
        
        self.ws_server = ws_server
                
        self.config: Dict[str, Any] = {}
        self.graph: Optional[Dict[str, Any]] = None
        
        # LLM Processing Pipeline
        self.pipeline: Optional[Any] = None # DefaultPipeline or GraphPipeline
        
        # Plugin Installer
        self.plugin_installer = PluginInstaller(self.vault_path)
        
        self._initialized = True
        logger.info(f"VaultBrain Singleton created for: {self.vault_path}")

    # ...

    # Internal Pub/Sub (Use sparingly!)
    
    def subscribe(self, event: str, handler: EventHandler, priority: int = 0) -> None:
        """
        Subscribe to an internal Python event.
        Delegates to EventBus.
        """
        self.events.subscribe(event, handler, priority)

    def unsubscribe(self, event: str, handler: EventHandler) -> bool:
        """
        Unsubscribe from an internal Python event.
        Delegates to EventBus.
        """
        return self.events.unsubscribe(event, handler)

    def clear_subscribers(self, event: str) -> None:
        """Clear all subscribers for an event."""
        self.events.clear_subscribers(event)

    async def publish(self, event: str, sequential: bool = False, **kwargs: Any) -> None:
        """
        Publish an internal Python event.
        Delegates to EventBus.
        """
        await self.events.publish(event, sequential=sequential, **kwargs)

    async def initialize(self) -> None:
        """
        Perform full asynchronous initialization.
        """
        logger.info("Starting VaultBrain initialization...")
        await self.publish(constants.CoreEvents.SYSTEM_STARTUP)
        
        # Load Config
        self.config = self._load_config()
        
        # Initialize Keyring Service and set API key env vars
        self._keyring = get_keyring_service()
        self._keyring.set_env_vars()
        
        # Initialize LLM Service
        llm_config = self.config.get("llm", {})
        self._llm_service = LLMService(self.vault_path, llm_config)
        
        # Store as singleton for other components
        import sidecar.services.llm_service as llm_module
        llm_module._llm_service = self._llm_service
        
        # Initialize Pipeline with config
        pipeline_config = PipelineConfig(**llm_config) if llm_config else PipelineConfig()
        
        # Decide between Default and Graph pipeline
        if pipeline_config.is_graph_mode:
            self.pipeline = GraphPipeline(pipeline_config)
        else:
            self.pipeline = DefaultPipeline(pipeline_config)
        

        # TODO: Implement file system watcher (watchdog) to emit:
        # - CoreEvents.FILE_SAVED
        # - CoreEvents.FILE_CREATED 
        # - CoreEvents.FILE_MODIFIED
        # - CoreEvents.FILE_DELETED

        # Load Plugins (Phase 1: Discovery & Registration)
        self._load_plugins()
        
        logger.info(
            f"VaultBrain configured: {len(self.plugins)} plugins, "
            f"{len(self.commands)} commands"
        )
        
        # Activate Plugins (Phase 2: on_load)
        await self._activate_plugins()
        
        # Register decorated methods (Core Commands)
        self._register_decorated_handlers()
        
        await self.publish(constants.CoreEvents.ALL_PLUGINS_LOADED)
        logger.info("VaultBrain fully initialized and ready.")

    def _register_decorated_handlers(self) -> None:
        """Scan and register decorated commands and event handlers."""
        # Scan self for decorated methods
        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            # Register Commands
            if hasattr(method, "_command_meta"):
                for meta in method._command_meta:
                    self.register_command(meta["id"], method, meta["plugin"])
            
            # Register Event Handlers
            if hasattr(method, "_event_meta"):
                for meta in method._event_meta:
                    self.subscribe(meta["event"], method)
        
    async def shutdown(self) -> None:
        """
        Perform graceful shutdown.
        """
        logger.info("Shutting down VaultBrain...")
        
        # Announce shutdown
        await self.publish(constants.CoreEvents.SYSTEM_SHUTDOWN)
        
        # Unload plugins (reverse order)
        for name, plugin in list(self.plugins.items())[::-1]:
            try:
                await plugin.on_unload()
            except Exception as e:
                logger.error(f"Error unloading plugin {name}: {e}")
                
        logger.info("VaultBrain shutdown complete.")

    # =========================================================================
    # Plugin Lifecycle
    # =========================================================================

    def _load_plugins(self) -> None:
        """
        Phase 1: Loading & Registration.
        Instantiates plugins and calls register_commands().
        Side-effect free (no active code execution).
        """
        plugins_dir = utils.get_plugins_dir(self.vault_path)
    
        if not plugins_dir:
            logger.info("No plugins found in vault")
            return
    
        logger.debug(f"Scanning plugins directory: {plugins_dir}")
    
        plugin_dirs = []
        for item in plugins_dir.iterdir():
            if item.is_file():
                continue
            if item.name.startswith(('.', '_')):
                continue
        
            main_file = item / constants.PLUGIN_MAIN_FILE
            if main_file.exists():
                plugin_dirs.append(item)

        plugin_dirs = sorted(plugin_dirs, key=lambda p: p.name)
    
        if not plugin_dirs:
            logger.info("No plugins found in vault")
            return
        
        loaded_count = 0
        for plugin_dir in plugin_dirs:
            plugin_name = plugin_dir.name
            # 1. Load defaults from settings.json (if exists)
            defaults = {}
            settings_path = plugin_dir / "settings.json"
            if settings_path.exists():
                try:
                    defaults = json.loads(settings_path.read_text(encoding="utf-8"))
                except Exception as e:
                    logger.error(f"Failed to load settings.json for plugin '{plugin_name}': {e}")
            
            # 2. Get Overrides from .vault.json (Global Config)
            # Structure: { "plugins": { "plugin_name": { "enabled": true, "param": 123 } } }
            vault_apps_config = self.config.get("plugins", {})
            # Handle both "plugins.plugin_name" direct object OR "plugins.enabled" list style legacy
            # We assume dictionary structure for overrides: "plugins": { "explorer": {...} }
            
            overrides = vault_apps_config.get(plugin_name, {})
            if not isinstance(overrides, dict):
                # Fallback if config is malformed or just a list
                overrides = {}

            # 3. Merge Configs (Override > Default)
            final_config = defaults.copy()
            final_config.update(overrides)
            
            # 4. Check Enablement (Default to False if not present in either)
            is_enabled = final_config.get("enabled", False)
            
            if not is_enabled:
                logger.debug(f"Plugin '{plugin_name}' is disabled, skipping")
                continue
            
            try:
                utils.validate_plugin_structure(plugin_dir)
                
                # Load module
                main_file = plugin_dir / "main.py"
                spec = importlib.util.spec_from_file_location(plugin_name, main_file)
                if not spec or not spec.loader:
                    raise exceptions.PluginLoadError(plugin_name, "Failed to create module spec")
                
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                if not hasattr(module, constants.PLUGIN_CLASS_NAME):
                    raise exceptions.PluginLoadError(plugin_name, f"No '{constants.PLUGIN_CLASS_NAME}' class found")
                
                # Instantiate (Fresh Init, no args passed mostly)
                plugin_class = getattr(module, constants.PLUGIN_CLASS_NAME)
                
                # Pass resolved config to plugin
                plugin = plugin_class(
                    plugin_dir=plugin_dir,
                    vault_path=self.vault_path,
                    config=final_config
                )
                
                # Phase 1: Register commands and hooks
                plugin.register_commands()
                
                # Call register_hooks if plugin has it
                if hasattr(plugin, 'register_hooks'):
                    plugin.register_hooks()
                
                self.plugins[plugin_name] = plugin
                logger.info(f"Plugin '{plugin_name}' loaded. Config: {final_config}")
            
            except Exception as e:
                logger.exception(f"Failed to load plugin '{plugin_name}': {e}")

    async def _activate_plugins(self):
        """
        Phase 2: Activation.
        Calls on_load() for all plugins.
        """
        logger.info("Activating plugins (calling on_load)...")
        for plugin_name, plugin in self.plugins.items():
            try:
                await plugin.on_load()
                
                # Auto-subscribe to TICK if plugin overrides on_tick
                # We check if the method is different from the base class implementation
                # This is a bit tricky since PluginBase is abstract, but we can check if it's callable
                # A safer way is checking if it's NOT the base implementation, but base is abstract pass?
                # Actually, PluginBase.on_tick is defined as 'pass'.
                # Let's just subscribe it. If it does nothing, it does nothing.
                # Optimization: Check if plugin.on_tick code object is different from PluginBase.on_tick code object?
                # For now, just subscribe. The event system handles errors.
                self.subscribe(constants.CoreEvents.TICK, plugin.on_tick)
                
                # Announce plugin loaded
                await self.publish(constants.CoreEvents.PLUGIN_LOADED, plugin_name=plugin_name)
            except Exception as e:
                logger.exception(f"Error activating plugin '{plugin_name}': {e}")

    # =========================================================================
    # Command Registry
    # =========================================================================

    def register_command(
        self,
        command_id: str,
        handler: CommandHandler,
        plugin_name: Optional[str] = None,
        override: bool = False
    ) -> None:
        """Register a command."""
        if not inspect.iscoroutinefunction(handler):
            raise exceptions.CommandRegistrationError(command_id, "Handler must be an async function")
        
        if command_id in self.commands:
            if not override:
                logger.warning(f"Overwriting command '{command_id}'")
            else:
                logger.debug(f"Overriding command '{command_id}'")
        
        self.commands[command_id] = {
            "handler": handler,
            "plugin": plugin_name,
        }
        logger.debug(f"Registered command: {command_id}")

    def unregister_command(self, command_id: str) -> bool:
        """
        Unregister a command.
        Returns True if command existed and was removed.
        """
        if command_id in self.commands:
            del self.commands[command_id]
            logger.debug(f"Unregistered command: {command_id}")
            return True
        return False

    async def execute_command(self, command_id: str, **kwargs: Any) -> Any:
        """
        Execute a registered command.
        
        Commands can be registered via:
        1. brain.register_command() - stored in self.commands
        2. ws_server.register_handler() - stored in ws_server.command_handlers
        
        This method checks both locations for backward compatibility.
        """
        handler = None
        
        if command_id in self.commands:
            handler = self.commands[command_id]["handler"]
        
        if handler is None:
            all_commands = list(self.commands.keys())
            raise exceptions.CommandNotFoundError(command_id, all_commands)
        
        try:
            result = await handler(**kwargs)
            
            # Emit command executed event (fire and forget)
            asyncio.create_task(self.publish(
                constants.CoreEvents.COMMAND_EXECUTED,
                command_id=command_id,
                args=kwargs,
                result_status="success"
            ))
            return result
        except Exception as e:
            logger.exception(f"Command '{command_id}' failed: {e}")
            raise exceptions.CommandExecutionError(command_id, e)

    @command("system.client_ready", constants.CORE_PLUGIN_NAME)
    async def _client_ready_handler(self, **kwargs):
        """Handle client ready signal."""
        logger.info("Client ready signal received. Triggering plugin hooks...")
        # Trigger on_client_connected for all plugins
        for name, plugin in self.plugins.items():
            try:
                await plugin.on_client_connected()
            except Exception as e:
                logger.error(f"Error in {name}.on_client_connected: {e}")
        return {"status": "ok"}



    # =========================================================================
    # Core Command Implementations
    # =========================================================================

    @command("system.chat", constants.CORE_PLUGIN_NAME)
    async def handle_chat(self, message: str = "", history: List[Dict[str, str]] = None, chat_id: str = "default", **kwargs) -> Dict[str, Any]:
        if self.pipeline:
            # Check kwargs for chat_id if not passed directly (legacy frontend support)
            if chat_id == "default":
                p = kwargs.get("p") or kwargs.get("params")
                if isinstance(p, dict):
                    chat_id = p.get("chat_id", chat_id)

            ctx = await self.pipeline.run(
                message=message,
                history=history or [],
                metadata={"chat_id": chat_id}
            )
            return {
                "response": ctx.response,
                "metadata": ctx.metadata,
                "status": "success"
            }
        return {"response": f"Echo: {message}", "status": "success"}


    @command("system.info", constants.CORE_PLUGIN_NAME)
    async def get_info(self) -> Dict[str, Any]:
        return {
            "vault": self.config.get("name"),
            "plugins": list(self.plugins.keys())
        }

    @command("system.list_commands", constants.CORE_PLUGIN_NAME)
    async def list_commands(self) -> Dict[str, Any]:
        """List all registered commands."""
        return {
            "status": "success",
            "commands": list(self.commands.keys())
        }




    # =========================================================================
    # Settings API Commands
    # =========================================================================

    @command("settings.store_api_key", constants.CORE_PLUGIN_NAME)
    async def store_api_key(self, provider: str = "", api_key: str = "", **kwargs) -> Dict[str, Any]:
        """Store an API key in secure OS storage."""
        # Handle nested params
        if not provider:
            p = kwargs.get("p") or kwargs.get("params")
            if isinstance(p, dict):
                provider = p.get("provider", provider)
                api_key = p.get("api_key", api_key)
        
        if not provider or not api_key:
            return {"status": "error", "error": "provider and api_key are required"}
        
        if provider not in PROVIDERS:
            return {"status": "error", "error": f"Unknown provider: {provider}"}
        
        success = self._keyring.store_api_key(provider, api_key)
        
        if success:
            # Update environment variable
            self._keyring.set_env_vars()
            logger.info(f"Stored API key for {provider}")
            return {"status": "success", "provider": provider}
        else:
            return {"status": "error", "error": "Failed to store API key"}

    @command("settings.delete_api_key", constants.CORE_PLUGIN_NAME)
    async def delete_api_key(self, provider: str = "", **kwargs) -> Dict[str, Any]:
        """Delete an API key from secure storage."""
        if not provider:
            p = kwargs.get("p") or kwargs.get("params")
            if isinstance(p, dict):
                provider = p.get("provider", provider)
        
        if not provider:
            return {"status": "error", "error": "provider is required"}
        
        success = self._keyring.delete_api_key(provider)
        return {
            "status": "success" if success else "error",
            "provider": provider
        }

    @command("settings.list_providers", constants.CORE_PLUGIN_NAME)
    async def list_providers(self, **kwargs) -> Dict[str, Any]:
        """List all providers and their configuration status."""
        return {
            "status": "success",
            "providers": self._keyring.get_provider_status()
        }

    @command("settings.verify_api_key", constants.CORE_PLUGIN_NAME)
    async def verify_api_key(self, provider: str = "", **kwargs) -> Dict[str, Any]:
        """Verify an API key by making a test request."""
        if not provider:
            p = kwargs.get("p") or kwargs.get("params")
            if isinstance(p, dict):
                provider = p.get("provider", provider)
        
        if not provider:
            return {"status": "error", "error": "provider is required"}
        
        result = await self._keyring.verify_api_key(provider)
        return {
            "status": "success" if result.get("valid") else "error",
            "provider": provider,
            **result
        }



    @command("settings.get_available_models", constants.CORE_PLUGIN_NAME)
    async def get_available_models(self, **kwargs) -> Dict[str, Any]:
        """Get all available models based on configured API keys and Ollama."""
        models = await self._llm_service.get_available_models()
        
        # Convert ModelInfo objects to dicts
        result = {}
        for provider, model_list in models.items():
            result[provider] = [
                {
                    "id": m.id,
                    "name": m.name,
                    "categories": m.categories,
                    "context_window": m.context_window,
                    "is_local": m.is_local
                }
                for m in model_list
            ]
        
        return {
            "status": "success",
            "models": result
        }

    @command("settings.get_model_categories", constants.CORE_PLUGIN_NAME)
    async def get_model_categories(self, **kwargs) -> Dict[str, Any]:
        """Get current category configuration and category metadata."""
        return {
            "status": "success",
            "categories_info": self._llm_service.get_categories_info(),
            "configured": self._llm_service.get_category_config()
        }

    @command("settings.set_model_category", constants.CORE_PLUGIN_NAME)
    async def set_model_category(self, category: str = "", model: str = "", **kwargs) -> Dict[str, Any]:
        """Set the model for a category and save to .vault.json."""
        # Handle nested params
        if not category:
            p = kwargs.get("p") or kwargs.get("params")
            if isinstance(p, dict):
                category = p.get("category", category)
                model = p.get("model", model)
        
        if not category or not model:
            return {"status": "error", "error": "category and model are required"}
        
        # Update in-memory
        self._llm_service.set_category_model(category, model)
        
        # Save to config
        try:
            config_path = utils.get_vault_config_path(self.vault_path)
            config = self._load_config()
            
            if "llm" not in config:
                config["llm"] = {}
            if "categories" not in config["llm"]:
                config["llm"]["categories"] = {}
            
            config["llm"]["categories"][category] = model
            
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
            
            self.config = config
            
            logger.info(f"Set model for category '{category}': {model}")
            return {
                "status": "success",
                "category": category,
                "model": model
            }
        except Exception as e:
            logger.error(f"Failed to save category config: {e}")
            return {"status": "error", "error": str(e)}

    @command("settings.detect_ollama", constants.CORE_PLUGIN_NAME)
    async def detect_ollama(self, **kwargs) -> Dict[str, Any]:
        """Detect Ollama and list installed models."""
        models = await self._llm_service.detect_ollama(force_refresh=True)
        is_available = await self._llm_service.is_ollama_available()
        
        return {
            "status": "success",
            "available": is_available,
            "models": [
                {
                    "name": m.name,
                    "size": m.size,
                    "categories": self._llm_service._get_ollama_categories(m.name)
                }
                for m in models
            ]
        }

    @command("settings.get_model_info", constants.CORE_PLUGIN_NAME)
    async def get_model_info(self, model_id: str = "", **kwargs) -> Dict[str, Any]:
        """Get detailed information about a specific model including pricing and specs."""
        # Handle nested params
        if not model_id:
            p = kwargs.get("p") or kwargs.get("params")
            if isinstance(p, dict):
                model_id = p.get("model_id", model_id)
        
        if not model_id:
            return {"status": "error", "error": "model_id is required"}
        
        try:
            model_info = await self._llm_service.get_model_info(model_id)
            return {
                "status": "success",
                "model": model_info
            }
        except Exception as e:
            logger.error(f"Failed to get model info: {e}")
            return {"status": "error", "error": str(e)}

    # =========================================================================
    # Chat Commands (Core - replaces LLM plugin)
    # =========================================================================

    @command("chat.set_model", constants.CORE_PLUGIN_NAME)
    async def chat_set_model(
        self,
        chat_id: str = "",
        model_id: str = "",
        category: str = "",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Set the active model for a specific chat.
        
        Args:
            chat_id: The chat ID
            model_id: Specific model ID (e.g., 'openai/gpt-4o') - takes precedence
            category: Category name (e.g., 'thinking') - used if model_id not provided
        """
        # Handle nested params
        if not chat_id:
            p = kwargs.get("p") or kwargs.get("params")
            if isinstance(p, dict):
                chat_id = p.get("chat_id", chat_id)
                model_id = p.get("model_id", model_id)
                category = p.get("category", category)
        
        if not chat_id:
            return {"status": "error", "error": "chat_id is required"}
        
        if not model_id and not category:
            return {"status": "error", "error": "Either model_id or category is required"}
        
        try:
            # Store in memory plugin if available
            # Use a generic command that Memory plugin should implement
            try:
                await self.execute_command(
                    "chat.set_metadata",
                    chat_id=chat_id,
                    key="model_override",
                    value={"model_id": model_id, "category": category}
                )
            except:
                # If memory plugin doesn't exist, just log
                # Frontend will still pass the model in each request
                logger.debug("Memory plugin not available for model persistence")
            
            # Get model info for response
            selected_model = model_id if model_id else self._llm_service.get_model_for_category(category)
            
            model_info = None
            if selected_model:
                try:
                    model_info = await self._llm_service.get_model_info(selected_model)
                except:
                    pass
            
            return {
                "status": "success",
                "chat_id": chat_id,
                "model_id": model_id,
                "category": category,
                "selected_model": selected_model,
                "model_info": model_info
            }
        except Exception as e:
            logger.error(f"Failed to set chat model: {e}")
            return {"status": "error", "error": str(e)}


    @command("chat.send", constants.CORE_PLUGIN_NAME)
    async def chat_send(
        self, 
        message: str = "", 
        history: List[Dict[str, str]] = None,
        category: str = "fast",
        stream: bool = False,
        stream_id: str = None,
        chat_id: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send a chat message and get a response.
        
        Args:
            message: The user message to send
            history: Conversation history (optional, now fetched from backend)
            category: Model category to use (fast, thinking, etc.)
            stream: If True, stream tokens via WebSocket events
            stream_id: Optional ID to identify this stream (for multiple concurrent streams)
            chat_id: Optional chat ID for memory persistence
        """
        # Handle nested params
        if not message:
            p = kwargs.get("p") or kwargs.get("params")
            if isinstance(p, dict):
                message = p.get("message", message)
                history = p.get("history", history)
                category = p.get("category", category)
                stream = p.get("stream", stream)
                stream_id = p.get("stream_id", stream_id)
                chat_id = p.get("chat_id", chat_id)
        
        if not message:
            return {"status": "error", "error": "message is required"}
        
        # Generate chat_id if not provided (Backend Authority)
        if not chat_id:
            chat_id = f"chat_{int(time.time())}"
            
        # Backend State Management: Check for chat-specific model override
        model_override = None
        if chat_id:
            try:
                metadata_res = await self.execute_command("chat.get_metadata", chat_id=chat_id, key="model_override")
                if metadata_res.get("status") == "success":
                    model_override = metadata_res.get("value")
            except:
                pass  # No override set or memory plugin not available
        
        # Determine which model/category to use
        # Priority: 1. Explicit model param 2. Chat override 3. Category default
        if not kwargs.get("model"):
            if model_override:
                if model_override.get("model_id"):
                    kwargs["model"] = model_override["model_id"]
                elif model_override.get("category"):
                    category = model_override["category"]
            
        # Backend State Management: Fetch history from Memory plugin if available
        # Use generic command 'chat.get_history' provided by plugins
        # This allows Memory (linear) or ChatBranches (branched) to provide context
        if chat_id:
            try:
                res = await self.execute_command("chat.get_history", chat_id=chat_id)
                if res.get("status") == "success":
                    history = res.get("history", [])
            except Exception:
                # No plugin provides history or command failed - ignore
                pass

        # Generate stream_id if streaming (Backend Authority)
        if stream and not stream_id:
            stream_id = utils.generate_id("stream_")
        
        try:
            if stream:
                # Streaming mode: emit tokens via WebSocket events
                return await self._stream_chat_response(
                    message=message,
                    history=history,
                    category=category,
                    stream_id=stream_id,
                    chat_id=chat_id,
                    model=kwargs.get("model")  # Pass specific model if provided
                )
            else:
                # Non-streaming mode: wait for full response
                metadata = {}
                if chat_id:
                    metadata["chat_id"] = chat_id
                    
                context = await self.pipeline.run(
                    message=message,
                    history=history,
                    stream=False,
                    metadata=metadata
                )
                
                return {
                    "status": "success",
                    "chat_id": chat_id, # Return authoritative chat_id
                    "response": context.response,
                    "model": context.metadata.get("model", "unknown"),
                    "usage": context.metadata.get("usage", {}),
                    "message_ids": context.metadata.get("generated_ids", {})
                }
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _stream_chat_response(
        self,
        message: str,
        history: List[Dict[str, str]],
        category: str,
        stream_id: str,
        chat_id: str = None,
        model: str = None
    ) -> Dict[str, Any]:
        """
        Stream chat response tokens via WebSocket events.
        
        Emits:
            - CHAT_STREAM_START: When streaming begins
            - CHAT_TOKEN: For each token received
            - CHAT_STREAM_END: When streaming completes (includes full response)
        """
        full_response = ""
        
        try:
            # Emit stream start event
            self.emit_to_frontend(
                constants.EventType.CHAT_STREAM_START,
                {
                    "stream_id": stream_id,
                    "message": message
                }
            )
            
            # Prepare metadata for pipeline (including model/category)
            metadata = {
                "category": category,
                "model": model  # May be None, pipeline will use category
            }
            if chat_id:
                metadata["chat_id"] = chat_id
            
            # Use pipeline's stream_run method
            async for token in self.pipeline.stream_run(
                message=message,
                history=history,
                metadata=metadata
            ):
                full_response += token
                
                # Emit token event
                self.emit_to_frontend(
                    constants.EventType.CHAT_TOKEN,
                    {
                        "stream_id": stream_id,
                        "token": token,
                        "accumulated": full_response
                    }
                )
            
            # Trigger OUTPUT event for plugins (like Memory) to capture the interaction
            # We need to reconstruct a PipelineContext
            from .pipeline.types import PipelineContext
            from .pipeline.events import PipelineEvents
            
            ctx = PipelineContext(
                message=message,
                original_message=message,
                history=history or [],
                response=full_response
            )
            
            if chat_id:
                ctx.metadata["chat_id"] = chat_id
            
            # Await OUTPUT sequentially to ensure IDs are generated
            await self.publish(PipelineEvents.OUTPUT, sequential=True, ctx=ctx)
            
            # Emit stream end event with full response AND generated IDs
            self.emit_to_frontend(
                constants.EventType.CHAT_STREAM_END,
                {
                    "stream_id": stream_id,
                    "response": full_response,
                    "status": "success",
                    "chat_id": chat_id,
                    "message_ids": ctx.metadata.get("generated_ids", {})
                }
            )
            
            return {
                "status": "success",
                "streaming": True,
                "stream_id": stream_id,
                "chat_id": chat_id,
                "response": full_response,
                "model": "stream-model",
                "usage": {},
                "message_ids": ctx.metadata.get("generated_ids", {})
            }
            
        except Exception as e:
            logger.error(f"Stream error: {e}")
            # Emit error event
            self.emit_to_frontend(
                constants.EventType.CHAT_STREAM_END,
                {
                    "stream_id": stream_id,
                    "status": "error",
                    "error": str(e),
                    "response": full_response  # Include partial response
                }
            )
            return {
                "status": "error",
                "streaming": True,
                "stream_id": stream_id,
                "error": str(e)
            }


    @command("plugins.install", constants.CORE_PLUGIN_NAME)
    async def install_plugin(self, download_url: str = "", repo_url: str = "", plugin_id: str = "", **kwargs) -> Dict[str, Any]:
        # Backward compatibility: Check if args are inside 'p' or 'params' dict in kwargs
        # This handles cases where frontend sends { "p": { ... } }
        if not plugin_id:
            # Try to find in 'p'
            p = kwargs.get("p") or kwargs.get("params")
            if isinstance(p, dict):
                download_url = p.get("download_url", download_url)
                repo_url = p.get("repo_url", repo_url)
                plugin_id = p.get("plugin_id", plugin_id)

        if not plugin_id:
             return {"status": "error", "error": "plugin_id is required"}
        
        # Prefer HTTP download over git clone
        if download_url:
            result = await self.plugin_installer.install_from_url(download_url, plugin_id)
        elif repo_url:
            result = await self.plugin_installer.install(repo_url, plugin_id)
        else:
            return {"status": "error", "error": "download_url or repo_url is required"}
        
        return {
            "status": result.status.value,
            "plugin_id": result.plugin_id,
            "message": result.message,
            "manifest": result.manifest
        }
    
    @command("plugins.update", constants.CORE_PLUGIN_NAME)
    async def update_plugin(self, plugin_id: str = "", **kwargs) -> Dict[str, Any]:
        if not plugin_id:
            # check 'p'
            p = kwargs.get("p") or kwargs.get("params")
            if isinstance(p, dict):
                plugin_id = p.get("plugin_id", plugin_id)

        if not plugin_id:
            return {"status": "error", "error": "plugin_id is required"}
        
        result = await self.plugin_installer.update(plugin_id)
        return {
            "status": result.status.value,
            "plugin_id": result.plugin_id,
            "message": result.message
        }
    
    @command("plugins.uninstall", constants.CORE_PLUGIN_NAME)
    async def uninstall_plugin(self, plugin_id: str = "", **kwargs) -> Dict[str, Any]:
        if not plugin_id:
             # check 'p'
            p = kwargs.get("p") or kwargs.get("params")
            if isinstance(p, dict):
                plugin_id = p.get("plugin_id", plugin_id)

        if not plugin_id:
            return {"status": "error", "error": "plugin_id is required"}
        
        success = await self.plugin_installer.uninstall(plugin_id)
        return {
            "status": "success" if success else "error",
            "plugin_id": plugin_id,
            "message": f"Plugin '{plugin_id}' uninstalled" if success else "Uninstall failed"
        }
    
    @command("plugins.list", constants.CORE_PLUGIN_NAME)
    async def list_plugins(self, **kwargs) -> Dict[str, Any]:
        """List installed plugins with their enabled state from .vault.json."""
        plugins = self.plugin_installer.list_installed()
        
        # Enrich with enabled state from config
        plugins_config = self.config.get("plugins", {})
        for plugin in plugins:
            plugin_id = plugin.get("id", "")
            plugin_conf = plugins_config.get(plugin_id, {})
            if isinstance(plugin_conf, dict):
                plugin["enabled"] = plugin_conf.get("enabled", False)
            else:
                plugin["enabled"] = False
        
        return {
            "status": "success",
            "plugins": plugins,
            "count": len(plugins)
        }
    
    @command("plugins.toggle", constants.CORE_PLUGIN_NAME)
    async def toggle_plugin(self, plugin_id: str = "", enabled: bool = True, **kwargs) -> Dict[str, Any]:
        """Toggle plugin enabled state in .vault.json."""
        # Handle nested params
        if not plugin_id:
            p = kwargs.get("p") or kwargs.get("params")
            if isinstance(p, dict):
                plugin_id = p.get("plugin_id", plugin_id)
                enabled = p.get("enabled", enabled)
        
        if not plugin_id:
            return {"status": "error", "error": "plugin_id is required"}
        
        try:
            # Read current config
            config_path = utils.get_vault_config_path(self.vault_path)
            config = self._load_config()
            
            # Ensure plugins dict exists
            if "plugins" not in config:
                config["plugins"] = {}
            
            # Ensure plugin entry exists
            if plugin_id not in config["plugins"]:
                config["plugins"][plugin_id] = {}
            
            # Update enabled state
            if isinstance(config["plugins"][plugin_id], dict):
                config["plugins"][plugin_id]["enabled"] = enabled
            else:
                config["plugins"][plugin_id] = {"enabled": enabled}
            
            # Write back
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
            
            # Update in-memory config
            self.config = config
            
            logger.info(f"Plugin '{plugin_id}' {'enabled' if enabled else 'disabled'}")
            
            return {
                "status": "success",
                "plugin_id": plugin_id,
                "enabled": enabled,
                "message": f"Plugin '{plugin_id}' {'enabled' if enabled else 'disabled'}. Restart vault to apply."
            }
        except Exception as e:
            logger.exception(f"Failed to toggle plugin: {e}")
            return {"status": "error", "error": str(e)}
    
    @command("system.restart_vault", constants.CORE_PLUGIN_NAME)
    async def restart_vault(self, **kwargs) -> Dict[str, Any]:
        """
        Hot-reload the vault: unload all plugins, reload config, reload plugins.
        This allows plugin changes to take effect without restarting the app.
        """
        logger.info("Restarting vault (hot reload)...")
        
        try:
            # 1. Announce shutdown
            await self.publish(constants.CoreEvents.SYSTEM_SHUTDOWN)
            
            # 2. Unload all plugins (reverse order)
            for name, plugin in list(self.plugins.items())[::-1]:
                try:
                    await plugin.on_unload()
                    logger.info(f"Unloaded plugin: {name}")
                except Exception as e:
                    logger.error(f"Error unloading plugin {name}: {e}")
            
            # 3. Clear plugin state
            self.plugins.clear()
            self.commands.clear()
            self.events = EventBus()
            
            # 4. Reload config
            self.config = self._load_config()
            
            # 5. Reload plugins
            self._load_plugins()
            
            # 6. Activate plugins
            await self._activate_plugins()
            
            # 7. Re-register decorated handlers
            self._register_decorated_handlers()
            
            # 8. Announce ready
            await self.publish(constants.CoreEvents.ALL_PLUGINS_LOADED)
            
            logger.info(f"Vault restarted: {len(self.plugins)} plugins loaded")
            
            return {
                "status": "success",
                "message": "Vault restarted successfully",
                "plugins_loaded": list(self.plugins.keys())
            }
        except Exception as e:
            logger.exception(f"Vault restart failed: {e}")
            return {"status": "error", "error": str(e)}

    @property
    def is_client_connected(self) -> bool:
        """Check if frontend client is connected."""
        return self.ws_server and self.ws_server.is_connected()

    # =========================================================================

    # Event System (Frontend Notification + Pub/Sub)
    # =========================================================================

    def notify_frontend(
        self,
        message: str,
        severity: str = constants.Severity.INFO
    ) -> None:
        """Send a notification toast to the Frontend."""
        self.emit_to_frontend(
            constants.EventType.NOTIFY,
            {"message": message, "severity": severity}
        )

    def update_state(self, key: str, value: Any) -> None:
        """Update a key in the Frontend global/vault state."""
        self.emit_to_frontend(
            constants.EventType.UPDATE_STATE,
            {"key": key, "value": value}
        )

    def emit_to_frontend(
        self,
        event_type: str,
        data: Dict[str, Any],
        scope: str = constants.EventScope.WINDOW
    ) -> None:
        """
        Send a raw event to the Frontend via WebSocket.
        """
        if not self.is_client_connected:
            logger.debug(f"Skipping '{event_type}': Client not connected")
            return

        # Construct JSON-RPC notification
        msg = utils.build_request(
            method="trigger_event",
            params={
                "event_type": event_type,
                "scope": scope,
                "data": data,
                "timestamp": time.time(),
            },
            request_id=utils.generate_id("evt_"),
        )
        self.ws_server.send_to_rust(msg)




    # =========================================================================
    # Config & Utils
    # =========================================================================

    def _load_config(self) -> Dict[str, Any]:
        """Load .vault.json."""
        config_file = utils.get_vault_config_path(self.vault_path)
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Config load error: {e}")
                
        default = constants.DEFAULT_VAULT_CONFIG.copy()
        default["id"] = str(self.vault_path)
        default["name"] = self.vault_path.name
        return default

    async def tick_loop(self) -> None:
        logger.info("Starting tick loop...")
        while True:
            await asyncio.sleep(constants.DEFAULT_TICK_INTERVAL)
            await self.publish(constants.CoreEvents.TICK)

    # Removed explicit _tick_plugins iteration

