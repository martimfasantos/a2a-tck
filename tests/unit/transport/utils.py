import json
import logging
import os
import sys
import tempfile
import importlib
from typing import Dict, List, Optional, Any, AsyncIterator, Union
from urllib.parse import urlparse
import asyncio

import grpc
from google.protobuf.struct_pb2 import Struct
from google.protobuf.timestamp_pb2 import Timestamp

from a2a.client import Client, TransportError
from a2a.types import TransportProtocol

logger = logging.getLogger(__name__)


class A2AValidationError(TransportError):
    """Raised when gRPC response doesn't conform to A2A specification."""

    pass

def _validate_task_object(task: Dict[str, Any]) -> None:
    """
    Validate that a Task object conforms to A2A specification.

    Raises A2AValidationError if validation fails.
    """
    # Validate required fields per A2A specification
    required_fields = ["id", "contextId", "status", "kind"]
    for field in required_fields:
        if field not in task:
            raise A2AValidationError(f"Task missing required field '{field}'", TransportProtocol.grpc)
        if not task[field]:  # Check for empty string or None
            raise A2AValidationError(f"Task field '{field}' cannot be empty", TransportProtocol.grpc)

    # Validate 'kind' field
    if task["kind"] != "task":
        raise A2AValidationError(f"Task 'kind' must be 'task', got '{task['kind']}'", TransportProtocol.grpc)

    # Validate 'id' field (must be non-empty string)
    if not isinstance(task["id"], str) or not task["id"].strip():
        raise A2AValidationError(f"Task 'id' must be a non-empty string, got '{task['id']}'", TransportProtocol.grpc)

    # Validate 'contextId' field (must be non-empty string)
    if not isinstance(task["contextId"], str) or not task["contextId"].strip():
        raise A2AValidationError(f"Task 'contextId' must be a non-empty string, got '{task['contextId']}'", TransportProtocol.grpc)

    # Validate 'status' field
    if not isinstance(task["status"], dict):
        raise A2AValidationError(f"Task 'status' must be an object, got {type(task['status'])}", TransportProtocol.grpc)

    # Validate TaskStatus object
    status = task["status"]
    if "state" not in status:
        raise A2AValidationError("Task status missing required field 'state'", TransportProtocol.grpc)

    valid_states = ["submitted", "working", "completed", "failed", "canceled", "input-required", "rejected", "auth-required"]
    if status["state"] not in valid_states:
        raise A2AValidationError(
            f"Task status 'state' must be one of {valid_states}, got '{status['state']}'", TransportProtocol.grpc
        )

    # Validate optional fields
    if "history" in task:
        if not isinstance(task["history"], list):
            raise A2AValidationError(f"Task 'history' must be an array, got {type(task['history'])}", TransportProtocol.grpc)
        for i, message in enumerate(task["history"]):
            _validate_message_object(message, f"history[{i}]")

    if "artifacts" in task:
        if not isinstance(task["artifacts"], list):
            raise A2AValidationError(f"Task 'artifacts' must be an array, got {type(task['artifacts'])}", TransportProtocol.grpc)
        for i, artifact in enumerate(task["artifacts"]):
            _validate_artifact_object(artifact, f"artifacts[{i}]")


def _validate_message_object(message: Dict[str, Any], context: str = "message") -> None:
    """
    Validate that a Message object conforms to A2A specification.
    """
    required_fields = ["role", "parts", "messageId", "kind"]
    for field in required_fields:
        if field not in message:
            raise A2AValidationError(f"{context} missing required field '{field}'", TransportProtocol.grpc)

    # Validate 'kind' field
    if message["kind"] != "message":
        raise A2AValidationError(f"{context} 'kind' must be 'message', got '{message['kind']}'", TransportProtocol.grpc)

    # Validate 'role' field
    valid_roles = ["user", "agent"]
    if message["role"] not in valid_roles:
        raise A2AValidationError(f"{context} 'role' must be one of {valid_roles}, got '{message['role']}'", TransportProtocol.grpc)

    # Validate 'messageId' field
    if not isinstance(message["messageId"], str) or not message["messageId"].strip():
        raise A2AValidationError(f"{context} 'messageId' must be a non-empty string", TransportProtocol.grpc)

    # Validate 'parts' field
    if not isinstance(message["parts"], list):
        raise A2AValidationError(f"{context} 'parts' must be an array", TransportProtocol.grpc)

    for i, part in enumerate(message["parts"]):
        _validate_part_object(part, f"{context}.parts[{i}]")


def _validate_part_object(part: Dict[str, Any], context: str = "part") -> None:
    """
    Validate that a Part object conforms to A2A specification.
    """
    if "kind" not in part:
        raise A2AValidationError(f"{context} missing required field 'kind'", TransportProtocol.grpc)

    valid_kinds = ["text", "file", "data"]
    if part["kind"] not in valid_kinds:
        raise A2AValidationError(f"{context} 'kind' must be one of {valid_kinds}, got '{part['kind']}'", TransportProtocol.grpc)

    # Validate specific part types
    if part["kind"] == "text":
        if "text" not in part:
            raise A2AValidationError(f"{context} TextPart missing required field 'text'", TransportProtocol.grpc)
        if not isinstance(part["text"], str):
            raise A2AValidationError(f"{context} TextPart 'text' must be a string", TransportProtocol.grpc)

    elif part["kind"] == "file":
        if "file" not in part:
            raise A2AValidationError(f"{context} FilePart missing required field 'file'", TransportProtocol.grpc)
        file_obj = part["file"]
        if not isinstance(file_obj, dict):
            raise A2AValidationError(f"{context} FilePart 'file' must be an object", TransportProtocol.grpc)

        # FilePart must have either 'bytes' or 'uri'
        if "bytes" not in file_obj and "uri" not in file_obj:
            raise A2AValidationError(f"{context} FilePart must have either 'bytes' or 'uri'", TransportProtocol.grpc)

    elif part["kind"] == "data":
        if "data" not in part:
            raise A2AValidationError(f"{context} DataPart missing required field 'data'", TransportProtocol.grpc)


