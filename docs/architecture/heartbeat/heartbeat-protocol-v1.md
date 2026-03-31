# Heartbeat Protocol v1

This document is the source of truth for the heartbeat contract used across `navpay-android` and `navpay-phonepe`.

## Scope

This protocol defines:
- request envelope fields
- response envelope fields
- command and ACK semantics
- standard `ping` command semantics
- compatibility and versioning rules

It does not define:
- transport implementation
- scheduler implementation
- app lifecycle integration
- retry/backoff execution details in a specific project

Those are adapter concerns and may differ per project.

## Versioning

The protocol version is explicit and mandatory.

- Request header: `x-navpay-hb-version`
- Canonical protocol version for this document: `1`
- New protocol capabilities must be introduced as a versioned change, not as silent field drift

Compatibility rules:
- Additive fields are allowed if they are optional and ignored by older implementations.
- Removing or renaming a required field is breaking.
- Changing command meaning is breaking.
- Changing ACK semantics is breaking.
- `ping` is always defined by this protocol and must remain backward compatible across adapters.
- If a change cannot be expressed as backward-compatible additive behavior, it requires a new protocol version.

## Request Envelope

The heartbeat request envelope is the canonical shape that adapters must produce before transport.

Required fields:
- `timestamp` - client-side timestamp in milliseconds
- `appName` - logical app identifier, for example `navpay` or `phonepe`
- `androidId` - stable device identity used by the server in current protocol v1
- `protocolVersion` - protocol version string or number represented by the adapter according to the transport contract

Canonical headers:
- `x-navpay-hb-version`
- `x-navpay-hb-android-id` when the transport uses headers for tracing or server-side routing
- `x-navpay-hb-app-name` when the transport uses headers for tracing or server-side routing

Notes:
- The payload and the headers are part of the contract only when a project uses them.
- A project may send the canonical values in JSON body, headers, or both, but the semantic fields must remain identical.
- The adapter must keep the semantic meaning stable even if the transport encoding changes.

## Response Envelope

The heartbeat response envelope is the canonical server-to-client shape.

Required fields:
- `ok` - boolean success flag
- `timestamp` - server-observed or echoed timestamp when present
- `error` - machine-readable error string when `ok=false`

Optional fields:
- `command` - command block or command identifier
- `commandId` - unique command id for ACK correlation
- `commandType` - command type string
- `commandPayload` - command-specific payload

Command envelope guidance:
- `command` is the canonical downlink envelope when the server delivers a command inside the heartbeat response.
- The canonical command envelope contains `commandId`, `commandType`, and `commandPayload`.
- `ping` is the shared, standard command type.
- `ping` has no app-specific side effect beyond a successful pong/ack path, unless an adapter explicitly extends it in a documented, backward-compatible way.

Response body guidance:
- Success responses should remain small and stable.
- Command delivery should be expressed as explicit fields or headers, not by overloading free-form error text.

## Command and ACK

Heartbeat may carry one or more server commands.

Command rules:
- A command must have a stable `commandId`
- A command must have a deterministic `commandType`
- A command payload must be schema-valid for that command type
- Command delivery must be idempotent from the client perspective

ACK rules:
- Client ACK must reference the original `commandId`
- ACK must be sent once per successfully handled command
- Server may re-deliver a command until ACK is observed
- Client must ignore duplicates by `commandId`

ACK envelope guidance:
- ACK may be encoded in a request header, request body field, or protocol-specific side channel.
- The encoding choice is adapter-specific, but the semantic identity must remain `commandId` + `commandType`.
- `ping` ACK should be a normal success acknowledgment with no app-specific follow-up work required.

Supported command semantics should be documented per version.
Project adapters may implement different internal side effects, but the command and ACK identifiers must remain stable.

## Core Contract

The reusable core layer must own:
- request payload building
- response parsing
- version validation
- command parsing
- ACK payload construction
- schedule policy inputs and outputs
- supported-command registry lookup inputs and outputs

The reusable core layer must not own:
- HTTP stack
- Android lifecycle hooks
- injection startup hooks
- app-specific auth/session plumbing
- foreground/background execution primitives

## Required Data Model

The canonical data model is:

```text
HeartbeatRequest
  - protocolVersion
  - timestampMs
  - appName
  - androidId
  - extraFields (optional, versioned)

HeartbeatResponse
  - ok
  - timestampMs
  - error
  - command (optional)

HeartbeatCommand
  - commandId
  - commandType
  - payload

HeartbeatCommandRegistryEntry
  - commandType
  - owningApp
  - handlerName
  - supportedProtocolVersions
  - isSharedCommand
```

## Change Rules

Any new heartbeat capability must follow this order:
1. Update this protocol document.
2. Update the shared core implementation.
3. Update each app's command registry.
4. Update each project adapter.
5. Update each project-specific validation checklist.

If a change touches transport only, it must still preserve the protocol contract defined here.
