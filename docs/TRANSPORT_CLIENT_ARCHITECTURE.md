# TCK Transport Client Architecture - Using SDK ClientFactory

## Overview

The TCK uses the **a2a-python SDK's `ClientFactory`** to create transport clients. This ensures protocol correctness by using the official SDK implementation directly.

## Architecture

```
TCK Test
    ↓
TransportManager.get_transport_client(TransportProtocol)
    ↓
ClientFactory.create(AgentCard, ClientConfig)
    ↓
BaseClient with Transport (GrpcTransport / JsonRpcTransport / RestTransport)
    ↓
Network (gRPC/JSON-RPC/REST)
```

## ClientFactory Usage in TransportManager

The `TransportManager` uses `ClientFactory` to create clients with transport-specific configurations:

```python
# In TransportManager._create_transport_client()

# 1. Create AgentCard for specific transport
card = AgentCard(
    name=self._agent_card.name,
    # ... other fields ...
    url=endpoint,  # Transport-specific endpoint
    preferred_transport=transport_type,  # e.g., TransportProtocol.grpc
    additional_interfaces=[]  # Isolate to single transport
)

# 2. Create ClientConfig with transport-specific settings
config_kwargs = {
    'supported_transports': [transport_type],
    'use_client_preference': False
}

# For HTTP transports (JSON-RPC, REST)
if transport_type in [TransportProtocol.jsonrpc, TransportProtocol.http_json]:
    if not self._httpx_client:
        self._httpx_client = httpx.AsyncClient(timeout=30.0)
    config_kwargs['httpx_client'] = self._httpx_client

# For gRPC transport
elif transport_type == TransportProtocol.grpc:
    if not self._grpc_channel_factory:
        import grpc.aio
        self._grpc_channel_factory = lambda url: grpc.aio.insecure_channel(url)
    config_kwargs['grpc_channel_factory'] = self._grpc_channel_factory

# 3. Use ClientFactory to create client
client_config = ClientConfig(**config_kwargs)
factory = ClientFactory(client_config)
client = factory.create(card)  # Returns SDK BaseClient
```

## Transport-Specific Configurations

Each transport protocol requires specific configuration:

### JSON-RPC Transport
```python
ClientConfig(
    supported_transports=[TransportProtocol.jsonrpc],
    httpx_client=httpx.AsyncClient(timeout=30.0),
    use_client_preference=False
)
# ClientFactory creates: BaseClient with JsonRpcTransport
```

### gRPC Transport
```python
ClientConfig(
    supported_transports=[TransportProtocol.grpc],
    grpc_channel_factory=lambda url: grpc.aio.insecure_channel(url),
    use_client_preference=False
)
# ClientFactory creates: BaseClient with GrpcTransport
```

### REST (HTTP+JSON) Transport
```python
ClientConfig(
    supported_transports=[TransportProtocol.http_json],
    httpx_client=httpx.AsyncClient(timeout=30.0),
    use_client_preference=False
)
# ClientFactory creates: BaseClient with RestTransport
```

## SDK Client Interface

All clients created by `ClientFactory` are instances of `a2a.client.base_client.BaseClient` which implements the `Client` interface:

```python
from a2a.client import Client

client: Client = manager.get_transport_client(TransportProtocol.jsonrpc)

# Common methods available on all transports
async for event in client.send_message(message):
    # Handle ClientEvent or Message
    pass

task = await client.get_task(TaskQueryParams(id="task-123"))
cancelled_task = await client.cancel_task(TaskIdParams(id="task-123"))
await client.close()
```

### Transport Capabilities

| Transport | SDK Transport Class | list_tasks Support | Protocol |
|-----------|---------------------|-------------------|----------|
| **gRPC** | `GrpcTransport` | ✅ YES | Protocol Buffers over gRPC |
| **JSON-RPC** | `JsonRpcTransport` | ❌ NO | JSON-RPC 2.0 over HTTP |
| **REST** | `RestTransport` | ✅ YES | REST with JSON payloads |

### Resource Management

TransportManager handles resource lifecycle:

