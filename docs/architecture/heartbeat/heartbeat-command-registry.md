# Heartbeat Command Registry

This document defines how each app records the heartbeat commands it supports.

The registry is the per-app source of truth for command support. It complements the shared heartbeat protocol spec:
- `heartbeat-protocol-v1.md` defines the wire contract.
- This document defines which commands each app supports.
- Adapter code must only execute commands that are listed in that app's registry.

## Registry Rules

1. Every command must be declared in the shared protocol before any app adapter implements it.
2. Every app must maintain its own registry entry set.
3. Shared commands, such as `ping`, must be present in every app registry that participates in heartbeat downlink.
4. App-specific commands may exist in only one app registry unless the protocol spec explicitly marks them shared.
5. A command handler may not be added silently inside an adapter without a registry update.
6. Registry changes must be reviewed together with protocol and adapter changes.

## Registry Entry Shape

Each registry entry should record:
- `commandType` - canonical command name
- `isSharedCommand` - whether all apps support it
- `owningApp` - app that owns the implementation or business side effect
- `handlerName` - adapter entrypoint or handler identifier
- `supportedProtocolVersions` - protocol versions that may carry the command
- `ackBehavior` - how the client acknowledges success or failure

## Standard Commands

### `ping`

`ping` is the standard shared command.

Expected behavior:
- parse the command through the shared codec
- acknowledge receipt using the shared ACK shape
- return a successful pong-style result
- do not require app-specific business logic beyond the shared handling path

### App-Specific Commands

App-specific commands must be explicitly declared in the owning app registry.

Examples:
- `navpay-android` may support runtime-task commands for heartbeat-driven flows.
- `navpay-phonepe` may support adapter-specific commands used by its injected runtime.

These commands may share the same wire format, but their side effects remain adapter-specific.

## Update Workflow

When adding a new command:
1. Update `heartbeat-protocol-v1.md`.
2. Update the command registry for each affected app.
3. Update the shared core codec or handler logic.
4. Update each adapter implementation.
5. Update tests and validation docs.

If a command is removed or renamed, treat it as a breaking change and update protocol versioning accordingly.

