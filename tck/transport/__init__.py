"""
A2A Transport Layer Module

This module provides the TransportManager for creating SDK-based transport clients
for the A2A protocol v0.3.0. Supports multiple transport protocols: JSON-RPC 2.0, 
gRPC, and HTTP+JSON/REST.

Uses the a2a-python SDK's ClientFactory pattern to create transport-specific clients.

Specification: A2A Protocol v0.3.0 §3 - Transport and Format
"""

from .transport_manager import TransportManager

__all__ = [
    "TransportManager",
]
