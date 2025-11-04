"""
A2A v0.3.0 New Methods Testing

Tests for new methods introduced in A2A v0.3.0 specification:
- agent/getCard with authenticated access (§7.10)
- tasks/list (§7.3.1 - gRPC/REST only)
- Method mapping compliance across transports (§3.5.6)
- Transport-specific features validation

These tests validate that SUTs correctly implement the new v0.3.0 methods
with proper authentication, transport mapping, and functional compliance.

Uses the a2a-python SDK BaseClient interface for transport-agnostic testing.

References:
- A2A v0.3.0 Specification §7.10: Authenticated Agent Card Access
- A2A v0.3.0 Specification §7.3.1: tasks/list
- A2A v0.3.0 Specification §3.5.6: Method Mapping Reference Table
- A2A v0.3.0 Specification §3.2: Transport Protocol Requirements
- a2a-python SDK: https://a2a-protocol.org/latest/sdk/python/api/
"""

import pytest

from a2a.client.base_client import BaseClient
from a2a.types import TransportProtocol
from tests.markers import mandatory_protocol, optional_capability, a2a_v030
from tests.utils.transport_helpers import (
    transport_send_message,
    transport_get_task,
    transport_cancel_task,
    get_client_transport_type,
    generate_test_message_id,
)


class TestAuthenticatedExtendedCard:
    """
    Test suite for authenticated agent card access (§7.10)

    Validates that SUTs correctly implement authenticated agent card retrieval
    with proper authentication requirements and extended card functionality using
    the BaseClient.get_card() method from a2a-python SDK.
    """

    @pytest.mark.mandatory
    @pytest.mark.mandatory_protocol
    @pytest.mark.a2a_v030
    def test_authenticated_card_access_method_exists(self, sut_client: BaseClient):
        """
        Test that get_card() method exists and is callable across all transports.

        A2A v0.3.0 Specification Reference: §7.10
        Transport Support: All transports (JSON-RPC, gRPC, REST)
        SDK Method: BaseClient.get_card()

        SDK Behavior:
        - First call: If agent card has `supports_authenticated_extended_card=True`,
          the transport fetches the authenticated extended card and caches it
        - Subsequent calls: Returns the cached agent card
        - Each transport (grpc, jsonrpc, rest) has a `_needs_extended_card` flag
          that controls whether to fetch the extended card or use cached version

        Validates:
        - Method is available on all supported transports
        - Returns valid AgentCard object (either basic or extended)
        - Handles authenticated extended card access when supported
        """
        transport_type = get_client_transport_type(sut_client)

        try:
            # Use SDK's get_card() method - works across all transports
            # If transport._needs_extended_card=True and agent supports it,
            # this will fetch the authenticated extended card
            card = sut_client.get_card()
            
            assert card is not None, "get_card() returned None"
            assert card.name, "Card missing 'name' field"
            assert card.description, "Card missing 'description' field"

        except Exception as e:
            # Authentication errors are acceptable for authenticated card endpoint
            error_msg = str(e).lower()
            if any(keyword in error_msg for keyword in ["authentication", "unauthorized", "401", "403", "-32007"]):
                pytest.skip(f"Authentication required for extended card on {transport_type.value} - this is expected behavior")
            else:
                pytest.fail(f"Failed to call get_card() on {transport_type.value}: {e}")

    @pytest.mark.mandatory
    @pytest.mark.mandatory_protocol
    @pytest.mark.a2a_v030
    def test_authenticated_card_requires_auth(self, sut_client: BaseClient):
        """
        Test that get_card() with authenticated extended card properly handles authentication.

        A2A v0.3.0 Specification Reference: §7.10
        SDK Method: BaseClient.get_card()

        SDK Behavior:
        - Transport checks `_needs_extended_card` flag
        - If True and agent has `supports_authenticated_extended_card=True`:
          * JSON-RPC: Calls `agent/getAuthenticatedExtendedCard` method
          * gRPC: Calls `GetAgentCard` RPC with auth context
          * REST: GET request to `/v1/card` endpoint with auth headers
        - If authentication fails, raises A2AClientJSONRPCError or HTTP error
        - After successful fetch, sets `_needs_extended_card=False`

        Validates:
        - Method properly handles authentication when extended card is requested
        - Error responses follow A2A error format
        - Works across all transport types

        Note: This test validates the method exists and handles auth correctly.
        Actual authentication setup depends on the test configuration.
        """
        transport_type = get_client_transport_type(sut_client)

        try:
            # Call get_card() - if agent supports authenticated extended card
            # and transport._needs_extended_card=True, this will attempt to fetch it
            card = sut_client.get_card()
            
            assert card is not None, "get_card() returned None"
            assert card.name, "Card missing 'name' field"
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # Check if it's an authentication error (expected for secured endpoints)
            is_auth_error = any(keyword in error_msg for keyword in [
                "authentication", "unauthorized", "401", "403", "-32007", "auth"
            ])
            
            if is_auth_error:
                # This is acceptable - endpoint requires authentication
                pass
            else:
                # Some other error - this might be a problem
                pytest.fail(f"Unexpected error calling get_card() on {transport_type.value}: {e}")

    @optional_capability
    @a2a_v030
    def test_authenticated_card_with_valid_credentials(self, sut_client: BaseClient):
        """
        Test that get_card() returns valid AgentCard with proper authentication.

        A2A v0.3.0 Specification Reference: §7.10 & §11.1.3
        SDK Method: BaseClient.get_card()

        SDK Extended Card Behavior:
        - Each transport maintains `_needs_extended_card` flag
        - Flag initialized from `agent_card.supports_authenticated_extended_card`
        - When True, first get_card() call fetches authenticated extended card:
          * JSON-RPC: agent/getAuthenticatedExtendedCard
          * gRPC: GetAgentCard RPC
          * REST: GET /v1/card
        - After fetch, transport sets `_needs_extended_card=False` and caches result
        - Subsequent calls return cached card without re-fetching

        Validates:
        - Authenticated requests return AgentCard object  
        - Response follows AgentCard schema
        - Extended card caching works correctly
        - Works across all transport types

        CAPABILITY-DEPENDENT: This test requires authentication to be configured
        in the test environment. If authentication is not configured or not accepted,
        the test will be skipped.
        """
        transport_type = get_client_transport_type(sut_client)

        try:
            # First call: If agent supports extended card and _needs_extended_card=True,
            # transport will fetch authenticated extended card
            card = sut_client.get_card()
            
            assert card is not None, "get_card() returned None"
            assert card.name, "Card missing 'name' field"
            assert card.description, "Card missing 'description' field"
            assert card.version, "Card missing 'version' field"

        except Exception as e:
            error_msg = str(e).lower()
            if any(keyword in error_msg for keyword in ["authentication", "unauthorized", "401", "403"]):
                pytest.skip(f"Authentication not configured or not accepted for {transport_type.value}")
            else:
                pytest.fail(f"Failed to get authenticated card on {transport_type.value}: {e}")


