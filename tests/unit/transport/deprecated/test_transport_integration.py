"""
Integration tests for A2A v0.3.0 transport clients with TransportManager.

These tests verify that all transport clients (JSON-RPC, gRPC, REST) are properly
integrated with the TransportManager and can be used interchangeably for A2A testing.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

from tck.transport.transport_manager import TransportManager, TransportSelectionStrategy
from tck.transport.base_client import TransportProtocol, BaseTransportClient
from tck.transport.a2a_client_wrapper import A2AClientWrapper
from a2a.types import AgentCard


@pytest.fixture
def multi_transport_agent_card():
    """Agent Card supporting all three transport types."""
    return {
        "protocol_version": "0.3.0",
        "name": "A2A Multi-Transport Test Agent",
        "description": "Test agent supporting all A2A v0.3.0 transports",
        "endpoint": "https://example.com/jsonrpc",  # Primary JSON-RPC endpoint
        "preferredTransport": "jsonrpc",
        "capabilities": {"streaming": True, "push_notifications": True},
        "additionalInterfaces": [
            {"transport": "grpc", "endpoint": "grpc://example.com:50051"},
            {"transport": "rest", "endpoint": "https://example.com/api"},
        ],
    }


@pytest.mark.core
class TestTransportIntegration:
    """Test integration of all transport clients with TransportManager."""

    @patch("tck.transport.transport_manager.fetch_agent_card")
    @patch("tck.transport.transport_manager.validate_transport_consistency")
    def test_all_transports_discovery(self, mock_validate, mock_fetch, multi_transport_agent_card):
        """Test that TransportManager discovers all supported transports."""
        mock_fetch.return_value = multi_transport_agent_card
        mock_validate.return_value = []

        manager = TransportManager("https://example.com")

        # Discover transports
        result = manager.discover_transports()
        assert result is True

        # Verify all transports are discovered
        supported = manager.get_supported_transports()
        assert len(supported) == 3
        assert TransportProtocol.jsonrpc in supported
        assert TransportProtocol.GRPC in supported
        assert TransportProtocol.REST in supported

        # Verify transport endpoints
        info = manager.get_transport_info()
        endpoints = info["transport_endpoints"]
        assert endpoints["jsonrpc"] == "https://example.com/jsonrpc"
        assert endpoints["grpc"] == "grpc://example.com:50051"
        assert endpoints["rest"] == "https://example.com/api"

    @patch("tck.transport.transport_manager.fetch_agent_card")
    @patch("tck.transport.transport_manager.validate_transport_consistency")
    def test_client_type_creation(self, mock_validate, mock_fetch, multi_transport_agent_card):
        """Test that correct client types are created for each transport."""
        mock_fetch.return_value = multi_transport_agent_card
        mock_validate.return_value = []

        manager = TransportManager("https://example.com")
        manager.discover_transports()

        # Test JSON-RPC client creation
        jsonrpc_client = manager.get_transport_client(TransportProtocol.jsonrpc)
        assert isinstance(jsonrpc_client, JSONRPCClient)
        assert jsonrpc_client.transport_type == TransportProtocol.jsonrpc
        assert jsonrpc_client.base_url == "https://example.com/jsonrpc"

        # Test gRPC client creation
        grpc_client = manager.get_transport_client(TransportProtocol.GRPC)
        assert isinstance(grpc_client, GRPCClient)
        assert grpc_client.transport_type == TransportProtocol.GRPC
        assert grpc_client.base_url == "grpc://example.com:50051"

        # Test REST client creation
        rest_client = manager.get_transport_client(TransportProtocol.REST)
        assert isinstance(rest_client, RESTClient)
        assert rest_client.transport_type == TransportProtocol.REST
        assert rest_client.base_url == "https://example.com/api/"  # REST client adds trailing slash

    @patch("tck.transport.transport_manager.fetch_agent_card")
    @patch("tck.transport.transport_manager.validate_transport_consistency")
    def test_client_caching(self, mock_validate, mock_fetch, multi_transport_agent_card):
        """Test that clients are properly cached and reused."""
        mock_fetch.return_value = multi_transport_agent_card
        mock_validate.return_value = []

        manager = TransportManager("https://example.com")
        manager.discover_transports()

        # First access creates clients
        client1_jsonrpc = manager.get_transport_client(TransportProtocol.jsonrpc)
        client1_grpc = manager.get_transport_client(TransportProtocol.GRPC)
        client1_rest = manager.get_transport_client(TransportProtocol.REST)

        # Second access returns cached clients
        client2_jsonrpc = manager.get_transport_client(TransportProtocol.jsonrpc)
        client2_grpc = manager.get_transport_client(TransportProtocol.GRPC)
        client2_rest = manager.get_transport_client(TransportProtocol.REST)

        # Verify same instances are returned
        assert client1_jsonrpc is client2_jsonrpc
        assert client1_grpc is client2_grpc
        assert client1_rest is client2_rest

        # Verify cache contains all clients
        assert len(manager._client_cache) == 3
        assert TransportProtocol.jsonrpc in manager._client_cache
        assert TransportProtocol.GRPC in manager._client_cache
        assert TransportProtocol.REST in manager._client_cache

    @patch("tck.transport.transport_manager.fetch_agent_card")
    @patch("tck.transport.transport_manager.validate_transport_consistency")
    def test_get_all_clients(self, mock_validate, mock_fetch, multi_transport_agent_card):
        """Test getting all transport clients at once."""
        mock_fetch.return_value = multi_transport_agent_card
        mock_validate.return_value = []

        manager = TransportManager("https://example.com")
        manager.discover_transports()

        all_clients = manager.get_all_transport_clients()

        # Verify all client types are present
        assert len(all_clients) == 3
        assert isinstance(all_clients[TransportProtocol.jsonrpc], JSONRPCClient)
        assert isinstance(all_clients[TransportProtocol.GRPC], GRPCClient)
        assert isinstance(all_clients[TransportProtocol.REST], RESTClient)

        # Verify all clients implement BaseTransportClient interface
        for transport_type, client in all_clients.items():
            assert isinstance(client, BaseTransportClient)
            assert client.transport_type == transport_type

            # Verify all required methods exist
            required_methods = [
                "send_message",
                "send_streaming_message",
                "get_task",
                "cancel_task",
                "subscribe_to_task",
                "get_agent_card",
                "get_authenticated_extended_card",
                "set_push_notification_config",
                "get_push_notification_config",
                "list_push_notification_configs",
                "delete_push_notification_config",
            ]

            for method_name in required_methods:
                assert hasattr(client, method_name)
                assert callable(getattr(client, method_name))

    @patch("tck.transport.transport_manager.fetch_agent_card")
    @patch("tck.transport.transport_manager.validate_transport_consistency")
    def test_transport_selection_strategies(self, mock_validate, mock_fetch, multi_transport_agent_card):
        """Test different transport selection strategies work with all clients."""
        mock_fetch.return_value = multi_transport_agent_card
        mock_validate.return_value = []

        test_cases = [
            (TransportSelectionStrategy.PREFER_JSONRPC, TransportProtocol.jsonrpc, JSONRPCClient),
            (TransportSelectionStrategy.PREFER_GRPC, TransportProtocol.GRPC, GRPCClient),
            (TransportSelectionStrategy.PREFER_REST, TransportProtocol.REST, RESTClient),
            (TransportSelectionStrategy.AGENT_PREFERRED, TransportProtocol.jsonrpc, JSONRPCClient),  # Agent prefers JSON-RPC
        ]

        for strategy, expected_type, expected_class in test_cases:
            manager = TransportManager("https://example.com", selection_strategy=strategy)
            manager.discover_transports()

            # Get client without specifying transport type (use strategy)
            client = manager.get_transport_client()

            assert isinstance(client, expected_class)
            assert client.transport_type == expected_type

    @patch("tck.transport.transport_manager.fetch_agent_card")
    @patch("tck.transport.transport_manager.validate_transport_consistency")
    def test_transport_specific_features(self, mock_validate, mock_fetch, multi_transport_agent_card):
        """Test transport-specific features are properly exposed."""
        mock_fetch.return_value = multi_transport_agent_card
        mock_validate.return_value = []

        manager = TransportManager("https://example.com")
        manager.discover_transports()

        all_clients = manager.get_all_transport_clients()

        # Test JSON-RPC client specific features
        jsonrpc_client = all_clients[TransportProtocol.jsonrpc]
        assert not hasattr(jsonrpc_client, "send_json_rpc")  # Legacy method was removed
        assert not jsonrpc_client.supports_method("list_tasks")  # Not supported in JSON-RPC

        # Test gRPC client specific features
        grpc_client = all_clients[TransportProtocol.GRPC]
        assert grpc_client.supports_streaming() is True
        assert grpc_client.supports_bidirectional_streaming() is True
        assert hasattr(grpc_client, "channel")  # gRPC channel property

        # Test REST client specific features
        rest_client = all_clients[TransportProtocol.REST]
        assert rest_client.supports_streaming() is True
        assert rest_client.supports_bidirectional_streaming() is False  # HTTP doesn't support bidirectional
        assert rest_client.supports_method("list_tasks") is True  # Supported in REST
        assert hasattr(rest_client, "list_tasks")  # REST-specific method

    @patch("tck.transport.transport_manager.fetch_agent_card")
    @patch("tck.transport.transport_manager.validate_transport_consistency")
    def test_interface_equivalence(self, mock_validate, mock_fetch, multi_transport_agent_card):
        """Test that all transport clients provide equivalent interfaces."""
        mock_fetch.return_value = multi_transport_agent_card
        mock_validate.return_value = []

        manager = TransportManager("https://example.com")
        manager.discover_transports()

        all_clients = manager.get_all_transport_clients()

        # Core A2A methods that must be supported by all transports
        core_methods = [
            "send_message",
            "send_streaming_message",
            "get_task",
            "cancel_task",
            "subscribe_to_task",
            "get_agent_card",
            "get_authenticated_extended_card",
            "set_push_notification_config",
            "get_push_notification_config",
            "list_push_notification_configs",
            "delete_push_notification_config",
            "resubscribe_task",
        ]

        for transport_type, client in all_clients.items():
            for method_name in core_methods:
                # All clients must support core methods
                assert client.supports_method(method_name), f"{transport_type.value} client missing {method_name}"
                assert hasattr(client, method_name), f"{transport_type.value} client missing {method_name} method"

    @patch("tck.transport.transport_manager.fetch_agent_card")
    @patch("tck.transport.transport_manager.validate_transport_consistency")
    def test_client_lifecycle_management(self, mock_validate, mock_fetch, multi_transport_agent_card):
        """Test client lifecycle management through TransportManager."""
        mock_fetch.return_value = multi_transport_agent_card
        mock_validate.return_value = []

        manager = TransportManager("https://example.com")
        manager.discover_transports()

        # Create all clients
        all_clients = manager.get_all_transport_clients()
        assert len(manager._client_cache) == 3

        # Clear cache
        manager.clear_client_cache()
        assert len(manager._client_cache) == 0

        # Clients should be recreated on next access
        new_client = manager.get_transport_client(TransportProtocol.jsonrpc)
        assert new_client is not all_clients[TransportProtocol.jsonrpc]  # Different instance
        assert len(manager._client_cache) == 1

    @patch("tck.transport.transport_manager.fetch_agent_card")
    @patch("tck.transport.transport_manager.validate_transport_consistency")
    def test_context_manager_integration(self, mock_validate, mock_fetch, multi_transport_agent_card):
        """Test using TransportManager as context manager with all clients."""
        mock_fetch.return_value = multi_transport_agent_card
        mock_validate.return_value = []

        # Create some mock clients that track close calls
        class MockClosableClient(BaseTransportClient):
            def __init__(self, base_url, transport_type):
                super().__init__(base_url, transport_type)
                self.closed = False

            def close(self):
                self.closed = True

            # Implement abstract methods with minimal implementations
            def send_message(self, message, **kwargs):
                pass

            def send_streaming_message(self, message, **kwargs):
                pass

            def get_task(self, task_id, **kwargs):
                pass

            def cancel_task(self, task_id, **kwargs):
                pass

            def resubscribe_task(self, task_id, **kwargs):
                pass

            def set_push_notification_config(self, task_id, config, **kwargs):
                pass

            def get_push_notification_config(self, task_id, config_id, **kwargs):
                pass

            def list_push_notification_configs(self, task_id, **kwargs):
                pass

            def delete_push_notification_config(self, task_id, config_id, **kwargs):
                pass

            def get_authenticated_extended_card(self, **kwargs):
                pass

        mock_clients = {
            TransportProtocol.jsonrpc: MockClosableClient("https://example.com/jsonrpc", TransportProtocol.jsonrpc),
            TransportProtocol.GRPC: MockClosableClient("grpc://example.com:50051", TransportProtocol.GRPC),
            TransportProtocol.REST: MockClosableClient("https://example.com/api", TransportProtocol.REST),
        }

        with TransportManager("https://example.com") as manager:
            manager.discover_transports()

            # Mock client creation to return our closable clients
            def mock_create_client(transport_type):
                return mock_clients[transport_type]

            with patch.object(manager, "_create_transport_client", side_effect=mock_create_client):
                # Create all clients
                all_clients = manager.get_all_transport_clients()

                # Verify clients are not closed yet
                for client in mock_clients.values():
                    assert not client.closed

        # After context exit, all clients should be closed
        for client in mock_clients.values():
            assert client.closed

    def test_transport_type_enum_completeness(self):
        """Test that TransportProtocol enum covers all implemented transports."""
        # Verify all transport types are defined
        assert hasattr(TransportProtocol, "JSON_RPC")
        assert hasattr(TransportProtocol, "GRPC")
        assert hasattr(TransportProtocol, "REST")

        # Verify enum values match expected strings
        assert TransportProtocol.jsonrpc.value == "jsonrpc"
        assert TransportProtocol.GRPC.value == "grpc"
        assert TransportProtocol.REST.value == "rest"

        # Verify all transports are covered by TransportManager
        manager = TransportManager("https://example.com")
        manager._discovery_completed = True
        manager._supported_transports = [TransportProtocol.jsonrpc, TransportProtocol.GRPC, TransportProtocol.REST]
        manager._transport_endpoints = {
            TransportProtocol.jsonrpc: "https://example.com/jsonrpc",
            TransportProtocol.GRPC: "grpc://example.com:50051",
            TransportProtocol.REST: "https://example.com/api",
        }

        # All transport types should be creatable
        for transport_type in [TransportProtocol.jsonrpc, TransportProtocol.GRPC, TransportProtocol.REST]:
            try:
                client = manager._create_transport_client(transport_type)
                assert isinstance(client, BaseTransportClient)
                assert client.transport_type == transport_type
            except Exception as e:
                pytest.fail(f"Failed to create client for {transport_type.value}: {e}")


@pytest.mark.core
def test_integration_smoke_test():
    """Smoke test to verify all components integrate without import errors."""
    # Test all imports work
    from tck.transport.transport_manager import TransportManager, TransportSelectionStrategy
    from tck.transport.base_client import TransportProtocol, BaseTransportClient, TransportError
    from tck.transport.jsonrpc_client import JSONRPCClient, JSONRPCError
    from tck.transport.grpc_client import GRPCClient
    from tck.transport.rest_client import RESTClient

    # Test basic object creation
    manager = TransportManager("https://example.com")
    assert manager.sut_base_url == "https://example.com"
    assert manager.selection_strategy == TransportSelectionStrategy.AGENT_PREFERRED

    # Test transport type enum
    assert len([t for t in TransportProtocol]) == 3

    # Test that all client classes inherit from BaseTransportClient
    assert issubclass(JSONRPCClient, BaseTransportClient)
    assert issubclass(GRPCClient, BaseTransportClient)
    assert issubclass(RESTClient, BaseTransportClient)

    print("✓ All A2A v0.3.0 transport components integrated successfully")
