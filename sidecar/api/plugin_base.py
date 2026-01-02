"""
Tailor - Plugin Base Class

Abstract base class that all plugins should inherit from.
Provides standardized lifecycle hooks and command registration.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional, TYPE_CHECKING, cast

# Handle imports for both package context (tests) and standalone context (plugins)
try:
    from sidecar.event_emitter import EventEmitter, EventScope
    from sidecar.utils.logging_config import get_plugin_logger
except ImportError:
    from event_emitter import EventEmitter, EventScope
    from utils.logging_config import get_plugin_logger


class PluginBase(ABC):
    """
    Abstract base class for Tailor plugins.
    
    All plugins must inherit from this class and implement the required methods.
    The plugin system will automatically discover and load plugins that follow
    this structure.
    
    Plugin Structure:
        my_plugin/
        ├── main.py          # Contains Plugin class inheriting from PluginBase
        ├── settings.json    # Optional plugin settings
        └── README.md        # Optional plugin documentation
    
    Lifecycle:
        1. __init__() - Plugin instantiated with emitter, brain, dirs
        2. on_load() - Called once after all plugins loaded
        3. on_tick() - Called periodically (every 5 seconds by default)
        4. on_unload() - Called when plugin is being unloaded
    
    Example:
        >>> class MyPlugin(PluginBase):
        ...     def __init__(self, emitter, brain, plugin_dir, vault_path):
        ...         super().__init__(emitter, brain, plugin_dir, vault_path)
        ...         self.register_commands()
        ...     
        ...     def register_commands(self):
        ...         self.brain.register_command("my.command", self.handle_command, self.name)
        ...     
        ...     async def handle_command(self, **kwargs):
        ...         return {"status": "ok", "data": kwargs}
    """
    
    def __init__(
        self,
        emitter: 'EventEmitter',
        brain: 'VaultBrain',
        plugin_dir: Path,
        vault_path: Path
    ):
        """
        Initialize plugin.
        
        Args:
            emitter: EventEmitter instance for sending UI events
            brain: VaultBrain instance for command registration
            plugin_dir: Path to this plugin's directory
            vault_path: Path to the vault root directory
        """
        self.emitter = emitter
        self.brain = brain
        self.plugin_dir = plugin_dir
        self.vault_path = vault_path
        
        # Plugin metadata
        self.name = plugin_dir.name
        self.logger = get_plugin_logger(self.name)
        
        # Plugin state
        self._loaded = False
        
        self.logger.debug(f"Plugin '{self.name}' initialized")
        
        # Auto-register commands
        self.register_commands()
    
    @abstractmethod
    def register_commands(self) -> None:
        """
        Register plugin commands with the brain.
        
        This method is called during __init__ and should register all
        commands that the plugin provides.
        
        Example:
            >>> def register_commands(self):
            ...     self.brain.register_command(
            ...         "myPlugin.doSomething",
            ...         self.handle_do_something,
            ...         self.name
            ...     )
        """
        pass
    
    async def on_load(self) -> None:
        """
        Called after all plugins have been loaded.
        
        Use this for initialization that depends on other plugins
        or needs to happen after the full system is ready.
        
        Optional to override.
        """
        self._loaded = True
        self.logger.debug(f"Plugin '{self.name}' loaded")
    
    async def on_tick(self, emitter: 'EventEmitter') -> None:
        """
        Called periodically (every 5 seconds by default).
        
        Use this for periodic tasks like:
        - Checking for updates
        - Syncing state
        - Emitting periodic events
        
        Optional to override.
        
        Args:
            emitter: EventEmitter instance for sending events
        """
        pass
    
    async def on_unload(self) -> None:
        """
        Called when plugin is being unloaded.
        
        Use this for cleanup:
        - Close connections
        - Save state
        - Release resources
        
        Optional to override.
        """
        self._loaded = False
        self.logger.debug(f"Plugin '{self.name}' unloaded")
    
    # Helper methods for common operations
    
    def get_config_path(self, filename: str = "settings.json") -> Path:
        """
        Get path to a config file in the plugin directory.
        
        Args:
            filename: Name of config file (default: settings.json)
        
        Returns:
            Path to config file
        """
        return self.plugin_dir / filename
    
    def load_settings(self, filename: str = "settings.json") -> Dict[str, Any]:
        """
        Load plugin settings from JSON file.
        
        Args:
            filename: Name of settings file (default: settings.json)
        
        Returns:
            Settings dictionary, empty dict if file doesn't exist
        """
        import json
        
        settings_file = self.get_config_path(filename)
        
        if not settings_file.exists():
            self.logger.debug(f"No settings file found: {settings_file}")
            return {}
        
        try:
            with open(settings_file, 'r', encoding='utf-8') as f:
                settings = cast(Dict[str, Any], json.load(f))
                self.logger.debug(f"Loaded settings from {settings_file}")
                return settings
        except Exception as e:
            self.logger.error(f"Failed to load settings: {e}")
            return {}
    
    def save_settings(
        self,
        settings: Dict[str, Any],
        filename: str = "settings.json"
    ) -> bool:
        """
        Save plugin settings to JSON file.
        
        Args:
            settings: Settings dictionary to save
            filename: Name of settings file (default: settings.json)
        
        Returns:
            True if saved successfully, False otherwise
        """
        import json
        
        settings_file = self.get_config_path(filename)
        
        try:
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2)
                self.logger.debug(f"Saved settings to {settings_file}")
                return True
        except Exception as e:
            self.logger.error(f"Failed to save settings: {e}")
            return False

    # UI Helper Methods

    async def register_sidebar_view(
        self,
        identifier: str,
        icon_svg: str,
        title: str
    ) -> None:
        """
        Register a sidebar view (activity bar item).

        Args:
            identifier: Unique ID for the view (e.g. 'my_plugin.explorer')
            icon_svg: SVG string for the icon
            title: Title to display in the header
        """
        # We emit a special 'UI_COMMAND' event that vault.html listens for.
        # This requires the event_emitter to support a generic 'emit' or we overload an existing one.
        # We'll use 'emit' method from EventEmitter with a custom type.
        
        # EventScope is imported at module level
        
        print(f"[PluginBase] register_sidebar_view called: id={identifier}, icon={icon_svg}, title={title}")
        self.logger.info(f"Registering sidebar view: {identifier}")
        
        self.emitter.emit(
            event_type="UI_COMMAND",
            data={
                "action": "register_sidebar",
                "id": identifier,
                "icon": icon_svg,
                "title": title
            },
            scope=EventScope.WINDOW
        )

    async def set_sidebar_content(
        self,
        identifier: str,
        html_content: str
    ) -> None:
        """
        Set the HTML content for a sidebar view.

        Args:
            identifier: ID of the view to update
            html_content: HTML string to render
        """
        # EventScope is imported at module level
        
        self.emitter.emit(
            event_type="UI_COMMAND",
            data={
                "action": "set_sidebar",
                "id": identifier,
                "html": html_content
            },
            scope=EventScope.WINDOW
        )
    
    @property
    def is_loaded(self) -> bool:
        """Check if plugin has been loaded."""
        return self._loaded
    
    def __repr__(self) -> str:
        """String representation of plugin."""
        return f"<{self.__class__.__name__} name='{self.name}' loaded={self._loaded}>"