def _validate_artifact_object(artifact: Dict[str, Any], context: str = "artifact") -> None:
    """
    Validate that an Artifact object conforms to A2A specification.
    """
    required_fields = ["artifactId", "parts"]
    for field in required_fields:
        if field not in artifact:
            raise A2AValidationError(f"{context} missing required field '{field}'", TransportProtocol.grpc)

    # Validate 'artifactId' field
    if not isinstance(artifact["artifactId"], str) or not artifact["artifactId"].strip():
        raise A2AValidationError(f"{context} 'artifactId' must be a non-empty string", TransportProtocol.grpc)

    # Validate 'parts' field
    if not isinstance(artifact["parts"], list):
        raise A2AValidationError(f"{context} 'parts' must be an array", TransportProtocol.grpc)

    for i, part in enumerate(artifact["parts"]):
        _validate_part_object(part, f"{context}.parts[{i}]")


def _validate_agent_card_object(agent_card: Dict[str, Any]) -> None:
    """
    Validate that an AgentCard object conforms to A2A specification.
    """
    required_fields = ["protocolVersion", "name", "description", "url", "preferredTransport"]
    for field in required_fields:
        if field not in agent_card:
            raise A2AValidationError(f"AgentCard missing required field '{field}'", TransportProtocol.grpc)
        if not agent_card[field]:  # Check for empty string or None
            raise A2AValidationError(f"AgentCard field '{field}' cannot be empty", TransportProtocol.grpc)

    # Validate transport protocols
    valid_transports = ["JSONRPC", "GRPC", "HTTP+JSON"]
    if agent_card["preferredTransport"] not in valid_transports:
        raise A2AValidationError(f"AgentCard 'preferredTransport' must be one of {valid_transports}", TransportProtocol.grpc)


def _validate_push_notification_config_list(config_list: List[Dict[str, Any]]) -> None:
    """
    Validate that a list of TaskPushNotificationConfig objects conforms to A2A specification.
    """
    if not isinstance(config_list, list):
        raise A2AValidationError(f"Push notification config list must be an array, got {type(config_list)}", TransportProtocol.grpc)

    for i, config in enumerate(config_list):
        if not isinstance(config, dict):
            raise A2AValidationError(f"Push notification config[{i}] must be an object", TransportProtocol.grpc)

        # Validate TaskPushNotificationConfig structure
        required_fields = ["pushNotificationConfig", "taskId"]
        for field in required_fields:
            if field not in config:
                raise A2AValidationError(f"Push notification config[{i}] missing required field '{field}'", TransportProtocol.grpc)

        # Validate taskId
        if not isinstance(config["taskId"], str):
            raise A2AValidationError(f"Push notification config[{i}] 'taskId' must be a string", TransportProtocol.grpc)

        # Validate pushNotificationConfig structure
        push_config = config["pushNotificationConfig"]
        if not isinstance(push_config, dict):
            raise A2AValidationError(
                f"Push notification config[{i}] 'pushNotificationConfig' must be an object", TransportProtocol.grpc
            )

        # PushNotificationConfig required fields
        push_required_fields = ["id", "url"]
        for field in push_required_fields:
            if field not in push_config:
                raise A2AValidationError(
                    f"Push notification config[{i}].pushNotificationConfig missing required field '{field}'", TransportProtocol.grpc
                )


def _validate_a2a_response(response: Dict[str, Any], method_name: str) -> None:
    """
    Validate gRPC response conforms to A2A specification based on the method.

    Args:
        response: The response object from gRPC call
        method_name: The A2A method name (e.g., 'send_message', 'get_task', etc.)
    """
    try:
        if method_name in ["send_message", "get_task", "cancel_task"]:
            # These methods should return Task objects
            _validate_task_object(response)

        elif method_name == "get_agent_card":
            # This method should return AgentCard object
            _validate_agent_card_object(response)

        elif method_name == "send_message_response":
            # When send_message returns a Message object instead of Task
            _validate_message_object(response)

        elif method_name == "list_push_notification_configs":
            # This method should return a list of TaskPushNotificationConfig objects
            _validate_push_notification_config_list(response)

        elif method_name in ["set_push_notification_config", "get_push_notification_config"]:
            # These methods should return TaskPushNotificationConfig objects
            required_fields = ["pushNotificationConfig"]
            for field in required_fields:
                if field not in response:
                    raise A2AValidationError(
                        f"Push notification config response missing required field '{field}'", TransportProtocol.grpc
                    )

        # Add validation for other methods as needed

    except A2AValidationError:
        # Re-raise A2A validation errors
        raise
    except Exception as e:
        # Catch any other validation errors and wrap them
        raise A2AValidationError(f"Unexpected validation error for {method_name}: {str(e)}", TransportProtocol.grpc)