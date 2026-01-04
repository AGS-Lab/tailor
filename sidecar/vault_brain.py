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
from pathlib import Path
from typing import Dict, Any, Optional, Callable, Awaitable, cast, List
from collections import defaultdict

from . import utils
from . import constants
from . import exceptions

# Local import avoids circular dependency in type checking if used carefully
# from .api.plugin_base import PluginBase

logger = utils.get_logger(__name__)

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
        if self._initialized:
            return
            
        self.vault_path = utils.validate_vault_path(vault_path)
        self.ws_server = ws_server
        
        self.plugins: Dict[str, Any] = {}
        self.commands: Dict[str, Dict[str, Any]] = {}
        self._subscribers: Dict[str, List[EventHandler]] = defaultdict(list)
        
        self.memory: Optional[Dict[str, Any]] = None
        self.config: Dict[str, Any] = {}
        self.graph: Optional[Dict[str, Any]] = None
        
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
        
        # 1. Load Config
        self.config = self._load_config()
        
        # 2. Initialize Memory
        self._init_memory()
        
        # 3. Setup Sidecar Path
        sidecar_dir = Path(__file__).parent
        if str(sidecar_dir) not in sys.path:
            sys.path.insert(0, str(sidecar_dir))
            logger.info(f"Added sidecar to PYTHONPATH: {sidecar_dir}")
        
        # 4. Register Core Commands
        self._register_core_commands()

        # 5. Load Plugins (Phase 1: Discovery & Registration)
        self._load_plugins()
        
        logger.info(
            f"VaultBrain configured: {len(self.plugins)} plugins, "
            f"{len(self.commands)} commands"
        )
        
        # 6. Activate Plugins (Phase 2: on_load)
        await self._activate_plugins()
        
        logger.info("VaultBrain fully initialized and ready.")

    # =========================================================================
    # Plugin Lifecycle
    # =========================================================================

    def _load_plugins(self) -> None:
        """
        Phase 1: Loading & Registration.
        Instantiates plugins and calls register_commands().
        Side-effect free (no active code execution).
        """
        plugin_dirs = utils.discover_plugins(self.vault_path)
        if not plugin_dirs:
            logger.info("No plugins found in vault")
            return
        
        logger.info(f"Discovered {len(plugin_dirs)} plugin(s)")
        
        for plugin_dir in plugin_dirs:
            plugin_name = plugin_dir.name
            plugin_logger = utils.get_plugin_logger(plugin_name)
            
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
                
                # We do NOT pass brain/emitter anymore. Plugin uses Singleton.
                plugin = plugin_class(
                    plugin_dir=plugin_dir,
                    vault_path=self.vault_path
                )
                
                # Phase 1: Register
                if hasattr(plugin, "register_commands"):
                    plugin.register_commands()
                
                self.plugins[plugin_name] = plugin
                plugin_logger.info(f"Plugin registered successfully")
            
            except Exception as e:
                logger.error(f"Failed to load plugin '{plugin_name}': {e}", exc_info=True)

    async def _activate_plugins(self):
        """
        Phase 2: Activation.
        Calls on_load() for all plugins.
        """
        logger.info("Activating plugins (calling on_load)...")
        for plugin_name, plugin in self.plugins.items():
            try:
                if hasattr(plugin, "on_load"):
                    await plugin.on_load()
            except Exception as e:
                logger.error(f"Error activating plugin '{plugin_name}': {e}", exc_info=True)

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
        if not asyncio.iscoroutinefunction(handler):
            raise exceptions.CommandRegistrationError(command_id, "Handler must be an async function")
        
        if command_id in self.commands:
            logger.warning(f"Overwriting command '{command_id}'")
        
        self.commands[command_id] = {
            "handler": handler,
            "plugin": plugin_name,
        }
        logger.debug(f"Registered command: {command_id}")

    async def execute_command(self, command_id: str, **kwargs: Any) -> Any:
        """Execute a registered command."""
        if command_id not in self.commands:
            raise exceptions.CommandNotFoundError(command_id, list(self.commands.keys()))
        
        info = self.commands[command_id]
        handler = info["handler"]
        
        try:
            return await handler(**kwargs)
        except Exception as e:
            logger.error(f"Command '{command_id}' failed: {e}", exc_info=True)
            raise exceptions.CommandExecutionError(command_id, e)

    def _register_core_commands(self) -> None:
        """Register system-level commands (chat, list, etc)."""
        
        # 1. Chat (Placeholder)
        async def handle_chat(message: str = "") -> Dict[str, Any]:
            return {"response": f"Echo: {message}", "status": "success"}
            
        # 2. List Commands
        async def list_commands() -> Dict[str, Any]:
            return {
                "commands": {k: v["plugin"] for k, v in self.commands.items()},
                "count": len(self.commands)
            }
            
        # 3. Get Info
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
        self.ws_server.register_handler(f"{constants.CHAT_COMMAND_PREFIX}send_message", 
            lambda p: handle_chat(p.get("message", "")))
            
        self.ws_server.register_handler("execute_command", 
            lambda p: self.execute_command(p.get("command"), **p.get("args", {})))
            
        self.ws_server.register_handler("list_commands", lambda p: list_commands())
        self.ws_server.register_handler("get_vault_info", lambda p: get_info())
        
        # Client Ready Signal
        async def client_ready(p: Dict[str, Any]):
            logger.info("Client ready signal received. Triggering plugin hooks...")
            # Trigger on_client_connected for all plugins
            for name, plugin in self.plugins.items():
                if hasattr(plugin, "on_client_connected"):
                    try:
                        await plugin.on_client_connected()
                    except Exception as e:
                        logger.error(f"Error in {name}.on_client_connected: {e}")
            
            return {"status": "ok"}
        self.ws_server.register_handler("system.client_ready", client_ready)

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
        if not self.ws_server:
            logger.warning(f"Cannot emit '{event_type}': No WebSocket server")
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
    
    def subscribe_internal(self, event: str, handler: EventHandler) -> None:
        """Subscribe to an internal Python event."""
        if not asyncio.iscoroutinefunction(handler):
            raise ValueError("Handler must be async")
        self._subscribers[event].append(handler)
        logger.debug(f"Subscribed to internal: {event}")

    async def publish(self, event: str, **kwargs: Any) -> None:
        """Publish an internal Python event."""
        handlers = self._subscribers.get(event, [])
        if not handlers:
            return
            
        # Execute concurrent, isolated
        tasks = []
        for h in handlers:
            tasks.append(self._safe_exec(h, event, **kwargs))
        await asyncio.gather(*tasks)

    async def _safe_exec(self, h, evt, **kwargs):
        try:
            await h(**kwargs)
        except Exception as e:
            logger.error(f"Event handler failed for '{evt}': {e}", exc_info=True)

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

    def _init_memory(self) -> None:
        """Init .memory dir."""
        memory_dir = utils.get_memory_dir(self.vault_path, create=True)
        self.memory = {"path": memory_dir}

    async def _on_tick(self) -> None:
        """Tick plugins."""
        for name, plugin in self.plugins.items():
            if hasattr(plugin, constants.PLUGIN_TICK_METHOD):
                try:
                    await getattr(plugin, constants.PLUGIN_TICK_METHOD)(self)
                except Exception as e:
                    logger.error(f"Tick error in {name}: {e}")

    async def tick_loop(self) -> None:
        logger.info("Starting tick loop...")
        while True:
            await asyncio.sleep(constants.DEFAULT_TICK_INTERVAL)
            await self._on_tick()
