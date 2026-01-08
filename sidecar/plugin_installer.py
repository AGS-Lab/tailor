"""
Plugin Installer - Handles plugin installation, updates, and removal.

Provides functionality for:
- Installing plugins from git repositories
- Updating installed plugins
- Removing plugins
- Validating plugin structure and manifests
"""

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional, List
from enum import Enum

from loguru import logger


class InstallStatus(Enum):
    """Plugin installation status."""
    SUCCESS = "success"
    ALREADY_EXISTS = "already_exists"
    CLONE_FAILED = "clone_failed"
    VALIDATION_FAILED = "validation_failed"
    DEPENDENCY_FAILED = "dependency_failed"


@dataclass
class InstallResult:
    """Result of a plugin installation."""
    status: InstallStatus
    plugin_id: str
    message: str
    plugin_dir: Optional[Path] = None
    manifest: Optional[Dict[str, Any]] = None


@dataclass
class ValidationResult:
    """Result of plugin validation."""
    valid: bool
    errors: List[str]
    warnings: List[str]
    manifest: Optional[Dict[str, Any]] = None


class PluginInstaller:
    """
    Handles plugin installation, updates, and removal.
    
    Plugins are installed via git clone into the vault's plugins directory.
    """
    
    REQUIRED_FILES = ["main.py", "plugin.json"]
    MANIFEST_REQUIRED_FIELDS = ["name", "version", "main"]
    
    def __init__(self, vault_path: Path):
        """
        Initialize the plugin installer.
        
        Args:
            vault_path: Path to the vault root
        """
        self.vault_path = vault_path
        self.plugins_dir = vault_path / "plugins"
        self._logger = logger.bind(component="PluginInstaller")
        
        # Ensure plugins directory exists
        self.plugins_dir.mkdir(exist_ok=True)
    
    async def install(
        self,
        repo_url: str,
        plugin_id: Optional[str] = None
    ) -> InstallResult:
        """
        Install a plugin from a git repository.
        
        Args:
            repo_url: Git repository URL
            plugin_id: Optional plugin ID (extracted from URL if not provided)
            
        Returns:
            InstallResult with status and details
        """
        # Extract plugin ID from URL if not provided
        if not plugin_id:
            plugin_id = self._extract_plugin_id(repo_url)
        
        plugin_dir = self.plugins_dir / plugin_id
        
        # Check if already installed
        if plugin_dir.exists():
            return InstallResult(
                status=InstallStatus.ALREADY_EXISTS,
                plugin_id=plugin_id,
                message=f"Plugin '{plugin_id}' is already installed",
                plugin_dir=plugin_dir
            )
        
        self._logger.info(f"Installing plugin '{plugin_id}' from {repo_url}")
        
        try:
            # Clone the repository
            result = subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, str(plugin_dir)],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                self._logger.error(f"Git clone failed: {result.stderr}")
                return InstallResult(
                    status=InstallStatus.CLONE_FAILED,
                    plugin_id=plugin_id,
                    message=f"Failed to clone repository: {result.stderr}"
                )
            
            # Validate the installed plugin
            validation = await self.validate(plugin_dir)
            
            if not validation.valid:
                # Remove the cloned directory
                shutil.rmtree(plugin_dir, ignore_errors=True)
                return InstallResult(
                    status=InstallStatus.VALIDATION_FAILED,
                    plugin_id=plugin_id,
                    message=f"Plugin validation failed: {', '.join(validation.errors)}"
                )
            
            # Install Python dependencies if requirements.txt exists
            requirements_file = plugin_dir / "requirements.txt"
            if requirements_file.exists():
                dep_result = await self._install_dependencies(requirements_file)
                if not dep_result:
                    self._logger.warning(
                        f"Some dependencies may have failed to install for {plugin_id}"
                    )
            
            # Create settings.json with enabled=true by default
            settings_file = plugin_dir / "settings.json"
            if not settings_file.exists():
                settings_file.write_text(json.dumps({"enabled": True}, indent=2))
            else:
                # Update existing settings to enable
                settings = json.loads(settings_file.read_text())
                settings["enabled"] = True
                settings_file.write_text(json.dumps(settings, indent=2))
            
            self._logger.info(f"Plugin '{plugin_id}' installed successfully")
            
            return InstallResult(
                status=InstallStatus.SUCCESS,
                plugin_id=plugin_id,
                message=f"Plugin '{plugin_id}' installed successfully",
                plugin_dir=plugin_dir,
                manifest=validation.manifest
            )
            
        except subprocess.TimeoutExpired:
            return InstallResult(
                status=InstallStatus.CLONE_FAILED,
                plugin_id=plugin_id,
                message="Git clone timed out after 60 seconds"
            )
        except Exception as e:
            self._logger.exception(f"Installation failed: {e}")
            # Cleanup on failure
            if plugin_dir.exists():
                shutil.rmtree(plugin_dir, ignore_errors=True)
            return InstallResult(
                status=InstallStatus.CLONE_FAILED,
                plugin_id=plugin_id,
                message=str(e)
            )
    
    async def update(self, plugin_id: str) -> InstallResult:
        """
        Update an installed plugin by pulling latest changes.
        
        Args:
            plugin_id: ID of the plugin to update
            
        Returns:
            InstallResult with status and details
        """
        plugin_dir = self.plugins_dir / plugin_id
        
        if not plugin_dir.exists():
            return InstallResult(
                status=InstallStatus.VALIDATION_FAILED,
                plugin_id=plugin_id,
                message=f"Plugin '{plugin_id}' is not installed"
            )
        
        self._logger.info(f"Updating plugin '{plugin_id}'")
        
        try:
            result = subprocess.run(
                ["git", "pull", "--ff-only"],
                cwd=str(plugin_dir),
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                return InstallResult(
                    status=InstallStatus.CLONE_FAILED,
                    plugin_id=plugin_id,
                    message=f"Git pull failed: {result.stderr}"
                )
            
            # Re-validate after update
            validation = await self.validate(plugin_dir)
            
            # Re-install dependencies
            requirements_file = plugin_dir / "requirements.txt"
            if requirements_file.exists():
                await self._install_dependencies(requirements_file)
            
            return InstallResult(
                status=InstallStatus.SUCCESS,
                plugin_id=plugin_id,
                message=f"Plugin '{plugin_id}' updated successfully",
                plugin_dir=plugin_dir,
                manifest=validation.manifest
            )
            
        except Exception as e:
            self._logger.exception(f"Update failed: {e}")
            return InstallResult(
                status=InstallStatus.CLONE_FAILED,
                plugin_id=plugin_id,
                message=str(e)
            )
    
    async def uninstall(self, plugin_id: str) -> bool:
        """
        Remove an installed plugin.
        
        Args:
            plugin_id: ID of the plugin to remove
            
        Returns:
            True if successfully removed, False otherwise
        """
        plugin_dir = self.plugins_dir / plugin_id
        
        if not plugin_dir.exists():
            self._logger.warning(f"Plugin '{plugin_id}' not found")
            return False
        
        self._logger.info(f"Uninstalling plugin '{plugin_id}'")
        
        try:
            shutil.rmtree(plugin_dir)
            self._logger.info(f"Plugin '{plugin_id}' uninstalled")
            return True
        except Exception as e:
            self._logger.exception(f"Uninstall failed: {e}")
            return False
    
    async def validate(self, plugin_dir: Path) -> ValidationResult:
        """
        Validate plugin structure and manifest.
        
        Args:
            plugin_dir: Path to the plugin directory
            
        Returns:
            ValidationResult with status and details
        """
        errors: List[str] = []
        warnings: List[str] = []
        manifest: Optional[Dict[str, Any]] = None
        
        # Check required files
        for required_file in self.REQUIRED_FILES:
            if not (plugin_dir / required_file).exists():
                errors.append(f"Missing required file: {required_file}")
        
        # Load and validate manifest
        manifest_file = plugin_dir / "plugin.json"
        if manifest_file.exists():
            try:
                manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                
                # Check required fields
                for field in self.MANIFEST_REQUIRED_FIELDS:
                    if field not in manifest:
                        errors.append(f"Missing required manifest field: {field}")
                
                # Validate version format
                version = manifest.get("version", "")
                if version and not self._is_valid_semver(version):
                    warnings.append(f"Version '{version}' is not valid semver")
                    
            except json.JSONDecodeError as e:
                errors.append(f"Invalid JSON in plugin.json: {e}")
        else:
            # Try loading settings.json as fallback (old format)
            settings_file = plugin_dir / "settings.json"
            if settings_file.exists():
                warnings.append("Using settings.json (plugin.json recommended)")
        
        # Check main.py has Plugin class
        main_file = plugin_dir / "main.py"
        if main_file.exists():
            content = main_file.read_text(encoding="utf-8")
            if "class Plugin" not in content:
                errors.append("main.py must contain a 'Plugin' class")
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            manifest=manifest
        )
    
    def list_installed(self) -> List[Dict[str, Any]]:
        """
        List all installed plugins.
        
        Returns:
            List of plugin info dicts
        """
        plugins = []
        
        for plugin_dir in self.plugins_dir.iterdir():
            if not plugin_dir.is_dir():
                continue
            if plugin_dir.name.startswith(".") or plugin_dir.name.startswith("_"):
                continue
            
            # Try to load manifest
            manifest_file = plugin_dir / "plugin.json"
            settings_file = plugin_dir / "settings.json"
            
            info = {
                "id": plugin_dir.name,
                "path": str(plugin_dir),
                "enabled": False
            }
            
            if manifest_file.exists():
                try:
                    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                    info.update({
                        "name": manifest.get("displayName", manifest.get("name", plugin_dir.name)),
                        "version": manifest.get("version", "unknown"),
                        "description": manifest.get("description", ""),
                        "author": manifest.get("author", {}).get("name", "Unknown")
                    })
                except Exception:
                    pass
            
            if settings_file.exists():
                try:
                    settings = json.loads(settings_file.read_text(encoding="utf-8"))
                    info["enabled"] = settings.get("enabled", False)
                except Exception:
                    pass
            
            plugins.append(info)
        
        return plugins
    
    async def _install_dependencies(self, requirements_file: Path) -> bool:
        """Install Python dependencies from requirements.txt."""
        try:
            lib_dir = self.vault_path / "lib"
            lib_dir.mkdir(exist_ok=True)
            
            result = subprocess.run(
                [
                    "pip", "install",
                    "-r", str(requirements_file),
                    "--target", str(lib_dir),
                    "--quiet"
                ],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            return result.returncode == 0
            
        except Exception as e:
            self._logger.exception(f"Dependency installation failed: {e}")
            return False
    
    def _extract_plugin_id(self, repo_url: str) -> str:
        """Extract plugin ID from repository URL."""
        # Handle various URL formats
        url = repo_url.rstrip("/")
        
        if url.endswith(".git"):
            url = url[:-4]
        
        # Get the last part of the URL
        parts = url.split("/")
        return parts[-1] if parts else "unknown-plugin"
    
    def _is_valid_semver(self, version: str) -> bool:
        """Check if version string is valid semver."""
        import re
        pattern = r"^\d+\.\d+\.\d+(-[\w.]+)?(\+[\w.]+)?$"
        return bool(re.match(pattern, version))
