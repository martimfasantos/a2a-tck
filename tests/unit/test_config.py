"""
Unit tests for the config module with A2A v0.3.0 transport configuration.

Tests configuration management including transport-specific settings,
environment variable handling, and capability detection.
"""

import os
import pytest
from unittest.mock import patch

import tck.config as config
from a2a.types import TransportProtocol


@pytest.mark.core
class TestBasicConfiguration:
    """Test basic configuration functionality."""

    def test_set_and_get_config(self):
        """Test basic config setting and getting."""
        config.set_config("https://example.com", "all")

        assert config.get_sut_url() == "https://example.com"
        assert config.get_test_scope() == "all"

    def test_get_sut_url_from_env(self):
        """Test getting SUT URL from environment variable."""
        # Reset config first
        config._sut_url = None

        with patch.dict(os.environ, {"SUT_URL": "https://env-example.com"}):
            assert config.get_sut_url() == "https://env-example.com"

    def test_get_sut_url_not_configured(self):
        """Test error when SUT URL is not configured."""
        config._sut_url = None

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError, match="SUT URL is not configured"):
                config.get_sut_url()


@pytest.mark.core
class TestTransportConfiguration:
    """Test transport-specific configuration."""

    def setup_method(self):
        """Reset config before each test."""
        config.reset_transport_config()

    def test_transport_selection_strategy(self):
        """Test transport selection strategy configuration."""
        # Test default
        assert config.get_transport_selection_strategy() == "agent_preferred"

        # Test setting valid strategy
        config.set_transport_selection_strategy("prefer_grpc")
        assert config.get_transport_selection_strategy() == "prefer_grpc"

        # Test invalid strategy
        with pytest.raises(ValueError, match="Invalid transport selection strategy"):
            config.set_transport_selection_strategy("invalid_strategy")

    def test_transport_selection_strategy_from_env(self):
        """Test transport selection strategy from environment."""
        with patch.dict(os.environ, {"A2A_TRANSPORT_STRATEGY": "prefer_rest"}):
            assert config.get_transport_selection_strategy() == "prefer_rest"

    def test_preferred_transport(self):
        """Test preferred transport configuration."""
        # Test default
        assert config.get_preferred_transport() is None

        # Test setting preferred transport
        config.set_preferred_transport(TransportProtocol.grpc)
        assert config.get_preferred_transport() == TransportProtocol.grpc

        # Test clearing preferred transport
        config.set_preferred_transport(None)
        assert config.get_preferred_transport() is None

    def test_preferred_transport_from_env(self):
        """Test preferred transport from environment."""
        with patch.dict(os.environ, {"A2A_PREFERRED_TRANSPORT": "grpc"}):
            assert config.get_preferred_transport() == TransportProtocol.grpc

        with patch.dict(os.environ, {"A2A_PREFERRED_TRANSPORT": "jsonrpc"}):
            assert config.get_preferred_transport() == TransportProtocol.jsonrpc

        with patch.dict(os.environ, {"A2A_PREFERRED_TRANSPORT": "rest"}):
            assert config.get_preferred_transport() == TransportProtocol.http_json

    def test_disabled_transports(self):
        """Test disabled transports configuration."""
        # Test default
        assert config.get_disabled_transports() == []

        # Test setting disabled transports
        disabled = [TransportProtocol.grpc, TransportProtocol.http_json]
        config.set_disabled_transports(disabled)
        assert config.get_disabled_transports() == disabled

        # Test transport enabled/disabled check
        assert config.is_transport_enabled(TransportProtocol.jsonrpc) is True
        assert config.is_transport_enabled(TransportProtocol.grpc) is False
        assert config.is_transport_enabled(TransportProtocol.http_json) is False

    def test_disabled_transports_from_env(self):
        """Test disabled transports from environment."""
        with patch.dict(os.environ, {"A2A_DISABLED_TRANSPORTS": "grpc,rest"}):
            disabled = config.get_disabled_transports()
            assert TransportProtocol.grpc in disabled
            assert TransportProtocol.http_json in disabled
            assert TransportProtocol.jsonrpc not in disabled

    def test_transport_specific_config(self):
        """Test transport-specific configuration."""
        # Test setting and getting config
        grpc_config = {"timeout": "30", "compression": "gzip"}
        config.set_transport_specific_config(TransportProtocol.grpc, grpc_config)

        retrieved_config = config.get_transport_specific_config(TransportProtocol.grpc)
        assert retrieved_config == grpc_config

        # Test empty config for unconfigured transport
        rest_config = config.get_transport_specific_config(TransportProtocol.http_json)
        assert rest_config == {}

    def test_transport_specific_config_from_env(self):
        """Test transport-specific config from environment variables."""
        env_vars = {"A2A_GRPC_TIMEOUT": "60", "A2A_GRPC_COMPRESSION": "deflate", "A2A_REST_AUTH_HEADER": "Bearer token123"}

        with patch.dict(os.environ, env_vars):
            grpc_config = config.get_transport_specific_config(TransportProtocol.grpc)
            assert grpc_config["timeout"] == "60"
            assert grpc_config["compression"] == "deflate"

            rest_config = config.get_transport_specific_config(TransportProtocol.http_json)
            assert rest_config["auth_header"] == "Bearer token123"

    def test_transport_equivalence_testing(self):
        """Test transport equivalence testing configuration."""
        # Test default
        assert config.is_transport_equivalence_testing_enabled() is True

        # Test disabling
        config.set_enable_transport_equivalence_testing(False)
        assert config.is_transport_equivalence_testing_enabled() is False

        # Test enabling
        config.set_enable_transport_equivalence_testing(True)
        assert config.is_transport_equivalence_testing_enabled() is True

    def test_transport_equivalence_testing_from_env(self):
        """Test transport equivalence testing from environment."""
        # Test enabling via env
        with patch.dict(os.environ, {"A2A_ENABLE_EQUIVALENCE_TESTING": "true"}):
            assert config.is_transport_equivalence_testing_enabled() is True

        with patch.dict(os.environ, {"A2A_ENABLE_EQUIVALENCE_TESTING": "1"}):
            assert config.is_transport_equivalence_testing_enabled() is True

        # Test disabling via env
        with patch.dict(os.environ, {"A2A_ENABLE_EQUIVALENCE_TESTING": "false"}):
            assert config.is_transport_equivalence_testing_enabled() is False

        with patch.dict(os.environ, {"A2A_ENABLE_EQUIVALENCE_TESTING": "0"}):
            assert config.is_transport_equivalence_testing_enabled() is False

    def test_transport_capabilities(self):
        """Test transport capabilities summary."""
        # Set up test configuration
        config.set_preferred_transport(TransportProtocol.grpc)
        config.set_disabled_transports([TransportProtocol.http_json])
        config.set_transport_selection_strategy("prefer_grpc")
        config.set_enable_transport_equivalence_testing(True)

        capabilities = config.get_transport_capabilities()

        assert capabilities["jsonrpc_enabled"] is True
        assert capabilities["grpc_enabled"] is True
        assert capabilities["rest_enabled"] is False
        assert capabilities["equivalence_testing_enabled"] is True
        assert capabilities["preferred_transport"] == "grpc"
        assert capabilities["selection_strategy"] == "prefer_grpc"

    def test_reset_transport_config(self):
        """Test resetting transport configuration."""
        # Change all settings
        config.set_transport_selection_strategy("prefer_rest")
        config.set_preferred_transport(TransportProtocol.http_json)
        config.set_disabled_transports([TransportProtocol.grpc])
        config.set_enable_transport_equivalence_testing(False)
        config.set_transport_specific_config(TransportProtocol.jsonrpc, {"test": "value"})

        # Reset and verify defaults
        config.reset_transport_config()

        assert config.get_transport_selection_strategy() == "agent_preferred"
        assert config.get_preferred_transport() is None
        assert config.get_disabled_transports() == []
        assert config.is_transport_equivalence_testing_enabled() is True
        assert config.get_transport_specific_config(TransportProtocol.jsonrpc) == {}