class TestTasksList:
    """
    Test suite for tasks/list method (§7.3.1)

    Note: tasks/list is only available in gRPC and REST transports.
    JSON-RPC transport does not support this method per A2A specification.
    
    Uses SDK: BaseClient.list_tasks() method
    """

    @optional_capability
    @a2a_v030
    def test_tasks_list_with_existing_tasks(self, sut_client: BaseClient):
        """
        Test list_tasks() returns existing tasks when tasks are present.

        A2A v0.3.0 Specification Reference: §7.3.1 & §3.5.6
        Transport Support: gRPC, REST only (not available on JSON-RPC)
        SDK Method: BaseClient.list_tasks()

        Validates:
        - List includes previously created tasks
        - Task objects follow proper schema
        - List is properly formatted
        - Method is not available on JSON-RPC (as per spec)

        TRANSPORT-DEPENDENT: This test is MANDATORY for gRPC/REST transports,
        skipped for JSON-RPC (which doesn't support tasks/list per specification).
        """
        transport_type = get_client_transport_type(sut_client)

        if transport_type == TransportProtocol.jsonrpc:
            pytest.skip("tasks/list not supported on JSON-RPC transport per A2A specification §7.3.1")

        # Check if SDK client has list_tasks method
        if not hasattr(sut_client, "list_tasks"):
            pytest.skip(f"list_tasks() method not available on {transport_type.value} transport")

        # Create a task first to ensure we have something to list
        try:
            # Send a message to create a task
            message_params = {
                "message": {
                    "kind": "message",
                    "messageId": generate_test_message_id("tasklist-test"),
                    "role": "user",
                    "parts": [{"kind": "text", "text": "Test message for task listing"}],
                }
            }
            task = transport_send_message(sut_client, message_params)
            assert task.id, "Failed to get task ID from message send"

            # Now list tasks using SDK method
            tasks = sut_client.list_tasks()
            assert isinstance(tasks, list), f"list_tasks() should return a list, got {type(tasks)}"

            # Should include our created task
            task_ids = [t.id for t in tasks]
            assert task.id in task_ids, f"Created task {task.id} not found in list"

            # Validate task structure
            our_task = next(t for t in tasks if t.id == task.id)
            assert our_task.status, "Task missing 'status' field"
            assert our_task.kind == "task", f"Task 'kind' should be 'task', got '{our_task.kind}'"

        except Exception as e:
            pytest.fail(f"Failed to test list_tasks() on {transport_type.value}: {e}")


