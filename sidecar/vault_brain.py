"""
Vault Brain - LangGraph orchestrator for vault-specific AI operations

Manages plugins, memory, and LangGraph execution for a single vault.
"""

import asyncio
import json
import importlib.util
from pathlib import Path
from typing import Dict, Any, Optional, Callable, Awaitable, cast

from .event_emitter import EventEmitter
from .utils.logging_config import get_logger, get_plugin_logger
from .utils.path_utils import (
    validate_vault_path,
    get_vault_config_path,
    get_memory_dir,
    discover_plugins,
    validate_plugin_structure,
)
from .constants import (
    DEFAULT_VAULT_CONFIG,
    DEFAULT_TICK_INTERVAL,
    PLUGIN_CLASS_NAME,
    PLUGIN_TICK_METHOD,
    CHAT_COMMAND_PREFIX,
)
from .exceptions import (
    VaultConfigError,
    PluginLoadError,
    PluginExecutionError,
    CommandNotFoundError,
    CommandRegistrationError,
    CommandExecutionError,
)

logger = get_logger(__name__)

# Type alias for command handlers
CommandHandler = Callable[..., Awaitable[Any]]


class VaultBrain:
    """
    LangGraph orchestrator that manages vault-specific operations.
    
    Responsibilities:
    - Load vault-specific plugins
    - Initialize memory storage
    - Create isolated LangGraph instance
    - Run periodic tick loop for plugins
    - Manage command registry for plugin commands
    
    Attributes:
        vault_path: Absolute path to vault directory
        ws_server: WebSocket server instance
        plugins: Dictionary of loaded plugin instances
        commands: Command registry mapping command IDs to handlers
        config: Vault configuration dictionary
        memory: Memory storage information
        graph: LangGraph instance (placeholder)
        emitter: EventEmitter for plugins to send UI events
    """
    
    def __init__(self, vault_path: Path, ws_server: Any):
        """
        Initialize VaultBrain.
        
        Args:
            vault_path: Path to vault directory
            ws_server: WebSocket server instance
        
        Raises:
            VaultNotFoundError: If vault directory doesn't exist
            VaultConfigError: If vault configuration is invalid
        """
        # Validate and resolve vault path
        self.vault_path = validate_vault_path(vault_path)
        self.ws_server = ws_server
        
        self.plugins: Dict[str, Any] = {}
        self.commands: Dict[str, Dict[str, Any]] = {}
        self.memory: Optional[Dict[str, Any]] = None
        self.graph: Optional[Dict[str, Any]] = None
        
        logger.info(f"Initializing VaultBrain for: {self.vault_path}")
        
        # Create event emitter with brain reference for command registration
        self.emitter = EventEmitter(websocket_server=ws_server, brain=self)
        
        # Load vault configuration
        self.config = self._load_config()
        
        # Initialize components
        self._init_memory()
        self._load_plugins()
        self._build_langgraph()
        self._register_commands()
        
        logger.info(
            f"VaultBrain initialized: {len(self.plugins)} plugins, "
            f"{len(self.commands)} commands"
        )
    
    async def initialize(self) -> None:
        """
        Perform async initialization.
        
        Calls on_load() for all loaded plugins.
        """
        logger.info("Running async initialization for plugins...")
        for plugin_name, plugin in self.plugins.items():
            try:
                await plugin.on_load()
            except Exception as e:
                logger.error(f"Error calling on_load for plugin '{plugin_name}': {e}", exc_info=True)
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load vault configuration from .vault.json.
        
        Returns:
            Configuration dictionary
        
        Raises:
            VaultConfigError: If configuration file is malformed
        """
        config_file = get_vault_config_path(self.vault_path)
        
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    config = cast(Dict[str, Any], json.load(f))
                    logger.debug(f"Loaded config from {config_file}")
                    return config
            except json.JSONDecodeError as e:
                raise VaultConfigError(
                    f"Invalid JSON in configuration file: {e}",
                    str(config_file)
                )
            except Exception as e:
                raise VaultConfigError(
                    f"Failed to read configuration: {e}",
                    str(config_file)
                )
        
        # Use default configuration
        logger.info("No .vault.json found, using default configuration")
        default_config = DEFAULT_VAULT_CONFIG.copy()
        default_config["id"] = str(self.vault_path)
        default_config["name"] = self.vault_path.name
        
        return default_config
    
    def _init_memory(self) -> None:
        """
        Initialize memory storage.
        
        Creates .memory directory and sets up memory tracking structure.
        """
        memory_dir = get_memory_dir(self.vault_path, create=True)
        logger.info(f"Memory directory: {memory_dir}")
        
        # In a full implementation, initialize a proper memory system
        # For now, store basic metadata
        self.memory = {
            "path": memory_dir,
            "conversations": [],
        }
    
    def _load_plugins(self) -> None:
        """
        Load and initialize vault-specific plugins from plugin directories.
        
        Discovers all valid plugin directories, loads their main.py files,
        and initializes Plugin classes with the event emitter and brain reference.
        """
        plugin_dirs = discover_plugins(self.vault_path)
        
        if not plugin_dirs:
            logger.info("No plugins found in vault")
            return
        
        logger.info(f"Discovered {len(plugin_dirs)} plugin(s)")
        
        for plugin_dir in plugin_dirs:
            plugin_name = plugin_dir.name
            plugin_logger = get_plugin_logger(plugin_name)
            
            try:
                # Validate plugin structure
                validate_plugin_structure(plugin_dir)
                
                plugin_logger.info(f"Loading plugin: {plugin_name}")
                
                # Load plugin module from main.py
                main_file = plugin_dir / "main.py"
                spec = importlib.util.spec_from_file_location(plugin_name, main_file)
                
                if not spec or not spec.loader:
                    raise PluginLoadError(
                        plugin_name,
                        "Failed to create module spec"
                    )
                
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Initialize plugin with emitter and brain reference
                if not hasattr(module, PLUGIN_CLASS_NAME):
                    raise PluginLoadError(
                        plugin_name,
                        f"No '{PLUGIN_CLASS_NAME}' class found in main.py"
                    )
                
                # Instantiate plugin
                plugin_class = getattr(module, PLUGIN_CLASS_NAME)
                plugin = plugin_class(
                    emitter=self.emitter,
                    brain=self,
                    plugin_dir=plugin_dir,
                    vault_path=self.vault_path
                )
                
                self.plugins[plugin_name] = plugin
                plugin_logger.info(f"Plugin loaded successfully")
            
            except PluginLoadError as e:
                logger.error(f"Failed to load plugin '{plugin_name}': {e.message}")
            
            except Exception as e:
                logger.error(
                    f"Unexpected error loading plugin '{plugin_name}': {e}",
                    exc_info=True
                )
        
        logger.info(f"Successfully loaded {len(self.plugins)}/{len(plugin_dirs)} plugin(s)")
    
    def _build_langgraph(self) -> None:
        """
        Build LangGraph instance with vault configuration.
        
        In a full implementation, this would create and configure a LangGraph
        instance with nodes, edges, and state management. For now, it's a placeholder.
        """
        self.graph = {
            "vault_id": self.config.get("id"),
            "nodes": [],
        }
        logger.debug("LangGraph initialized (placeholder)")
    
    def _register_commands(self) -> None:
        """
        Register command handlers with WebSocket server.
        
        Registers core commands for chat, command execution, and vault info.
        """
        async def handle_chat(params: Dict[str, Any]) -> Dict[str, Any]:
            """Handle chat.send_message command."""
            message = params.get("message", "")
            logger.debug(f"Received chat message: {message[:50]}...")
            
            # TODO: In full implementation, process with LangGraph
            # For now, echo back
            return {
                "response": f"Echo: {message}",
                "status": "success",
            }
        
        async def handle_execute(params: Dict[str, Any]) -> Dict[str, Any]:
            """Handle execute_command to run registered commands."""
            command_id = params.get("command", "")
            args = params.get("args", {})
            
            logger.debug(f"Executing command: {command_id}")
            
            result = await self.execute_command(command_id, **args)
            return {"result": result, "status": "success"}
        
        async def handle_list_commands(params: Dict[str, Any]) -> Dict[str, Any]:
            """Handle list_commands to return all available commands."""
            commands = self.get_commands()
            return {
                "commands": commands,
                "count": len(commands),
                "status": "success"
            }
        
        async def handle_get_vault_info(params: Dict[str, Any]) -> Dict[str, Any]:
            """Handle get_vault_info to return vault configuration."""
            return {
                "vault_path": str(self.vault_path),
                "name": self.config.get("name"),
                "version": self.config.get("version"),
                "id": self.config.get("id"),
                "plugins_loaded": list(self.plugins.keys()),
                "commands_available": len(self.commands),
                "status": "success"
            }
        
        # Register handlers with WebSocket server
        self.ws_server.register_handler(f"{CHAT_COMMAND_PREFIX}send_message", handle_chat)
        self.ws_server.register_handler("execute_command", handle_execute)
        self.ws_server.register_handler("list_commands", handle_list_commands)
        self.ws_server.register_handler("get_vault_info", handle_get_vault_info)
        
        logger.debug("Registered 4 core WebSocket commands")
    
    def register_command(
        self,
        command_id: str,
        handler: CommandHandler,
        plugin_name: Optional[str] = None
    ) -> None:
        """
        Register a command that can be executed by anyone.
        
        Args:
            command_id: Unique command identifier (e.g., "myPlugin.doSomething")
            handler: Async function to handle the command
            plugin_name: Name of the plugin registering this command
        
        Raises:
            CommandRegistrationError: If handler is not a coroutine function
        
        Example:
            >>> brain.register_command("database.query", self.query_handler, "database_plugin")
        """
        # Validate handler is async
        if not asyncio.iscoroutinefunction(handler):
            raise CommandRegistrationError(
                command_id,
                "Handler must be an async function"
            )
        
        if command_id in self.commands:
            logger.warning(
                f"Command '{command_id}' already registered by "
                f"'{self.commands[command_id]['plugin']}', overwriting"
            )
        
        self.commands[command_id] = {
            "handler": handler,
            "plugin": plugin_name,
        }
        
        logger.debug(f"Registered command: {command_id} (plugin: {plugin_name})")
    
    async def execute_command(self, command_id: str, **kwargs: Any) -> Any:
        """
        Execute a registered command.
        
        Args:
            command_id: Command to execute
            **kwargs: Arguments to pass to the command handler
        
        Returns:
            Result from the command handler
        
        Raises:
            CommandNotFoundError: If command doesn't exist
            CommandExecutionError: If command execution fails
        
        Example:
            >>> result = await brain.execute_command("database.query", table="users")
        """
        if command_id not in self.commands:
            available = list(self.commands.keys())
            raise CommandNotFoundError(command_id, available)
        
        command_info = self.commands[command_id]
        handler = command_info["handler"]
        plugin_name = command_info.get("plugin", "unknown")
        
        logger.debug(f"Executing command: {command_id} (plugin: {plugin_name})")
        
        try:
            result = await handler(**kwargs)
            return result
        except Exception as e:
            logger.error(
                f"Command '{command_id}' execution failed: {e}",
                exc_info=True
            )
            raise CommandExecutionError(command_id, e)
    
    def get_commands(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all registered commands.
        
        Returns:
            Dictionary of command_id -> {plugin}
        
        Useful for building command palettes or documentation.
        """
        return {
            cmd_id: {"plugin": info["plugin"]}
            for cmd_id, info in self.commands.items()
        }
    
    async def _on_tick(self) -> None:
        """
        Internal tick handler - executes one tick cycle.
        
        Useful for testing without starting the infinite loop.
        """
        # Call on_tick for each plugin
        for plugin_name, plugin in self.plugins.items():
            if not hasattr(plugin, PLUGIN_TICK_METHOD):
                continue
            
            try:
                await getattr(plugin, PLUGIN_TICK_METHOD)(self.emitter)
            except Exception as e:
                # Log error but don't crash the tick loop
                plugin_logger = get_plugin_logger(plugin_name)
                plugin_logger.error(f"Tick error: {e}", exc_info=True)
                
                # Optionally emit error event
                try:
                    self.emitter.notify(
                        f"Plugin '{plugin_name}' tick error: {str(e)}",
                        severity="error"
                    )
                except:
                    pass  # Don't crash even if notification fails

    async def tick_loop(self) -> None:
        """
        Periodic tick loop for plugins.
        
        Runs every 5 seconds (configurable), calling on_tick() for each plugin
        that implements it. Errors in one plugin don't affect others.
        """
        logger.info("Starting tick loop...")
        
        tick_count = 0
        
        while True:
            await asyncio.sleep(DEFAULT_TICK_INTERVAL)
            tick_count += 1
            logger.debug(f"Tick #{tick_count}")
            await self._on_tick()
