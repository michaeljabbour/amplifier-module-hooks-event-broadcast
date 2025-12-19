# amplifier-module-hooks-event-broadcast

Transport-agnostic event broadcast hook for Amplifier - enables real-time UI updates via capability injection.

## Overview

This module provides a bridge between Amplifier kernel events and external transports (WebSocket, SSE, console, etc.) without coupling the kernel to any specific transport mechanism.

**The Pattern:**
1. Application registers a "broadcast" capability with the coordinator
2. This module listens to kernel events
3. When events fire, it calls the broadcast capability
4. The application's transport handles delivery

## Why Capability Injection?

| Approach | Problem |
|----------|---------|
| Hard-coded WebSocket | Only works for Desktop |
| Hard-coded console | Only works for CLI |
| Hard-coded SSE | Only works for Web |
| **Capability injection** | **Works for ANY transport** |

The same module works for:
- **Desktop** → WebSocket
- **CLI** → Console/stdout
- **Web Service** → Server-Sent Events
- **Mobile** → WebSocket

## Installation

### In a Bundle

```yaml
hooks:
  - module: hooks-event-broadcast
    source: git+https://github.com/michaeljabbour/amplifier-module-hooks-event-broadcast@v0.1.0
    config:
      events:
        - content_block:*
        - tool:*
        - orchestrator:complete
        - session:*
```

### Local Development

```bash
export AMPLIFIER_MODULE_HOOKS_EVENT_BROADCAST=$(pwd)
```

## Usage

### 1. Register Your Transport

```python
from amplifier_core import AmplifierSession

# Create session with the broadcast hook module
session = await AmplifierSession.create(mount_plan)

# Register WebSocket as broadcast capability
async def ws_broadcast(event: str, data: dict):
    await websocket.send_json({"type": event, "data": data})

session.coordinator.register_capability("broadcast", ws_broadcast)

# Now execute - events automatically flow to WebSocket
result = await session.execute("Hello!")
```

### 2. Events Flow Automatically

When `session.execute()` runs, events like:
- `content_block:delta` (streaming text)
- `tool:pre` / `tool:post` (tool execution)
- `orchestrator:complete` (done)

...are automatically broadcast via your registered capability.

## Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `events` | list | All events | Event names/patterns to broadcast |
| `capability_name` | string | `"broadcast"` | Capability to call |

### Event Patterns

Supports wildcards:
- `content_block:*` matches `content_block:start`, `content_block:delta`, `content_block:end`
- `tool:*` matches `tool:pre`, `tool:post`, `tool:error`

### Default Events

When no `events` config is provided, broadcasts:
- `content_block:start/delta/end` - Streaming content
- `tool:pre/post/error` - Tool execution
- `orchestrator:complete` - Generation finished
- `session:start/end` - Session lifecycle
- `prompt:submit` - User prompt received
- `error:*` - Error events

## Example: Desktop Sidecar

```python
from fastapi import WebSocket
from amplifier_core import AmplifierSession
from amplifier_foundation import load_bundle

async def websocket_handler(websocket: WebSocket):
    await websocket.accept()
    
    # Load bundle with hooks-event-broadcast
    bundle = await load_bundle("foundation:bundles/desktop")
    session = await bundle.prepare().create_session()
    
    # Register WebSocket as transport
    async def broadcast(event: str, data: dict):
        await websocket.send_json({"type": event, "data": data})
    
    session.coordinator.register_capability("broadcast", broadcast)
    
    # Handle messages
    async for message in websocket.iter_json():
        if message["type"] == "prompt":
            result = await session.execute(message["content"])
            await websocket.send_json({"type": "done", "content": result})
```

## Example: CLI with Console Output

```python
import json

def console_broadcast(event: str, data: dict):
    if event == "content_block:delta":
        print(data.get("content", ""), end="", flush=True)
    elif event == "tool:pre":
        print(f"\n[Tool: {data.get('tool_name')}]")

session.coordinator.register_capability("broadcast", console_broadcast)
```

## License

MIT


MIT License - See LICENSE file
