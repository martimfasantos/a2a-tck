"""
Raw HTTP Client for Protocol Violation Testing

This module provides a minimal HTTP client for testing protocol violations,
malformed JSON-RPC requests, and other edge cases that need to bypass
the a2a-python SDK's validation.

This is NOT for normal A2A operations - use transport-specific wrappers
(A2AClientWrapper) with the SDK's BaseClient for that.
"""

import logging
from typing import Any, Dict, Optional, Tuple, cast

import requests

logger = logging.getLogger(__name__)


class RawHTTPClient:
    """
    Simple HTTP client for protocol violation testing.
    
    This client intentionally bypasses all A2A SDK validation to allow
    testing of malformed requests, invalid JSON, and protocol violations.
    """

    def __init__(self, base_url: str):
        """
        Initialize the raw HTTP client.

        Args:
            base_url: The base URL of the endpoint to test
        """
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def raw_send(self, raw_data: str) -> Tuple[int, str]:
        """
        Send raw data to the endpoint without JSON validation.

        This method is primarily used for testing the SUT's handling of invalid JSON
        and other protocol violations.

        Args:
            raw_data: The raw string data to send

        Returns:
            A tuple of (status_code, response_text)
        """
        headers = {"Content-Type": "application/json"}

        logger.info(f"Sending raw data to {self.base_url}: {raw_data}")

        try:
            response = self.session.post(
                self.base_url, data=raw_data, headers=headers, timeout=10
            )
            logger.info(f"Server responded with {response.status_code}: {response.text}")
            return response.status_code, response.text
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP request failed: {e}")
            raise

    def send_raw_json_rpc(self, json_request: dict) -> Dict[str, Any]:
        """
        Send a JSON-RPC request without validation.

        This method is primarily used for testing the SUT's handling of malformed
        JSON-RPC requests and protocol violations.

        Args:
            json_request: The JSON-RPC request as a dictionary (can be malformed)

        Returns:
            The JSON response from the server

        Raises:
            requests.RequestException: If the HTTP request fails
            ValueError: If the response is not valid JSON
        """
        headers = {"Content-Type": "application/json"}

        logger.info(f"Sending raw JSON-RPC request to {self.base_url}: {json_request}")

        try:
            response = self.session.post(
                self.base_url, json=json_request, headers=headers, timeout=10
            )
            logger.info(f"Server responded with {response.status_code}: {response.text}")
            response.raise_for_status()
            return cast(Dict[str, Any], response.json())
        except requests.RequestException as e:
            logger.error(f"HTTP error communicating with server: {e}")
            raise
        except ValueError as e:
            logger.error(f"Failed to parse JSON response from server: {e}")
            raise

    def close(self):
        """Close the HTTP session."""
        self.session.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
