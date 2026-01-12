"""
Vault Brain - Singleton Orchestrator for Sidecar Operations

Manages plugins, commands, and communication with the frontend.
Acts as the central Event/Command hub.
"""

import asyncio
import json
import importlib.util
import sys
import time
import inspect
from pathlib import Path
from typing import Dict, Any, Optional, Callable, Awaitable, cast, List
from collections import defaultdict

from . import utils
from . import constants
from . import exceptions

from .pipeline import PipelineManager, DefaultPipeline, GraphPipeline, PipelineConfig
from .plugin_installer import PluginInstaller

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
        self.subscribers: Dict[str, List[EventHandler]] = defaultdict(list)
        self.ws_server = ws_server
        
        self.config: Dict[str, Any] = {}
        self.graph: Optional[Dict[str, Any]] = None
        
        # LLM Processing Pipeline
        self.pipeline_manager = PipelineManager()
        self.pipeline: Optional[Any] = None # DefaultPipeline or GraphPipeline
        
        # Plugin Installer
        self.plugin_installer = PluginInstaller(self.vault_path)
        
        self._initialized = True
        logger.info(f"VaultBrain Singleton created for: {self.vault_path}")

    async def initialize(self) -> None:
        """
        Perform full asynchronous initialization.
        
        This method handles:
        1. Loading Configuration
        2. Initializing Memory
        3. Setting up Python Path
        4. Registering Core Commands
        5. Loading & Activating Plugins
        """
        logger.info("Starting VaultBrain initialization...")
        await self.publish(constants.CoreEvents.SYSTEM_STARTUP)
        
        # Load Config
        self.config = self._load_config()
        
        # Initialize LLM Pipeline with config
        llm_config = self.config.get("llm", {})
        pipeline_config = PipelineConfig(**llm_config) if llm_config else PipelineConfig()
        
        # Decide between Default and Graph pipeline
        if pipeline_config.is_graph_mode:
            self.pipeline = GraphPipeline(self.pipeline_manager, pipeline_config)
        else:
            self.pipeline = DefaultPipeline(self.pipeline_manager, pipeline_config)
        
        # Register Core Commands
        self._register_core_commands()

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
        
        await self.publish(constants.CoreEvents.ALL_PLUGINS_LOADED)
        logger.info("VaultBrain fully initialized and ready.")
        
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
                    plugin_logger.error(f"Failed to load settings.json: {e}")
            
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
                # plugin_logger.debug("Plugin disabled")
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
        plugin_name: Optional[str] = None
    ) -> None:
        """Register a command."""
        if not inspect.iscoroutinefunction(handler):
            raise exceptions.CommandRegistrationError(command_id, "Handler must be an async function")
        
        if command_id in self.commands:
            logger.warning(f"Overwriting command '{command_id}'")
        
        self.commands[command_id] = {
            "handler": handler,
            "plugin": plugin_name,
        }
        logger.debug(f"Registered command: {command_id}")

    async def execute_command(self, command_id: str, **kwargs: Any) -> Any:
        """
        Execute a registered command.
        
        Commands can be registered via:
        1. brain.register_command() - stored in self.commands
        2. ws_server.register_handler() - stored in ws_server.command_handlers
        
        This method checks both locations for backward compatibility.
        """
        handler = None
        source = None
        
        # Check brain commands first
        if command_id in self.commands:
            handler = self.commands[command_id]["handler"]
            source = "brain"
        # Fallback: check ws_server handlers (for plugins that register there)
        elif self.ws_server and command_id in self.ws_server.command_handlers:
            handler = self.ws_server.command_handlers[command_id]
            source = "ws_server"
            # ws_server handlers expect a params dict, wrap kwargs
            kwargs = {"params": kwargs} if kwargs else {}
        
        if handler is None:
            all_commands = list(self.commands.keys())
            if self.ws_server:
                all_commands.extend(list(self.ws_server.command_handlers.keys()))
            raise exceptions.CommandNotFoundError(command_id, all_commands)
        
        try:
            # Execute handler
            if source == "ws_server":
                # ws_server handlers take a single params dict
                result = await handler(kwargs.get("params", {}))
            else:
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

    def _register_core_commands(self) -> None:
        """Register system-level commands (chat, list, etc)."""
        
        # Chat - Now uses LLM Pipeline
        async def handle_chat(message: str = "", history: List[Dict[str, str]] = None) -> Dict[str, Any]:
            if self.pipeline:
                ctx = await self.pipeline.run(
                    message=message,
                    history=history or []
                )
                return {
                    "response": ctx.response,
                    "metadata": ctx.metadata,
                    "status": "success"
                }
            return {"response": f"Echo: {message}", "status": "success"}
            
        # List Commands
        async def list_commands() -> Dict[str, Any]:
            return {
                "commands": {k: v["plugin"] for k, v in self.commands.items()},
                "count": len(self.commands)
            }
            
        # Get Info
        async def get_info() -> Dict[str, Any]:
            return {
                "vault": self.config.get("name"),
                "plugins": list(self.plugins.keys())
            }

        # No "ui.notify" commands here. Plugins call brain.notify_frontend directly.
        
        # Register them
        # Note: We rely on WebSocketServer mapping "execute_command" -> brain.execute_command
        # But we also register these so internal plugins can call them if needed?
        # Actually, the WebSocketServer handles specific prefixes or purely 'execute_command'.
        # Let's keep these as standard commands.
        self.register_command("system.chat", handle_chat, constants.CORE_PLUGIN_NAME)
        self.register_command("system.list_commands", list_commands, constants.CORE_PLUGIN_NAME)
        self.register_command("system.info", get_info, constants.CORE_PLUGIN_NAME)

        # Connect WebSocket handlers
        
        async def chat_handler(message: str = "", **kwargs) -> Dict[str, Any]:
            return await handle_chat(str(message))
            
        async def execute_handler(command: str = "", args: Dict[str, Any] = None, **kwargs) -> Any:
            return await self.execute_command(str(command), **(args or {}))
            
        async def list_handler(**kwargs) -> Dict[str, Any]:
            return await list_commands()
            
        async def info_handler(**kwargs) -> Dict[str, Any]:
            return await get_info()

        self.ws_server.register_handler(f"{constants.CHAT_COMMAND_PREFIX}send_message", chat_handler)
        self.ws_server.register_handler("execute_command", execute_handler)
        self.ws_server.register_handler("list_commands", list_handler)
        self.ws_server.register_handler("get_vault_info", info_handler)
        
        # Client Ready Signal
        async def client_ready(**kwargs):
            logger.info("Client ready signal received. Triggering plugin hooks...")
            # Trigger on_client_connected for all plugins
            for name, plugin in self.plugins.items():
                try:
                    await plugin.on_client_connected()
                except Exception as e:
                    logger.error(f"Error in {name}.on_client_connected: {e}")
            
            return {"status": "ok"}
        self.ws_server.register_handler("system.client_ready", client_ready)
        
        # Plugin Management Commands
        async def install_plugin(p: Dict[str, Any]) -> Dict[str, Any]:
            download_url = p.get("download_url", "")
            repo_url = p.get("repo_url", "")
            plugin_id = p.get("plugin_id", "")
            
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
        
        async def update_plugin(plugin_id: str = "", **kwargs) -> Dict[str, Any]:
            if not plugin_id:
                return {"status": "error", "error": "plugin_id is required"}
            
            result = await self.plugin_installer.update(plugin_id)
            return {
                "status": result.status.value,
                "plugin_id": result.plugin_id,
                "message": result.message
            }
        
        async def uninstall_plugin(plugin_id: str = "", **kwargs) -> Dict[str, Any]:
            if not plugin_id:
                return {"status": "error", "error": "plugin_id is required"}
            
            success = await self.plugin_installer.uninstall(plugin_id)
            return {
                "status": "success" if success else "error",
                "plugin_id": plugin_id,
                "message": f"Plugin '{plugin_id}' uninstalled" if success else "Uninstall failed"
            }
        
        async def list_plugins(**kwargs) -> Dict[str, Any]:
            # Ignores args anyway
            plugins = self.plugin_installer.list_installed()
            return {
                "status": "success",
                "plugins": plugins,
                "count": len(plugins)
            }
        
        self.ws_server.register_handler("plugins.install", install_plugin)
        self.ws_server.register_handler("plugins.update", update_plugin)
        self.ws_server.register_handler("plugins.uninstall", uninstall_plugin)
        self.ws_server.register_handler("plugins.list", list_plugins)
        
        # Also register the async functions directly as brain commands
        self.register_command("plugins.install", install_plugin, constants.CORE_PLUGIN_NAME)
        self.register_command("plugins.update", update_plugin, constants.CORE_PLUGIN_NAME)
        self.register_command("plugins.uninstall", uninstall_plugin, constants.CORE_PLUGIN_NAME)
        self.register_command("plugins.list", list_plugins, constants.CORE_PLUGIN_NAME)

    @property
    def is_client_connected(self) -> bool:
        """Check if frontend client is connected."""
        if not self.ws_server:
            return False
        return self.ws_server.is_connected()

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

    # Internal Pub/Sub (Use sparingly!)
    
    def subscribe(self, event: str, handler: EventHandler) -> None:
        """Subscribe to an internal Python event."""
        if not inspect.iscoroutinefunction(handler):
            raise ValueError("Handler must be async")
        self.subscribers[event].append(handler)
        logger.debug(f"Subscribed to internal: {event}")

    async def publish(self, event: str, **kwargs: Any) -> None:
        """Publish an internal Python event."""
        handlers = self.subscribers.get(event, [])
        if not handlers:
            return
                    
        async def safe_exec(h: EventHandler) -> None:
            try:
                await h(**kwargs)
            except Exception as e:
                logger.exception(f"Event handler failed for '{event}': {e}")

        # Execute concurrent, isolated
        await asyncio.gather(*(safe_exec(h) for h in handlers))


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
            await self._tick_plugins()

    async def _tick_plugins(self) -> None:
        """Run one tick cycle for all plugins."""
        for name, plugin in self.plugins.items():
            try:
                await plugin.on_tick()
            except Exception as e:
                logger.error(f"Tick error in {name}: {e}")