- **HTTP Client Reuse**: Single `httpx.AsyncClient` shared between JSON-RPC and REST clients
- **gRPC Channel Factory**: Created on-demand for gRPC clients
- **Client Caching**: Clients cached by transport type to avoid recreation
- **Cleanup**: `close_async()` closes all clients and shared resources

## Benefits of Using ClientFactory

### 1. **Official SDK Implementation**
- Uses the same client creation pattern as production applications
- Guaranteed protocol compliance through SDK
- Automatic SDK updates and bug fixes

### 2. **Proper Transport Configuration**
- Each transport gets correct configuration (httpx client, gRPC channel)
- Resource sharing where appropriate (httpx client reused)
- Follows SDK best practices from official examples

### 3. **No Custom Client Code**
- Zero TCK-specific transport implementation
- Eliminates maintenance burden of custom clients
- Tests verify actual SDK behavior users will experience

### 4. **Flexibility**
- Easy to add new transports when SDK supports them
- Can customize ClientConfig per transport as needed
- Supports all SDK features (streaming, middleware, interceptors)

## Usage in Tests

### Via TransportManager (Recommended)

```python
from tck.transport.transport_manager import TransportManager
from a2a.types import TransportProtocol, Message, TaskQueryParams

# Initialize manager
manager = TransportManager("http://sut-url")
manager.discover_transports()

# Get specific transport client (SDK BaseClient)
client = manager.get_transport_client(TransportProtocol.jsonrpc)

# Send message (returns async iterator)
async for event in client.send_message(message):
    if isinstance(event, Task):
        print(f"Task created: {event.id}")

# Get task status
task = await client.get_task(TaskQueryParams(id="task-123"))

# Get all transports for equivalence testing
all_clients = manager.get_all_transport_clients()
for transport, client in all_clients.items():
    async for event in client.send_message(message):
        print(f"{transport}: {event}")

# Cleanup
await manager.close_async()
```

### Direct ClientFactory Usage (Advanced)

```python
from a2a.client import ClientFactory, ClientConfig
from a2a.types import AgentCard, TransportProtocol
import httpx

# Create config for JSON-RPC
config = ClientConfig(
    supported_transports=[TransportProtocol.jsonrpc],
    httpx_client=httpx.AsyncClient(timeout=30.0)
)

# Create client
factory = ClientFactory(config)
client = factory.create(agent_card)

# Use client
async for event in client.send_message(message):
    # Handle event
    pass

await client.close()
```

## Client Caching

TransportManager caches clients by transport type:

```python
# First call creates client
client1 = manager.get_transport_client(TransportProtocol.jsonrpc)

# Second call returns cached instance
client2 = manager.get_transport_client(TransportProtocol.jsonrpc)

assert client1 is client2  # Same instance
```

## Cleanup

```python
# Close all clients via manager
await manager.close_async()

# Or close individual client
await client.close()
```

## SDK Dependencies

```toml
# pyproject.toml
dependencies = [
    "a2a-sdk>=0.3.10",
    "grpcio>=1.76.0",          # For gRPC support
    "grpcio-tools>=1.76.0",
    "httpx>=0.28.1",           # For HTTP transports
    "httpx-sse>=0.4.3",        # For REST streaming
]
```

## Summary

The TCK uses **SDK's ClientFactory directly** to create transport clients:
- ✅ Uses official SDK client creation (same as production apps)
- ✅ Zero custom transport implementation code
- ✅ Proper resource management (shared httpx client, gRPC channels)
- ✅ Supports all three A2A transports (gRPC, JSON-RPC, REST)
- ✅ Easy to extend when SDK adds new transports

**Key Principle**: TransportManager orchestrates client lifecycle; ClientFactory creates SDK clients; SDK implements A2A protocol.

## References

- **SDK ClientFactory**: https://github.com/a2aproject/a2a-python/blob/main/src/a2a/client/client_factory.py
- **SDK Transports**: https://github.com/a2aproject/a2a-python/tree/main/src/a2a/client/transports
- **SDK Client Interface**: https://github.com/a2aproject/a2a-python/blob/main/src/a2a/client/client.py
