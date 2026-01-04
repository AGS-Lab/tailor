"""
Tailor Python Sidecar

A vault-specific Python sidecar process providing:
- WebSocket communication with Tauri frontend
- Plugin system for extensibility
- Event emission for UI updates
- LangGraph orchestration (placeholder)
"""

__version__ = "0.1.0"
__author__ = "Tailor Team"

# Public API exports
# Public API exports
from .websocket_server import WebSocketServer
from .vault_brain import VaultBrain

__all__ = [
    "WebSocketServer",
    "VaultBrain",
]
