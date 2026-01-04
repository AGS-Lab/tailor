"""
Tailor - Plugin Base Class

Abstract base class that all plugins should inherit from.
Provides standardized lifecycle hooks and command registration.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional, TYPE_CHECKING, cast, Callable, Awaitable

# Handle imports for both package context (tests) and standalone context (plugins)
try:
    from sidecar import utils
    from sidecar import constants
    from sidecar.constants import CoreEvents
except ImportError:
    import utils
    import constants
    from api.events import CoreEvents

if TYPE_CHECKING:
    from sidecar.vault_brain import VaultBrain


class PluginBase(ABC):
    """
    Abstract base class for Tailor plugins.
    
    All plugins must inherit from this class.
    
    Key Changes in v2 Architecture:
    - No 'brain' or 'emitter' passed in __init__.
    - Access 'self.brain' property for singleton instance.
    - 'register_commands()' is called EXPLICITLY by the Brain, not in __init__.
    
    Lifecycle:
        1. __init__(plugin_dir, vault_path)
        2. register_commands() - Called by Brain (Phase 1)
        3. on_load() - Called by Brain (Phase 2 - Active)
        4. on_tick() - Called periodically
        5. on_unload() - Called on shutdown
    """
    
    def __init__(
        self,
        plugin_dir: Path,
        vault_path: Path
    ):
        """
        Initialize plugin.
        
        Args:
            plugin_dir: Path to this plugin's directory
            vault_path: Path to the vault root directory
        """
        self.plugin_dir = plugin_dir
        self.vault_path = vault_path
        
        # Plugin metadata
        self.name = plugin_dir.name
        from loguru import logger
        self.logger = logger.bind(name=f"plugin:{self.name}")
        
        # Plugin state
        self._loaded = False
        
        self.logger.debug(f"Plugin '{self.name}' initialized (Passive)")

    @property
    def brain(self) -> 'VaultBrain':
        """
        Access the Singleton VaultBrain.
        Lazy import to avoid circular dependency issues at module level.
        """
        # Local import to retrieve singleton
        try:
            from sidecar.vault_brain import VaultBrain
            return VaultBrain.get()
        except ImportError:
            # Fallback for when running in non-standard environment
            from ..vault_brain import VaultBrain
            return VaultBrain.get()
    
    @abstractmethod
    def register_commands(self) -> None:
        """
        Register plugin commands with the brain.
        
        Called by VaultBrain during Phase 1 (Registration).
        DO NOT run active code here. Just register.
        """
        pass
    
    async def on_load(self) -> None:
        """
        Called while the plugin is being loaded.

        Safe to communicate with other plugins here.
        """
        self._loaded = True
        self.logger.debug(f"Plugin '{self.name}' loaded (Active)")
    
    async def on_tick(self) -> None:
        """
        Called periodically.
        Refactored to receive 'brain' instead of 'emitter'.
        """
        pass
    
    async def on_client_connected(self) -> None:
        """
        Called when the frontend client connects and sends 'system.client_ready'.
        Use this for UI registration (register_sidebar_view, etc) to ensure
        the client receives the commands.
        """
        pass
    
    async def on_unload(self) -> None:
        """Called when plugin is being unloaded."""
        self._loaded = False
        self.logger.debug(f"Plugin '{self.name}' unloaded")
    
    # Helper methods for common operations
    
    def notify(self, message: str, severity: str = "info") -> None:
        """Send a notification to the frontend."""
        self.brain.notify_frontend(message, severity)

    def progress(self, percentage: int, message: str = "") -> None:
        """Report progress to the frontend."""
        self.brain.emit_to_frontend(
            constants.EventType.PROGRESS,
            {"percentage": percentage, "message": message}
        )

    def update_state(self, key: str, value: Any) -> None:
        """Update a key in the Frontend global/vault state."""
        self.brain.update_state(key, value)

    def get_config_path(self, filename: str = constants.PLUGIN_SETTINGS_FILE) -> Path:
        """Get path to a config file."""
        return self.plugin_dir / filename
    
    def load_settings(self, filename: str = constants.PLUGIN_SETTINGS_FILE) -> Dict[str, Any]:
        """Load plugin settings from JSON file."""
        import json
        settings_file = self.get_config_path(filename)
        if not settings_file.exists():
            return {}
        try:
            with open(settings_file, 'r', encoding='utf-8') as f:
                return cast(Dict[str, Any], json.load(f))
        except Exception as e:
            self.logger.error(f"Failed to load settings: {e}")
            return {}
    
    def save_settings(
        self,
        settings: Dict[str, Any],
        filename: str = constants.PLUGIN_SETTINGS_FILE
    ) -> bool:
        """Save plugin settings to JSON file."""
        import json
        settings_file = self.get_config_path(filename)
        try:
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2)
                return True
        except Exception as e:
            self.logger.error(f"Failed to save settings: {e}")
            return False
        
    async def publish(self, event_name: str, **kwargs: Any) -> None:
        """Publish internal event."""
        await self.brain.publish(event_name, **kwargs)

    def subscribe(self, event_name: str, handler: Callable[..., Awaitable[None]]) -> None:
        """Subscribe to internal event."""
        self.brain.subscribe(event_name, handler)

    # UI Helpers

    async def register_sidebar_view(
        self,
        identifier: str,
        icon_svg: str,
        title: str
    ) -> None:
        """Register a sidebar view."""
        self.brain.emit_to_frontend(
            event_type=constants.EventType.UI_COMMAND,
            data={
                "action": "register_sidebar",
                "id": identifier,
                "icon": icon_svg,
                "title": title
            },
            scope=constants.EventScope.WINDOW # Imported from constants
        )

    async def set_sidebar_content(
        self,
        identifier: str,
        html_content: str
    ) -> None:
        """Set sidebar content."""
        self.brain.emit_to_frontend(
            event_type=constants.EventType.UI_COMMAND,
            data={
                "action": "set_sidebar",
                "id": identifier,
                "html": html_content
            },
            scope=constants.EventScope.WINDOW
        )
    
    @property
    def is_loaded(self) -> bool:
        """Check if plugin has been loaded."""
        return self._loaded
    
    @property
    def is_client_connected(self) -> bool:
        """Check if frontend client is connected."""
        return self.brain.is_client_connected
    
    def __repr__(self) -> str:
        """String representation of plugin."""
        return f"<{self.__class__.__name__} name='{self.name}' loaded={self._loaded}>"
