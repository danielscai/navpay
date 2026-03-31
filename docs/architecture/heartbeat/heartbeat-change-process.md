# Heartbeat Change Process

This document defines the required workflow for changing the shared heartbeat protocol or its reusable core.

## Goal

Prevent protocol drift between `navpay-android` and `navpay-phonepe`.

## Mandatory Workflow

All heartbeat changes must follow this sequence:

1. Update `heartbeat-protocol-v1.md` first.
2. Update the shared core logic next.
3. Update each app's command registry next.
4. Update each project adapter last.
5. Update each project-specific validation checklist.
6. Run both project test suites or their minimum heartbeat-focused subsets.
7. Run real device or emulator verification.

Do not merge adapter changes that introduce behavior not described in the protocol document.

## Layer Ownership

### `spec`

The spec layer owns:
- envelope shape
- field names
- response semantics
- command and ACK semantics
- versioning rules
- compatibility rules

### `core`

The core layer owns:
- payload builders
- parsers
- validators
- command codecs
- schedule policy inputs and outputs
- shared command primitives such as `ping`

The core layer must remain runtime-agnostic.

### `registry`

Each app owns its own command support registry.

The registry owns:
- supported command types for that app
- whether a command is shared or app-specific
- the handler name or adapter entrypoint
- protocol versions that the command is valid for

Registry rules:
- A command may not be implemented in an adapter unless it is registered.
- Shared commands such as `ping` must be listed in every app registry that supports heartbeat downlink.
- App-specific commands may only appear in one app registry unless the spec explicitly says they are shared.

### `adapter`

The adapter layer owns:
- transport
- lifecycle integration
- scheduler execution
- platform-specific auth or state management
- logging and observability hooks

## Compatibility Policy

Compatibility policy is strict:

- Additive optional fields are preferred.
- Required field removals are breaking.
- Changing command meaning is breaking.
- Changing ACK identity is breaking.
- Adding a new command type is allowed only after it is documented in the spec.
- Adding a new app-specific command also requires updating that app's registry and validation doc.

If backward compatibility is not possible, the protocol version must advance and all consumers must be updated explicitly.

## Review Gate

Before implementation starts, the author must answer:
- What changed in the protocol?
- Is it backward compatible?
- Which layer owns the change?
- Which app registries need updates?
- Which project adapters need updates?
- What are the validation steps?

If any answer is unclear, do not start implementation.

## CI Gate

The cross-repo contract gate runs from workspace root:

```bash
python3 tools/heartbeat/verify_contract.py
```

This check validates:
- shared protocol version and version header
- shared canonical field names (`timestamp`, `appName`, `androidId`)
- shared command envelope field names (`commandId`, `commandType`, `commandPayload`)
- required shared command `ping` in both protocol constants and both app registries

GitHub Actions workflow:
- `.github/workflows/heartbeat-contract-gate.yml`

The CI job must pass before merge for heartbeat-related changes.

## Required Validation

Every heartbeat change must include:

- unit tests for the core layer
- adapter contract tests
- project-level integration tests
- emulator or device confirmation for the affected runtime

For `navpay-phonepe`, the final check must confirm the full composed build still injects `heartbeat_bridge` and that heartbeat logs appear from the bridge layer, not from deprecated sender code.

For `navpay-android`, the final check must confirm the heartbeat loop still reaches the device API and that the payload contains the canonical protocol fields.

## Review Checklist

Use this checklist in every review:
- Protocol version explicitly set
- Request envelope fields match spec
- Response parsing matches spec
- Command and ACK semantics preserved
- Registry entries match the supported command set for each app
- Schedule policy is only in core or adapter as intended
- Transport code does not leak into core
- Platform-specific code does not leak into spec
- Both project validation docs updated
