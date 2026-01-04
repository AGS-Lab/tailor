"""
Unit tests for logging_config module.

Tests logger configuration, plugin loggers, and file handlers.
"""

import pytest
import logging
from pathlib import Path
import tempfile
import shutil
from sidecar import utils


@pytest.mark.unit
class TestConfigureLogging:
    """Test logging configuration."""
    
    def test_configure_logging_basic(self, tmp_path):
        """Test basic logging configuration."""
        log_file = tmp_path / "logs" / "tailor.log"
        
        utils.configure_logging(log_file=log_file)
        
        # Check log directory was created
        assert log_file.parent.exists()
        assert log_file.parent.is_dir()
    
    def test_configure_logging_with_level(self, tmp_path):
        """Test configuration with specific log level."""
        log_file = tmp_path / "logs" / "tailor.log"
        
        utils.configure_logging(log_file=log_file, level="DEBUG")
        
        logger = utils.get_logger("test")
        assert logger.level <= logging.DEBUG
    
    def test_creates_log_file(self, tmp_path):
        """Test that log file is created."""
        log_file = tmp_path / "logs" / "tailor.log"
        
        utils.configure_logging(log_file=log_file)
        
        # Get a logger and log something
        logger = utils.get_logger("test")
        logger.info("Test message")
        
        # Check log file exists
        assert log_file.exists()
    
    def test_verbose_mode(self, tmp_path):
        """Test verbose mode enables more detailed logging."""
        log_file = tmp_path / "logs" / "tailor.log"
        
        utils.configure_logging(log_file=log_file, verbose=True)
        
        logger = utils.get_logger("test")
        # In verbose mode, logger should accept DEBUG messages
        assert logger.isEnabledFor(logging.DEBUG)


@pytest.mark.unit
class TestGetLogger:
    """Test get_logger function."""
    
    def test_get_logger_basic(self, tmp_path):
        """Test getting a basic logger."""
        log_file = tmp_path / "logs" / "tailor.log"
        utils.configure_logging(log_file=log_file)
        
        logger = utils.get_logger("my_module")
        
        assert logger is not None
        assert isinstance(logger, logging.Logger)
    
    def test_get_logger_same_name_returns_same_instance(self, tmp_path):
        """Test that same name returns same logger instance."""
        log_file = tmp_path / "logs" / "tailor.log"
        utils.configure_logging(log_file=log_file)
        
        logger1 = utils.get_logger("module1")
        logger2 = utils.get_logger("module1")
        
        assert logger1 is logger2
    
    def test_get_logger_different_names(self, tmp_path):
        """Test that different names return different loggers."""
        log_file = tmp_path / "logs" / "tailor.log"
        utils.configure_logging(log_file=log_file)
        
        logger1 = utils.get_logger("module1")
        logger2 = utils.get_logger("module2")
        
        assert logger1 is not logger2
    
    def test_logger_can_log_messages(self, tmp_path):
        """Test that logger can actually log messages."""
        log_file = tmp_path / "logs" / "tailor.log"
        utils.configure_logging(log_file=log_file)
        
        logger = utils.get_logger("test_module")
        
        # Should not raise
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")


@pytest.mark.unit
class TestGetPluginLogger:
    """Test get_plugin_logger function."""
    
    def test_get_plugin_logger_basic(self, tmp_path):
        """Test getting a plugin-specific logger."""
        log_file = tmp_path / "logs" / "tailor.log"
        utils.configure_logging(log_file=log_file)
        
        logger = utils.get_plugin_logger("my_plugin")
        
        assert logger is not None
        assert isinstance(logger, logging.Logger)
    
    def test_plugin_logger_has_plugin_prefix(self, tmp_path):
        """Test that plugin loggers have appropriate naming."""
        log_file = tmp_path / "logs" / "tailor.log"
        utils.configure_logging(log_file=log_file)
        
        logger = utils.get_plugin_logger("test_plugin")
        
        # Logger name should include plugin identifier
        assert "plugin" in logger.name.lower() or "test_plugin" in logger.name
    
    def test_different_plugins_get_different_loggers(self, tmp_path):
        """Test that different plugins get separate loggers."""
        log_file = tmp_path / "logs" / "tailor.log"
        utils.configure_logging(log_file=log_file)
        
        logger1 = utils.get_plugin_logger("plugin1")
        logger2 = utils.get_plugin_logger("plugin2")
        
        assert logger1 is not logger2 # Corrected from assert logger1 is not logger2

    
    def test_same_plugin_gets_same_logger(self, tmp_path):
        """Test that same plugin name returns same logger."""
        log_file = tmp_path / "logs" / "tailor.log"
        utils.configure_logging(log_file=log_file)
        
        logger1 = utils.get_plugin_logger("my_plugin")
        logger2 = utils.get_plugin_logger("my_plugin")
        
        assert logger1 is logger2


@pytest.mark.unit
class TestLoggingIntegration:
    """Integration tests for logging system."""
    
    def test_multiple_loggers_write_to_same_file(self, tmp_path):
        """Test that multiple loggers can write to same log file."""
        log_file = tmp_path / "logs" / "tailor.log"
        utils.configure_logging(log_file=log_file)
        
        logger1 = utils.get_logger("module1")
        logger2 = utils.get_logger("module2")
        plugin_logger = utils.get_plugin_logger("test_plugin")
        
        # All should be able to log
        logger1.info("Message from module1")
        logger2.info("Message from module2")
        plugin_logger.info("Message from plugin")
        
        # Check that log file was created and has content
        assert log_file.exists()
        
        log_content = log_file.read_text()
        assert "module1" in log_content or "Message from module1" in log_content
    
    def test_log_levels_are_respected(self, tmp_path):
        """Test that log level filtering works."""
        log_file = tmp_path / "logs" / "tailor.log"
        
        # Configure with INFO level
        utils.configure_logging(log_file=log_file, level="INFO")
        
        logger = utils.get_logger("test")
        
        # INFO and above should be enabled
        assert logger.isEnabledFor(logging.INFO)
        assert logger.isEnabledFor(logging.WARNING)
        assert logger.isEnabledFor(logging.ERROR)
