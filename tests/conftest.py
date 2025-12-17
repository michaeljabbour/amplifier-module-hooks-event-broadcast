"""Test fixtures for hooks-event-broadcast module."""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator with hooks and capabilities."""
    coordinator = MagicMock()
    
    # Mock hooks registry
    hooks = MagicMock()
    registered_handlers = {}
    
    def mock_register(event, handler, priority=0, name=None):
        if event not in registered_handlers:
            registered_handlers[event] = []
        registered_handlers[event].append({
            "handler": handler,
            "priority": priority,
            "name": name
        })
        return lambda: registered_handlers[event].pop() if registered_handlers[event] else None
    
    hooks.register = mock_register
    coordinator.hooks = hooks
    coordinator._registered_handlers = registered_handlers
    
    # Mock capabilities
    capabilities = {}
    coordinator.register_capability = lambda name, value: capabilities.update({name: value})
    coordinator.get_capability = lambda name: capabilities.get(name)
    coordinator._capabilities = capabilities
    
    return coordinator


@pytest.fixture
def mock_broadcast():
    """Create a mock broadcast function."""
    return AsyncMock()
