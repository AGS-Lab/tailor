from typing import Dict, Any, List, Optional, Callable, Awaitable
from collections import defaultdict
import asyncio
from loguru import logger

from .types import PipelineContext
from .events import PipelineEvents

EventHandler = Callable[[PipelineContext], Awaitable[None]]

class PipelineManager:
    """
    Central Orchestrator for Pipeline Events and Commands.
    """
    
    def __init__(self):
        self._subscribers: Dict[str, List[EventHandler]] = defaultdict(list)
        self._logger = logger.bind(component="PipelineManager")

    def subscribe(self, event: str, handler: EventHandler) -> None:
        """Register an async event handler."""
        self._subscribers[event].append(handler)
        self._logger.debug(f"Registered handler for {event}")

    async def emit(self, event: str, ctx: PipelineContext) -> None:
        """
        Emit an event to all subscribers sequentially or in parallel.
        For pipeline, sequential execution often makes sense to ensure order of transforms.
        """
        if ctx.should_abort:
            return

        ctx.events_emitted.append(event)

        handlers = self._subscribers.get(event, [])
        if not handlers:
            return
        
        # We execute sequentially to allow modifications to flow down the chain
        for handler in handlers:
            try:
                await handler(ctx)
                if ctx.should_abort:
                    self._logger.info(f"Pipeline aborted during {event}: {ctx.abort_reason}")
                    return
            except Exception as e:
                self._logger.error(f"Error in handler for {event}: {e}")
                # We don't abort on handler error, just log? Or should we?
                # For now, continue but log.
