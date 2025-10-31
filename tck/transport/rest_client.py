"""REST (HTTP+JSON) Transport Client wrapping a2a-python SDK BaseClient."""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Union

import httpx
from a2a.client import ClientFactory, ClientConfig
from a2a.types import (
    TransportProtocol,
    AgentCard,
    Message,
    Task,
    PushNotificationConfig,
)

from tck.transport.base_client import BaseTransportClient, TransportError

logger = logging.getLogger(__name__)


class RESTClient(BaseTransportClient):
    """REST (HTTP+JSON) transport client wrapping SDK BaseClient."""

    def __init__(
        self,
        agent_card: AgentCard,
        base_url: str,
        timeout: float = 30.0,
        push_notifications_url: Optional[str] = None,
    ):
        super().__init__(base_url, TransportProtocol.HTTP_JSON)
        self._agent_card = agent_card
        self._push_notifications_url = push_notifications_url
        self._timeout = timeout
        self._sdk_client = None
        self._httpx_client = None
        self._initialize_sdk_client()

    def _initialize_sdk_client(self):
        self._httpx_client = httpx.AsyncClient(
            timeout=httpx.Timeout(self._timeout),
            follow_redirects=True,
        )

        push_configs = []
        if (
            self._push_notifications_url
            and self._agent_card.capabilities
            and self._agent_card.capabilities.push_notifications
        ):
            push_configs.append(PushNotificationConfig(url=self._push_notifications_url))

        config = ClientConfig(
            httpx_client=self._httpx_client,
            supported_transports=[TransportProtocol.HTTP_JSON],
            streaming=bool(self._agent_card.capabilities and self._agent_card.capabilities.streaming),
            polling=bool(self._agent_card.capabilities and self._agent_card.capabilities.push_notifications),
            push_notification_configs=push_configs,
        )

        factory = ClientFactory(config)
        self._sdk_client = factory.create(self._agent_card)
        self._logger.info(f"Initialized REST client for {self._agent_card.name}")

    def _run_async(self, coro):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)

    def send_message(self, message: Union[Message, Dict[str, Any]], extra_headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        async def _send():
            if isinstance(message, dict):
                message_obj = Message.model_validate(message)
            else:
                message_obj = message
            response = None
            async for event in self._sdk_client.send_message(message_obj):
                if isinstance(event, (Task, Message)):
                    response = event
            if response and hasattr(response, 'model_dump'):
                return response.model_dump()
            return response
        try:
            return self._run_async(_send())
        except Exception as e:
            self._logger.error(f"Error sending message: {e}")
            raise TransportError(f"Failed to send message: {e}", self.transport_type, original_error=e)

    def send_streaming_message(self, message: Union[Message, Dict[str, Any]], extra_headers: Optional[Dict[str, str]] = None) -> Any:
        raise NotImplementedError("Streaming not yet implemented")

    def get_task(self, task_id: str, history_length: Optional[int] = None, extra_headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        async def _get():
            task = await self._sdk_client.get_task(task_id)
            if task and hasattr(task, 'model_dump'):
                return task.model_dump()
            return task
        try:
            return self._run_async(_get())
        except Exception as e:
            self._logger.error(f"Error getting task: {e}")
            raise TransportError(f"Failed to get task: {e}", self.transport_type, original_error=e)

    def cancel_task(self, task_id: str, extra_headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        async def _cancel():
            result = await self._sdk_client.cancel_task(task_id)
            if result and hasattr(result, 'model_dump'):
                return result.model_dump()
            return result
        try:
            return self._run_async(_cancel())
        except Exception as e:
            self._logger.error(f"Error cancelling task: {e}")
            raise TransportError(f"Failed to cancel task: {e}", self.transport_type, original_error=e)

    def resubscribe_task(self, task_id: str, extra_headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        async def _resubscribe():
            result = await self._sdk_client.resubscribe(task_id)
            if result and hasattr(result, 'model_dump'):
                return result.model_dump()
            return result
        try:
            return self._run_async(_resubscribe())
        except Exception as e:
            self._logger.error(f"Error resubscribing to task: {e}")
            raise TransportError(f"Failed to resubscribe to task: {e}", self.transport_type, original_error=e)

    def set_push_notification_config(self, task_id: str, config: Union[PushNotificationConfig, Dict[str, Any]], extra_headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        raise NotImplementedError("Push notification config not yet implemented in SDK")

    def get_push_notification_config(self, task_id: str, extra_headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        raise NotImplementedError("Push notification config not yet implemented in SDK")

    def list_push_notification_configs(self, extra_headers: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
        raise NotImplementedError("Push notification config not yet implemented in SDK")

    def delete_push_notification_config(self, task_id: str, extra_headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        raise NotImplementedError("Push notification config not yet implemented in SDK")

    def get_authenticated_extended_card(self, extra_headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        async def _get_card():
            card = await self._sdk_client.get_card()
            if card and hasattr(card, 'model_dump'):
                return card.model_dump()
            return card
        try:
            return self._run_async(_get_card())
        except Exception as e:
            self._logger.error(f"Error getting authenticated card: {e}")
            raise TransportError(f"Failed to get authenticated card: {e}", self.transport_type, original_error=e)

    def close(self):
        if self._sdk_client:
            self._run_async(self._sdk_client.close())
        if self._httpx_client:
            self._run_async(self._httpx_client.aclose())

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
