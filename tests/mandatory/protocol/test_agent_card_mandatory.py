"""
A2A Protocol Specification: Agent Card mandatory fields validation tests.

This test suite validates the mandatory fields and structure of the SUT's Agent Card
according to the A2A specification: https://google.github.io/A2A/specification/#agent-card
"""

import logging
import pytest

from a2a.types import (
    AgentCard, 
    AgentCapabilities, 
    AgentSkill, 
    AgentInterface, 
    AgentProvider,
    TransportProtocol,
)
from tck import agent_card_utils

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def fetched_agent_card(agent_card_data):
    """
    Fixture to reuse the global agent_card_data fixture or fetch it if not available.

    This adds an extra layer to handle cases where the agent_card_data fixture might be None
    because of the --skip-agent-card flag.
    """
    if agent_card_data is not None and AgentCard.model_validate(agent_card_data):
        return agent_card_data

    # Try to fetch it directly for this test suite
    logger.info("Global agent_card_data is None, attempting to fetch directly")
    agent_card = agent_card_utils.fetch_agent_card(agent_card_data)

    if agent_card is None:
        pytest.skip("Failed to fetch Agent Card - skipping Agent Card validation tests")

    return agent_card


def test_agent_card_mandatory_fields(fetched_agent_card: AgentCard):
    """
    MANDATORY: A2A Specification §5.5 - AgentCard Required Fields

    Tests that all mandatory fields are present in the Agent Card.
    These fields are required by the A2A specification for all agents.

    Failure Impact: Critical - violates A2A specification compliance
    Fix Suggestion: Ensure all mandatory fields are included in Agent Card

    Asserts:
        - All required fields are present
        - Field types match specification requirements
        - Basic structure is valid
    """
    assert isinstance(fetched_agent_card, dict), "Agent Card must be an object"

    # Use Pydantic's model_validate to validate all required fields and structure
    try:
        AgentCard.model_validate(fetched_agent_card)
    except Exception as e:
        # Get required fields dynamically from the AgentCard model
        required_fields = [
            field_name for field_name, field_info in AgentCard.model_fields.items()
            if field_info.is_required()
        ]
        # Validate presence of each required field
        for field in required_fields:
            assert field in fetched_agent_card, f"Required field '{field}' missing from Agent Card"
            assert fetched_agent_card[field] is not None, f"Required field '{field}' cannot be null"
        
        # If validation failed for another reason, show the Pydantic error
        assert False, f"Agent Card validation failed: {str(e)}"


def test_agent_card_capabilities_mandatory(fetched_agent_card):
    """
    MANDATORY: A2A Specification §5.5.2 - AgentCapabilities Field Required

    Tests that the capabilities field is present and properly structured.
    The capabilities field is mandatory in the Agent Card, even if individual
    capabilities within it are optional.

    Failure Impact: Critical - violates A2A specification compliance
    Fix Suggestion: Include capabilities object in Agent Card

    Asserts:
        - capabilities field is present
        - capabilities is an object (not null/undefined)
        - capabilities field has proper structure
    """
    assert "capabilities" in fetched_agent_card, "Agent Card must include capabilities field"

    capabilities = fetched_agent_card["capabilities"]
    assert capabilities is not None, "capabilities field cannot be null"
    
    # Use Pydantic's model_validate to validate AgentCapabilities structure
    try:
        AgentCapabilities.model_validate(capabilities)
    except Exception as e:
        assert False, f"AgentCapabilities validation failed: {str(e)}"


