"""
Event Broadcast Hook Module for Amplifier.

Provides transport-agnostic event broadcasting via capability injection.
Applications register their transport (WebSocket, SSE, console, etc.) as
the "broadcast" capability, and this module relays all kernel events to it.

This enables real-time UI updates without coupling the kernel to any
specific transport mechanism.

Pattern:
    # Application registers transport
    async def ws_send(event: str, data: dict):
        await websocket.send_json({"type": event, "data": data})
    
    coordinator.register_capability("broadcast", ws_send)
    
    # This module broadcasts events via that capability
    # Events like content_block:delta, tool:pre, etc. flow to the UI

Supported Events:
    - content_block:start/delta/end - Streaming content
    - tool:pre/post - Tool execution
    - orchestrator:complete - Generation finished
    - session:start/end - Session lifecycle
    - prompt:submit - User prompt received
    - error:* - Error events
"""

import logging
from typing import Any

from amplifier_core import ModuleCoordinator, HookResult

__version__ = "0.1.0"
__all__ = ["mount"]

logger = logging.getLogger(__name__)

# Default events to broadcast
DEFAULT_EVENTS = [
    # Streaming events
    "content_block:start",
    "content_block:delta",
    "content_block:end",
    # Tool events
    "tool:pre",
    "tool:post",
    "tool:error",
    # Orchestration events
    "orchestrator:complete",
    "prompt:submit",
    "provider:request",
    # Session events
    "session:start",
    "session:end",
    # Error events
    "error:tool",
    "error:provider",
    "error:orchestration",
    # User notifications
    "user:notification",
]


class EventBroadcaster:
    """
    Broadcasts kernel events via a registered capability.
    
    The application registers a "broadcast" capability that accepts
    (event: str, data: dict) and handles the actual transport.
    """
    
    def __init__(self, coordinator: ModuleCoordinator, config: dict):
        self.coordinator = coordinator
        self.config = config
        self._unregister_funcs: list[callable] = []
        
        # Get events to broadcast from config, or use defaults
        self.events = config.get("events", DEFAULT_EVENTS)
        
        # Support wildcard patterns like "content_block:*"
        self.event_patterns = [e for e in self.events if "*" in e]
        self.exact_events = [e for e in self.events if "*" not in e]
        
        # Capability name to look up (configurable for flexibility)
        self.capability_name = config.get("capability_name", "broadcast")
        
        logger.debug(f"EventBroadcaster configured for {len(self.events)} event patterns")
    
    def _matches_pattern(self, event: str) -> bool:
        """Check if event matches any configured pattern."""
        # Check exact matches
        if event in self.exact_events:
            return True
        
        # Check wildcard patterns
        for pattern in self.event_patterns:
            prefix = pattern.rstrip("*")
            if event.startswith(prefix):
                return True
        
        return False
    
    async def _broadcast_handler(self, event: str, data: dict[str, Any]) -> HookResult:
        """
        Handler that broadcasts events via the registered capability.
        
        This is registered as a hook handler for each event type.
        """
        # Skip if event doesn't match our patterns
        if not self._matches_pattern(event):
            return HookResult(action="continue")
        
        # Get the broadcast capability
        broadcast = self.coordinator.get_capability(self.capability_name)
        
        if broadcast is None:
            # No broadcast capability registered - silently continue
            # This is normal when no UI is connected
            logger.debug(f"No '{self.capability_name}' capability registered, skipping broadcast for {event}")
            return HookResult(action="continue")
        
        try:
            # Call the broadcast capability
            # It may be sync or async, handle both
            import asyncio
            if asyncio.iscoroutinefunction(broadcast):
                await broadcast(event, data)
            else:
                broadcast(event, data)
            
            logger.debug(f"Broadcast event: {event}")
            
        except Exception as e:
            # Don't fail the event chain if broadcast fails
            logger.warning(f"Failed to broadcast event {event}: {e}")
        
        # Always continue - broadcasting is passive observation
        return HookResult(action="continue")
    
    def register_handlers(self):
        """Register hook handlers for all configured events."""
        hooks = self.coordinator.hooks
        
        # Register for exact events
        for event in self.exact_events:
            unregister = hooks.register(
                event=event,
                handler=self._broadcast_handler,
                priority=1000,  # Low priority - run after other hooks
                name=f"event-broadcast:{event}"
            )
            self._unregister_funcs.append(unregister)
            logger.debug(f"Registered broadcast handler for: {event}")
        
        # For wildcard patterns, register for known events that match
        # We also register a catch-all for the base event
        for pattern in self.event_patterns:
            prefix = pattern.rstrip("*")
            # Register common sub-events
            for suffix in ["start", "delta", "end", "pre", "post", "error", "complete"]:
                event = f"{prefix}{suffix}"
                unregister = hooks.register(
                    event=event,
                    handler=self._broadcast_handler,
                    priority=1000,
                    name=f"event-broadcast:{event}"
                )
                self._unregister_funcs.append(unregister)
            logger.debug(f"Registered broadcast handlers for pattern: {pattern}")
        
        logger.info(f"Event broadcast registered for {len(self._unregister_funcs)} event handlers")
    
    def unregister_handlers(self):
        """Unregister all hook handlers."""
        for unregister in self._unregister_funcs:
            try:
                unregister()
            except Exception as e:
                logger.warning(f"Error unregistering handler: {e}")
        self._unregister_funcs.clear()
        logger.info("Event broadcast handlers unregistered")


async def mount(coordinator: ModuleCoordinator, config: dict | None = None):
    """
    Mount the event broadcast hook module.
    
    Args:
        coordinator: Amplifier coordinator instance
        config: Configuration dictionary with optional keys:
            - events: List of event names/patterns to broadcast (default: all streaming/tool events)
            - capability_name: Name of capability to call (default: "broadcast")
    
    Returns:
        Cleanup function
    
    Example config:
        config:
          events:
            - content_block:*
            - tool:*
            - orchestrator:complete
          capability_name: broadcast
    """
    config = config or {}
    
    broadcaster = EventBroadcaster(coordinator, config)
    broadcaster.register_handlers()
    
    logger.info(f"Event broadcast module mounted (capability: {broadcaster.capability_name})")
    
    async def cleanup():
        broadcaster.unregister_handlers()
        logger.info("Event broadcast module cleanup complete")
    
    return cleanup
