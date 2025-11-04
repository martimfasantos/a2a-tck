"""
Transport Manager for A2A Protocol v0.3.0

This module manages transport selection, client instantiation, and multi-transport
coordination for the A2A Test Compatibility Kit. It provides the main interface
for tests to interact with different transport protocols in a unified way.

Specification Reference: A2A Protocol v0.3.0 §3.4 - Transport Compliance and Interoperability
"""

import logging
from typing import Any, Dict, List, Optional, Set, Union

import httpx
import requests

import asyncio
from a2a.types import AgentCard, TransportProtocol
from a2a.client import ClientFactory, ClientConfig, Client
from a2a.client.base_client import BaseClient
from tck.agent_card_utils import (
    fetch_agent_card,
    get_supported_transports,
    get_preferred_transport,
    get_transport_urls,
    validate_transport_consistency,
)
from tck import config as tck_config

logger = logging.getLogger(__name__)


class TransportManagerError(Exception):
    """
    Exception raised by TransportManager operations.
    """

    pass


class TransportSelectionStrategy:
    """
    Defines strategies for transport selection in multi-transport scenarios.
    """

    PREFER_JSONRPC = "prefer_jsonrpc"
    PREFER_GRPC = "prefer_grpc"
    PREFER_REST = "prefer_rest"
    AGENT_PREFERRED = "agent_preferred"
    ALL_SUPPORTED = "all_supported"


