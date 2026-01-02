"""
Tailor - Constants Module

Centralized constants for the Tailor sidecar application.
All magic numbers, strings, and configuration values are defined here.
"""

from enum import Enum
from typing import Final


# ============================================================================
# JSON-RPC Constants
# ============================================================================

JSONRPC_VERSION: Final[str] = "2.0"
"""JSON-RPC protocol version."""

# JSON-RPC Error Codes (following JSON-RPC 2.0 spec)
JSONRPC_PARSE_ERROR: Final[int] = -32700
"""Invalid JSON was received."""

JSONRPC_INVALID_REQUEST: Final[int] = -32600
"""The JSON sent is not a valid Request object."""

JSONRPC_METHOD_NOT_FOUND: Final[int] = -32601
"""The method does not exist / is not available."""

JSONRPC_INVALID_PARAMS: Final[int] = -32602
"""Invalid method parameter(s)."""

JSONRPC_INTERNAL_ERROR: Final[int] = -32603
"""Internal JSON-RPC error."""


# ============================================================================
# Timing Constants
# ============================================================================

DEFAULT_TICK_INTERVAL: Final[float] = 5.0
"""Default interval in seconds for plugin tick loop."""

WEBSOCKET_TIMEOUT: Final[float] = 30.0
"""WebSocket connection timeout in seconds."""

WEBSOCKET_PING_INTERVAL: Final[float] = 20.0
"""WebSocket ping interval in seconds."""


# ============================================================================
# Event Types
# ============================================================================

class EventType(str, Enum):
    """Event types for UI notifications."""
    
    NOTIFY = "NOTIFY"
    """General notification event."""
    
    PROGRESS = "PROGRESS"
    """Progress update event."""
    
    UPDATE_STATE = "UPDATE_STATE"
    """UI state update event."""
    
    LLM_RESPONSE = "LLM_RESPONSE"
    """LLM response event."""
    
    LLM_CLEARED = "LLM_CLEARED"
    """LLM conversation cleared event."""


class EventScope(str, Enum):
    """Event routing scopes."""
    
    WINDOW = "window"
    """Route event to only the originating window."""
    
    VAULT = "vault"
    """Route event to all windows of the same vault."""
    
    GLOBAL = "global"
    """Route event to all windows in the application."""


class Severity(str, Enum):
    """Notification severity levels."""
    
    INFO = "info"
    """Informational message."""
    
    SUCCESS = "success"
    """Success message."""
    
    WARNING = "warning"
    """Warning message."""
    
    ERROR = "error"
    """Error message."""


# ============================================================================
# WebSocket Constants
# ============================================================================

DEFAULT_WEBSOCKET_HOST: Final[str] = "127.0.0.1"
"""Default WebSocket host."""

MIN_WEBSOCKET_PORT: Final[int] = 9000
"""Minimum WebSocket port number."""

MAX_WEBSOCKET_PORT: Final[int] = 9999
"""Maximum WebSocket port number."""


# ============================================================================
# Path Constants
# ============================================================================

VAULT_CONFIG_FILE: Final[str] = ".vault.json"
"""Vault configuration file name."""

MEMORY_DIR: Final[str] = ".memory"
"""Memory directory name within vault."""

PLUGINS_DIR: Final[str] = "plugins"
"""Plugins directory name within vault."""

LIB_DIR: Final[str] = "lib"
"""Library directory name within vault."""

PLUGIN_MAIN_FILE: Final[str] = "main.py"
"""Plugin entry point file name."""

PLUGIN_SETTINGS_FILE: Final[str] = "settings.json"
"""Plugin settings file name."""


# ============================================================================
# Plugin Constants
# ============================================================================

PLUGIN_CLASS_NAME: Final[str] = "Plugin"
"""Required plugin class name."""

PLUGIN_TICK_METHOD: Final[str] = "on_tick"
"""Plugin tick method name."""

PLUGIN_LOAD_METHOD: Final[str] = "on_load"
"""Plugin load method name."""

PLUGIN_UNLOAD_METHOD: Final[str] = "on_unload"
"""Plugin unload method name."""


# ============================================================================
# Command Registry Constants
# ============================================================================

CORE_PLUGIN_NAME: Final[str] = "core"
"""Name for core system commands."""

UI_COMMAND_PREFIX: Final[str] = "ui."
"""Prefix for UI-related commands."""

CHAT_COMMAND_PREFIX: Final[str] = "chat."
"""Prefix for chat-related commands."""


# ============================================================================
# Logging Constants
# ============================================================================

LOG_FORMAT: Final[str] = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
"""Default log format."""

LOG_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"
"""Default log date format."""

DEFAULT_LOG_LEVEL: Final[str] = "INFO"
"""Default logging level."""


# ============================================================================
# Vault Configuration Defaults
# ============================================================================

DEFAULT_VAULT_VERSION: Final[str] = "1.0.0"
"""Default vault configuration version."""

DEFAULT_VAULT_CONFIG: Final[dict] = {
    "version": DEFAULT_VAULT_VERSION,
    "plugins": {
        "enabled": [],
    }
}
"""Default vault configuration structure."""


# ============================================================================
# Environment Variable Names
# ============================================================================

ENV_LOG_LEVEL: Final[str] = "TAILOR_LOG_LEVEL"
"""Environment variable for log level."""

ENV_VAULT_PATH: Final[str] = "TAILOR_VAULT_PATH"
"""Environment variable for vault path."""

ENV_WS_PORT: Final[str] = "TAILOR_WS_PORT"
"""Environment variable for WebSocket port."""

ENV_TICK_INTERVAL: Final[str] = "TAILOR_TICK_INTERVAL"
"""Environment variable for tick interval."""
