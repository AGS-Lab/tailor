"""
Plugin Installer - Handles plugin installation, updates, and removal.

Provides functionality for:
- Installing plugins from HTTP URLs (zip archives)
- Installing plugins from git repositories
- Updating installed plugins
- Removing plugins
- Validating plugin structure and manifests
"""

import json
import shutil
import asyncio
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional, List
from enum import Enum

import httpx
from loguru import logger


class InstallStatus(Enum):
    """Plugin installation status."""

    SUCCESS = "success"
    ALREADY_EXISTS = "already_exists"
    CLONE_FAILED = "clone_failed"
    DOWNLOAD_FAILED = "download_failed"
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

    Plugins can be installed via:
    - HTTP download (zip file from GitHub releases/archives)
    - Git clone (for development)
    """

    REQUIRED_FILES = ["main.py"]  # plugin.json is optional
    MANIFEST_REQUIRED_FIELDS = ["name", "version"]

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
        self, repo_url: str, plugin_id: Optional[str] = None
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
                plugin_dir=plugin_dir,
            )

        self._logger.info(f"Installing plugin '{plugin_id}' from {repo_url}")

        try:
            # Clone the repository using async subprocess
            process = await asyncio.create_subprocess_exec(
                "git",
                "clone",
                "--depth",
                "1",
                repo_url,
                str(plugin_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                self._logger.error(f"Git clone failed: {error_msg}")
                return InstallResult(
                    status=InstallStatus.CLONE_FAILED,
                    plugin_id=plugin_id,
                    message=f"Failed to clone repository: {error_msg}",
                )

            # Validate the installed plugin
            validation = await self.validate(plugin_dir)

            if not validation.valid:
                # Remove the cloned directory
                shutil.rmtree(plugin_dir, ignore_errors=True)
                return InstallResult(
                    status=InstallStatus.VALIDATION_FAILED,
                    plugin_id=plugin_id,
                    message=f"Plugin validation failed: {', '.join(validation.errors)}",
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
                manifest=validation.manifest,
            )

        except asyncio.TimeoutError:
            return InstallResult(
                status=InstallStatus.CLONE_FAILED,
                plugin_id=plugin_id,
                message="Git clone timed out after 60 seconds",
            )
        except Exception as e:
            self._logger.exception(f"Installation failed: {e}")
            # Cleanup on failure
            if plugin_dir.exists():
                shutil.rmtree(plugin_dir, ignore_errors=True)
            return InstallResult(
                status=InstallStatus.CLONE_FAILED, plugin_id=plugin_id, message=str(e)
            )

    async def install_from_url(
        self, download_url: str, plugin_id: str
    ) -> InstallResult:
        """
        Install a plugin from an HTTP URL (zip file).

        Args:
            download_url: URL to download the plugin zip file
            plugin_id: Plugin identifier

        Returns:
            InstallResult with status and details
        """
        plugin_dir = self.plugins_dir / plugin_id

        # Check if already installed
        if plugin_dir.exists():
            return InstallResult(
                status=InstallStatus.ALREADY_EXISTS,
                plugin_id=plugin_id,
                message=f"Plugin '{plugin_id}' is already installed",
                plugin_dir=plugin_dir,
            )

        self._logger.info(f"Installing plugin '{plugin_id}' from {download_url}")

        try:
            # Create temporary directory for download and extraction
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                zip_path = temp_path / f"{plugin_id}.zip"

                # Download the file using httpx
                self._logger.debug(f"Downloading {download_url}")
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.get(download_url, follow_redirects=True)
                        response.raise_for_status()

                        # Write file in chunks or all at once (for small files all at once is fine)
                        # but let's use a thread for file I/O if possible, or just write it.
                        # Since we are in async, avoiding blocking write is good, but for
                        # this size, simple write is okay, or use aiofiles if available.
                        # Standard write is blocking. Let's wrap in to_thread.
                        await asyncio.to_thread(zip_path.write_bytes, response.content)

                except httpx.HTTPError as e:
                    return InstallResult(
                        status=InstallStatus.DOWNLOAD_FAILED,
                        plugin_id=plugin_id,
                        message=f"Failed to download plugin: {e}",
                    )
                except Exception as e:
                    return InstallResult(
                        status=InstallStatus.DOWNLOAD_FAILED,
                        plugin_id=plugin_id,
                        message=f"Download error: {e}",
                    )

                # Extract zip file in thread
                self._logger.debug(f"Extracting {zip_path}")
                extract_dir = temp_path / "extracted"
                extract_dir.mkdir()

                try:
                    await asyncio.to_thread(self._extract_zip, zip_path, extract_dir)
                except zipfile.BadZipFile:
                    return InstallResult(
                        status=InstallStatus.DOWNLOAD_FAILED,
                        plugin_id=plugin_id,
                        message="Downloaded file is not a valid zip archive",
                    )

                # GitHub archives have a top-level folder like "repo-main/"
                # Find the actual plugin directory
                extracted_items = list(extract_dir.iterdir())
                if len(extracted_items) == 1 and extracted_items[0].is_dir():
                    source_dir = extracted_items[0]
                else:
                    source_dir = extract_dir

                # Move to plugins directory (blocking IO, wrap in thread)
                await asyncio.to_thread(shutil.copytree, source_dir, plugin_dir)

            # Validate the installed plugin
            validation = await self.validate(plugin_dir)

            if not validation.valid:
                # Remove the directory
                shutil.rmtree(plugin_dir, ignore_errors=True)
                return InstallResult(
                    status=InstallStatus.VALIDATION_FAILED,
                    plugin_id=plugin_id,
                    message=f"Plugin validation failed: {', '.join(validation.errors)}",
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

            self._logger.info(f"Plugin '{plugin_id}' installed successfully from URL")

            return InstallResult(
                status=InstallStatus.SUCCESS,
                plugin_id=plugin_id,
                message=f"Plugin '{plugin_id}' installed successfully",
                plugin_dir=plugin_dir,
                manifest=validation.manifest,
            )

        except Exception as e:
            self._logger.exception(f"Installation from URL failed: {e}")
            # Cleanup on failure
            if plugin_dir.exists():
                shutil.rmtree(plugin_dir, ignore_errors=True)
            return InstallResult(
                status=InstallStatus.DOWNLOAD_FAILED,
                plugin_id=plugin_id,
                message=str(e),
            )

    def _extract_zip(self, zip_path: Path, extract_dir: Path) -> None:
        """Helper to extract zip file (blocking)."""
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_dir)

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
                message=f"Plugin '{plugin_id}' is not installed",
            )

        self._logger.info(f"Updating plugin '{plugin_id}'")

        try:
            # Git pull using async subprocess
            process = await asyncio.create_subprocess_exec(
                "git",
                "pull",
                "--ff-only",
                cwd=str(plugin_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                return InstallResult(
                    status=InstallStatus.CLONE_FAILED,
                    plugin_id=plugin_id,
                    message=f"Git pull failed: {error_msg}",
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
                manifest=validation.manifest,
            )

        except Exception as e:
            self._logger.exception(f"Update failed: {e}")
            return InstallResult(
                status=InstallStatus.CLONE_FAILED, plugin_id=plugin_id, message=str(e)
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
            # Use to_thread for blocking file IO
            await asyncio.to_thread(shutil.rmtree, plugin_dir)
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

        # File IO in async method - for small JSONs it's usually acceptable,
        # but for consistency let's use to_thread or just leave it simpler as it's fast.
        # Given it's local disk, blocking is minimal, but technically incorrect for strict async.
        # We will keep it simple here as it's just a file read.

        if manifest_file.exists():
            try:
                content = manifest_file.read_text(encoding="utf-8")
                manifest = json.loads(content)

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
            try:
                content = main_file.read_text(encoding="utf-8")
                if "class Plugin" not in content:
                    errors.append("main.py must contain a 'Plugin' class")
            except Exception:
                pass  # If we can't read it, it might be an issue, but we already checked existence

        return ValidationResult(
            valid=len(errors) == 0, errors=errors, warnings=warnings, manifest=manifest
        )

    def list_installed(self) -> List[Dict[str, Any]]:
        """
        List all installed plugins.

        Returns:
            List of plugin info dicts
        """
        plugins = []

        self._logger.debug(f"Listing plugins from: {self.plugins_dir}")

        if not self.plugins_dir.exists():
            self._logger.warning(
                f"Plugins directory does not exist: {self.plugins_dir}"
            )
            return plugins

        for plugin_dir in self.plugins_dir.iterdir():
            if not plugin_dir.is_dir():
                continue
            if plugin_dir.name.startswith(".") or plugin_dir.name.startswith("_"):
                continue

            self._logger.debug(f"Found plugin directory: {plugin_dir.name}")

            # Try to load manifest
            manifest_file = plugin_dir / "plugin.json"
            settings_file = plugin_dir / "settings.json"

            # Default info (always include name, version, description)
            info = {
                "id": plugin_dir.name,
                "name": plugin_dir.name.replace("-", " ").replace("_", " ").title(),
                "version": "1.0.0",
                "description": "",
                "path": str(plugin_dir),
                "enabled": False,
            }

            if manifest_file.exists():
                try:
                    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                    info.update(
                        {
                            "name": manifest.get(
                                "displayName", manifest.get("name", info["name"])
                            ),
                            "version": manifest.get("version", info["version"]),
                            "description": manifest.get("description", ""),
                            "author": manifest.get("author", {}).get("name", "Unknown"),
                        }
                    )
                except Exception as e:
                    self._logger.debug(
                        f"Failed to load manifest for {plugin_dir.name}: {e}"
                    )

            if settings_file.exists():
                try:
                    settings = json.loads(settings_file.read_text(encoding="utf-8"))
                    info["enabled"] = settings.get("enabled", False)
                except Exception as e:
                    self._logger.debug(
                        f"Failed to load settings for {plugin_dir.name}: {e}"
                    )

            plugins.append(info)

        self._logger.info(f"Found {len(plugins)} installed plugins")
        return plugins

    async def _install_dependencies(self, requirements_file: Path) -> bool:
        """Install Python dependencies from requirements.txt."""
        try:
            lib_dir = self.vault_path / "lib"
            lib_dir.mkdir(exist_ok=True)

            # Use async subprocess for pip install
            process = await asyncio.create_subprocess_exec(
                "pip",
                "install",
                "-r",
                str(requirements_file),
                "--target",
                str(lib_dir),
                "--quiet",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)

            return process.returncode == 0

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