def test_agent_card_skills_mandatory(fetched_agent_card):
    """
    MANDATORY: A2A Specification §5.5.6 - Skills Array Required

    Tests that the skills field is present and properly structured.
    Skills define what the agent can do and are mandatory.

    Failure Impact: Critical - violates A2A specification compliance
    Fix Suggestion: Include skills array in Agent Card

    Asserts:
        - skills field is present
        - skills is an array
        - skills array is not empty
        - each skill has required fields
    """
    assert "skills" in fetched_agent_card, "Agent Card must include skills field"

    skills = fetched_agent_card["skills"]
    assert skills is not None, "skills field cannot be null"
    assert isinstance(skills, list), "skills must be an array"
    assert len(skills) > 0, "skills array cannot be empty"

    # Validate each skill using Pydantic's AgentSkill model
    for i, skill in enumerate(skills):
        try:
            AgentSkill.model_validate(skill)
        except Exception as e:
            # Get required fields dynamically from AgentSkill model
            required_fields = [
                field_name for field_name, field_info in AgentSkill.model_fields.items()
                if field_info.is_required()
            ]
            
            for field in required_fields:
                assert field in skill, f"skill at index {i} missing required field '{field}'"
                assert skill[field] is not None, f"skill at index {i} field '{field}' cannot be null"
            
            # If validation failed for another reason, show the Pydantic error
            assert False, f"skill at index {i} validation failed: {str(e)}"


def test_agent_card_input_output_modes_mandatory(fetched_agent_card):
    """
    MANDATORY: A2A Specification §5.5.3/5.5.4 - Input/Output Modes Required

    Tests that defaultInputModes and defaultOutputModes are present and valid.
    These define the media types the agent supports.

    Failure Impact: Critical - violates A2A specification compliance
    Fix Suggestion: Include input/output mode arrays in Agent Card

    Asserts:
        - default_input_modes field is present and is array
        - default_output_modes field is present and is array
        - modes are non-empty strings
    """
    # Check default_input_modes (AgentCard uses snake_case field names)
    assert "default_input_modes" in fetched_agent_card, "Agent Card must include default_input_modes field"
    input_modes = fetched_agent_card["default_input_modes"]
    assert input_modes is not None, "default_input_modes field cannot be null"
    assert isinstance(input_modes, list), "default_input_modes must be an array"

    for i, mode in enumerate(input_modes):
        assert isinstance(mode, str), f"default_input_modes[{i}] must be a string"
        assert mode.strip(), f"default_input_modes[{i}] cannot be empty"

    # Check default_output_modes (AgentCard uses snake_case field names)
    assert "default_output_modes" in fetched_agent_card, "Agent Card must include default_output_modes field"
    output_modes = fetched_agent_card["default_output_modes"]
    assert output_modes is not None, "default_output_modes field cannot be null"
    assert isinstance(output_modes, list), "default_output_modes must be an array"

    for i, mode in enumerate(output_modes):
        assert isinstance(mode, str), f"default_output_modes[{i}] must be a string"
        assert mode.strip(), f"default_output_modes[{i}] cannot be empty"


def test_agent_card_basic_info_mandatory(fetched_agent_card):
    """
    MANDATORY: A2A Specification §5.5.1 - Basic Agent Information Required

    Tests that basic agent information fields are present and valid.
    These provide essential information about the agent.

    Failure Impact: Critical - violates A2A specification compliance
    Fix Suggestion: Include all required basic information fields

    Asserts:
        - name, description, url, version are present
        - fields are non-empty strings
        - url appears to be a valid URL format
    """
    # Basic info fields are already validated by AgentCard.model_validate in test_agent_card_mandatory_fields
    # Here we add additional semantic validation beyond type checking
    
    # Check name is not empty
    assert "name" in fetched_agent_card, "Agent Card must include name field"
    assert fetched_agent_card["name"] and fetched_agent_card["name"].strip(), "name cannot be empty"

    # Check description is not empty
    assert "description" in fetched_agent_card, "Agent Card must include description field"
    assert fetched_agent_card["description"] and fetched_agent_card["description"].strip(), "description cannot be empty"

    # Check url is valid HTTP/HTTPS URL
    assert "url" in fetched_agent_card, "Agent Card must include url field"
    url = fetched_agent_card["url"]
    assert url and url.strip(), "url cannot be empty"
    assert url.startswith(("http://", "https://")), "url must be a valid HTTP/HTTPS URL"

    # Check version is not empty
    assert "version" in fetched_agent_card, "Agent Card must include version field"
    assert fetched_agent_card["version"] and fetched_agent_card["version"].strip(), "version cannot be empty"


