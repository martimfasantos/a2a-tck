"""
Agent Card Utility Module for the A2A TCK v0.3.0.

This module provides utilities for fetching, parsing, and extracting information
from an Agent Card as specified in the A2A Protocol Specification v0.3.0.
Includes support for multi-transport discovery and enhanced security schemes.

Specification Reference: A2A Protocol v0.3.0 §5 - Agent Discovery
"""
import httpx
import logging
from typing import Any, Dict, List, Optional, Set
from a2a.client import A2ACardResolver
from a2a.types import (
    AgentCard, 
    AgentCapabilities, 
    AgentInterface, 
    AgentSkill, 
    TransportProtocol,
    SecurityScheme,
)

logger = logging.getLogger(__name__)


async def fetch_agent_card(sut_base_url: str) -> Optional[AgentCard]:
    """
    Retrieve the Agent Card JSON from the SUT.

    Tries A2A v0.3.0 location first (/.well-known/agent-card.json), then falls back
    to v0.2.5 location (/.well-known/agent.json) for backward compatibility.

    Args:
        sut_base_url: The base URL of the SUT

    Returns:
        The parsed Agent Card, or None if it cannot be retrieved or parsed

    Specification Reference: A2A Protocol v0.3.0 §5.3 - Recommended Location
    """
    async with httpx.AsyncClient() as httpx_client:
        resolver = A2ACardResolver(
            httpx_client=httpx_client,
            base_url=sut_base_url,
        )
        
        try:
            agent_card = await resolver.get_agent_card()
            return agent_card
        except Exception as e:
            logger.error(f"Failed to fetch Agent Card: {e}")
            return None

def get_sut_rpc_endpoint(agent_card: AgentCard) -> Optional[str]:
    """
    Extract the SUT's JSON-RPC endpoint URL from the Agent Card.

    Args:
        agent_card: The parsed Agent Card

    Returns:
        The JSON-RPC endpoint URL, or None if not found
    """
    # The endpoint might be directly in the root of the Agent Card
    if agent_card.url and agent_card.preferred_transport == "JSONRPC":
        return agent_card.url
    
    # Check additional interfaces for JSON-RPC endpoint
    if agent_card.preferred_transport != "JSONRPC":
        for interface in agent_card.additional_interfaces or []:
            if interface.transport == "JSONRPC":
                return interface.url

    # If we can't find it, return None
    logger.warning("Could not find JSON-RPC endpoint in Agent Card")
    return None


def get_capability_streaming(agent_card: AgentCard) -> bool:
    """
    Check if the SUT supports streaming capabilities.

    Args:
        agent_card: The parsed Agent Card

    Returns:
        True if streaming is supported, False otherwise
    """
    if agent_card.capabilities and isinstance(agent_card.capabilities, AgentCapabilities):
        return bool(agent_card.capabilities.streaming)

    # Default to False if not specified
    return False


def get_capability_push_notifications(agent_card: AgentCard) -> bool:
    """
    Check if the SUT supports push notifications.

    Args:
        agent_card: The parsed Agent Card data

    Returns:
        True if push notifications are supported, False otherwise
    """
    if agent_card.capabilities and isinstance(agent_card.capabilities, AgentCapabilities):
        return bool(agent_card.capabilities.push_notifications)

    # Default to False if not specified
    return False


def get_supported_modalities(agent_card: AgentCard, skill_id: Optional[str] = None) -> List[str]:
    """
    Get the supported modalities (input/output modes) from the Agent Card.

    Args:
        agent_card: The parsed Agent Card data (AgentCard object or dict)
        skill_id: Optional skill ID to get modalities for a specific skill

    Returns:
        A list of supported modality strings (e.g., ["text", "file", "data"])
    """
    modalities: Set[str] = set()
    
    skills = agent_card.skills
    
    if skills and isinstance(skills, list):
        for skill in skills:
            if isinstance(skill, AgentSkill):
                # Skip if we're looking for a specific skill and this isn't it
                if skill_id and skill.id != skill_id:
                    continue
                io_modes = skill.input_modes
            else:
                continue

            if io_modes and isinstance(io_modes, list):
                modalities.update(mode for mode in io_modes if isinstance(mode, str))

    return list(modalities)


