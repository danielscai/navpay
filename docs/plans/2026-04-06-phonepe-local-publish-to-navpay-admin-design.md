# PhonePe Local Publish to navpay-admin Design (2026-04-06)

## 1. Goal

Provide a local manual command that publishes a newly built PhonePe package into `navpay-admin` as a managed payment-app release.

Confirmed constraints:
- Trigger mode: manual command (no auto-trigger).
- Environment switch: `--env` supports `local/staging/prod`, default `local`.
- Auth model: release token only; no admin cookie/session reuse.
- Permission scope: token can only access payment-app release flow.
- Token storage: hash-only at rest (plaintext visible only once at create time).

## 2. Current Context

`navpay-admin` already has the release lifecycle for payment apps:
- Create release (`POST /api/admin/payment-apps/:appId/releases`)
- Upload artifacts (`POST /api/admin/payment-apps/:appId/releases/:releaseId/artifacts`)
- Activate release (`POST /api/admin/payment-apps/:appId/releases/:releaseId/activate`)
- Personal-side manifest/artifact download routes already exist.

This design adds a machine-to-machine publish lane and a publisher CLI in `navpay-phonepe`.

## 3. Proposed Architecture

### 3.1 navpay-admin

1. Add a release-token management capability under system settings.
2. Introduce a dedicated auth guard for bearer release tokens.
3. Add token-scoped publish endpoints (or allow existing endpoints through new guard path) restricted to:
   - create release
   - upload artifact
   - activate release
4. Persist token lifecycle and usage audit.

### 3.2 navpay-phonepe

1. Add a CLI command (for example `yarn release:to-admin`) that:
   - resolves target environment (`--env`, default `local`)
   - loads release token from CLI arg/env
   - reads APK + metadata
   - calls create -> upload -> activate sequentially
2. Implement idempotency check to avoid duplicate active release for same version+artifact hash.

## 4. Components and Data Model

### 4.1 Release Token Data Model (new)

Recommended table: `release_tokens`
- `id`
- `name`
- `scope` (fixed value: `payment_app_release`)
- `token_hash` (hash only)
- `status` (`active` / `revoked`)
- `last_used_at_ms`
- `created_at_ms`, `updated_at_ms`

Security properties:
- Plain token shown once at creation.
- Verification uses hash compare only.
- Revoked token hard-fails authorization.

### 4.2 System Settings UI

Under admin system settings, add “Release Tokens” panel:
- Create token (name + scope).
- Show metadata only (never show stored plaintext).
- Revoke token.
- Show `last_used_at_ms` and status.

### 4.3 Publish Auth Guard

New guard behavior:
- Read `Authorization: Bearer <token>`.
- Resolve token by hash and `status=active`.
- Enforce `scope=payment_app_release`.
- Attach actor identity as `token:<token_id>` for release events/audit.

## 5. Publish Flow

From `navpay-phonepe` CLI:

1. Resolve config by env:
- `local` default URL `http://localhost:3000` (overridable)
- `staging/prod` from env mapping.

2. Load package metadata and APK bytes; compute `sha256`.

3. Pre-check idempotency:
- Query existing active release for target app.
- If `versionCode` and artifact hash already match, return success without mutation.

4. Create release (draft).

5. Upload artifact(s):
- At minimum `base.apk`.
- Future-compatible for ABI/density split uploads.

6. Activate release.

7. Emit summary output:
- target env, appId, releaseId, artifact hash, status.

## 6. Error Handling and Recovery

- Create succeeded, upload failed: keep draft; print releaseId for retry.
- Upload succeeded, activate failed: keep release with artifacts; print gate reasons.
- Transient network failures: retry with bounded backoff (max 3 attempts).
- Auth errors (`401/403`): stop immediately; do not retry blindly.
- Activation gate failure: return structured reason list to CLI output.

## 7. Testing Strategy

### 7.1 navpay-admin
- Unit tests:
  - token hash verify and scope enforcement
  - revoked/inactive token rejection
  - publish-route authorization boundaries
- API tests:
  - bearer token can complete create/upload/activate
  - token cannot access unrelated `system.write` operations
- UI tests:
  - token create/revoke flows in system settings

### 7.2 navpay-phonepe
- Unit tests:
  - env resolution (`local` default)
  - idempotency branch behavior
  - API error mapping/retry behavior
- Dry-run smoke:
  - verify request payloads without mutation mode (optional)
- Local e2e:
  - generate release against local `navpay-admin` with default dev token

## 8. Rollout Plan

1. Add `release_tokens` schema + migration + service.
2. Add system settings UI for token lifecycle.
3. Add publish auth guard and publish-lane routes.
4. Seed local default dev token (local only).
5. Add `navpay-phonepe` publish CLI and script.
6. Validate end-to-end local publish using `--env local`.
7. Document staging/prod token provisioning process.

## 9. Operational Rules

- `local` default token is `DEV ONLY`; never auto-seed in staging/prod.
- Rotate tokens by creating a new token and revoking old token.
- Audit all publish operations via release event actor and token usage timestamp.
- Do not persist plaintext token in repo, logs, or screenshots.

## 10. Implementation Sync (2026-04-06)

Delivered scope:
- `payment_app_release` scoped publish token model + hash-only verification.
- Publisher-only bearer auth guard (no admin cookie/session reuse).
- Publisher create/upload/activate route lane with token actor audit.
- Local-only default publish token seed (`APP_ENV=staging/prod` and `NODE_ENV=production` skip).
- `navpay-phonepe` release CLI (`--env` default local) with idempotency precheck.

Local verification notes:
- Local default token used for e2e: `nprt_local_phonepe_publisher` (stored as hash only in DB).
- This workstation lacked `aapt`, so CLI metadata parsing uses local fallback values when `aapt` is unavailable.
- Local run required explicit `--baseUrl http://localhost:3001` and `--appId <actual-payment-app-id>` because active dev service and app id were environment-specific.
