"""
Unit tests for TransportManager's use of SDK ClientFactory.

These tests verify that TransportManager correctly uses the a2a-python SDK's
ClientFactory to create transport clients (gRPC, JSON-RPC, REST) rather than
custom client implementations.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
import httpx

from a2a.types import (
    AgentCard,
    AgentCapabilities,
    AgentInterface,
    TransportProtocol,
)
from a2a.client import Client, ClientConfig, ClientFactory

from tck.transport.transport_manager import TransportManager, TransportManagerError


# Fixtures


@pytest.fixture
def mock_agent_card() -> AgentCard:
    """Provides a sample AgentCard with multiple transports."""
    return AgentCard(
        name="Test Agent",
        description="Test agent for TCK",
        version="1.0.0",
        url="http://testserver:8000",
        capabilities=AgentCapabilities(streaming=True, push_notifications=False),
        skills=[],
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        preferred_transport=TransportProtocol.jsonrpc,
        supports_authenticated_extended_card=False,
        additional_interfaces=[
            AgentInterface(
                transport=TransportProtocol.http_json,
                url="http://testserver:8000/rest"
            ),
            AgentInterface(
                transport=TransportProtocol.grpc,
                url="localhost:50051"
            ),
        ],
    )


@pytest.fixture
def grpc_only_agent_card() -> AgentCard:
    """Provides an AgentCard that only supports gRPC."""
    return AgentCard(
        name="gRPC Agent",
        description="gRPC-only test agent",
        version="1.0.0",
        url="localhost:50051",
        capabilities=AgentCapabilities(streaming=True, push_notifications=False),
        skills=[],
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        preferred_transport=TransportProtocol.grpc,
        supports_authenticated_extended_card=False,
        additional_interfaces=[],
    )


# Tests for ClientFactory integration


class TestTransportManagerClientFactory:
    """Tests verifying TransportManager uses SDK ClientFactory correctly."""

    @patch("tck.transport.transport_manager.fetch_agent_card")
    @patch("tck.transport.transport_manager.ClientFactory")
    @pytest.mark.asyncio
    async def test_creates_jsonrpc_client_via_factory(
        self, mock_client_factory_class, mock_fetch_card, mock_agent_card
    ):
        """Verify TransportManager creates JSON-RPC client using ClientFactory."""
        # Setup mocks
        mock_fetch_card.return_value = mock_agent_card
        
        mock_factory_instance = MagicMock()
        mock_client = AsyncMock(spec=Client)
        mock_factory_instance.create.return_value = mock_client
        mock_client_factory_class.return_value = mock_factory_instance

        # Create manager and get JSON-RPC client
        manager = TransportManager("http://testserver:8000")
        manager.discover_transports()
        
        client = manager.get_transport_client(TransportProtocol.jsonrpc)

        # Verify ClientFactory was instantiated with correct config
        assert mock_client_factory_class.called
        config_arg = mock_client_factory_class.call_args[0][0]
        assert isinstance(config_arg, ClientConfig)
        assert TransportProtocol.jsonrpc in config_arg.supported_transports
        assert config_arg.httpx_client is not None
        assert isinstance(config_arg.httpx_client, httpx.AsyncClient)

        # Verify factory.create was called with correct AgentCard
        assert mock_factory_instance.create.called
        card_arg = mock_factory_instance.create.call_args[0][0]
        assert isinstance(card_arg, AgentCard)
        assert card_arg.preferred_transport == TransportProtocol.jsonrpc
        assert card_arg.url == "http://testserver:8000"

        # Verify we got back the mock client
        assert client == mock_client

    @patch("tck.transport.transport_manager.fetch_agent_card")
    @patch("tck.transport.transport_manager.ClientFactory")
    @pytest.mark.asyncio
    async def test_creates_rest_client_via_factory(
        self, mock_client_factory_class, mock_fetch_card, mock_agent_card
    ):
        """Verify TransportManager creates REST client using ClientFactory."""
        mock_fetch_card.return_value = mock_agent_card
        
        mock_factory_instance = MagicMock()
        mock_client = AsyncMock(spec=Client)
        mock_factory_instance.create.return_value = mock_client
        mock_client_factory_class.return_value = mock_factory_instance

        manager = TransportManager("http://testserver:8000")
        manager.discover_transports()
        
        client = manager.get_transport_client(TransportProtocol.http_json)

        # Verify ClientFactory config for REST
        config_arg = mock_client_factory_class.call_args[0][0]
        assert TransportProtocol.http_json in config_arg.supported_transports
        assert config_arg.httpx_client is not None

        # Verify AgentCard for REST
        card_arg = mock_factory_instance.create.call_args[0][0]
        assert card_arg.preferred_transport == TransportProtocol.http_json
        assert card_arg.url == "http://testserver:8000/rest"

    @patch("tck.transport.transport_manager.fetch_agent_card")
    @patch("tck.transport.transport_manager.ClientFactory")
    @patch("tck.transport.transport_manager.grpc.aio.insecure_channel")
    @pytest.mark.asyncio
    async def test_creates_grpc_client_via_factory(
        self, mock_grpc_channel, mock_client_factory_class, mock_fetch_card, grpc_only_agent_card
    ):
        """Verify TransportManager creates gRPC client using ClientFactory."""
        mock_fetch_card.return_value = grpc_only_agent_card
        
        mock_factory_instance = MagicMock()
        mock_client = AsyncMock(spec=Client)
        mock_factory_instance.create.return_value = mock_client
        mock_client_factory_class.return_value = mock_factory_instance

        # Mock gRPC channel
        mock_channel = MagicMock()
        mock_grpc_channel.return_value = mock_channel

        manager = TransportManager("http://testserver:8000")
        manager.discover_transports()
        
        client = manager.get_transport_client(TransportProtocol.grpc)

        # Verify ClientFactory config for gRPC
        config_arg = mock_client_factory_class.call_args[0][0]
        assert TransportProtocol.grpc in config_arg.supported_transports
        assert config_arg.grpc_channel_factory is not None

        # Verify AgentCard for gRPC
        card_arg = mock_factory_instance.create.call_args[0][0]
        assert card_arg.preferred_transport == TransportProtocol.grpc
        assert card_arg.url == "localhost:50051"

    @patch("tck.transport.transport_manager.fetch_agent_card")
    @patch("tck.transport.transport_manager.ClientFactory")
    @pytest.mark.asyncio
    async def test_reuses_httpx_client_across_transports(
        self, mock_client_factory_class, mock_fetch_card, mock_agent_card
    ):
        """Verify TransportManager reuses same httpx client for JSON-RPC and REST."""
        mock_fetch_card.return_value = mock_agent_card
        
        mock_factory_instance = MagicMock()
        mock_jsonrpc_client = AsyncMock(spec=Client)
        mock_rest_client = AsyncMock(spec=Client)
        mock_factory_instance.create.side_effect = [mock_jsonrpc_client, mock_rest_client]
        mock_client_factory_class.return_value = mock_factory_instance

        manager = TransportManager("http://testserver:8000")
        manager.discover_transports()
        
        # Get JSON-RPC client
        jsonrpc_client = manager.get_transport_client(TransportProtocol.jsonrpc)
        jsonrpc_config = mock_client_factory_class.call_args[0][0]
        jsonrpc_httpx_client = jsonrpc_config.httpx_client

        # Reset mock to track second call
        mock_client_factory_class.reset_mock()
        
        # Get REST client
        rest_client = manager.get_transport_client(TransportProtocol.http_json)
        rest_config = mock_client_factory_class.call_args[0][0]
        rest_httpx_client = rest_config.httpx_client

        # Verify same httpx client instance is reused
        assert jsonrpc_httpx_client is rest_httpx_client

    @patch("tck.transport.transport_manager.fetch_agent_card")
    @patch("tck.transport.transport_manager.ClientFactory")
    @pytest.mark.asyncio
    async def test_caches_clients_by_transport_type(
        self, mock_client_factory_class, mock_fetch_card, mock_agent_card
    ):
        """Verify TransportManager caches clients and doesn't recreate them."""
        mock_fetch_card.return_value = mock_agent_card
        
        mock_factory_instance = MagicMock()
        mock_client = AsyncMock(spec=Client)
        mock_factory_instance.create.return_value = mock_client
        mock_client_factory_class.return_value = mock_factory_instance

        manager = TransportManager("http://testserver:8000")
        manager.discover_transports()
        
        # Get same transport twice
        client1 = manager.get_transport_client(TransportProtocol.jsonrpc)
        client2 = manager.get_transport_client(TransportProtocol.jsonrpc)

        # Verify same instance returned (cached)
        assert client1 is client2

        # Verify ClientFactory.create only called once
        assert mock_factory_instance.create.call_count == 1

    @patch("tck.transport.transport_manager.fetch_agent_card")
    @patch("tck.transport.transport_manager.ClientFactory")
    @pytest.mark.asyncio
    async def test_get_all_transport_clients_creates_all(
        self, mock_client_factory_class, mock_fetch_card, mock_agent_card
    ):
        """Verify get_all_transport_clients creates clients for all supported transports."""
        mock_fetch_card.return_value = mock_agent_card
        
        mock_factory_instance = MagicMock()
        # Create different mock clients for each transport
        mock_clients = {
            TransportProtocol.jsonrpc: AsyncMock(spec=Client),
            TransportProtocol.http_json: AsyncMock(spec=Client),
            TransportProtocol.grpc: AsyncMock(spec=Client),
        }
        mock_factory_instance.create.side_effect = lambda card: mock_clients[card.preferred_transport]
        mock_client_factory_class.return_value = mock_factory_instance

        manager = TransportManager("http://testserver:8000")
        manager.discover_transports()
        
        clients = manager.get_all_transport_clients()

        # Verify we got clients for all 3 transports
        assert len(clients) == 3
        assert TransportProtocol.jsonrpc in clients
        assert TransportProtocol.http_json in clients
        assert TransportProtocol.grpc in clients

        # Verify ClientFactory.create called 3 times
        assert mock_factory_instance.create.call_count == 3

    @patch("tck.transport.transport_manager.fetch_agent_card")
    @pytest.mark.asyncio
    async def test_raises_error_when_grpc_dependencies_missing(
        self, mock_fetch_card, grpc_only_agent_card
    ):
        """Verify proper error when gRPC dependencies not installed."""
        mock_fetch_card.return_value = grpc_only_agent_card

        manager = TransportManager("http://testserver:8000")
        manager.discover_transports()

        # Mock ImportError for grpc
        with patch("tck.transport.transport_manager.grpc", side_effect=ImportError("No module named 'grpc'")):
            with pytest.raises(TransportManagerError, match="gRPC dependencies not installed"):
                manager.get_transport_client(TransportProtocol.grpc)