def get_authentication_schemes(agent_card: AgentCard) -> List[AgentCard]:
    """
    Get the authentication schemes declared in the Agent Card.

    According to the A2A specification, authentication schemes should be defined
    using OpenAPI 3.x Security Scheme objects in the 'securitySchemes' field.

    Args:
        agent_card: The parsed Agent Card

    Returns:
        A list of authentication scheme objects from securitySchemes
    """
    # Look for securitySchemes as per A2A/OpenAPI specification
    if (
        agent_card.security_schemes and
        isinstance(agent_card.security_schemes, dict[str, SecurityScheme])
    ):
        return list(agent_card.security_schemes.values())

    # Fallback: check for legacy 'authentication' field for backward compatibility
    if agent_card.authentication:
        if isinstance(agent_card.authentication, list):
            return agent_card.authentication

    # Return empty list if no authentication is declared
    return []


# A2A v0.3.0 Transport Discovery Functions

def get_supported_transports(agent_card: AgentCard) -> List[TransportProtocol]:
    """
    Discover supported transport protocols from the Agent Card.

    Extracts transport information from preferredTransport and additionalInterfaces fields.

    Args:
        agent_card: The parsed Agent Card data

    Returns:
        List of supported TransportProtocol enums

    Specification Reference: A2A Protocol v0.3.0 §3.4.2 - Transport Selection and Negotiation
    """
    supported_transports: Set[TransportProtocol] = set()

    # Check preferred transport
    preferred = agent_card.preferred_transport
    if preferred and isinstance(preferred, str):
        transport_type = _parse_transport_type(preferred)
        if transport_type:
            supported_transports.add(transport_type)

    # Check additional interfaces
    additional = agent_card.additional_interfaces
    if isinstance(additional, list):
        for interface in additional:
            if isinstance(interface, AgentInterface):
                transport_name = interface.transport
                if transport_name and isinstance(transport_name, str):
                    transport_type = _parse_transport_type(transport_name)
                    if transport_type:
                        supported_transports.add(transport_type)

    return list(supported_transports)


def get_preferred_transport(agent_card: AgentCard) -> Optional[TransportProtocol]:
    """
    Get the preferred transport protocol from the Agent Card.

    Args:
        agent_card: The parsed Agent Card

    Returns:
        The preferred TransportProtocol, or None if not specified

    Specification Reference: A2A Protocol v0.3.0 §3.4.2 - Transport Selection and Negotiation
    """
    preferred = agent_card.preferred_transport
    if preferred and isinstance(preferred, str):
        return _parse_transport_type(preferred)
    return None


def get_transport_urls(agent_card: AgentCard) -> Dict[TransportProtocol, str]:
    """
    Extract transport-specific endpoints from the Agent Card.

    Maps each supported transport to its corresponding endpoint URL.

    Args:
        agent_card: The parsed Agent Card data

    Returns:
        Dictionary mapping TransportProtocol to endpoint URL

    Specification Reference: A2A Protocol v0.3.0 §3.1 - Transport Layer Requirements
    """
    urls: Dict[TransportProtocol, str] = {}

    # Check for main endpoint (usually JSON-RPC)
    main_url = agent_card.url
    if main_url and isinstance(main_url, str):
        transport_type = _parse_transport_type(agent_card.preferred_transport or "")
        if transport_type:
            urls[transport_type] = main_url
        else:
            # Default to JSON-RPC if no preferred transport specified
            urls[TransportProtocol.jsonrpc] = main_url
        
    # Check additional interfaces for transport-specific urls
    if (
        agent_card.additional_interfaces and
        isinstance(agent_card.additional_interfaces, list[AgentInterface])
    ):
        for interface in agent_card.additional_interfaces:
            if isinstance(interface, AgentInterface):
                transport_name = interface.transport
                url = interface.url
                if transport_name and url and isinstance(transport_name, str) and isinstance(url, str):
                    transport_type = _parse_transport_type(transport_name)
                    if transport_type:
                        urls[transport_type] = url

    return urls