@pytest.mark.core
class TestTransportParsing:
    """Test transport parsing utilities."""

    def test_parse_transport_from_env(self):
        """Test parsing transport from environment string."""
        # Test valid transports
        assert config._parse_transport_from_env("jsonrpc") == TransportProtocol.jsonrpc
        assert config._parse_transport_from_env("json-rpc") == TransportProtocol.jsonrpc
        assert config._parse_transport_from_env("grpc") == TransportProtocol.grpc
        assert config._parse_transport_from_env("rest") == TransportProtocol.http_json
        assert config._parse_transport_from_env("http") == TransportProtocol.http_json

        # Test case insensitive
        assert config._parse_transport_from_env("GRPC") == TransportProtocol.grpc
        assert config._parse_transport_from_env("Rest") == TransportProtocol.http_json

        # Test invalid transport
        assert config._parse_transport_from_env("invalid") is None

    def test_parse_transport_list_from_env(self):
        """Test parsing transport list from environment string."""
        # Test single transport
        transports = config._parse_transport_list_from_env("grpc")
        assert transports == [TransportProtocol.grpc]

        # Test multiple transports
        transports = config._parse_transport_list_from_env("jsonrpc,grpc,rest")
        expected = [TransportProtocol.jsonrpc, TransportProtocol.grpc, TransportProtocol.http_json]
        assert transports == expected

        # Test with spaces
        transports = config._parse_transport_list_from_env("jsonrpc, grpc , rest")
        assert transports == expected

        # Test with invalid transport (should be filtered out)
        transports = config._parse_transport_list_from_env("jsonrpc,invalid,grpc")
        assert transports == [TransportProtocol.jsonrpc, TransportProtocol.grpc]

        # Test empty string
        transports = config._parse_transport_list_from_env("")
        assert transports == []
