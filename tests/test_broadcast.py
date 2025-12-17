"""Tests for the event broadcast hook module."""

import pytest
from unittest.mock import AsyncMock

from amplifier_module_hooks_event_broadcast import mount, EventBroadcaster
from amplifier_core import HookResult


class TestEventBroadcaster:
    """Tests for EventBroadcaster class."""
    
    def test_matches_exact_event(self, mock_coordinator):
        """Test matching exact event names."""
        broadcaster = EventBroadcaster(mock_coordinator, {
            "events": ["tool:pre", "tool:post"]
        })
        
        assert broadcaster._matches_pattern("tool:pre") is True
        assert broadcaster._matches_pattern("tool:post") is True
        assert broadcaster._matches_pattern("content_block:delta") is False
    
    def test_matches_wildcard_pattern(self, mock_coordinator):
        """Test matching wildcard patterns."""
        broadcaster = EventBroadcaster(mock_coordinator, {
            "events": ["content_block:*", "tool:*"]
        })
        
        assert broadcaster._matches_pattern("content_block:start") is True
        assert broadcaster._matches_pattern("content_block:delta") is True
        assert broadcaster._matches_pattern("content_block:end") is True
        assert broadcaster._matches_pattern("tool:pre") is True
        assert broadcaster._matches_pattern("session:start") is False
    
    def test_default_events(self, mock_coordinator):
        """Test that default events are used when none configured."""
        broadcaster = EventBroadcaster(mock_coordinator, {})
        
        # Should include default events
        assert "content_block:delta" in broadcaster.exact_events
        assert "tool:pre" in broadcaster.exact_events
        assert "orchestrator:complete" in broadcaster.exact_events
    
    @pytest.mark.asyncio
    async def test_broadcast_when_capability_exists(self, mock_coordinator, mock_broadcast):
        """Test that events are broadcast when capability is registered."""
        broadcaster = EventBroadcaster(mock_coordinator, {
            "events": ["test:event"]
        })
        
        # Register broadcast capability
        mock_coordinator.register_capability("broadcast", mock_broadcast)
        
        # Call handler
        result = await broadcaster._broadcast_handler("test:event", {"key": "value"})
        
        assert result.action == "continue"
        mock_broadcast.assert_called_once_with("test:event", {"key": "value"})
    
    @pytest.mark.asyncio
    async def test_no_broadcast_when_no_capability(self, mock_coordinator):
        """Test that handler continues silently when no capability registered."""
        broadcaster = EventBroadcaster(mock_coordinator, {
            "events": ["test:event"]
        })
        
        # Don't register any capability
        result = await broadcaster._broadcast_handler("test:event", {"key": "value"})
        
        assert result.action == "continue"
    
    @pytest.mark.asyncio
    async def test_continues_on_broadcast_error(self, mock_coordinator):
        """Test that handler continues even if broadcast fails."""
        broadcaster = EventBroadcaster(mock_coordinator, {
            "events": ["test:event"]
        })
        
        # Register a failing broadcast
        async def failing_broadcast(event, data):
            raise Exception("Broadcast failed!")
        
        mock_coordinator.register_capability("broadcast", failing_broadcast)
        
        # Should not raise, should continue
        result = await broadcaster._broadcast_handler("test:event", {"key": "value"})
        assert result.action == "continue"
    
    def test_register_handlers(self, mock_coordinator):
        """Test that handlers are registered for configured events."""
        broadcaster = EventBroadcaster(mock_coordinator, {
            "events": ["tool:pre", "tool:post"]
        })
        
        broadcaster.register_handlers()
        
        # Check handlers were registered
        assert "tool:pre" in mock_coordinator._registered_handlers
        assert "tool:post" in mock_coordinator._registered_handlers
        assert len(broadcaster._unregister_funcs) == 2
    
    def test_unregister_handlers(self, mock_coordinator):
        """Test that handlers can be unregistered."""
        broadcaster = EventBroadcaster(mock_coordinator, {
            "events": ["tool:pre"]
        })
        
        broadcaster.register_handlers()
        assert len(broadcaster._unregister_funcs) == 1
        
        broadcaster.unregister_handlers()
        assert len(broadcaster._unregister_funcs) == 0


class TestMount:
    """Tests for the mount function."""
    
    @pytest.mark.asyncio
    async def test_mount_returns_cleanup(self, mock_coordinator):
        """Test that mount returns a cleanup function."""
        cleanup = await mount(mock_coordinator, {
            "events": ["test:event"]
        })
        
        assert cleanup is not None
        assert callable(cleanup)
    
    @pytest.mark.asyncio
    async def test_mount_registers_handlers(self, mock_coordinator):
        """Test that mount registers hook handlers."""
        await mount(mock_coordinator, {
            "events": ["tool:pre", "tool:post"]
        })
        
        assert "tool:pre" in mock_coordinator._registered_handlers
        assert "tool:post" in mock_coordinator._registered_handlers
    
    @pytest.mark.asyncio
    async def test_mount_with_custom_capability_name(self, mock_coordinator, mock_broadcast):
        """Test mount with custom capability name."""
        await mount(mock_coordinator, {
            "events": ["test:event"],
            "capability_name": "my_broadcast"
        })
        
        # Register with custom name
        mock_coordinator.register_capability("my_broadcast", mock_broadcast)
        
        # Get the registered handler
        handlers = mock_coordinator._registered_handlers.get("test:event", [])
        assert len(handlers) >= 1
        
        # Call the handler
        handler = handlers[0]["handler"]
        await handler("test:event", {"data": "test"})
        
        mock_broadcast.assert_called_once()


class TestIntegration:
    """Integration-style tests."""
    
    @pytest.mark.asyncio
    async def test_full_event_flow(self, mock_coordinator):
        """Test complete flow from mount to broadcast."""
        # Track broadcast calls
        broadcast_calls = []
        
        async def track_broadcast(event: str, data: dict):
            broadcast_calls.append((event, data))
        
        # Mount module
        cleanup = await mount(mock_coordinator, {
            "events": ["content_block:delta", "tool:pre"]
        })
        
        # Register broadcast capability
        mock_coordinator.register_capability("broadcast", track_broadcast)
        
        # Simulate events by calling handlers directly
        handlers = mock_coordinator._registered_handlers
        
        # Call content_block:delta handler
        delta_handlers = handlers.get("content_block:delta", [])
        if delta_handlers:
            await delta_handlers[0]["handler"]("content_block:delta", {"content": "Hello"})
        
        # Call tool:pre handler
        tool_handlers = handlers.get("tool:pre", [])
        if tool_handlers:
            await tool_handlers[0]["handler"]("tool:pre", {"tool_name": "bash"})
        
        # Verify broadcasts
        assert len(broadcast_calls) == 2
        assert broadcast_calls[0] == ("content_block:delta", {"content": "Hello"})
        assert broadcast_calls[1] == ("tool:pre", {"tool_name": "bash"})
        
        # Cleanup
        await cleanup()