class TestTransportManagerClientLifecycle:
    """Tests for client lifecycle management."""

    @patch("tck.transport.transport_manager.fetch_agent_card")
    @patch("tck.transport.transport_manager.ClientFactory")
    @pytest.mark.asyncio
    async def test_close_async_closes_all_clients(
        self, mock_client_factory_class, mock_fetch_card, mock_agent_card
    ):
        """Verify close_async() closes all cached clients."""
        mock_fetch_card.return_value = mock_agent_card
        
        mock_factory_instance = MagicMock()
        mock_client1 = AsyncMock(spec=Client)
        mock_client2 = AsyncMock(spec=Client)
        mock_factory_instance.create.side_effect = [mock_client1, mock_client2]
        mock_client_factory_class.return_value = mock_factory_instance

        manager = TransportManager("http://testserver:8000")
        manager.discover_transports()
        
        # Create two clients
        manager.get_transport_client(TransportProtocol.jsonrpc)
        manager.get_transport_client(TransportProtocol.http_json)

        # Close manager
        await manager.close_async()

        # Verify both clients were closed
        mock_client1.close.assert_awaited_once()
        mock_client2.close.assert_awaited_once()

    @patch("tck.transport.transport_manager.fetch_agent_card")
    @patch("tck.transport.transport_manager.ClientFactory")
    @pytest.mark.asyncio
    async def test_close_async_closes_httpx_client(
        self, mock_client_factory_class, mock_fetch_card, mock_agent_card
    ):
        """Verify close_async() closes the httpx client."""
        mock_fetch_card.return_value = mock_agent_card
        
        mock_factory_instance = MagicMock()
        mock_client = AsyncMock(spec=Client)
        mock_factory_instance.create.return_value = mock_client
        mock_client_factory_class.return_value = mock_factory_instance

        manager = TransportManager("http://testserver:8000")
        manager.discover_transports()
        
        # Create a client (which creates httpx client internally)
        manager.get_transport_client(TransportProtocol.jsonrpc)

        # Get reference to httpx client before closing
        httpx_client = manager._httpx_client
        assert httpx_client is not None

        # Close manager
        await manager.close_async()

        # Verify httpx client was closed
        httpx_client.aclose.assert_awaited_once()

    @patch("tck.transport.transport_manager.fetch_agent_card")
    @patch("tck.transport.transport_manager.ClientFactory")
    def test_clear_client_cache_removes_all_clients(
        self, mock_client_factory_class, mock_fetch_card, mock_agent_card
    ):
        """Verify clear_client_cache() removes all cached clients."""
        mock_fetch_card.return_value = mock_agent_card
        
        mock_factory_instance = MagicMock()
        mock_client = AsyncMock(spec=Client)
        mock_factory_instance.create.return_value = mock_client
        mock_client_factory_class.return_value = mock_factory_instance

        manager = TransportManager("http://testserver:8000")
        manager.discover_transports()
        
        # Create client
        manager.get_transport_client(TransportProtocol.jsonrpc)
        assert len(manager._client_cache) == 1

        # Clear cache
        manager.clear_client_cache()
        assert len(manager._client_cache) == 0