def get_transport_interface_info(agent_card: AgentCard, transport_type: TransportProtocol) -> Optional[Dict[str, Any]]:
    """
    Get detailed interface information for a specific transport.

    Args:
        agent_card: The parsed Agent Card
        transport_type: The transport type to get information for

    Returns:
        Interface information dictionary, or None if not found

    Specification Reference: A2A Protocol v0.3.0 §3.2 - Supported Transport Protocols
    """
    # Check if this is the preferred transport with main endpoint
    preferred = get_preferred_transport(agent_card)
    if preferred == transport_type:
        url = agent_card.url
        if url:
            return {"transport": transport_type.value, "url": url, "preferred": True}

    # Check additional interfaces
    if (
        agent_card.additional_interfaces and
        isinstance(agent_card.additional_interfaces, list[AgentInterface])
    ):
        for interface in agent_card.additional_interfaces:
            if isinstance(interface, AgentInterface):
                transport_name = interface.transport
                if transport_name and _parse_transport_type(transport_name) == transport_type:
                    return {"transport": transport_type.value, "url": interface.url, "preferred": False}

    return None


def _parse_transport_type(transport_name: str) -> Optional[TransportProtocol]:
    """
    Parse a transport name string to TransportProtocol enum.

    Handles various naming conventions for transport types.

    Args:
        transport_name: String representation of transport type

    Returns:
        Corresponding TransportProtocol enum or None if not recognized
    """
    normalized = transport_name.lower().strip()

    # JSON-RPC variants
    if normalized in ["jsonrpc", "json-rpc", "jsonrpc2.0", "json-rpc-2.0", "rpc"]:
        return TransportProtocol.jsonrpc

    # gRPC variants
    if normalized in ["grpc", "grpc-web", "protobuf"]:
        return TransportProtocol.grpc

    # REST variants
    if normalized in ["rest", "http", "http+json", "restful", "http-json"]:
        return TransportProtocol.http_json

    return None


def has_transport_support(agent_card: AgentCard, transport_type: TransportProtocol) -> bool:
    """
    Check if the agent supports a specific transport type.

    Args:
        agent_card: The parsed Agent Card data
        transport_type: The transport type to check for

    Returns:
        True if the transport is supported, False otherwise

    Specification Reference: A2A Protocol v0.3.0 §3.4.1 - Functional Equivalence Requirements
    """
    supported_transports = get_supported_transports(agent_card)
    return transport_type in supported_transports


def validate_transport_consistency(agent_card: AgentCard) -> List[str]:
    """
    Validate that transport declarations are consistent and complete.

    Checks for common issues in transport configuration.

    Args:
        agent_card: The parsed Agent Card

    Returns:
        List of validation error messages (empty if valid)

    Specification Reference: A2A Protocol v0.3.0 §3.4 - Transport Compliance and Interoperability
    """
    errors: List[str] = []

    # Check that at least one transport is declared
    supported_transports = get_supported_transports(agent_card)
    if not supported_transports:
        errors.append("No supported transports declared in Agent Card")
        return errors  # Can't validate further without transports

    # Check that all declared transports have urls
    urls = get_transport_urls(agent_card)
    for transport in supported_transports:
        if transport not in urls:
            errors.append(f"Transport {transport.value} declared but no url provided")

    # Check for orphaned urls (urls without transport declarations)
    if (
        agent_card.additional_interfaces and
        isinstance(agent_card.additional_interfaces, list)
    ):
        for interface in agent_card.additional_interfaces:
            if isinstance(interface, AgentInterface):
                transport_name = interface.transport
                if transport_name:
                    transport_type = _parse_transport_type(transport_name)
                    if not transport_type:
                        errors.append(f"Unknown transport type in additionalInterfaces: {transport_name}")

    return errors
