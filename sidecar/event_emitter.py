"""
Event Emitter - Plugin API for emitting events back to Rust/UI

This module provides the EventEmitter class that plugins use to send
events back to the Tauri application. It uses the command registry 
pattern for all UI interactions.
"""

import time
from typing import Any, Dict, Optional, TYPE_CHECKING

from .utils.logging_config import get_logger
from .utils.json_rpc import build_request
from .constants import (
    EventType,
    EventScope,
    Severity,
    CORE_PLUGIN_NAME,
    UI_COMMAND_PREFIX,
)

if TYPE_CHECKING:
    from vault_brain import VaultBrain

logger = get_logger(__name__)


class EventEmitter:
    """
    API for plugins to emit events back to the UI.
    
    All methods are registered as commands in VaultBrain's command registry.
    Plugins can call emitter methods directly or use brain.execute_command().
    
    Usage in plugins:
        >>> emitter.notify("Task complete!")
        >>> emitter.progress(75, "Processing...")
        
        # Or via command registry:
        >>> await brain.execute_command("ui.notify", message="Hello", severity="info")
    
    Attributes:
        ws_server: WebSocket server instance for sending messages
        brain: VaultBrain instance for command registration (optional)
    """
    
    def __init__(
        self,
        websocket_server: Any,
        brain: Optional[Any] = None
    ):
        """
        Initialize EventEmitter.
        
        Args:
            websocket_server: WebSocketServer instance for sending messages
            brain: VaultBrain instance for command registration (optional)
        """
        self.ws_server = websocket_server
        self.brain = brain
        self._id_counter = 0
        
        # Register UI commands if brain is provided
        if brain:
            self._register_ui_commands()
            logger.debug("EventEmitter initialized with command registry")
        else:
            logger.debug("EventEmitter initialized without command registry")
    
    def _register_ui_commands(self) -> None:
        """Register all UI interaction commands in the command registry."""
        if not self.brain:
            return
        
        # Register core UI commands
        self.brain.register_command(
            f"{UI_COMMAND_PREFIX}notify",
            self._cmd_notify,
            CORE_PLUGIN_NAME
        )
        self.brain.register_command(
            f"{UI_COMMAND_PREFIX}progress",
            self._cmd_progress,
            CORE_PLUGIN_NAME
        )
        self.brain.register_command(
            f"{UI_COMMAND_PREFIX}updateState",
            self._cmd_update_state,
            CORE_PLUGIN_NAME
        )
        self.brain.register_command(
            f"{UI_COMMAND_PREFIX}emit",
            self._cmd_emit,
            CORE_PLUGIN_NAME
        )
        
        logger.debug("Registered 4 UI commands")
    
    # ========================================================================
    # Command Handlers (async for consistency with command pattern)
    # ========================================================================
    
    async def _cmd_notify(
        self,
        message: str,
        severity: str = Severity.INFO,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Command handler for ui.notify."""
        self.notify(message, severity)
        return {"sent": True, "type": "notify"}
    
    async def _cmd_progress(
        self,
        percent: int,
        status: str,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Command handler for ui.progress."""
        self.progress(percent, status)
        return {"sent": True, "type": "progress"}
    
    async def _cmd_update_state(
        self,
        key: str,
        value: Any,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Command handler for ui.updateState."""
        self.update_state(key, value)
        return {"sent": True, "type": "update_state", "key": key}
    
    async def _cmd_emit(
        self, 
        event_type: str, 
        data: Dict[str, Any], 
        scope: str = EventScope.WINDOW,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Command handler for ui.emit."""
        self.emit(event_type, data, scope)
        return {"sent": True, "type": "emit", "event_type": event_type}
    
    # ========================================================================
    # Public API Methods
    # ========================================================================
    
    def emit(
        self,
        event_type: str,
        data: Dict[str, Any],
        scope: str = EventScope.WINDOW,
    ) -> None:
        """
        Emit a generic event.
        
        Args:
            event_type: Type of event (e.g., "NOTIFY", "UPDATE_STATE")
            data: Event payload
            scope: Routing scope (window, global, vault)
        
        Example:
            >>> emitter.emit("CUSTOM_EVENT", {"key": "value"}, scope="vault")
        """
        # Validate scope
        valid_scopes = [EventScope.WINDOW, EventScope.VAULT, EventScope.GLOBAL]
        if scope not in valid_scopes and scope not in [s.value for s in valid_scopes]:
            raise ValueError(
                f"Invalid scope '{scope}'. Must be one of: {[s.value for s in valid_scopes]}"
            )
        
        message = build_request(
            method="trigger_event",
            params={
                "event_type": event_type,
                "scope": scope,
                "data": data,
                "timestamp": time.time(),
            },
            request_id=self._next_id(),
        )
        
        # Send via WebSocket (if available)
        if self.ws_server:
            self.ws_server.send_to_rust(message)
            logger.debug(f"Emitted event '{event_type}' with scope '{scope}'")
        else:
            logger.warning(f"Cannot emit event '{event_type}': WebSocket server not available")
    
    def notify(
        self,
        message: str,
        severity: str = Severity.INFO
    ) -> None:
        """
        Show notification in current window.
        
        Can also be called via: 
        brain.execute_command("ui.notify", message="...", severity="info")
        
        Args:
            message: Notification message
            severity: Severity level (info, success, warning, error)
        
        Example:
            >>> emitter.notify("Plugin loaded successfully", severity="success")
            >>> emitter.notify("Failed to connect", severity="error")
        """
        # Validate severity
        valid_severities = [Severity.INFO, Severity.SUCCESS, Severity.WARNING, Severity.ERROR]
        if severity not in valid_severities and severity not in [s.value for s in valid_severities]:
            raise ValueError(
                f"Invalid severity '{severity}'. Must be one of: {[s.value for s in valid_severities]}"
            )
        
        self.emit(
            EventType.NOTIFY,
            {"message": message, "severity": severity}
        )
    
    def progress(self, percent: int, status: str = "") -> None:
        """
        Update progress bar.
        
        Can also be called via: 
        brain.execute_command("ui.progress", percent=50, status="...")
        
        Args:
            percent: Progress percentage (0-100)
            status: Status message
        
        Example:
            >>> emitter.progress(50, "Processing files...")
            >>> emitter.progress(100, "Complete")
        """
        # Validate percent is in range
        if not (0 <= percent <= 100):
            raise ValueError(f"Percent must be between 0 and 100, got {percent}")
        
        self.emit(
            EventType.PROGRESS,
            {"percent": percent, "message": status}
        )
    
    def update_state(self, key: str, value: Any) -> None:
        """
        Update vault-specific UI state.
        
        Can also be called via: 
        brain.execute_command("ui.updateState", key="...", value=...)
        
        Args:
            key: State key
            value: State value
        
        Example:
            >>> emitter.update_state("task_count", 42)
            >>> emitter.update_state("is_processing", True)
        """
        self.emit(
            EventType.UPDATE_STATE,
            {"key": key, "value": value}
        )
    
    def global_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Emit event to all windows.
        
        Args:
            event_type: Type of global event
            data: Event data
        
        Example:
            >>> emitter.global_event("SYSTEM_ALERT", {"message": "Important update"})
        """
        self.emit(event_type, data, scope=EventScope.GLOBAL)
    
    def vault_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Emit event to all windows with same vault.
        
        Args:
            event_type: Type of vault event
            data: Event data
        
        Example:
            >>> emitter.vault_event("STATE_CHANGED", {"key": "value"})
        """
        self.emit(event_type, data, scope=EventScope.VAULT)
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    def _next_id(self) -> str:
        """
        Generate next event ID.
        
        Returns:
            Unique event ID string
        """
        self._id_counter += 1
        return f"evt_{self._id_counter}"
