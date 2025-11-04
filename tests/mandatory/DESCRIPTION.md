# 🧭 Guide to Mandatory Tests in the A2A-TCK (`tests/mandatory`)

This guide summarises **all tests in the `tests/mandatory` folder** of the [A2A Test Compatibility Kit (TCK)](https://github.com/a2aproject/a2a-tck).
Each subsection explains the **purpose** and **use case** of the tests inside its sub-directory.
Use this to ensure your A2A agent/server correctly implements and passes all **mandatory conformance tests**.

---

## 🧩 Authentication Tests (`tests/mandatory/authentication`)

These tests verify that A2A agents **expose and enforce authentication schemes** correctly, with consistent behaviour across transport types.

| **Test Name**                                    | **Objective / Use-Case**                                                                                                                                                    |
| ------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`test_security_scheme_structure_compliance`**  | Ensures that security schemes declared in the agent’s card follow the OpenAPI 3.0 security scheme structure. Verifies correct `type`, `scheme`, `bearerFormat` fields, etc. |
| **`test_authentication_transport_consistency`**  | Confirms authentication enforcement is consistent across transports (HTTP, JSON-RPC). Requests needing authentication must produce uniform error codes and messages.        |
| **`test_security_error_response_compliance`**    | Verifies that missing or invalid credentials return correct A2A error formats, proper HTTP status codes (401/403), and `WWW-Authenticate` headers.                          |
| **`test_oauth2_metadata_url_validation`**        | Checks that OAuth2 schemes with an `oauth2MetadataUrl` expose a valid HTTPS URL and that metadata is retrievable.                                                           |
| **`test_mutual_tls_scheme_declaration`**         | Ensures mutual TLS usage is correctly declared with a `mutualTLS` scheme and no extra properties.                                                                           |
| **`test_authentication_required_when_declared`** | From `test_auth_enforcement.py`: verifies unauthenticated requests to protected endpoints return 401/403 and follow A2A error format.                                       |
| **`test_invalid_credentials_rejected`**          | Confirms invalid credentials for each scheme are rejected consistently.                                                                                                     |
| **`test_authentication_scheme_consistency`**     | Validates `securitySchemes` structure and that security requirements reference declared schemes.                                                                            |

---

## ⚙️ JSON-RPC Tests (`tests/mandatory/jsonrpc`)

These enforce **JSON-RPC 2.0 compliance** and **A2A-specific error codes**.

### 🧱 Error Code Tests (`test_a2a_error_codes.py` and `test_a2a_error_codes_enhanced.py`)

| **Test Name**                                      | **Objective / Use-Case**                                                                                       |
| -------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| `test_push_notification_not_supported_error_32003` | Ensures agents return error `-32003` when push-notifications are unsupported.                                  |
| `test_unsupported_operation_error_32004`           | Verifies unsupported operations produce `-32004`. The enhanced version tests extreme/malformed requests.       |
| `test_content_type_not_supported_error_32005`      | Ensures unsupported MIME types (e.g., video upload when only text allowed) produce `-32005`.                   |
| `test_invalid_agent_response_error_32006`          | Ensures `-32006` is returned for internal agent response errors. Enhanced variant tests complex chained tasks. |
| `test_a2a_error_code_coverage_summary`             | Verifies all A2A-specific error codes (`-32001`–`-32006`) are implemented or documented.                       |

### 🧩 JSON-RPC Compliance (`test_json_rpc_compliance.py`)

| **Test Name**                            | **Objective / Use-Case**                                                                                                       |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `test_rejects_malformed_json`            | Ensures malformed JSON returns `-32700` (Parse Error).                                                                         |
| `test_rejects_invalid_json_rpc_requests` | Ensures invalid requests missing `jsonrpc`, `method`, or `id` fields return proper error codes (`-32600`, `-32601`, `-32602`). |
| `test_rejects_unknown_method`            | Returns `-32601` for unknown methods.                                                                                          |
| `test_rejects_invalid_params`            | Returns `-32602` when parameters are wrong.                                                                                    |

### 🚨 Protocol Violations (`test_protocol_violations.py`)

| **Test Name**                  | **Objective / Use-Case**                                                         |
| ------------------------------ | -------------------------------------------------------------------------------- |
| `test_duplicate_request_ids`   | Validates duplicate request ID handling — must not corrupt response pairing.     |
| `test_invalid_jsonrpc_version` | Rejects any JSON-RPC version other than “2.0”.                                   |
| `test_missing_method_field`    | Rejects requests without a `method` field.                                       |
| `test_raw_invalid_json`        | Tests raw malformed JSON, expecting HTTP 400 or JSON-RPC Parse Error (`-32700`). |

---

## 🧠 Protocol Tests (`tests/mandatory/protocol`)

These cover **A2A protocol semantics** and new features introduced in **v0.3.0** — including agent card validation, method mapping, tasks, and state transitions.

### 🪪 Agent Card Validation

| **Test Name**                                  | **Objective / Use-Case**                                                                                                                   |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `test_agent_card_availability`                 | Ensures the `/agent/card` endpoint exists and returns valid JSON.                                                                          |
| `test_mandatory_fields_present`                | Checks all mandatory fields: `capabilities`, `defaultInputModes`, `defaultOutputModes`, `description`, `name`, `skills`, `url`, `version`. |
| `test_mandatory_field_types`                   | Ensures fields have correct data types.                                                                                                    |
| `test_agent_card_capabilities_mandatory`       | Verifies the `capabilities` field exists as an object.                                                                                     |
| `test_agent_card_skills_mandatory`             | Ensures a non-empty `skills` array with correct structure (`id`, `name`, `description`, `tags`).                                           |
| `test_agent_card_input_output_modes_mandatory` | Confirms `defaultInputModes`/`defaultOutputModes` exist and contain valid strings.                                                         |
| `test_agent_card_basic_info_mandatory`         | Checks `name`, `description`, `url`, `version` are valid and non-empty.                                                                    |

### 🚀 New A2A v0.3.0 Methods

| **Test Name**                                   | **Objective / Use-Case**                                                                |
| ----------------------------------------------- | --------------------------------------------------------------------------------------- |
| `test_authenticated_extended_card_without_auth` | Unauthenticated requests to `getAuthenticatedExtendedCard` must be rejected (401/403).  |
| `test_authenticated_extended_card_with_auth`    | Authenticated calls must return the extended card per schema.                           |
| `test_tasks_list_with_existing_tasks`           | Confirms `tasks/list` returns existing tasks properly structured.                       |
| `test_core_method_mapping_compliance`           | Validates core methods (message/send, tasks/get, etc.) map correctly across transports. |
| `test_transport_specific_method_naming`         | Checks naming convention per transport (REST, gRPC, JSON-RPC).                          |
| `test_grpc_specific_features`                   | Ensures gRPC features like streaming and metadata are supported.                        |
| `test_rest_specific_features`                   | Validates REST-specific caching and status codes.                                       |
| `test_jsonrpc_specific_features`                | Confirms JSON-RPC batch and extension support.                                          |

### 🧩 Transport Compliance (`test_a2a_v030_transport_compliance.py`)

| **Test Name**                            | **Objective / Use-Case**                                      |
| ---------------------------------------- | ------------------------------------------------------------- |
| `test_transport_compliance_validation`   | Validates each transport implements all required methods.     |
| `test_required_method_availability`      | Checks existence of mandatory core methods across transports. |
| `test_transport_specific_features`       | Ensures transport-specific behavior follows spec.             |
| `test_multi_transport_method_mapping`    | Confirms methods map consistently between transports.         |
| `test_comprehensive_a2a_v030_compliance` | Runs full multi-transport compliance verification.            |

### 💬 Message and Task Methods

| **Test Name**                        | **Objective / Use-Case**                                                               |
| ------------------------------------ | -------------------------------------------------------------------------------------- |
| `test_message_send_valid_text`       | Ensures message/send works with text content and returns valid Task or Message object. |
| `test_message_send_invalid_params`   | Tests error `-32602` when required parameters missing.                                 |
| `test_message_send_continue_task`    | Ensures continued messages on existing tasks don’t spawn new ones.                     |
| `test_tasks_cancel_valid`            | Cancels existing task and verifies result.                                             |
| `test_tasks_cancel_nonexistent`      | Cancelling non-existent tasks returns `-32001`.                                        |
| `test_tasks_get_valid`               | Retrieves task with proper fields and states.                                          |
| `test_tasks_get_with_history_length` | Validates history truncation when `historyLength` specified.                           |
| `test_tasks_get_nonexistent`         | Retrieving non-existent task returns `-32001`.                                         |
| `test_task_history_length`           | Confirms `historyLength` affects number of history entries.                            |

### 🪪 Extended Agent Card (`test_extended_agent_card.py`)

| **Test Name**                                      | **Objective / Use-Case**                                        |
| -------------------------------------------------- | --------------------------------------------------------------- |
| `test_extended_agent_card_endpoint_exists`         | Ensures `/v1/card` endpoint exists and requires authentication. |
| `test_extended_agent_card_authentication_required` | Confirms 401/403 on missing credentials.                        |
| `test_extended_agent_card_invalid_authentication`  | Ensures invalid credentials rejected correctly.                 |
| `test_extended_agent_card_response_format`         | Validates response structure after authentication.              |

### 🔄 State & History Tests

| **Test Name**              | **Objective / Use-Case**                                                 |
| -------------------------- | ------------------------------------------------------------------------ |
| `test_task_history_length` | Validates `historyLength` parameter controls number of entries returned. |

---

## ✅ Quality Tests (`tests/mandatory/quality`)

| **Test Name**                                | **Objective / Use-Case**                                               |
| -------------------------------------------- | ---------------------------------------------------------------------- |
| `test_invalid_method_error_validation`       | Ensures invalid methods return `-32601` with meaningful messages.      |
| `test_invalid_params_error_validation`       | Confirms malformed parameters return `-32602` with correct structure.  |
| `test_nonexistent_resource_error_validation` | Verifies proper A2A error codes for missing resources (`-32001`).      |
| `test_error_consistency_across_methods`      | Checks same errors produce consistent messages across all operations.  |
| `test_error_response_completeness`           | Ensures every error includes `code`, `message`, and contextual `data`. |

---

## 🔒 Security Tests (`tests/mandatory/security`)

### 🪪 Agent Card Security (`test_agent_card_security.py`)

| **Test Name**                           | **Objective / Use-Case**                                    |
| --------------------------------------- | ----------------------------------------------------------- |
| `test_public_agent_card_access_control` | Ensures public card doesn’t expose sensitive details.       |
| `test_extended_card_access_controls`    | Confirms extended card requires authentication.             |
| `test_authentication_scheme_validation` | Validates rejection of invalid credentials.                 |
| `test_sensitive_information_protection` | Scans for secrets or internal hostnames.                    |
| `test_security_scheme_consistency`      | Ensures consistent and valid OpenAPI 3.x `securitySchemes`. |

### 🔐 TLS & Certificate Validation (`test_certificate_validation.py`)

| **Test Name**                             | **Objective / Use-Case**               |
| ----------------------------------------- | -------------------------------------- |
| `test_certificate_chain_trust_validation` | Valid chain signed by trusted CA.      |
| `test_hostname_verification`              | CN/SAN must match hostname.            |
| `test_certificate_revocation_status`      | Optionally checks OCSP/CRL.            |
| `test_invalid_certificate_rejection`      | Rejects expired or mismatched certs.   |
| `test_certificate_security_headers`       | Verifies HSTS, CT, and secure headers. |

### 🧠 In-Task Authentication (`test_in_task_authentication.py`)

| **Test Name**                           | **Objective / Use-Case**                                |
| --------------------------------------- | ------------------------------------------------------- |
| `test_auth_required_state_support`      | Verifies `auth-required` state in tasks.                |
| `test_in_task_authentication_workflow`  | Tests end-to-end in-task auth flow.                     |
| `test_authentication_challenge_headers` | Checks proper 401/403 and headers.                      |
| `test_invalid_authentication_handling`  | Ensures invalid credentials are rejected.               |
| `test_auth_state_transitions`           | Confirms correct transitions in/out of `auth-required`. |

### 🔏 TLS Configuration Enhanced (`test_tls_configuration_enhanced.py`)

| **Test Name**                            | **Objective / Use-Case**                              |
| ---------------------------------------- | ----------------------------------------------------- |
| `test_tls_protocol_version_security`     | TLS ≥ 1.2 required; old versions rejected.            |
| `test_cipher_suite_security_analysis`    | Evaluates cipher suite strength and FS.               |
| `test_certificate_chain_validation`      | Checks expiration and key strength.                   |
| `test_tls_security_features`             | Validates ALPN, no compression, FS, TLS 1.3 features. |
| `test_tls_implementation_best_practices` | Assigns overall TLS security grade.                   |

---

## 🌐 Transport Tests (`tests/mandatory/transport`)

Ensure consistent behaviour and equivalence across JSON-RPC, REST, and gRPC transports.

| **Test Name**                           | **Objective / Use-Case**                                               |
| --------------------------------------- | ---------------------------------------------------------------------- |
| `test_task_retrieval_equivalence`       | Ensures tasks retrieved via all transports are identical.              |
| `test_agent_card_access_equivalence`    | Confirms identical card data across transports.                        |
| `test_error_handling_equivalence`       | Validates consistent error codes/messages.                             |
| `test_performance_equivalence`          | Checks comparable performance across transports.                       |
| `test_message_sending_equivalence`      | Ensures consistent message/send responses.                             |
| `test_concurrent_operation_equivalence` | Verifies no interference during parallel operations across transports. |

---

## 🧾 Summary

| **Area**       | **Folder**        | **Focus**                          |
| -------------- | ----------------- | ---------------------------------- |
| Authentication | `authentication/` | OAuth2, mTLS, scope enforcement    |
| JSON-RPC       | `jsonrpc/`        | Protocol & A2A error compliance    |
| Protocol       | `protocol/`       | Card schema, state, task lifecycle |
| Quality        | `quality/`        | Error response consistency         |
| Security       | `security/`       | TLS, auth, data protection         |
| Transport      | `transport/`      | Cross-transport equivalence        |

---

### **References**

* [A2A Protocol Specification v0.3.0](https://github.com/a2aproject/specification)
* [A2A-TCK Source Code](https://github.com/a2aproject/a2a-tck)
* [JSON-RPC 2.0 Specification](https://www.jsonrpc.org/specification)