class TransportManager:
    """
    Manages transport client selection and coordination for A2A testing.

    The TransportManager is responsible for:
    - Discovering supported transports from Agent Card
    - Selecting appropriate transport clients based on strategy
    - Coordinating multi-transport testing scenarios
    - Managing client lifecycle and connection pooling

    Specification Reference: A2A Protocol v0.3.0 §3.4.2 - Transport Selection and Negotiation
    """

    def __init__(
        self,
        sut_base_url: str,
        session: Optional[requests.Session] = None,
        selection_strategy: str = TransportSelectionStrategy.AGENT_PREFERRED,
    ):
        """
        Initialize the TransportManager.

        Args:
            sut_base_url: Base URL of the SUT
            session: Optional requests session for HTTP operations
            selection_strategy: Strategy for transport selection
        """
        self.sut_base_url = sut_base_url
        self.session = session or requests.Session()
        self.selection_strategy = selection_strategy

        # Initialize internal state
        self._agent_card: Optional[AgentCard] = None
        self._supported_transports: List[TransportProtocol] = []
        self._transport_endpoints: Dict[TransportProtocol, str] = {}
        self._client_cache: Dict[TransportProtocol, Client] = {}
        self._discovery_completed = False
        self._httpx_client: Optional[httpx.AsyncClient] = None
        self._grpc_channel_factory = None  # Will be set if gRPC is needed

        logger.info(f"TransportManager initialized for {sut_base_url} with strategy: {selection_strategy}")

    def discover_transports(self, force_refresh: bool = False) -> bool:
        """
        Discover supported transports from the SUT's Agent Card.

        Args:
            force_refresh: Force re-discovery even if already completed

        Returns:
            True if discovery was successful, False otherwise

        Raises:
            TransportManagerError: If discovery fails or Agent Card is invalid
        """
        if self._discovery_completed and not force_refresh:
            return True

        logger.info(f"Discovering transports for SUT: {self.sut_base_url}")

        try:
            # Fetch the Agent Card
            self._agent_card = asyncio.run(fetch_agent_card(self.sut_base_url))
            if not self._agent_card:
                raise TransportManagerError("Failed to fetch Agent Card from SUT")

            # Validate transport consistency
            validation_errors = validate_transport_consistency(self._agent_card)
            if validation_errors:
                error_msg = "Agent Card transport validation failed: " + "; ".join(validation_errors)
                raise TransportManagerError(error_msg)

            # Extract transport information
            discovered = get_supported_transports(self._agent_card)
            endpoints = get_transport_urls(self._agent_card)

            # Apply required transports restriction, if any
            required = tck_config.get_required_transports()
            if required is not None:
                self._supported_transports = [t for t in discovered if t in required]
                self._transport_endpoints = {t: ep for t, ep in endpoints.items() if t in self._supported_transports}
            else:
                self._supported_transports = discovered
                self._transport_endpoints = endpoints

            if not self._supported_transports:
                raise TransportManagerError("No supported transports found in Agent Card")

            logger.info(f"Discovered transports: {[t.value for t in self._supported_transports]}")
            logger.info(f"Transport endpoints: {[(t.value, ep) for t, ep in self._transport_endpoints.items()]}")

            self._discovery_completed = True
            return True

        except Exception as e:
            logger.error(f"Transport discovery failed: {e}")
            if isinstance(e, TransportManagerError):
                raise
            raise TransportManagerError(f"Transport discovery failed: {e}") from e

    def get_supported_transports(self) -> List[TransportProtocol]:
        """
        Get list of supported transport types.

        Returns:
            List of supported TransportProtocol enums

        Raises:
            TransportManagerError: If discovery has not been completed
        """
        if not self._discovery_completed:
            if not self.discover_transports():
                raise TransportManagerError("Transport discovery not completed and failed to discover")

        return self._supported_transports.copy()

    def get_preferred_transport(self) -> Optional[TransportProtocol]:
        """
        Get the preferred transport type based on Agent Card.

        Returns:
            Preferred TransportProtocol or None if not specified

        Raises:
            TransportManagerError: If discovery has not been completed
        """
        if not self._discovery_completed:
            if not self.discover_transports():
                raise TransportManagerError("Transport discovery not completed and failed to discover")

        if not self._agent_card:
            return None

        return get_preferred_transport(self._agent_card)

    def supports_transport(self, transport_type: TransportProtocol) -> bool:
        """
        Check if the SUT supports a specific transport type.

        Args:
            transport_type: Transport type to check

        Returns:
            True if supported, False otherwise
        """
        if not self._discovery_completed:
            try:
                self.discover_transports()
            except TransportManagerError:
                return False

        return transport_type in self._supported_transports

    def get_transport_client(self, transport_type: Optional[TransportProtocol] = None) -> BaseClient:
        """
        Get a transport client for the specified transport type.

        Args:
            transport_type: Specific transport type, or None to use selection strategy

        Returns:
            Configured transport client instance (SDK BaseClient)

        Raises:
            TransportManagerError: If transport is not supported or client creation fails
        """
        if not self._discovery_completed:
            if not self.discover_transports():
                raise TransportManagerError("Cannot get client: transport discovery failed")

        # Determine which transport to use
        selected_transport = transport_type
        if not selected_transport:
            selected_transport = self._select_transport_by_strategy()

        if not selected_transport:
            raise TransportManagerError("No transport selected")

        if not self.supports_transport(selected_transport):
            raise TransportManagerError(f"Transport {selected_transport.value} is not supported by SUT")

        # Check cache first
        if selected_transport in self._client_cache:
            return self._client_cache[selected_transport]

        # Create new client
        client = self._create_transport_client(selected_transport)
        self._client_cache[selected_transport] = client

        return client

    def get_all_transport_clients(self) -> Dict[TransportProtocol, Client]:
        """
        Get transport clients for all supported transports.

        Useful for multi-transport equivalence testing.

        Returns:
            Dictionary mapping TransportProtocol to client instances (SDK BaseClient)

        Raises:
            TransportManagerError: If any client creation fails
        """
        if not self._discovery_completed:
            if not self.discover_transports():
                raise TransportManagerError("Cannot get clients: transport discovery failed")

        clients: Dict[TransportProtocol, Client] = {}

        for transport_type in self._supported_transports:
            try:
                clients[transport_type] = self.get_transport_client(transport_type)
            except Exception as e:
                raise TransportManagerError(f"Failed to create client for {transport_type.value}: {e}") from e

        return clients

    def is_multi_transport_sut(self) -> bool:
        """
        Check if the SUT supports multiple transport protocols.

        Returns:
            True if SUT supports more than one transport
        """
        if not self._discovery_completed:
            try:
                self.discover_transports()
            except TransportManagerError:
                return False

        return len(self._supported_transports) > 1

    def get_transport_info(self) -> Dict[str, Any]:
        """
        Get comprehensive transport information for the SUT.

        Returns:
            Dictionary containing transport discovery results
        """
        if not self._discovery_completed:
            try:
                self.discover_transports()
            except TransportManagerError:
                return {"error": "Transport discovery failed"}

        preferred = self.get_preferred_transport()

        return {
            "sut_base_url": self.sut_base_url,
            "supported_transports": [t.value for t in self._supported_transports],
            "preferred_transport": preferred.value if preferred else None,
            "transport_endpoints": {t.value: ep for t, ep in self._transport_endpoints.items()},
            "is_multi_transport": self.is_multi_transport_sut(),
            "selection_strategy": self.selection_strategy,
            "discovery_completed": self._discovery_completed,
        }

    def _select_transport_by_strategy(self) -> Optional[TransportProtocol]:
        """
        Select a transport based on the configured selection strategy.

        Returns:
            Selected TransportProtocol or None if no suitable transport found
        """
        if not self._supported_transports:
            return None

        if self.selection_strategy == TransportSelectionStrategy.AGENT_PREFERRED:
            # Use agent's preferred transport if available
            preferred = self.get_preferred_transport()
            if preferred and preferred in self._supported_transports:
                return preferred
            # Fall back to first supported transport
            return self._supported_transports[0]

        elif self.selection_strategy == TransportSelectionStrategy.PREFER_JSONRPC:
            if TransportProtocol.jsonrpc in self._supported_transports:
                return TransportProtocol.jsonrpc
            return self._supported_transports[0]

        elif self.selection_strategy == TransportSelectionStrategy.PREFER_GRPC:
            if TransportProtocol.grpc in self._supported_transports:
                return TransportProtocol.grpc
            return self._supported_transports[0]

        elif self.selection_strategy == TransportSelectionStrategy.PREFER_REST:
            if TransportProtocol.http_json in self._supported_transports:
                return TransportProtocol.http_json
            return self._supported_transports[0]

        else:
            # Default: return first supported transport
            return self._supported_transports[0]

    def _create_transport_client(self, transport_type: TransportProtocol) -> BaseClient:
        """
        Create a transport client using SDK's ClientFactory.

        Args:
            transport_type: Transport type to create client for

        Returns:
            Configured client instance (SDK BaseClient with appropriate transport)

        Raises:
            TransportManagerError: If client creation fails
        """
        if transport_type not in self._transport_endpoints:
            raise TransportManagerError(f"No endpoint configured for transport {transport_type.value}")

        if not self._agent_card:
            raise TransportManagerError("Agent card not available - discovery must be completed first")

        endpoint = self._transport_endpoints[transport_type]

        try:
            # Create AgentCard with specific transport preference
            card = AgentCard(
                name=self._agent_card.name,
                description=self._agent_card.description,
                version=self._agent_card.version,
                url=endpoint,
                capabilities=self._agent_card.capabilities,
                skills=self._agent_card.skills,
                default_input_modes=self._agent_card.default_input_modes,
                default_output_modes=self._agent_card.default_output_modes,
                preferred_transport=transport_type,
                supports_authenticated_extended_card=self._agent_card.supports_authenticated_extended_card,
                additional_interfaces=[]  # Don't include other transports
            )

            # Create ClientConfig for this transport
            config_params = {
                'supported_transports': [transport_type],
                'use_client_preference': False  # Use server preference
            }

            # Add httpx client for HTTP-based transports
            if transport_type in [TransportProtocol.jsonrpc, TransportProtocol.http_json]:
                if not self._httpx_client:
                    self._httpx_client = httpx.AsyncClient(timeout=30.0)
                config_params['httpx_client'] = self._httpx_client

            # Add gRPC channel factory for gRPC transport
            elif transport_type == TransportProtocol.grpc:
                if not self._grpc_channel_factory:
                    try:
                        import grpc.aio
                        self._grpc_channel_factory = lambda url: grpc.aio.insecure_channel(url)
                    except ImportError as e:
                        raise TransportManagerError(
                            "gRPC dependencies not installed. Install with: pip install a2a-sdk[grpc]"
                        ) from e
                config_params['grpc_channel_factory'] = self._grpc_channel_factory

            client_config = ClientConfig(**config_params)

            # Use ClientFactory to create the client
            factory = ClientFactory(client_config)
            client = factory.create(card)

            logger.info(f"Created {transport_type.value} client using SDK ClientFactory")
            return client

        except ImportError as e:
            raise TransportManagerError(f"Transport client not available for {transport_type.value}: {e}") from e
        except Exception as e:
            raise TransportManagerError(f"Failed to create {transport_type.value} client: {e}") from e

    def clear_client_cache(self):
        """
        Clear the client cache, forcing recreation of clients on next access.
        """
        self._client_cache.clear()
        logger.debug("Transport client cache cleared")

    async def close_async(self):
        """
        Close all clients and clean up resources (async version).
        """
        for client in self._client_cache.values():
            if hasattr(client, "close"):
                try:
                    await client.close()
                except Exception as e:
                    logger.warning(f"Error closing transport client {client}: {e}")

        self.clear_client_cache()

        if self._httpx_client:
            await self._httpx_client.aclose()
            self._httpx_client = None

        if hasattr(self.session, "close"):
            self.session.close()

        logger.info("TransportManager closed")

    def close(self):
        """
        Close all clients and clean up resources (sync version).
        
        Note: This is a synchronous wrapper. For async contexts, prefer close_async().
        """
        try:
            asyncio.run(self.close_async())
        except RuntimeError:
            # If we're already in an event loop, just clear cache
            self.clear_client_cache()
            if hasattr(self.session, "close"):
                self.session.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def __str__(self) -> str:
        return f"TransportManager({self.sut_base_url}, strategy={self.selection_strategy})"

    def __repr__(self) -> str:
        return (
            f"TransportManager(sut_base_url='{self.sut_base_url}', "
            f"selection_strategy='{self.selection_strategy}', "
            f"supported_transports={[t.value for t in self._supported_transports]})"
        )