def test_agent_card_protocol_version(fetched_agent_card):
    """
    MANDATORY: A2A Specification §5.5 - Protocol Version Validation

    Tests that the protocol version is present and valid.
    The protocol version indicates which version of the A2A spec the agent supports.

    Failure Impact: Medium - May cause compatibility issues
    Fix Suggestion: Include valid protocol_version in Agent Card (e.g., "0.3.0")

    Asserts:
        - protocol_version field is present
        - protocol_version follows semantic versioning format
    """
    assert "protocol_version" in fetched_agent_card, "Agent Card must include protocol_version field"
    protocol_version = fetched_agent_card["protocol_version"]
    assert protocol_version, "protocol_version cannot be empty"
    
    # Validate semantic versioning format (basic check)
    import re
    semver_pattern = r'^\d+\.\d+\.\d+$'
    assert re.match(semver_pattern, protocol_version), \
        f"protocol_version '{protocol_version}' must follow semantic versioning (e.g., '0.3.0')"


def test_agent_card_preferred_transport(fetched_agent_card):
    """
    OPTIONAL: A2A Specification §5.5 - Preferred Transport Validation

    Tests that the preferred transport is valid if present.
    The preferred transport indicates the agent's preferred communication protocol.

    Failure Impact: Low - Falls back to defaults if invalid
    Fix Suggestion: Use valid transport value: 'JSONRPC', 'GRPC', or 'HTTP+JSON'

    Asserts:
        - preferred_transport (if present) is a valid transport protocol
    """
    if "preferred_transport" in fetched_agent_card and fetched_agent_card["preferred_transport"]:
        preferred_transport = fetched_agent_card["preferred_transport"]
        valid_transports = [t.value for t in TransportProtocol]
        assert preferred_transport in valid_transports, \
            f"preferred_transport '{preferred_transport}' must be one of {valid_transports}"


def test_agent_card_additional_interfaces(fetched_agent_card):
    """
    OPTIONAL: A2A Specification §5.5 - Additional Interfaces Validation

    Tests that additional interfaces are properly structured if present.
    Additional interfaces provide alternative ways to communicate with the agent.

    Failure Impact: Medium - May prevent multi-transport scenarios
    Fix Suggestion: Ensure each interface has required fields: transport, url

    Asserts:
        - additional_interfaces (if present) is an array
        - each interface has required fields
        - each interface validates against AgentInterface model
    """
    if "additional_interfaces" in fetched_agent_card and fetched_agent_card["additional_interfaces"]:
        interfaces = fetched_agent_card["additional_interfaces"]
        assert isinstance(interfaces, list), "additional_interfaces must be an array"
        
        for i, interface in enumerate(interfaces):
            try:
                AgentInterface.model_validate(interface)
            except Exception as e:
                # Get required fields dynamically
                required_fields = [
                    field_name for field_name, field_info in AgentInterface.model_fields.items()
                    if field_info.is_required()
                ]
                
                for field in required_fields:
                    assert field in interface, \
                        f"additional_interfaces[{i}] missing required field '{field}'"
                    assert interface[field] is not None, \
                        f"additional_interfaces[{i}] field '{field}' cannot be null"
                
                assert False, f"additional_interfaces[{i}] validation failed: {str(e)}"


def test_agent_card_provider(fetched_agent_card):
    """
    OPTIONAL: A2A Specification §5.5 - Provider Information Validation

    Tests that provider information is properly structured if present.
    Provider information identifies the organization or entity behind the agent.

    Failure Impact: Low - Informational only
    Fix Suggestion: Include provider with organization and url fields

    Asserts:
        - provider (if present) is an object
        - provider has required fields
        - provider validates against AgentProvider model
    """
    if "provider" in fetched_agent_card and fetched_agent_card["provider"]:
        provider = fetched_agent_card["provider"]
        assert isinstance(provider, dict), "provider must be an object"
        
        try:
            AgentProvider.model_validate(provider)
        except Exception as e:
            # Get required fields dynamically
            required_fields = [
                field_name for field_name, field_info in AgentProvider.model_fields.items()
                if field_info.is_required()
            ]
            
            for field in required_fields:
                assert field in provider, f"provider missing required field '{field}'"
                assert provider[field] is not None, f"provider field '{field}' cannot be null"
            
            assert False, f"provider validation failed: {str(e)}"


