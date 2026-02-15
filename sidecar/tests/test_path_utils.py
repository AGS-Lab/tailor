"""
Unit tests for path_utils module.

Tests safe path operations, vault validation, and plugin discovery.
"""

import pytest
from pathlib import Path
import tempfile
import shutil
from sidecar import utils
from sidecar import exceptions


@pytest.mark.unit
class TestValidateVaultPath:
    """Test vault path validation."""
    
    def test_valid_vault_path(self, tmp_path):
        """Test validating an existing vault directory."""
        vault_path = tmp_path / "test_vault"
        vault_path.mkdir()
        (vault_path / ".vault.toml").write_text("")
        
        # Should not raise
        utils.validate_vault_path(vault_path)
    
    def test_nonexistent_vault(self):
        """Test validation fails for nonexistent path."""
        fake_path = Path("/nonexistent/vault")
        
        with pytest.raises(exceptions.VaultNotFoundError):
            utils.validate_vault_path(fake_path)
    
    def test_vault_is_file_not_directory(self, tmp_path):
        """Test validation fails if vault path is a file."""
        vault_file = tmp_path / "vault.txt"
        vault_file.write_text("not a directory")
        
        with pytest.raises(exceptions.InvalidPathError, match="not a directory"):
            utils.validate_vault_path(vault_file)
    
    def test_missing_vault_config(self, tmp_path):
        """Test validation warns/passes without .vault.toml."""
        vault_path = tmp_path / "vault_no_config"
        vault_path.mkdir()
        
        # Should still pass but might log warning
        utils.validate_vault_path(vault_path)




@pytest.mark.unit
class TestValidatePluginStructure:
    """Test plugin structure validation."""
    
    def test_valid_plugin_structure(self, tmp_path):
        """Test validating a plugin with proper structure."""
        plugin_dir = tmp_path / "my_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "main.py").write_text("class Plugin: pass")
        
        # Should not raise
        utils.validate_plugin_structure(plugin_dir)
    
    def test_missing_main_py(self, tmp_path):
        """Test validation fails without main.py."""
        plugin_dir = tmp_path / "incomplete_plugin"
        plugin_dir.mkdir()
        
        with pytest.raises(exceptions.PluginLoadError, match="missing main.py"):
            utils.validate_plugin_structure(plugin_dir)
    
    def test_plugin_with_optional_files(self, tmp_path):
        """Test plugin with optional settings.json and README."""
        plugin_dir = tmp_path / "full_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "main.py").write_text("class Plugin: pass")
        (plugin_dir / "settings.json").write_text("{}")
        (plugin_dir / "README.md").write_text("# Plugin")
        
        # Should still validate successfully
        utils.validate_plugin_structure(plugin_dir)