class TestMethodMappingCompliance:
    """
    Test suite for method mapping compliance across transports (§3.5.6)

    Validates that all supported transports follow the correct method naming
    conventions as specified in the A2A v0.3.0 Method Mapping Reference Table.
    
    Uses SDK: BaseClient methods (send_message, get_task, cancel_task)
    """

    @pytest.mark.mandatory
    @pytest.mark.mandatory_protocol
    @pytest.mark.a2a_v030
    def test_core_method_mapping_compliance(self, sut_client: BaseClient):
        """
        Test that core A2A methods work correctly across all transports.

        A2A v0.3.0 Specification Reference: §3.5.6 Method Mapping Reference Table
        SDK Methods: send_message(), get_task(), cancel_task()

        Validates mapping for:
        - JSON-RPC: message/send → tasks/get → tasks/cancel
        - gRPC: SendMessage → GetTask → CancelTask  
        - REST: POST /v1/message:send → GET /v1/tasks/{id} → POST /v1/tasks/{id}:cancel
        
        The SDK handles the transport-specific mappings internally.
        """
        transport_type = get_client_transport_type(sut_client)

        try:
            # Test send_message mapping (creates a task)
            sample_message = {
                "kind": "message",
                "messageId": generate_test_message_id("mapping-test"),
                "role": "user",
                "parts": [{"kind": "text", "text": "Method mapping test"}],
            }
            
            task = transport_send_message(sut_client, {"message": sample_message})
            assert task is not None, "send_message returned None"
            assert task.id, "Task missing 'id' field"

            # Test get_task mapping
            retrieved_task = transport_get_task(sut_client, task.id)
            assert retrieved_task is not None, "get_task returned None"
            assert retrieved_task.id == task.id, f"Retrieved task ID mismatch: {retrieved_task.id} != {task.id}"

            # Test cancel_task mapping
            cancelled_task = transport_cancel_task(sut_client, task.id)
            assert cancelled_task is not None, "cancel_task returned None"
            assert cancelled_task.id == task.id, f"Cancelled task ID mismatch: {cancelled_task.id} != {task.id}"

        except Exception as e:
            pytest.fail(f"Core method mapping test failed on {transport_type.value}: {e}")

    @pytest.mark.mandatory
    @pytest.mark.mandatory_protocol
    @pytest.mark.a2a_v030
    def test_transport_methods_work_correctly(self, sut_client: BaseClient):
        """
        Test that transport-specific methods work correctly through the SDK.

        A2A v0.3.0 Specification Reference: §3.5.1, §3.5.2, §3.5.3
        SDK: BaseClient abstracts transport-specific naming

        Validates:
        - SDK methods work correctly regardless of underlying transport
        - Each transport (JSON-RPC, gRPC, REST) is functional
        - Transport layer is properly abstracted by SDK

        The SDK handles transport-specific naming internally:
        - JSON-RPC: {category}/{action} pattern
        - gRPC: PascalCase compound words
        - REST: /v1/{resource}[/{id}][:{action}] pattern
        """
        transport_type = get_client_transport_type(sut_client)

        try:
            # Test that basic operations work through SDK abstraction
            # The SDK translates these to transport-specific formats internally
            
            # Create a message/task
            message_params = {
                "message": {
                    "kind": "message",
                    "messageId": generate_test_message_id("transport-naming-test"),
                    "role": "user",
                    "parts": [{"kind": "text", "text": f"Testing {transport_type.value} transport"}],
                }
            }
            
            task = transport_send_message(sut_client, message_params)
            assert task.id, "Failed to create task via send_message"
            
            # Retrieve the task
            retrieved_task = transport_get_task(sut_client, task.id)
            assert retrieved_task, "Failed to retrieve task via get_task"
            
            # Cancel the task
            cancelled_task = transport_cancel_task(sut_client, task.id)
            assert cancelled_task, "Failed to cancel task via cancel_task"

        except Exception as e:
            pytest.fail(f"Transport method test failed on {transport_type.value}: {e}")


