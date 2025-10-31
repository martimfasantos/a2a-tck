"""
A2A Transport Layer Module

This module provides transport-agnostic client implementations for the A2A protocol v0.3.0.
Supports multiple transport protocols: JSON-RPC 2.0, gRPC, and HTTP+JSON/REST.

The transport layer abstracts protocol-specific details while maintaining functional
equivalence across all supported transports.

Specification: A2A Protocol v0.3.0 §3 - Transport and Format
"""

from .base_client import BaseTransportClient, TransportError
from a2a.types import TransportProtocol

# Re-export TransportProtocol as TransportType for backward compatibility
TransportType = TransportProtocol

__all__ = [
    "BaseTransportClient",
    "TransportError",
    "TransportType",
    "TransportProtocol",
]
