"""
Tailor - Exception Hierarchy

Custom exception classes for the Tailor sidecar application.
Provides structured error handling and clear error messages.
"""

from typing import Optional, Dict, Any


class TailorError(Exception):
    """
    Base exception for all Tailor-related errors.
    
    All custom exceptions in the Tailor sidecar should inherit from this class.
    """
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        """
        Initialize TailorError.
        
        Args:
            message: Human-readable error message
            details: Optional dictionary with additional error context
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert exception to dictionary for JSON-RPC error response.
        
        Returns:
            Dictionary with message and details
        """
        return {
            "message": self.message,
            "details": self.details,
            "type": self.__class__.__name__,
        }


# ============================================================================
# Vault-Related Exceptions
# ============================================================================

class VaultError(TailorError):
    """Base exception for vault-related errors."""
    pass


class VaultNotFoundError(VaultError):
    """Raised when vault directory does not exist."""
    
    def __init__(self, vault_path: str):
        super().__init__(
            f"Vault directory not found: {vault_path}",
            {"vault_path": vault_path}
        )


class VaultInvalidError(VaultError):
    """Raised when vault directory is invalid (e.g., is a file not a directory)."""
    
    def __init__(self, vault_path: str, reason: str):
        super().__init__(
            f"Vault path is invalid: {reason}",
            {"vault_path": vault_path, "reason": reason}
        )


class VaultConfigError(VaultError):
    """Raised when vault configuration is invalid or cannot be loaded."""
    
    def __init__(self, message: str, config_file: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        error_details: Dict[str, Any] = details or {}
        if config_file:
            error_details["config_file"] = config_file
        super().__init__(f"Vault configuration error: {message}", error_details)


class VaultConfigValidationError(VaultConfigError):
    """Raised when vault configuration fails schema validation."""
    
    def __init__(self, errors: list):
        super().__init__(
            "Vault configuration validation failed",
            details={"validation_errors": errors}
        )


# ============================================================================
# Plugin-Related Exceptions
# ============================================================================

class PluginError(TailorError):
    """Base exception for plugin-related errors."""
    pass


class PluginLoadError(PluginError):
    """Raised when a plugin cannot be loaded."""
    
    def __init__(self, plugin_name: str, reason: str):
        super().__init__(
            f"Failed to load plugin '{plugin_name}': {reason}",
            {"plugin_name": plugin_name, "reason": reason}
        )


class PluginValidationError(PluginError):
    """Raised when a plugin fails validation checks."""
    
    def __init__(self, plugin_name: str, validation_errors: list):
        super().__init__(
            f"Plugin '{plugin_name}' failed validation",
            {"plugin_name": plugin_name, "errors": validation_errors}
        )


class PluginExecutionError(PluginError):
    """Raised when a plugin method execution fails."""
    
    def __init__(self, plugin_name: str, method: str, error: Exception):
        super().__init__(
            f"Plugin '{plugin_name}' method '{method}' failed: {str(error)}",
            {
                "plugin_name": plugin_name,
                "method": method,
                "error_type": type(error).__name__,
                "error_message": str(error),
            }
        )


class PluginNotFoundError(PluginError):
    """Raised when a requested plugin is not found."""
    
    def __init__(self, plugin_name: str):
        super().__init__(
            f"Plugin '{plugin_name}' not found",
            {"plugin_name": plugin_name}
        )


# ============================================================================
# WebSocket-Related Exceptions
# ============================================================================

class WebSocketError(TailorError):
    """Base exception for WebSocket-related errors."""
    pass


class WebSocketConnectionError(WebSocketError):
    """Raised when WebSocket connection fails."""
    
    def __init__(self, host: str, port: int, reason: str):
        super().__init__(
            f"WebSocket connection failed to {host}:{port}: {reason}",
            {"host": host, "port": port, "reason": reason}
        )


class WebSocketMessageError(WebSocketError):
    """Raised when WebSocket message handling fails."""
    
    def __init__(self, message: str, reason: str):
        super().__init__(
            f"WebSocket message error: {reason}",
            {"message_preview": message[:100] if len(message) > 100 else message, "reason": reason}
        )



from . import constants

class JSONRPCError(WebSocketError):
    """Raised when JSON-RPC message is invalid."""
    
    def __init__(self, message: str, code: int = -32603):
        super().__init__(
            f"JSON-RPC error: {message}",
            {"code": code}
        )
        self.code = code


class MethodNotFoundError(JSONRPCError):
    """Raised when a JSON-RPC method is not found."""
    
    def __init__(self, method: str):
        super().__init__(f"Method not found: {method}", code=-32601)



# ============================================================================
# Command Registry Exceptions
# ============================================================================

class CommandError(TailorError):
    """Base exception for command registry errors."""
    pass


class CommandNotFoundError(CommandError):
    """Raised when a command is not found in the registry."""
    
    def __init__(self, command_id: str, available_commands: Optional[list] = None):
        details: Dict[str, Any] = {"command_id": command_id}
        if available_commands:
            details["available_commands"] = available_commands[:10]  # Limit to first 10
        
        super().__init__(
            f"Command '{command_id}' not found",
            details
        )


class CommandRegistrationError(CommandError):
    """Raised when command registration fails."""
    
    def __init__(self, command_id: str, reason: str):
        super().__init__(
            f"Failed to register command '{command_id}': {reason}",
            {"command_id": command_id, "reason": reason}
        )


class CommandExecutionError(CommandError):
    """Raised when command execution fails."""
    
    def __init__(self, command_id: str, error: Exception):
        super().__init__(
            f"Command '{command_id}' execution failed: {str(error)}",
            {
                "command_id": command_id,
                "error_type": type(error).__name__,
                "error_message": str(error),
            }
        )


# ============================================================================
# Configuration Exceptions
# ============================================================================

class ConfigurationError(TailorError):
    """Base exception for configuration errors."""
    pass


class InvalidConfigurationError(ConfigurationError):
    """Raised when configuration values are invalid."""
    
    def __init__(self, key: str, value: Any, reason: str):
        super().__init__(
            f"Invalid configuration for '{key}': {reason}",
            {"key": key, "value": str(value), "reason": reason}
        )


class MissingConfigurationError(ConfigurationError):
    """Raised when required configuration is missing."""
    
    def __init__(self, key: str):
        super().__init__(
            f"Required configuration '{key}' is missing",
            {"key": key}
        )


# ============================================================================
# Path Validation Exceptions
# ============================================================================

class PathError(TailorError):
    """Base exception for path-related errors."""
    pass


class InvalidPathError(PathError):
    """Raised when a path is invalid or unsafe."""
    
    def __init__(self, path: str, reason: str):
        super().__init__(
            f"Invalid path '{path}': {reason}",
            {"path": path, "reason": reason}
        )


class PathTraversalError(PathError):
    """Raised when path traversal attack is detected."""
    
    def __init__(self, path: str):
        super().__init__(
            f"Path traversal attempt detected: {path}",
            {"path": path}
        )
