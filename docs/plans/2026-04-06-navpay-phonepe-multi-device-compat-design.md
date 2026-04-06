# NavPay PhonePe Multi-Device Compatibility Design (2026-04-06)

## Context

`navpay-phonepe` is installed by `navpay-android`, while release/version lifecycle is maintained in `navpay-admin`.

The target is not generic ABI/SDK compatibility first, but realistic ROM behavior compatibility across real-world Android vendors (for example MIUI, ColorOS, OriginOS, One UI), with:

- a single `navpay-phonepe` base package line,
- `navpay-admin` as single source of truth for release/version,
- convenient multi-device testing in local emulators plus a small real-device supplement,
- fast and safe publish/rollback operations.

## Goals

- Keep one base package release line for `navpay-phonepe`.
- Centralize release/version authority in `navpay-admin` only.
- Improve real-world ROM compatibility via policy adaptation, not per-ROM APK forks.
- Build a convenient multi-device test framework for emulator-first execution.
- Support fast release cadence with strong observability and quick rollback.

## Non-Goals

- No immediate split into multiple APK/product flavors by ROM.
- No cloud real-device platform as the primary test path in this phase.
- No redesign of all existing install APIs if current contracts can be extended.

## Chosen Approach

Adopt **Approach A: Admin-driven single-base plus device policy layer**.

Core principle:

- **Artifact is unified**: only one active base release line.
- **Behavior is adaptable**: install strategy is resolved per device profile at runtime.

This keeps publishing simple while still handling ROM-level behavior differences.

## Architecture

### 1. Release Source of Truth (`navpay-admin`)

- Keep release creation/upload/activation in `navpay-admin`.
- Keep publisher token flow for secure release operations.
- Add install-policy configuration capability keyed by device profile segments.

### 2. Device Profiling (`navpay-android` -> `navpay-admin`)

- On startup and install lifecycle, report profile fields:
  - `brand`, `model`, `osVersion`, `sdkInt`,
  - install capabilities and relevant runtime signals,
  - installed app version snapshot (`com.phonepe.app` / `navpay-phonepe`).
- `navpay-admin` maps devices into compatibility segments (for example high-risk ROM groups).

### 3. Install Execution (`navpay-android`)

- Pull active release manifest for the single base package.
- Pull install policy for current device segment.
- Execute installer using policy controls (permission guidance, timeout, retry, verification).

### 4. Observability and Recovery

- Report structured install events with stage/error/profile dimensions.
- Aggregate by ROM segment in admin dashboards.
- Support quick policy hotfix and release rollback.

## Data Flow and Contracts

### A. Startup Sync (existing contract, enhanced usage)

Endpoint:

- `POST /api/personal/report/sync`

Use:

- Ensure each device and installed app version is up-to-date in backend (`payment_device_apps`).

### B. Install Policy Fetch (new)

Endpoint (proposed):

- `GET /api/personal/payment-apps/{appId}/install-policy`

Response includes policy fields such as:

- permission guidance mode,
- confirm/install timeout windows,
- retry limits and intervals,
- post-install verification requirements.

### C. Install Event Upload (existing route, stricter schema)

Endpoint:

- `POST /api/personal/payment-apps/install-events`

Required dimensions:

- `deviceId/androidId`, `brand/model/os/sdk`,
- `releaseId/versionCode`,
- `stage` (`prepare`, `download`, `await_confirm`, `installing`, `success`, `failed`),
- standardized `errorCode`,
- optional ROM hints.

## Compatibility Error Model

Standardized error codes:

1. `PERMISSION_BLOCKED_BY_ROM`
2. `INSTALLER_UI_NOT_SHOWN`
3. `USER_CONFIRM_TIMEOUT`
4. `SESSION_COMMIT_FAILED`
5. `APK_PARSE_FAILED`
6. `POST_INSTALL_NOT_FOUND`
7. `POST_INSTALL_LAUNCH_FAILED`

Each failure must be uploaded with release and device profile metadata so admin can drive policy refinement by ROM segment.

## Policy Templates (Behavior Layer)

Policy is segmented by compatibility group, not by APK variant:

- Permission policy:
  - whether to hard-gate unknown-app install before action,
  - ROM-specific guidance/copy path.
- Confirmation policy:
  - wait windows for installer confirmation and commit phases.
- Retry policy:
  - bounded retries by selected error codes.
- Post-install verification policy:
  - package existence check,
  - optional launch check and timing capture.

## Multi-Device Testing Framework (Emulator-First)

### Device Pool

- **Tier-1**: local multi-emulator matrix (main daily gate).
- **Tier-2**: small real-device set (pre-release sampling).

### Test Layers

- `L1`: policy resolution and error mapping unit tests.
- `L2`: Android instrumentation for permission/install state machine.
- `L3`: cross-repo orchestration (admin release + android install flow).
- `L4`: black-box real-user flow extended to multi-device parallel runs.

### Multi-Device Orchestrator (new script layer)

Inputs:

- device inventory (`serial`, tags, tier).

Execution:

- run the same install flow in parallel across devices,
- collect per-device result and failure signatures.

Outputs:

- `artifacts/multi-device/<run-id>/summary.json`
- `artifacts/multi-device/<run-id>/by-rom.json`
- `artifacts/multi-device/<run-id>/failures.csv`

## Release and Rollback Workflow (Fast Cadence)

### Pre-Release

- Create/upload candidate release in admin.
- Run Tier-1 mandatory matrix and Tier-2 sample checks.
- Activate only if gate thresholds pass.

### Post-Release Monitoring

- Monitor ROM-segmented failure rates in near real time.
- Prioritize top error codes by impact.

### Rollback Levels

1. Policy hotfix (fastest): adjust install policy without changing artifacts.
2. Release fallback: switch active release to previous stable version.
3. Distribution stop: disable current release distribution when needed.

## Acceptance Criteria

- Single-base release flow remains the default across devices.
- `navpay-admin` remains the only version/release source of truth.
- Multi-device emulator gate can run in one command and output standardized artifacts.
- Top ROM-specific failures are observable within one monitoring window.
- Rollback can be executed in minutes with clear evidence of effect.

## Risks and Mitigations

- Risk: policy complexity grows too fast.
  - Mitigation: start with minimal policy dimensions and fixed error taxonomy.
- Risk: emulator behavior diverges from real ROM.
  - Mitigation: keep Tier-2 real-device sampling before activation.
- Risk: noisy event telemetry.
  - Mitigation: enforce schema validation and standardized error mapping in client.

## Recommendation

Proceed with Approach A in two phases:

1. **Foundation**: policy endpoint + standardized event/error model + multi-device orchestrator.
2. **Optimization**: ROM-segment tuning loops based on measured failure distributions.

This path best balances realistic compatibility improvements with fast release velocity.
