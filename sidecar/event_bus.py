"""
Tailor - Event Bus

Handles internal Pub/Sub with priority support.
"""

import asyncio
import inspect
from typing import Dict, List, Tuple, Any, Callable, Awaitable
from collections import defaultdict
from loguru import logger

# Type aliases
EventHandler = Callable[..., Awaitable[None]]


class EventBus:
    """
    Internal Event Bus with priority support.
    """

    def __init__(self):
        self._subscribers: Dict[str, List[Tuple[int, EventHandler]]] = defaultdict(list)
        self.logger = logger.bind(component="EventBus")

    def subscribe(self, event: str, handler: EventHandler, priority: int = 0) -> None:
        """
        Subscribe to an internal event.

        Args:
            event: Event name
            handler: Async callback
            priority: Execution priority (Higher runs first). Default 0.
        """
        if not inspect.iscoroutinefunction(handler):
            raise ValueError("Handler must be async")

        # Store as tuple (priority, handler)
        # We sort descending so higher priority is first
        self._subscribers[event].append((priority, handler))
        self._subscribers[event].sort(key=lambda x: x[0], reverse=True)

        self.logger.debug(f"Subscribed to: {event} (priority={priority})")

    def unsubscribe(self, event: str, handler: EventHandler) -> bool:
        """
        Unsubscribe from an internal event.
        Returns True if handler was found and removed.
        """
        if event in self._subscribers:
            handlers_list = self._subscribers[event]
            for i, (p, h) in enumerate(handlers_list):
                if h == handler:
                    handlers_list.pop(i)
                    self.logger.debug(f"Unsubscribed from: {event}")
                    return True
        return False

    def clear_subscribers(self, event: str) -> None:
        """Clear all subscribers for an event."""
        if event in self._subscribers:
            self._subscribers[event].clear()
            self.logger.debug(f"Cleared subscribers for: {event}")

    async def publish(
        self, event: str, sequential: bool = False, **kwargs: Any
    ) -> None:
        """
        Publish an internal event.

        Args:
            event: Event name
            sequential: If True, await handlers one by one.
                       If False, run all handlers in parallel.
            **kwargs: Arguments to pass to handlers
        """
        priority_handlers = self._subscribers.get(event, [])
        # print(f"DEBUG: EventBus publishing {event}, found {len(priority_handlers)} subscribers")
        if not priority_handlers:
            return

        # Extract just the handlers in order
        handlers = [h for _, h in priority_handlers]

        async def safe_exec(h: EventHandler) -> None:
            try:
                await h(**kwargs)
            except Exception as e:
                self.logger.exception(f"Event handler failed for '{event}': {e}")

        if sequential:
            for h in handlers:
                await safe_exec(h)
        else:
            await asyncio.gather(*(safe_exec(h) for h in handlers))
