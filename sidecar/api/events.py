"""
Core Events Definition

This module defines standard event names used across the Tailor ecosystem.
Plugins should use these constants instead of raw strings to ensure consistency.

Usage:
    from .events import CoreEvents
    
    emitter.publish(CoreEvents.FILE_SAVED, path="...")
    sub.subscribe(CoreEvents.FILE_SAVED, handler)
"""

from enum import Enum


class CoreEvents(str, Enum):
    """
    Standard event names for core system activities.
    """
    
    # System Lifecycle
    SYSTEM_STARTUP = "system:startup"
    SYSTEM_SHUTDOWN = "system:shutdown"
    PLUGIN_LOADED = "plugin:loaded"
    ALL_PLUGINS_LOADED = "system:ready"
    
    # File Operations
    FILE_SAVED = "file:saved"
    FILE_OPENED = "file:opened"
    FILE_CREATED = "file:created"
    FILE_DELETED = "file:deleted"
    FILE_MODIFIED = "file:modified"
    
    # Editor/UI Interactions
    EDITOR_CHANGED = "editor:changed"
    COMMAND_EXECUTED = "command:executed"
    
    # AI/LLM
    LLM_REQUEST = "llm:request"
    LLM_RESPONSE = "llm:response"
    LLM_ERROR = "llm:error"
    
    def __str__(self) -> str:
        return self.value
