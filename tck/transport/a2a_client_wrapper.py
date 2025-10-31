"""
A2A BaseClient Wrapper for TCK Integration

This module wraps the a2a-python SDK's BaseClient to integrate it with the TCK
testing framework, providing a bridge between the SDK's async client interface
and the TCK's test patterns.

Specification Reference: A2A Protocol v0.3.0
"""

import asyncio
import httpx
import logging
from typing import Any, Dict, List, Optional, Union

from a2a.client.base_client import BaseClient
from a2a.client.client_factory import ClientFactory
from a2a.client.client import ClientConfig
from a2a.types import (
    AgentCard,
    Message,
    Task,
    TransportProtocol,
    PushNotificationConfig,
)
from tck.transport.base_client import BaseTransportClient, TransportError

logger = logging.getLogger(__name__)


class A2AClientWrapper(BaseTransportClient):
    """
    Wrapper around a2a-python SDK's BaseClient for TCK integration.
    
    This class adapts the async BaseClient from the a2a-python SDK to work
    with TCK's testing patterns, handling configuration, push notifications,
    and providing a consistent interface for tests.
    """

    def __init__(
        self,
        agent_card: AgentCard,
        transport_protocol: TransportProtocol,
        endpoint: str,
        push_notifications_url: Optional[str] = None,
        timeout: float = 30.0,
    ):
        """
        Initialize the A2A client wrapper.

        Args:
            agent_card: The agent card defining the agent's capabilities
            transport_protocol: The transport protocol to use
            endpoint: The endpoint URL for the agent
            push_notifications_url: Optional URL for push notifications
            timeout: Request timeout in seconds
        """
        super().__init__(endpoint, transport_protocol)
        
        self._agent_card = agent_card
        self._push_notifications_url = push_notifications_url
        self._timeout = timeout
        self._base_client: Optional[BaseClient] = None
        self._httpx_client: Optional[httpx.AsyncClient] = None
        
        # Initialize the client
        self._initialize_client()

    def _initialize_client(self):
        """Initialize the a2a-python BaseClient with proper configuration."""
        # Validate push notification requirements
        if (
            self._agent_card.capabilities
            and self._agent_card.capabilities.push_notifications
            and not self._push_notifications_url
        ):
            logger.warning(
                f"Agent {self._agent_card.name} supports push notifications but no "
                f"push_notifications_url was provided. Push notifications will be disabled."
            )

        # Create HTTP client configuration
        http_client_config = {
            "timeout": httpx.Timeout(self._timeout),
            "follow_redirects": True,
        }

        # Determine supported transports based on the protocol
        supported_transports = [self.transport_type]

        # Create A2A client configuration
        config = ClientConfig(
            httpx_client=httpx.AsyncClient(**http_client_config),
            supported_transports=supported_transports,
            streaming=(
                self._agent_card.capabilities.streaming
                if self._agent_card.capabilities and hasattr(self._agent_card.capabilities, 'streaming')
                else False
            ),
            polling=(
                self._agent_card.capabilities.push_notifications
                if self._agent_card.capabilities
                else False
            ),  # This makes blocking=False in BaseClient
            push_notification_configs=[
                PushNotificationConfig(
                    url=self._push_notifications_url,
                    # token=...  # To validate incoming push notifications
                    # authentication=...  # Optional auth for the agent to use when calling the notification URL
                )
            ]
            if self._agent_card.capabilities
            and self._agent_card.capabilities.push_notifications
            and self._push_notifications_url
            else [],
        )

        # Create the client using ClientFactory
        factory = ClientFactory(config)
        self._base_client = factory.create(self._agent_card)
        
        logger.info(
            f"Initialized A2A BaseClient for {self._agent_card.name} "
            f"using {self.transport_type.value} transport"
        )

    def _run_async(self, coro):
        """Helper to run async coroutines, handling event loop properly."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(coro)

    async def _send_message_async(
        self,
        message: Union[Message, Dict[str, Any]],
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Union[Task, Message, Dict[str, Any]]:
        """
        Send a message asynchronously using the BaseClient.

        Args:
            message: The message to send
            extra_headers: Optional additional headers

        Returns:
            Task or Message response from the agent
        """
        if not self._base_client:
            raise TransportError(
                "Client not initialized",
                self.transport_type
            )

        # Convert dict to Message if needed
        if isinstance(message, dict):
            message = Message(**message)

        # TODO: Handle extra_headers if needed (may require custom interceptor)
        
        # Send message and collect response
        response = None
        async for event in self._base_client.send_message(message):
            # Get the final message response
            if isinstance(event, Message):
                response = event
            # Could also be a Task for async operations
            elif isinstance(event, Task):
                response = event

        # Convert to dict for TCK compatibility
        if hasattr(response, 'model_dump'):
            return response.model_dump()
        return response

    def send_message(
        self,
        message: Union[Message, Dict[str, Any]],
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Send a message to the agent (synchronous wrapper).

        Args:
            message: The message to send
            extra_headers: Optional additional headers

        Returns:
            Response from the agent as dict
        """
        try:
            return self._run_async(self._send_message_async(message, extra_headers))
        except Exception as e:
            self._logger.error(f"Error sending message: {e}")
            raise TransportError(
                f"Failed to send message: {e}",
                self.transport_type,
                original_error=e
            )

    def send_streaming_message(
        self,
        message: Union[Message, Dict[str, Any]],
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        """
        Send a message with streaming response.

        Args:
            message: The message to send
            extra_headers: Optional additional headers

        Returns:
            Stream iterator
        """
        # For now, return NotImplemented - streaming needs special handling
        raise NotImplementedError("Streaming not yet implemented in wrapper")

    async def _get_task_async(
        self,
        task_id: str,
        history_length: Optional[int] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Get task status asynchronously.

        Args:
            task_id: Task identifier
            history_length: Optional history length parameter
            extra_headers: Optional additional headers

        Returns:
            Task information as dict
        """
        if not self._base_client:
            raise TransportError(
                "Client not initialized",
                self.transport_type
            )

        # TODO: Handle extra_headers if needed
        # Use the BaseClient's get_task method
        # Note: a2a-python SDK doesn't have history_length parameter yet
        task = await self._base_client.get_task(task_id)
        
        # Convert to dict for TCK compatibility
        if hasattr(task, 'model_dump'):
            return task.model_dump()
        return task

    def get_task(
        self,
        task_id: str,
        history_length: Optional[int] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Get task status (synchronous wrapper).

        Args:
            task_id: Task identifier
            history_length: Optional history length parameter
            extra_headers: Optional additional headers

        Returns:
            Task information as dict
        """
        try:
            return self._run_async(self._get_task_async(task_id, history_length, extra_headers))
        except Exception as e:
            self._logger.error(f"Error getting task: {e}")
            raise TransportError(
                f"Failed to get task: {e}",
                self.transport_type,
                original_error=e
            )

    def cancel_task(
        self,
        task_id: str,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Cancel a task.

        Args:
            task_id: Task identifier
            extra_headers: Optional additional headers

        Returns:
            Response confirming cancellation
        """
        async def _cancel():
            if not self._base_client:
                raise TransportError("Client not initialized", self.transport_type)
            result = await self._base_client.cancel_task(task_id)
            if hasattr(result, 'model_dump'):
                return result.model_dump()
            return result

        try:
            return self._run_async(_cancel())
        except Exception as e:
            self._logger.error(f"Error cancelling task: {e}")
            raise TransportError(
                f"Failed to cancel task: {e}",
                self.transport_type,
                original_error=e
            )

    def resubscribe_task(
        self,
        task_id: str,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        """
        Resubscribe to task updates.

        Args:
            task_id: Task identifier
            extra_headers: Optional additional headers

        Returns:
            Stream iterator
        """
        raise NotImplementedError("Task resubscription not yet implemented in wrapper")

    def set_push_notification_config(
        self,
        task_id: str,
        config: Dict[str, Any],
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Set push notification configuration for a task.

        Args:
            task_id: Task identifier
            config: Push notification configuration
            extra_headers: Optional additional headers

        Returns:
            Response confirming configuration was set
        """
        async def _set_config():
            if not self._base_client:
                raise TransportError("Client not initialized", self.transport_type)
            result = await self._base_client.set_push_notification_config(task_id, config)
            if hasattr(result, 'model_dump'):
                return result.model_dump()
            return result

        try:
            return self._run_async(_set_config())
        except Exception as e:
            self._logger.error(f"Error setting push notification config: {e}")
            raise TransportError(
                f"Failed to set push notification config: {e}",
                self.transport_type,
                original_error=e
            )

    def get_push_notification_config(
        self,
        task_id: str,
        config_id: str,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Get push notification configuration for a task.

        Args:
            task_id: Task identifier
            config_id: Configuration identifier
            extra_headers: Optional additional headers

        Returns:
            Push notification configuration
        """
        async def _get_config():
            if not self._base_client:
                raise TransportError("Client not initialized", self.transport_type)
            result = await self._base_client.get_push_notification_config(task_id, config_id)
            if hasattr(result, 'model_dump'):
                return result.model_dump()
            return result

        try:
            return self._run_async(_get_config())
        except Exception as e:
            self._logger.error(f"Error getting push notification config: {e}")
            raise TransportError(
                f"Failed to get push notification config: {e}",
                self.transport_type,
                original_error=e
            )

    def list_push_notification_configs(
        self,
        task_id: str,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        List all push notification configurations for a task.

        Args:
            task_id: Task identifier
            extra_headers: Optional additional headers

        Returns:
            List of push notification configurations
        """
        async def _list_configs():
            if not self._base_client:
                raise TransportError("Client not initialized", self.transport_type)
            result = await self._base_client.list_push_notification_configs(task_id)
            if hasattr(result, 'model_dump'):
                return result.model_dump()
            return result

        try:
            return self._run_async(_list_configs())
        except Exception as e:
            self._logger.error(f"Error listing push notification configs: {e}")
            raise TransportError(
                f"Failed to list push notification configs: {e}",
                self.transport_type,
                original_error=e
            )

    def delete_push_notification_config(
        self,
        task_id: str,
        config_id: str,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Delete a push notification configuration for a task.

        Args:
            task_id: Task identifier
            config_id: Configuration identifier
            extra_headers: Optional additional headers

        Returns:
            Response confirming configuration was deleted
        """
        async def _delete_config():
            if not self._base_client:
                raise TransportError("Client not initialized", self.transport_type)
            result = await self._base_client.delete_push_notification_config(task_id, config_id)
            if hasattr(result, 'model_dump'):
                return result.model_dump()
            return result

        try:
            return self._run_async(_delete_config())
        except Exception as e:
            self._logger.error(f"Error deleting push notification config: {e}")
            raise TransportError(
                f"Failed to delete push notification config: {e}",
                self.transport_type,
                original_error=e
            )

    def get_authenticated_extended_card(
        self,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Get the authenticated extended agent card.

        Args:
            extra_headers: Optional additional headers (typically auth headers)

        Returns:
            Extended agent card with additional authenticated information
        """
        # The a2a-python SDK doesn't have this method yet,
        # so we'll need to implement it manually or raise NotImplementedError
        raise NotImplementedError("Authenticated extended card not yet available in a2a-python SDK")

    def get_agent_card(
        self,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Get the agent card.

        Args:
            extra_headers: Optional additional headers

        Returns:
            Agent card as dict
        """
        # Return the agent card we have
        if self._agent_card and hasattr(self._agent_card, 'model_dump'):
            return self._agent_card.model_dump()
        return self._agent_card

    def close(self):
        """Close the client and cleanup resources."""
        if self._httpx_client:
            try:
                self._run_async(self._httpx_client.aclose())
            except Exception as e:
                self._logger.warning(f"Error closing httpx client: {e}")
        self._base_client = None
        self._logger.info(f"Closed A2A client for {self.transport_type.value}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
