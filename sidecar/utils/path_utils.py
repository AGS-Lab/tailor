"""
Tailor - Path Utilities Module

Utilities for safe path operations and validation.
Prevents directory traversal and validates vault structure.
"""

from pathlib import Path
from typing import Optional, List

from ..constants import (
    VAULT_CONFIG_FILE,
    MEMORY_DIR,
    PLUGINS_DIR,
    LIB_DIR,
    PLUGIN_MAIN_FILE,
)
from ..exceptions import (
    VaultNotFoundError,
    InvalidPathError,
    PathTraversalError,
    PluginLoadError,
)


def validate_vault_path(vault_path: Path) -> Path:
    """
    Validate that a vault directory exists and is accessible.
    
    Args:
        vault_path: Path to vault directory
    
    Returns:
        Resolved absolute path to vault
    
    Raises:
        VaultNotFoundError: If vault directory doesn't exist
        InvalidPathError: If path is not a directory
    
    Example:
        >>> vault_path = validate_vault_path(Path("./my-vault"))
        >>> # Returns: /absolute/path/to/my-vault
    """
    try:
        resolved_path = vault_path.resolve()
    except Exception as e:
        raise InvalidPathError(str(vault_path), f"Cannot resolve path: {e}")
    
    if not resolved_path.exists():
        raise VaultNotFoundError(str(vault_path))
    
    if not resolved_path.is_dir():
        raise InvalidPathError(str(vault_path), "Path is not a directory")
    
    return resolved_path


def validate_plugin_structure(plugin_dir: Path) -> None:
    """
    Validate that a plugin directory has the required structure.
    
    Args:
        plugin_dir: Path to plugin directory
    
    Raises:
        PluginLoadError: If plugin structure is invalid
    
    Example:
        >>> validate_plugin_structure(Path("vault/plugins/my_plugin"))
    """
    if not plugin_dir.exists():
        raise PluginLoadError(
            plugin_dir.name,
            f"Plugin directory does not exist: {plugin_dir}"
        )
    
    if not plugin_dir.is_dir():
        raise PluginLoadError(
            plugin_dir.name,
            f"Plugin path is not a directory: {plugin_dir}"
        )
    
    main_file = plugin_dir / PLUGIN_MAIN_FILE
    if not main_file.exists():
        raise PluginLoadError(
            plugin_dir.name,
            f"Plugin missing {PLUGIN_MAIN_FILE}"
        )
    
    if not main_file.is_file():
        raise PluginLoadError(
            plugin_dir.name,
            f"{PLUGIN_MAIN_FILE} is not a file"
        )


def safe_path_join(base: Path, *parts: str) -> Path:
    """
    Safely join path components, preventing directory traversal.
    
    Args:
        base: Base directory path
        *parts: Path components to join
    
    Returns:
        Joined path
    
    Raises:
        PathTraversalError: If joined path would escape base directory
    
    Example:
        >>> safe_path_join(Path("/vault"), "plugins", "my_plugin")
        >>> # Returns: /vault/plugins/my_plugin
        
        >>> safe_path_join(Path("/vault"), "..", "etc", "passwd")
        >>> # Raises: PathTraversalError
    """
    base = base.resolve()
    joined = (base / Path(*parts)).resolve()
    
    # Check if joined path is within base directory
    try:
        joined.relative_to(base)
    except ValueError:
        raise PathTraversalError(str(joined))
    
    return joined


def ensure_directory(path: Path, create: bool = True) -> Path:
    """
    Ensure a directory exists, optionally creating it.
    
    Args:
        path: Directory path
        create: If True, create directory if it doesn't exist
    
    Returns:
        Absolute path to directory
    
    Raises:
        InvalidPathError: If path exists but is not a directory
    
    Example:
        >>> memory_dir = ensure_directory(vault_path / ".memory")
    """
    resolved = path.resolve()
    
    if resolved.exists():
        if not resolved.is_dir():
            raise InvalidPathError(
                str(path),
                "Path exists but is not a directory"
            )
    elif create:
        try:
            resolved.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise InvalidPathError(
                str(path),
                f"Failed to create directory: {e}"
            )
    
    return resolved


def get_vault_config_path(vault_path: Path) -> Path:
    """
    Get the path to the vault configuration file.
    
    Args:
        vault_path: Vault directory path
    
    Returns:
        Path to .vault.json file
    """
    return vault_path / VAULT_CONFIG_FILE


def get_memory_dir(vault_path: Path, create: bool = True) -> Path:
    """
    Get the memory directory for a vault.
    
    Args:
        vault_path: Vault directory path
        create: If True, create directory if it doesn't exist
    
    Returns:
        Path to .memory directory
    """
    return ensure_directory(vault_path / MEMORY_DIR, create=create)


def get_plugins_dir(vault_path: Path) -> Optional[Path]:
    """
    Get the plugins directory for a vault.
    
    Args:
        vault_path: Vault directory path
    
    Returns:
        Path to plugins directory if it exists, None otherwise
    """
    plugins_path = vault_path / PLUGINS_DIR
    return plugins_path if plugins_path.exists() and plugins_path.is_dir() else None


def get_lib_dir(vault_path: Path, create: bool = True) -> Path:
    """
    Get the lib directory for a vault (for isolated dependencies).
    
    Args:
        vault_path: Vault directory path
        create: If True, create directory if it doesn't exist
    
    Returns:
        Path to lib directory
    """
    return ensure_directory(vault_path / LIB_DIR, create=create)


def discover_plugins(vault_path: Path) -> List[Path]:
    """
    Discover all plugin directories in a vault.
    
    Args:
        vault_path: Vault directory path
    
    Returns:
        List of plugin directory paths
    
    Example:
        >>> plugins = discover_plugins(Path("/vault"))
        >>> # [Path("/vault/plugins/example"), Path("/vault/plugins/llm"), ...]
    """
    plugins_dir = get_plugins_dir(vault_path)
    
    if not plugins_dir:
        return []
    
    plugin_dirs = []
    
    for item in plugins_dir.iterdir():
        # Skip hidden directories and files
        if item.name.startswith(('.', '_')):
            continue
        
        # Only include directories with main.py
        if item.is_dir() and (item / PLUGIN_MAIN_FILE).exists():
            plugin_dirs.append(item)
    
    return sorted(plugin_dirs, key=lambda p: p.name)


def is_safe_filename(filename: str) -> bool:
    """
    Check if a filename is safe (no path traversal characters).
    
    Args:
        filename: Filename to check
    
    Returns:
        True if filename is safe, False otherwise
    
    Example:
        >>> is_safe_filename("plugin.py")  # True
        >>> is_safe_filename("../etc/passwd")  # False
    """
    dangerous_chars = ['..', '/', '\\', '\0']
    return not any(char in filename for char in dangerous_chars)


def get_relative_path(path: Path, base: Path) -> Optional[Path]:
    """
    Get relative path from base to path.
    
    Args:
        path: Target path
        base: Base path
    
    Returns:
        Relative path if path is within base, None otherwise
    """
    try:
        return path.resolve().relative_to(base.resolve())
    except ValueError:
        return None
