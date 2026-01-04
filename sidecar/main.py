"""
Tailor Python Sidecar Entry Point

This module initializes a vault-specific Python sidecar process with:
- Bi-directional WebSocket communication
- Event emission capabilities for plugins
- LangGraph orchestration
- Vault-specific plugin loading
"""

import argparse
import asyncio
import sys
from pathlib import Path

from .websocket_server import WebSocketServer
from .vault_brain import VaultBrain
from . import utils
from . import exceptions

logger = utils.get_logger(__name__)


async def run_servers(ws_server: WebSocketServer, brain: VaultBrain) -> None:
    """
    Run WebSocket server and tick loop concurrently.
    
    Args:
        ws_server: WebSocket server instance
        brain: VaultBrain instance
    """
    # Initialize plugins
    await brain.initialize()
    
    await asyncio.gather(
        ws_server.start(),
        brain.tick_loop(),
    )


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.
    
    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Tailor Python Sidecar - Vault orchestrator with plugin support",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    
    # Required arguments
    parser.add_argument(
        "--vault",
        required=True,
        help="Path to vault directory"
    )
    parser.add_argument(
        "--ws-port",
        type=int,
        required=True,
        help="WebSocket port for communication with Tauri"
    )
    
    # Optional arguments
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level (default: from environment or INFO)"
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        help="Log file path (if not specified, logs only to console)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging (DEBUG level with detailed format)"
    )
    parser.add_argument(
        "--version",
        action="version",
        version="Tailor Sidecar v0.1.0"
    )
    
    return parser.parse_args()


def main() -> None:
    """Main entry point for the sidecar process."""
    
    # Parse arguments
    args = parse_arguments()
    vault_path = Path(args.vault)
    
    # Configure logging first
    utils.configure_logging(
        level=args.log_level,
        log_file=args.log_file,
        verbose=args.verbose,
    )
    
    logger.info("=" * 60)
    logger.info("Tailor Python Sidecar starting...")
    logger.info("=" * 60)
    logger.info(f"Vault path: {vault_path}")
    logger.info(f"WebSocket port: {args.ws_port}")
    
    # Validate vault exists
    if not vault_path.exists():
        logger.error(f"Vault path does not exist: {vault_path}")
        sys.exit(1)
    
    # Add vault's lib directory to Python path for isolated dependencies
    lib_path = vault_path / "lib"
    if lib_path.exists():
        sys.path.insert(0, str(lib_path))
        logger.info(f"Added to PYTHONPATH: {lib_path}")
    
    try:
        # Initialize WebSocket server
        logger.info("Initializing WebSocket server...")
        ws_server = WebSocketServer(port=args.ws_port)
        
        # Initialize vault brain (creates emitter internally)
        logger.info("Initializing VaultBrain...")
        brain = VaultBrain(vault_path=vault_path, ws_server=ws_server)
        
        logger.info("=" * 60)
        logger.info("Sidecar initialized successfully!")
        logger.info(f"Plugins loaded: {len(brain.plugins)}")
        logger.info(f"Commands registered: {len(brain.commands)}")
        logger.info("=" * 60)
        logger.info("Starting WebSocket server and tick loop...")
        
        # Run both servers
        asyncio.run(run_servers(ws_server, brain))
        
    except exceptions.VaultNotFoundError as e:
        logger.error(f"Vault error: {e.message}")
        logger.error("Please check that the vault path is correct")
        sys.exit(1)
    
    except exceptions.TailorError as e:
        logger.error(f"Tailor error: {e.message}")
        if e.details:
            logger.error(f"Details: {e.details}")
        sys.exit(1)
    
    except KeyboardInterrupt:
        logger.info("")
        logger.info("Received shutdown signal (Ctrl+C)")
        logger.info("Sidecar shutting down gracefully...")
        sys.exit(0)
    
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        logger.critical("Sidecar crashed unexpectedly")
        sys.exit(1)


if __name__ == "__main__":
    main()
