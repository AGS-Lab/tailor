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
    from sidecar.llm import HookPhase, HookContext
except ImportError:
    from sidecar import utils
    from sidecar import constants
    try:
        from sidecar.llm import HookPhase, HookContext
    except ImportError:
        HookPhase = None  # type: ignore
        HookContext = None  # type: ignore

if TYPE_CHECKING:
    from sidecar.vault_brain import VaultBrain
    from sidecar.llm import HookContext as HookContextType


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
        vault_path: Path,
        config: Dict[str, Any] = None
    ):
        """
        Initialize plugin.
        
        Args:
            plugin_dir: Path to this plugin's directory
            vault_path: Path to the vault root directory
            config: Resolved configuration dictionary (Defaults + Overrides)
        """
        self.plugin_dir = plugin_dir
        self.vault_path = vault_path
        self.config = config or {}
        
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
    
    def register_hooks(self) -> None:
        """
        Register LLM processing hooks.
        
        Called by VaultBrain after register_commands().
        Override this method to register hooks for LLM pipeline phases.
        
        Available hooks:
        - input.transform: Modify user message before processing
        - input.validate: Validate/filter input (can abort pipeline)
        - process.before_llm: Inject context before LLM call
        - process.after_llm: Post-process LLM response
        - output.format: Format response for UI
        
        Example:
            def register_hooks(self) -> None:
                self.register_hook(
                    "process.before_llm",
                    self._inject_context,
                    priority=50
                )
        """
        pass
    
    def register_hook(
        self,
        phase: str,
        handler: Callable[["HookContextType"], Awaitable["HookContextType"]],
        priority: int = 100
    ) -> None:
        """
        Register a hook for LLM processing.
        
        Args:
            phase: Hook phase (e.g., "input.transform", "process.before_llm")
            handler: Async function that receives and returns HookContext
            priority: Execution priority (lower = runs first)
        """
        if HookPhase is None:
            self.logger.warning("Hook system not available")
            return
        
        try:
            hook_phase = HookPhase(phase)
            self.brain.hook_registry.register(
                hook_phase,
                handler,
                self.name,
                priority
            )
            self.logger.debug(f"Registered hook: {phase} (priority={priority})")
        except ValueError as e:
            self.logger.error(f"Invalid hook phase '{phase}': {e}")
    
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
    
    def emit(self, event_type: str, data: Dict[str, Any], scope: str = constants.EventScope.WINDOW) -> None:
        """
        Emit a generic event to the frontend.
        
        Args:
            event_type: Type/Name of event (e.g. "llm.response")
            data: Payload dictionary
            scope: Event scope (window/global)
        """
        self.brain.emit_to_frontend(event_type, data, scope)

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

    # =========================================================================
    # UI Helpers - Methods for plugins to control frontend UI elements
    # =========================================================================

    def _emit_ui_command(self, action: str, data: Dict[str, Any]) -> None:
        """Helper to emit UI commands to frontend."""
        self.brain.emit_to_frontend(
            event_type=constants.EventType.UI_COMMAND,
            data={"action": action, **data},
            scope=constants.EventScope.WINDOW
        )

    # --- Sidebar Views ---

    async def register_sidebar_view(
        self,
        identifier: str,
        icon_svg: str,
        title: str
    ) -> None:
        """
        Register a sidebar view in the activity bar.
        
        Args:
            identifier: Unique ID for this sidebar view
            icon_svg: Either an SVG string or a Lucide icon name (e.g., "folder")
            title: Display title for the sidebar
        """
        self._emit_ui_command(
            constants.UIAction.REGISTER_SIDEBAR,
            {"id": identifier, "icon": icon_svg, "title": title}
        )

    async def set_sidebar_content(
        self,
        identifier: str,
        html_content: str
    ) -> None:
        """
        Set HTML content for a sidebar view.
        
        Args:
            identifier: ID of the sidebar view
            html_content: HTML string to display
        """
        self._emit_ui_command(
            constants.UIAction.SET_SIDEBAR,
            {"id": identifier, "html": html_content}
        )

    # --- Panel/Tab Management (GoldenLayout) ---

    async def register_panel(
        self,
        panel_id: str,
        title: str,
        icon: str = None,
        position: str = "right"
    ) -> None:
        """
        Register a new panel/tab in the layout.
        
        Args:
            panel_id: Unique ID for this panel
            title: Tab title
            icon: Optional Lucide icon name
            position: Where to add panel ("left", "right", "bottom")
        """
        self._emit_ui_command(
            constants.UIAction.REGISTER_PANEL,
            {"id": panel_id, "title": title, "icon": icon, "position": position}
        )

    async def set_panel_content(
        self,
        panel_id: str,
        html_content: str
    ) -> None:
        """
        Set HTML content for a panel.
        
        Args:
            panel_id: ID of the panel
            html_content: HTML string to display
        """
        self._emit_ui_command(
            constants.UIAction.SET_PANEL,
            {"id": panel_id, "html": html_content}
        )

    async def remove_panel(self, panel_id: str) -> None:
        """
        Remove a panel from the layout.
        
        Args:
            panel_id: ID of the panel to remove
        """
        self._emit_ui_command(
            constants.UIAction.REMOVE_PANEL,
            {"id": panel_id}
        )

    # --- Toolbar Buttons ---

    async def register_toolbar_button(
        self,
        button_id: str,
        icon: str,
        title: str,
        command: str
    ) -> None:
        """
        Register a toolbar button that executes a command when clicked.
        
        Args:
            button_id: Unique ID for this button
            icon: Lucide icon name (e.g., "play", "settings")
            title: Tooltip text
            command: Command to execute on click (e.g., "my_plugin.run")
        """
        self._emit_ui_command(
            constants.UIAction.REGISTER_TOOLBAR,
            {"id": button_id, "icon": icon, "title": title, "command": command}
        )

    # --- Stage Content ---

    async def set_stage_content(self, html_content: str) -> None:
        """
        Set HTML content for the main stage area.
        
        Args:
            html_content: HTML string to display in the stage
        """
        self._emit_ui_command(
            constants.UIAction.SET_STAGE,
            {"html": html_content}
        )

    # --- Modal Dialogs ---

    async def show_modal(
        self,
        title: str,
        html_content: str,
        width: str = "500px"
    ) -> None:
        """
        Show a modal dialog.
        
        Args:
            title: Modal title
            html_content: HTML content for the modal body
            width: CSS width (default: "500px")
        """
        self._emit_ui_command(
            constants.UIAction.SHOW_MODAL,
            {"title": title, "html": html_content, "width": width}
        )

    async def close_modal(self) -> None:
        """Close the currently open modal dialog."""
        self._emit_ui_command(
            constants.UIAction.CLOSE_MODAL,
            {}
        )

    # =========================================================================
    # Properties
    # =========================================================================
    
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

