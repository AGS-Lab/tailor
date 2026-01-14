"""
Decorators for Sidecar Command and Event System.

These decorators are used to tag methods in VaultBrain (and potentially plugins)
for automatic registration.
"""

from typing import Optional, Callable, Any
from functools import wraps

def command(name: str, plugin_name: Optional[str] = None) -> Callable:
    """
    Decorator to register a method as a named command.
    
    Args:
        name: The command ID (e.g., 'system.chat')
        plugin_name: Optional plugin name owner (defaults to Core if None)
    """
    def decorator(func: Callable) -> Callable:
        # Attach metadata to the function
        # We use a list because a single function might handle multiple aliases
        if not hasattr(func, "_command_meta"):
            func._command_meta = []
        
        func._command_meta.append({
            "id": name,
            "plugin": plugin_name
        })
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def on_event(event_type: str) -> Callable:
    """
    Decorator to subscribe a method to an internal event.
    
    Args:
        event_type: The event string constant
    """
    def decorator(func: Callable) -> Callable:
        if not hasattr(func, "_event_meta"):
            func._event_meta = []
            
        func._event_meta.append({
            "event": event_type
        })
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator
