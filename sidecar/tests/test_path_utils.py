"""
Unit tests for path_utils module.

Tests safe path operations, vault validation, and plugin discovery.
"""

import pytest
from pathlib import Path
import tempfile
import shutil
from sidecar.utils.path_utils import (
    validate_vault_path,
    safe_path_join,
    discover_plugins,
    validate_plugin_structure,
)
from sidecar.exceptions import (
    VaultNotFoundError, 
    VaultInvalidError,
    PathTraversalError,
    PluginLoadError,
    InvalidPathError,
)


@pytest.mark.unit
class TestValidateVaultPath:
    """Test vault path validation."""
    
    def test_valid_vault_path(self, tmp_path):
        """Test validating an existing vault directory."""
        vault_path = tmp_path / "test_vault"
        vault_path.mkdir()
        (vault_path / ".vault.json").write_text("{}")
        
        # Should not raise
        validate_vault_path(vault_path)
    
    def test_nonexistent_vault(self):
        """Test validation fails for nonexistent path."""
        fake_path = Path("/nonexistent/vault")
        
        with pytest.raises(VaultNotFoundError):
            validate_vault_path(fake_path)
    
    def test_vault_is_file_not_directory(self, tmp_path):
        """Test validation fails if vault path is a file."""
        vault_file = tmp_path / "vault.txt"
        vault_file.write_text("not a directory")
        
        with pytest.raises(InvalidPathError, match="not a directory"):
            validate_vault_path(vault_file)
    
    def test_missing_vault_config(self, tmp_path):
        """Test validation warns/passes without .vault.json."""
        vault_path = tmp_path / "vault_no_config"
        vault_path.mkdir()
        
        # Should still pass but might log warning
        validate_vault_path(vault_path)


@pytest.mark.unit
class TestSafePathJoin:
    """Test safe path joining with directory traversal prevention."""
    
    def test_safe_join_normal_path(self, tmp_path):
        """Test joining a safe relative path."""
        base = tmp_path
        result = safe_path_join(base, "subdir", "file.txt")
        
        assert result == base / "subdir" / "file.txt"
        assert base in result.parents or result == base
    
    def test_prevent_directory_traversal_dotdot(self, tmp_path):
        """Test prevention of .. directory traversal."""
        base = tmp_path / "vault"
        base.mkdir()
        
        with pytest.raises(PathTraversalError):
            safe_path_join(base, "..", "secret.txt")
    
    def test_prevent_absolute_path_injection(self, tmp_path):
        """Test prevention of absolute path injection."""
        base = tmp_path / "vault"
        base.mkdir()
        
        with pytest.raises(PathTraversalError):
            # On Windows, absolute path might be different, but safe_path_join should catch it
            # if it resolves to outside base.
            # Using a path that is definitely outside base.
            safe_path_join(base, "/etc/passwd")
    
    def test_multiple_components(self, tmp_path):
        """Test joining multiple path components safely."""
        base = tmp_path
        result = safe_path_join(base, "a", "b", "c", "file.txt")
        
        expected = base / "a" / "b" / "c" / "file.txt"
        assert result == expected


@pytest.mark.unit
class TestDiscoverPlugins:
    """Test plugin discovery."""
    
    def test_discover_plugins_empty_directory(self, tmp_path):
        """Test discovering plugins in empty plugins directory."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        
        result = discover_plugins(tmp_path)
        assert result == []
    
    def test_discover_valid_plugin(self, tmp_path):
        """Test discovering a valid plugin."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        
        # Create plugin directory with main.py
        plugin_dir = plugins_dir / "my_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "main.py").write_text("class Plugin: pass")
        
        result = discover_plugins(tmp_path)
        
        assert len(result) == 1
        assert result[0].name == "my_plugin"
    
    def test_discover_multiple_plugins(self, tmp_path):
        """Test discovering multiple plugins."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        
        # Create multiple plugin directories
        for name in ["plugin1", "plugin2", "plugin3"]:
            plugin_dir = plugins_dir / name
            plugin_dir.mkdir()
            (plugin_dir / "main.py").write_text("class Plugin: pass")
        
        result = discover_plugins(tmp_path)
        
        assert len(result) == 3
        plugin_names = {p.name for p in result}
        assert plugin_names == {"plugin1", "plugin2", "plugin3"}
    
    def test_ignore_files_in_plugins_dir(self, tmp_path):
        """Test that files in plugins dir are ignored."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        
        # Create a file (not a directory)
        (plugins_dir / "not_a_plugin.py").write_text("# Not a plugin")
        
        # Create a valid plugin
        plugin_dir = plugins_dir / "real_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "main.py").write_text("class Plugin: pass")
        
        result = discover_plugins(tmp_path)
        
        assert len(result) == 1
        assert result[0].name == "real_plugin"
    
    def test_ignore_plugin_without_main_py(self, tmp_path):
        """Test that directories without main.py are ignored."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        
        # Create directory without main.py
        (plugins_dir / "incomplete_plugin").mkdir()
        
        result = discover_plugins(tmp_path)
        
        assert len(result) == 0
    
    def test_nonexistent_plugins_directory(self):
        """Test handling of nonexistent plugins directory."""
        fake_dir = Path("/nonexistent/plugins")
        
        result = discover_plugins(fake_dir)
        assert result == []


@pytest.mark.unit
class TestValidatePluginStructure:
    """Test plugin structure validation."""
    
    def test_valid_plugin_structure(self, tmp_path):
        """Test validating a plugin with proper structure."""
        plugin_dir = tmp_path / "my_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "main.py").write_text("class Plugin: pass")
        
        # Should not raise
        validate_plugin_structure(plugin_dir)
    
    def test_missing_main_py(self, tmp_path):
        """Test validation fails without main.py."""
        plugin_dir = tmp_path / "incomplete_plugin"
        plugin_dir.mkdir()
        
        with pytest.raises(PluginLoadError, match="missing main.py"):
            validate_plugin_structure(plugin_dir)
    
    def test_plugin_with_optional_files(self, tmp_path):
        """Test plugin with optional settings.json and README."""
        plugin_dir = tmp_path / "full_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "main.py").write_text("class Plugin: pass")
        (plugin_dir / "settings.json").write_text("{}")
        (plugin_dir / "README.md").write_text("# Plugin")
        
        # Should still validate successfully
        validate_plugin_structure(plugin_dir)
