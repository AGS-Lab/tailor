"""
Tailor - Utilities Module

Consolidated utilities for the Sidecar application.
Includes:
- Logging Configuration
- JSON-RPC Utilities
- Path Utilities
- ID Generation
"""

import logging
import sys
import time
import json
import uuid
import random
import string
from pathlib import Path
from typing import Dict, Any, Optional, Union, List, cast
from logging.handlers import RotatingFileHandler
import os

from . import constants
from . import exceptions

# =============================================================================
# Logging Configuration
# =============================================================================

# Module-level logger cache
_loggers: dict[str, logging.Logger] = {}
_configured: bool = False


def configure_logging(
    level: Optional[str] = None,
    log_file: Optional[Path] = None,
    verbose: bool = False,
) -> None:
    """
    Configure logging for the entire application.
    
    Should be called once at application startup.
    """
    global _configured
    
    # Determine log level
    if verbose:
        log_level = "DEBUG"
    elif level:
        log_level = level.upper()
    else:
        log_level = os.getenv(constants.ENV_LOG_LEVEL, constants.DEFAULT_LOG_LEVEL).upper()
    
    # Convert string level to logging constant
    numeric_level = getattr(logging, log_level, logging.INFO)
    
    # Create formatters
    if verbose:
        # More detailed format for debugging
        format_str = "%(asctime)s [%(levelname)-8s] [%(name)-20s] [%(filename)s:%(lineno)d] %(message)s"
    else:
        format_str = constants.LOG_FORMAT
    
    formatter = logging.Formatter(format_str, datefmt=constants.LOG_DATE_FORMAT)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if requested)
    if log_file:
        try:
            # Ensure parent directory exists
            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Rotating file handler (max 10MB, keep 5 backups)
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setLevel(numeric_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
            
            root_logger.info(f"Logging to file: {log_file}")
        except Exception as e:
            root_logger.warning(f"Failed to configure file logging: {e}")
    
    _configured = True
    root_logger.info(f"Logging configured at {log_level} level")


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a specific module or component."""
    if name not in _loggers:
        logger = logging.getLogger(name)
        _loggers[name] = logger
    
    return _loggers[name]


def get_plugin_logger(plugin_name: str) -> logging.Logger:
    """
    Get a logger specifically for a plugin.
    Plugin loggers are prefixed with 'plugin:' for easy identification.
    """
    return get_logger(f"plugin:{plugin_name}")


def set_log_level(level: str) -> None:
    """Dynamically change the log level for all loggers."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    for handler in root_logger.handlers:
        handler.setLevel(numeric_level)
    
    root_logger.info(f"Log level changed to {level.upper()}")


def is_configured() -> bool:
    """Check if logging has been configured."""
    return _configured


def setup_dev_logging() -> None:
    """Quick setup for development logging."""
    configure_logging(verbose=True)


# =============================================================================
# JSON-RPC Utilities
# =============================================================================

def build_request(
    method: str,
    params: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a JSON-RPC 2.0 request message."""
    message: Dict[str, Any] = {
        "jsonrpc": constants.JSONRPC_VERSION,
        "method": method,
    }
    
    if params is not None:
        message["params"] = params
    
    if request_id is None:
        request_id = f"req_{int(time.time() * 1000)}"
    
    message["id"] = request_id
    
    return message


def build_response(
    result: Any,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a JSON-RPC 2.0 success response message."""
    return {
        "jsonrpc": constants.JSONRPC_VERSION,
        "result": result,
        "id": request_id,
    }


def build_error(
    code: int,
    message: str,
    data: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a JSON-RPC 2.0 error response message."""
    error_obj = {
        "code": code,
        "message": message,
    }
    
    if data is not None:
        error_obj["data"] = data
    
    return {
        "jsonrpc": constants.JSONRPC_VERSION,
        "error": error_obj,
        "id": request_id,
    }


def build_parse_error(request_id: Optional[str] = None) -> Dict[str, Any]:
    """Build a JSON parse error response."""
    return build_error(
        constants.JSONRPC_PARSE_ERROR,
        "Parse error",
        data={"description": "Invalid JSON was received by the server"},
        request_id=request_id,
    )


def build_invalid_request_error(request_id: Optional[str] = None) -> Dict[str, Any]:
    """Build an invalid request error response."""
    return build_error(
        constants.JSONRPC_INVALID_REQUEST,
        "Invalid Request",
        data={"description": "The JSON sent is not a valid Request object"},
        request_id=request_id,
    )


def build_method_not_found_error(
    method: str,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a method not found error response."""
    return build_error(
        constants.JSONRPC_METHOD_NOT_FOUND,
        f"Method not found: {method}",
        data={"method": method},
        request_id=request_id,
    )


def build_invalid_params_error(
    reason: str,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build an invalid params error response."""
    return build_error(
        constants.JSONRPC_INVALID_PARAMS,
        "Invalid params",
        data={"reason": reason},
        request_id=request_id,
    )


def build_internal_error(
    message: str,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build an internal error response."""
    return build_error(
        constants.JSONRPC_INTERNAL_ERROR,
        message,
        data=details,
        request_id=request_id,
    )


def validate_jsonrpc_message(message: Dict[str, Any]) -> None:
    """Validate that a message conforms to JSON-RPC 2.0 spec."""
    # Check jsonrpc version
    if "jsonrpc" not in message:
        raise exceptions.JSONRPCError("Missing 'jsonrpc' field", constants.JSONRPC_INVALID_REQUEST)
    
    if message["jsonrpc"] != constants.JSONRPC_VERSION:
        raise exceptions.JSONRPCError(
            f"Invalid JSON-RPC version: {message['jsonrpc']}",
            constants.JSONRPC_INVALID_REQUEST
        )
    
    # Check if it's a request or response
    if "method" in message:
        # Request validation
        if not isinstance(message["method"], str):
            raise exceptions.JSONRPCError("Method must be a string", constants.JSONRPC_INVALID_REQUEST)
        
        if "params" in message and not isinstance(message["params"], (dict, list)):
            raise exceptions.JSONRPCError("Params must be object or array", constants.JSONRPC_INVALID_PARAMS)
    
    elif "result" in message or "error" in message:
        # Response validation
        if "result" in message and "error" in message:
            raise exceptions.JSONRPCError(
                "Response cannot have both 'result' and 'error'",
                constants.JSONRPC_INVALID_REQUEST
            )
        
        if "error" in message:
            error = message["error"]
            if not isinstance(error, dict):
                raise exceptions.JSONRPCError("Error must be an object", constants.JSONRPC_INVALID_REQUEST)
            
            if "code" not in error or "message" not in error:
                raise exceptions.JSONRPCError(
                    "Error must have 'code' and 'message'",
                    constants.JSONRPC_INVALID_REQUEST
                )
    
    else:
        raise exceptions.JSONRPCError(
            "Message must be request or response",
            constants.JSONRPC_INVALID_REQUEST
        )


def is_request(message: Dict[str, Any]) -> bool:
    """Check if a message is a JSON-RPC request (has method and id)."""
    return "method" in message and "id" in message


def is_response(message: Dict[str, Any]) -> bool:
    """Check if a message is a JSON-RPC response."""
    return "result" in message or "error" in message


def is_notification(message: Dict[str, Any]) -> bool:
    """Check if a message is a JSON-RPC notification (request without ID)."""
    return "method" in message and "id" not in message


def get_request_id(message: Dict[str, Any]) -> Optional[str]:
    """Extract request ID from a JSON-RPC message."""
    return message.get("id")


def get_method(message: Dict[str, Any]) -> Optional[str]:
    """Extract method name from a JSON-RPC request."""
    return message.get("method")


def get_params(message: Dict[str, Any]) -> Dict[str, Any]:
    """Extract params from a JSON-RPC request."""
    params = message.get("params", {})
    
    # Convert list params to dict (some clients might send arrays)
    if isinstance(params, list):
        return {"args": params}
    
    return params if isinstance(params, dict) else {}


# =============================================================================
# Path Utilities
# =============================================================================

def validate_vault_path(vault_path: Path) -> Path:
    """Validate that a vault directory exists and is accessible."""
    try:
        resolved_path = vault_path.resolve()
    except Exception as e:
        raise exceptions.InvalidPathError(str(vault_path), f"Cannot resolve path: {e}")
    
    if not resolved_path.exists():
        raise exceptions.VaultNotFoundError(str(vault_path))
    
    if not resolved_path.is_dir():
        raise exceptions.InvalidPathError(str(vault_path), "Path is not a directory")
    
    return resolved_path


def validate_plugin_structure(plugin_dir: Path) -> None:
    """Validate that a plugin directory has the required structure."""
    if not plugin_dir.exists():
        raise exceptions.PluginLoadError(
            plugin_dir.name,
            f"Plugin directory does not exist: {plugin_dir}"
        )
    
    if not plugin_dir.is_dir():
        raise exceptions.PluginLoadError(
            plugin_dir.name,
            f"Plugin path is not a directory: {plugin_dir}"
        )
    
    main_file = plugin_dir / constants.PLUGIN_MAIN_FILE
    if not main_file.exists():
        raise exceptions.PluginLoadError(
            plugin_dir.name,
            f"Plugin missing {constants.PLUGIN_MAIN_FILE}"
        )
    
    if not main_file.is_file():
        raise exceptions.PluginLoadError(
            plugin_dir.name,
            f"{constants.PLUGIN_MAIN_FILE} is not a file"
        )


def safe_path_join(base: Path, *parts: str) -> Path:
    """Safely join path components, preventing directory traversal."""
    base = base.resolve()
    joined = (base / Path(*parts)).resolve()
    
    # Check if joined path is within base directory
    try:
        joined.relative_to(base)
    except ValueError:
        raise exceptions.PathTraversalError(str(joined))
    
    return joined


def ensure_directory(path: Path, create: bool = True) -> Path:
    """Ensure a directory exists, optionally creating it."""
    resolved = path.resolve()
    
    if resolved.exists():
        if not resolved.is_dir():
            raise exceptions.InvalidPathError(
                str(path),
                "Path exists but is not a directory"
            )
    elif create:
        try:
            resolved.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise exceptions.InvalidPathError(
                str(path),
                f"Failed to create directory: {e}"
            )
    
    return resolved


def get_vault_config_path(vault_path: Path) -> Path:
    """Get the path to the vault configuration file."""
    return vault_path / constants.VAULT_CONFIG_FILE


def get_memory_dir(vault_path: Path, create: bool = True) -> Path:
    """Get the memory directory for a vault."""
    return ensure_directory(vault_path / constants.MEMORY_DIR, create=create)


def get_plugins_dir(vault_path: Path) -> Optional[Path]:
    """Get the plugins directory for a vault."""
    plugins_path = vault_path / constants.PLUGINS_DIR
    return plugins_path if plugins_path.exists() and plugins_path.is_dir() else None


def get_lib_dir(vault_path: Path, create: bool = True) -> Path:
    """Get the lib directory for a vault (for isolated dependencies)."""
    return ensure_directory(vault_path / constants.LIB_DIR, create=create)


def discover_plugins(vault_path: Path) -> List[Path]:
    """Discover all plugin directories in a vault."""
    plugins_dir = get_plugins_dir(vault_path)
    
    if not plugins_dir:
        return []
    
    plugin_dirs = []
    
    for item in plugins_dir.iterdir():
        # Skip hidden directories and files
        if item.name.startswith(('.', '_')):
            continue
        
        # Only include directories with main.py
        if item.is_dir() and (item / constants.PLUGIN_MAIN_FILE).exists():
            plugin_dirs.append(item)
    
    return sorted(plugin_dirs, key=lambda p: p.name)


def is_safe_filename(filename: str) -> bool:
    """Check if a filename is safe (no path traversal characters)."""
    dangerous_chars = ['..', '/', '\\', '\0']
    return not any(char in filename for char in dangerous_chars)


def get_relative_path(path: Path, base: Path) -> Optional[Path]:
    """Get relative path from base to path."""
    try:
        return path.resolve().relative_to(base.resolve())
    except ValueError:
        return None


# =============================================================================
# ID Generation / Info Utilities
# =============================================================================

def generate_id(prefix: str = "") -> str:
    """
    Generate a unique ID.
    Uses a combination of timestamp and random characters.
    """
    timestamp = int(time.time() * 1000)
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    
    if prefix:
        return f"{prefix}{timestamp}_{random_suffix}"
    return f"{timestamp}_{random_suffix}"


def generate_uuid() -> str:
    """Generate a standard UUID v4 string."""
    return str(uuid.uuid4())
