"""
Hook Registry - Manages plugin hooks for LLM processing pipeline.

This module provides a registry for plugins to register hooks that
intercept and modify LLM processing at defined extension points.
"""

from typing import Callable, Dict, List, Any, Optional, Awaitable
from dataclasses import dataclass, field
from enum import Enum
import asyncio

from loguru import logger


class HookPhase(Enum):
    """Available hook phases in the LLM processing pipeline."""
    
    # Input phase - before LLM processing
    INPUT_TRANSFORM = "input.transform"
    INPUT_VALIDATE = "input.validate"
    
    # Process phase - around LLM call
    PROCESS_BEFORE_LLM = "process.before_llm"
    PROCESS_AFTER_LLM = "process.after_llm"
    
    # Output phase - before sending to UI
    OUTPUT_FORMAT = "output.format"


@dataclass
class HookContext:
    """
    Context passed through all hooks in the pipeline.
    
    Hooks can read and modify this context. The `should_abort` flag
    can be set by validation hooks to stop processing.
    """
    
    # Primary data
    message: str
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    
    # Response (populated after LLM call)
    response: str = ""
    
    # Metadata for inter-hook communication
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Abort control (only for validation hooks)
    should_abort: bool = False
    abort_reason: str = ""
    
    # Tracking
    hooks_executed: List[str] = field(default_factory=list)


# Type alias for hook handlers
HookHandler = Callable[[HookContext], Awaitable[HookContext]]


@dataclass
class RegisteredHook:
    """A registered hook with metadata."""
    
    handler: HookHandler
    plugin_name: str
    priority: int
    phase: HookPhase


class HookRegistry:
    """
    Registry for managing plugin hooks.
    
    Plugins register hooks for specific phases, and the pipeline
    executes them in priority order (lower = earlier).
    """
    
    def __init__(self):
        """Initialize the hook registry."""
        self._hooks: Dict[HookPhase, List[RegisteredHook]] = {
            phase: [] for phase in HookPhase
        }
        self._logger = logger.bind(component="HookRegistry")
    
    def register(
        self,
        phase: HookPhase,
        handler: HookHandler,
        plugin_name: str,
        priority: int = 100
    ) -> None:
        """
        Register a hook handler for a phase.
        
        Args:
            phase: The hook phase to register for
            handler: Async function that receives and returns HookContext
            plugin_name: Name of the plugin registering this hook
            priority: Execution priority (lower = runs first)
        """
        hook = RegisteredHook(
            handler=handler,
            plugin_name=plugin_name,
            priority=priority,
            phase=phase
        )
        
        self._hooks[phase].append(hook)
        
        # Sort by priority
        self._hooks[phase].sort(key=lambda h: h.priority)
        
        self._logger.info(
            f"Registered hook: {plugin_name} -> {phase.value} (priority={priority})"
        )
    
    def unregister(self, phase: HookPhase, plugin_name: str) -> int:
        """
        Unregister all hooks for a plugin in a phase.
        
        Args:
            phase: The hook phase
            plugin_name: Name of the plugin
            
        Returns:
            Number of hooks removed
        """
        before_count = len(self._hooks[phase])
        self._hooks[phase] = [
            h for h in self._hooks[phase]
            if h.plugin_name != plugin_name
        ]
        removed = before_count - len(self._hooks[phase])
        
        if removed > 0:
            self._logger.info(
                f"Unregistered {removed} hook(s) for {plugin_name} from {phase.value}"
            )
        
        return removed
    
    def unregister_all(self, plugin_name: str) -> int:
        """
        Unregister all hooks for a plugin.
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            Total number of hooks removed
        """
        total_removed = 0
        for phase in HookPhase:
            total_removed += self.unregister(phase, plugin_name)
        return total_removed
    
    async def run_phase(
        self,
        phase: HookPhase,
        ctx: HookContext,
        timeout: float = 5.0
    ) -> HookContext:
        """
        Execute all hooks for a phase.
        
        Args:
            phase: The hook phase to run
            ctx: The context to pass through hooks
            timeout: Timeout per hook in seconds
            
        Returns:
            Modified context after all hooks have run
        """
        hooks = self._hooks[phase]
        
        if not hooks:
            return ctx
        
        self._logger.debug(f"Running {len(hooks)} hook(s) for {phase.value}")
        
        for hook in hooks:
            if ctx.should_abort:
                self._logger.info(
                    f"Aborting pipeline: {ctx.abort_reason}"
                )
                break
            
            try:
                ctx = await asyncio.wait_for(
                    hook.handler(ctx),
                    timeout=timeout
                )
                ctx.hooks_executed.append(f"{hook.plugin_name}:{phase.value}")
                
            except asyncio.TimeoutError:
                self._logger.warning(
                    f"Hook timeout: {hook.plugin_name}:{phase.value}"
                )
                # Continue with next hook
                
            except Exception as e:
                self._logger.error(
                    f"Hook error: {hook.plugin_name}:{phase.value} - {e}",
                    exc_info=True
                )
                # Continue with next hook (don't crash pipeline)
        
        return ctx
    
    def get_hooks(self, phase: Optional[HookPhase] = None) -> Dict[str, List[str]]:
        """
        Get registered hooks, optionally filtered by phase.
        
        Args:
            phase: Optional phase to filter by
            
        Returns:
            Dict mapping phase names to list of plugin names
        """
        if phase:
            return {
                phase.value: [h.plugin_name for h in self._hooks[phase]]
            }
        
        return {
            p.value: [h.plugin_name for h in hooks]
            for p, hooks in self._hooks.items()
        }
    
    def has_hooks(self, phase: HookPhase) -> bool:
        """Check if any hooks are registered for a phase."""
        return len(self._hooks[phase]) > 0
    
    def clear(self) -> None:
        """Clear all registered hooks."""
        for phase in HookPhase:
            self._hooks[phase] = []
        self._logger.info("Cleared all hooks")