def test_agent_card_optional_urls(fetched_agent_card):
    """
    OPTIONAL: A2A Specification §5.5 - Optional URL Fields Validation

    Tests that optional URL fields are valid URLs if present.
    These provide additional resources about the agent.

    Failure Impact: Low - Informational only
    Fix Suggestion: Ensure URLs are valid HTTP/HTTPS URLs

    Asserts:
        - documentation_url (if present) is a valid URL
        - icon_url (if present) is a valid URL
    """
    # Check documentation_url if present
    if "documentation_url" in fetched_agent_card and fetched_agent_card["documentation_url"]:
        doc_url = fetched_agent_card["documentation_url"]
        assert isinstance(doc_url, str), "documentation_url must be a string"
        assert doc_url.strip(), "documentation_url cannot be empty if provided"
        assert doc_url.startswith(("http://", "https://")), \
            "documentation_url must be a valid HTTP/HTTPS URL"
    
    # Check icon_url if present
    if "icon_url" in fetched_agent_card and fetched_agent_card["icon_url"]:
        icon_url = fetched_agent_card["icon_url"]
        assert isinstance(icon_url, str), "icon_url must be a string"
        assert icon_url.strip(), "icon_url cannot be empty if provided"
        assert icon_url.startswith(("http://", "https://")), \
            "icon_url must be a valid HTTP/HTTPS URL"


def test_agent_card_skills_structure(fetched_agent_card):
    """
    MANDATORY: A2A Specification §5.5.6 - Skills Structure Validation

    Tests that skills have proper structure with all required and optional fields.
    Skills define the agent's capabilities in detail.

    Failure Impact: Critical - Skills define agent capabilities
    Fix Suggestion: Ensure each skill has id, name, description, and tags

    Asserts:
        - Each skill has required fields (id, name, description, tags)
        - Skill IDs are unique
        - Tags are non-empty arrays of strings
    """
    assert "skills" in fetched_agent_card, "Agent Card must include skills field"
    skills = fetched_agent_card["skills"]
    
    skill_ids = set()
    for i, skill in enumerate(skills):
        
        assert isinstance(skill, AgentSkill), f"Skill at index {i} must be an object"
        
        # Check for duplicate skill IDs
        if "id" in skill:
            skill_id = skill["id"]
            assert skill_id not in skill_ids, f"Duplicate skill id '{skill_id}' found at index {i}"
            skill_ids.add(skill_id)
        
        # Validate tags structure
        if "tags" in skill:
            tags = skill["tags"]
            assert isinstance(tags, list), f"skill[{i}].tags must be an array"
            for j, tag in enumerate(tags):
                assert isinstance(tag, str), f"skill[{i}].tags[{j}] must be a string"
                assert tag.strip(), f"skill[{i}].tags[{j}] cannot be empty"


def test_agent_card_capabilities_structure(fetched_agent_card):
    """
    MANDATORY: A2A Specification §5.5.2 - Capabilities Structure Validation

    Tests that capabilities have proper boolean values.
    Capabilities indicate which optional features the agent supports.

    Failure Impact: Medium - May cause incorrect feature detection
    Fix Suggestion: Ensure capability values are booleans

    Asserts:
        - streaming (if present) is a boolean
        - push_notifications (if present) is a boolean
        - state_transition_history (if present) is a boolean
    """
    assert "capabilities" in fetched_agent_card, "Agent Card must include capabilities field"
    capabilities = fetched_agent_card["capabilities"]
    
    assert AgentCapabilities.model_validate(capabilities), "capabilities must conform to AgentCapabilities model"
    
    boolean_fields = ["streaming", "push_notifications", "state_transition_history"]
    for field in boolean_fields:
        if field in capabilities and capabilities[field] is not None:
            assert isinstance(capabilities[field], bool), \
                f"capabilities.{field} must be a boolean, got {type(capabilities[field])}"
