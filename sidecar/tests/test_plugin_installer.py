"""
Tests for PluginInstaller.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from sidecar.plugin_installer import PluginInstaller, InstallStatus


@pytest.fixture
def vault_path(tmp_path):
    v = tmp_path / "vault"
    v.mkdir()
    (v / "plugins").mkdir()
    return v


@pytest.fixture
def installer(vault_path):
    return PluginInstaller(vault_path)


@pytest.mark.asyncio
async def test_extract_plugin_id(installer):
    assert (
        installer._extract_plugin_id("https://github.com/user/plugin-name")
        == "plugin-name"
    )
    assert (
        installer._extract_plugin_id("https://github.com/user/plugin-name.git")
        == "plugin-name"
    )
    assert (
        installer._extract_plugin_id("https://example.com/download/my_plugin.zip")
        == "my_plugin.zip"
    )


@pytest.mark.asyncio
async def test_validate_valid_plugin(installer, vault_path):
    """Test validation of a valid plugin structure."""
    p_dir = vault_path / "plugins" / "valid_plugin"
    p_dir.mkdir()
    (p_dir / "main.py").write_text("class Plugin:\n    pass")
    (p_dir / "plugin.json").write_text('{"name": "Valid", "version": "1.0.0"}')

    result = await installer.validate(p_dir)
    assert result.valid is True
    assert len(result.errors) == 0


@pytest.mark.asyncio
async def test_validate_invalid_plugin(installer, vault_path):
    """Test validation of an invalid plugin."""
    p_dir = vault_path / "plugins" / "invalid_plugin"
    p_dir.mkdir()
    # Missing main.py
    (p_dir / "plugin.json").write_text('{"name": "Invalid"}')

    result = await installer.validate(p_dir)
    assert result.valid is False
    assert "Missing required file: main.py" in result.errors


@pytest.mark.asyncio
async def test_install_already_exists(installer, vault_path):
    """Test installing a plugin that already exists."""
    p_id = "existing_plugin"
    (vault_path / "plugins" / p_id).mkdir()

    result = await installer.install("http://repo", plugin_id=p_id)
    assert result.status == InstallStatus.ALREADY_EXISTS


@pytest.mark.asyncio
async def test_install_git_clone_success(installer, vault_path):
    """Test successful installation via git clone."""

    # Mock subprocess
    process_mock = MagicMock()
    process_mock.communicate = AsyncMock(return_value=(b"", b""))
    process_mock.returncode = 0

    # Simulate git clone side effect
    def clone_side_effect(*args, **kwargs):
        (vault_path / "plugins" / "test_plugin").mkdir()
        return process_mock

    with patch(
        "asyncio.create_subprocess_exec", side_effect=clone_side_effect
    ) as mock_exec:
        # We need to mock validate to return True, otherwise it will fail because no files are actually cloned
        with patch.object(installer, "validate") as mock_validate:
            mock_validate.return_value = MagicMock(valid=True, manifest={})

            result = await installer.install("http://repo.git", plugin_id="test_plugin")
            if result.status != InstallStatus.SUCCESS:
                print(f"DEBUG: Install failed with message: {result.message}")

            assert result.status == InstallStatus.SUCCESS
            assert (vault_path / "plugins" / "test_plugin" / "settings.json").exists()


@pytest.mark.asyncio
async def test_install_git_clone_failure(installer):
    """Test failed installation via git clone."""

    process_mock = MagicMock()
    process_mock.communicate = AsyncMock(return_value=(b"", b"git error"))
    process_mock.returncode = 1

    with patch("asyncio.create_subprocess_exec", return_value=process_mock):
        result = await installer.install("http://repo.git", plugin_id="fail_plugin")

        assert result.status == InstallStatus.CLONE_FAILED
        assert "git error" in result.message


@pytest.mark.asyncio
async def test_uninstall(installer, vault_path):
    """Test uninstallation."""
    p_id = "test_plugin"
    p_dir = vault_path / "plugins" / p_id
    p_dir.mkdir()
    (p_dir / "file.txt").touch()

    assert await installer.uninstall(p_id) is True
    assert not p_dir.exists()

    # Uninstall non-existent
    assert await installer.uninstall("non_existent") is False
