"""
Tailor - Utilities Module

Consolidated utilities for the Sidecar application.
Includes:
- Logging Configuration
- JSON-RPC Utilities
- Path Utilities
- ID Generation
"""

from typing import Any, Dict, Optional, List
from pathlib import Path
import os
import sys
import time
import json

import random
import string
from . import constants
from . import exceptions

# =============================================================================
# Logging Configuration
# =============================================================================

from loguru import logger

def configure_logging(
    level: Optional[str] = None,
    log_file: Optional[Path] = None,
    verbose: bool = False,
) -> None:
    """
    Configure logging using Loguru.
    """
    # Remove default handler
    logger.remove()
    
    # Determine log level
    if verbose:
        log_level = "DEBUG"
    elif level:
        log_level = level.upper()
    else:
        log_level = os.getenv(constants.ENV_LOG_LEVEL, constants.DEFAULT_LOG_LEVEL).upper()
    
    # Define detailed format
    format_str = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    
    # Console handler
    logger.add(
        sys.stdout,
        level=log_level,
        format=format_str,
        colorize=True
    )
    
    # File handler (if requested)
    if log_file:
        try:
            # Ensure parent directory exists
            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            logger.add(
                str(log_file),
                rotation="10 MB",
                retention="5 files",
                level=log_level,
                format=format_str,
                encoding="utf-8"
            )
            
            logger.info(f"Logging to file: {log_file}")
        except Exception as e:
            # Using sys.stderr directly to avoid recursive logging issues if logger is broken
            print(f"Failed to configure file logging: {e}", file=sys.stderr)
            
    logger.info(f"Logging configured at {log_level} level")





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