class TestTransportManagerConfiguration:
    """Tests for transport configuration with ClientFactory."""

    @patch("tck.transport.transport_manager.fetch_agent_card")
    @patch("tck.transport.transport_manager.ClientFactory")
    @pytest.mark.asyncio
    async def test_client_config_uses_server_preference(
        self, mock_client_factory_class, mock_fetch_card, mock_agent_card
    ):
        """Verify ClientConfig is created with use_client_preference=False."""
        mock_fetch_card.return_value = mock_agent_card
        
        mock_factory_instance = MagicMock()
        mock_client = AsyncMock(spec=Client)
        mock_factory_instance.create.return_value = mock_client
        mock_client_factory_class.return_value = mock_factory_instance

        manager = TransportManager("http://testserver:8000")
        manager.discover_transports()
        
        manager.get_transport_client(TransportProtocol.jsonrpc)

        # Verify ClientConfig uses server preference
        config_arg = mock_client_factory_class.call_args[0][0]
        assert config_arg.use_client_preference is False

    @patch("tck.transport.transport_manager.fetch_agent_card")
    @patch("tck.transport.transport_manager.ClientFactory")
    @pytest.mark.asyncio
    async def test_agent_card_isolates_transport(
        self, mock_client_factory_class, mock_fetch_card, mock_agent_card
    ):
        """Verify AgentCard passed to factory only includes requested transport."""
        mock_fetch_card.return_value = mock_agent_card
        
        mock_factory_instance = MagicMock()
        mock_client = AsyncMock(spec=Client)
        mock_factory_instance.create.return_value = mock_client
        mock_client_factory_class.return_value = mock_factory_instance

        manager = TransportManager("http://testserver:8000")
        manager.discover_transports()
        
        manager.get_transport_client(TransportProtocol.jsonrpc)

        # Verify AgentCard only has the requested transport (no additional_interfaces)
        card_arg = mock_factory_instance.create.call_args[0][0]
        assert card_arg.preferred_transport == TransportProtocol.jsonrpc
        assert card_arg.additional_interfaces == []