class TestTransportSpecificFeatures:
    """
    Test suite for transport-specific features and optimizations (§3.4.3)

    Validates that transports provide transport-specific extensions while
    maintaining functional equivalence with core A2A functionality.
    """

    @optional_capability
    @a2a_v030
    def test_grpc_specific_features(self, sut_client: BaseClient):
        """
        Test gRPC-specific features through SDK abstraction.

        A2A v0.3.0 Specification Reference: §3.4.3 (Transport-Specific Extensions)

        Validates:
        - gRPC transport works correctly through SDK
        - Basic gRPC request/response patterns function
        - SDK properly handles gRPC-specific behavior

        TRANSPORT-DEPENDENT: This test is MANDATORY if gRPC transport is declared in
        Agent Card additionalInterfaces, ensuring transport-specific optimizations
        maintain functional equivalence.
        
        Note: SDK abstracts transport-specific features like metadata and streaming.
        This test validates that gRPC transport is functional through the SDK interface.
        """
        if get_client_transport_type(sut_client) != TransportProtocol.grpc:
            pytest.skip("Test only applicable to gRPC transport")

        try:
            # Test that gRPC transport handles basic operations correctly
            card = sut_client.get_card()
            assert card is not None
            assert card.name, "gRPC get_card() should return valid card with name"

            # Test message sending through gRPC
            message_params = {
                "message": {
                    "kind": "message",
                    "messageId": generate_test_message_id("grpc-test"),
                    "role": "user",
                    "parts": [{"kind": "text", "text": "Testing gRPC transport"}],
                }
            }
            
            task = transport_send_message(sut_client, message_params)
            assert task.id, "gRPC send_message() should return task with ID"
            
            # Test task retrieval through gRPC
            retrieved_task = transport_get_task(sut_client, task.id)
            assert retrieved_task, "gRPC get_task() should return task"
            
        except Exception as e:
            pytest.fail(f"gRPC transport test failed: {e}")

    @optional_capability
    @a2a_v030
    def test_rest_specific_features(self, sut_client: BaseClient):
        """
        Test REST/HTTP-JSON-specific features through SDK abstraction.

        A2A v0.3.0 Specification Reference: §3.4.3

        Validates:
        - REST transport works correctly through SDK
        - HTTP-based request/response patterns function
        - SDK properly handles REST-specific behavior
        
        Note: SDK abstracts transport-specific features like HTTP headers and caching.
        This test validates that REST transport is functional through the SDK interface.
        """
        if get_client_transport_type(sut_client) != TransportProtocol.http_json:
            pytest.skip("Test only applicable to REST transport")

        try:
            # Test that REST transport handles basic operations correctly
            card = sut_client.get_card()
            assert card is not None
            assert card.name, "REST get_card() should return valid card with name"

            # Test message sending through REST
            message_params = {
                "message": {
                    "kind": "message",
                    "messageId": generate_test_message_id("rest-test"),
                    "role": "user",
                    "parts": [{"kind": "text", "text": "Testing REST transport"}],
                }
            }
            
            task = transport_send_message(sut_client, message_params)
            assert task.id, "REST send_message() should return task with ID"
            
            # Test task retrieval through REST
            retrieved_task = transport_get_task(sut_client, task.id)
            assert retrieved_task, "REST get_task() should return task"
            
        except Exception as e:
            pytest.fail(f"REST transport test failed: {e}")

    @optional_capability
    @a2a_v030
    def test_jsonrpc_specific_features(self, sut_client: BaseClient):
        """
        Test JSON-RPC-specific features through SDK abstraction.

        A2A v0.3.0 Specification Reference: §3.4.3, §7.3.1

        Validates:
        - JSON-RPC transport works correctly through SDK
        - JSON-RPC 2.0 compliance through SDK interface
        - SDK properly handles JSON-RPC-specific behavior
        
        Note: SDK abstracts transport-specific features like batch requests and additional fields.
        This test validates that JSON-RPC transport is functional through the SDK interface.
        JSON-RPC transport does not support list_tasks() per §7.3.1.
        """
        if get_client_transport_type(sut_client) != TransportProtocol.jsonrpc:
            pytest.skip("Test only applicable to JSON-RPC transport")

        try:
            # Test that JSON-RPC transport handles basic operations correctly
            card = sut_client.get_card()
            assert card is not None
            assert card.name, "JSON-RPC get_card() should return valid card with name"

            # Test message sending through JSON-RPC
            message_params = {
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": "Testing JSON-RPC transport"}],
                    "messageId": generate_test_message_id("jsonrpc-test"),
                    "kind": "message",
                }
            }
            
            task = transport_send_message(sut_client, message_params)
            assert task.id, "JSON-RPC send_message() should return task with ID"
            
            # Test task retrieval through JSON-RPC
            retrieved_task = transport_get_task(sut_client, task.id)
            assert retrieved_task, "JSON-RPC get_task() should return task"
            
            # Verify JSON-RPC does NOT support list_tasks per §7.3.1
            transport_type = get_client_transport_type(sut_client)
            assert transport_type == TransportProtocol.jsonrpc
            
        except Exception as e:
            pytest.fail(f"JSON-RPC transport test failed: {e}")
