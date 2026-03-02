# 2026-03-01 PhonePe Minimal Auto Assignment Plan

## 1. Goal

Implement the smallest viable architecture for `navpay-android` and `navpay-phonepe` coordination with these priorities:

- Keep implementation and testing simple.
- Avoid over-design and complex cryptography for V1.
- Do not require any UI confirmation inside `phonepe`.
- Let server auto-assign `phonepe` uploads to the current Android user on the same device.
- Support one user on multiple phones.

## 2. Naming and Scope

- Use full name `phonepe` in code and docs (not `pe`).
- Device identifier for V1: `ANDROID_ID` (read directly, no extra hash).
- This plan is V1 only; stronger hardening can be added later.

## 3. Core Model

### 3.1 Device Ownership Pointer (single current owner)

Server maintains one current owner per device:

- Key: `android_id`
- Value: `current_user_id`, `owner_version`, `updated_at`

Behavior:

- Android login/switch updates pointer to the currently logged-in user.
- `owner_version` increments on each switch.

### 3.2 PhonePe Upload Assignment

`phonepe` upload request does not carry `user_id`.

Server assigns upload on ingest:

- Read `android_id` from request.
- Look up `device_owner_current` by `android_id`.
- Persist business record with `assigned_user_id = current_user_id`.

No retroactive reassignment in V1.

## 4. End-to-End Flow

### 4.1 Normal Flow

1. User logs in on `navpay-android`.
2. Android calls `POST /device/owner/update` with auth token + `android_id`.
3. Server upserts current owner pointer.
4. `phonepe` keeps background upload as usual (no UI confirmation).
5. Server auto-assigns each upload to current owner.

### 4.2 Android User Switch on Same Phone

1. Android user switches account.
2. Android calls `POST /device/owner/update` again.
3. Server sets new `current_user_id`, increments `owner_version`.
4. Subsequent `phonepe` uploads from same `android_id` are assigned to new user.

### 4.3 PhonePe Offline Recovery

- Android checks phonepe online status from server (`last_seen`).
- If offline, Android shows a button: "Open PhonePe".
- Button triggers deep link/package launch to bring `phonepe` to foreground.
- `phonepe` resumes normal upload automatically.

This action is fallback only, not mandatory in every login/switch.

## 5. API (Minimal V1)

### 5.1 Update Device Owner

`POST /device/owner/update`

Request:

- Auth: Android user login token (required)
- Body:
  - `android_id: string`
  - `client_time_ms: number` (optional)

Server action:

- Upsert `device_owner_current`
- If owner changed: `owner_version = owner_version + 1`

Response:

- `ok: true`
- `owner_version: number`
- `current_user_id: string`

### 5.2 PhonePe Snapshot Upload

`POST /phonepe/snapshot`

Request:

- Body:
  - `android_id: string`
  - `event_time_ms: number`
  - `payload: object`
  - `request_id: string` (for dedupe)

Server action:

- Resolve current owner by `android_id`
- Save snapshot/transaction with `assigned_user_id`
- Save/refresh device `last_seen`

Response:

- `ok: true`
- `assigned_user_id: string | null`

### 5.3 Device Status Query (Android)

`GET /device/status?android_id=...`

Response:

- `ok: true`
- `online: boolean` (`now - last_seen <= threshold_sec`)
- `last_seen_ms: number | null`
- `current_user_id: string | null`

## 6. Data Tables (Minimal)

### 6.1 `device_owner_current`

- `android_id` (PK)
- `current_user_id`
- `owner_version` (int, default 1)
- `updated_at`

### 6.2 `phonepe_events` (or snapshot table)

- `id`
- `android_id`
- `assigned_user_id`
- `owner_version`
- `event_time_ms`
- `request_id` (unique per sender window)
- `payload_json`
- `received_at`

### 6.3 `device_presence` (can be merged if preferred)

- `android_id` (PK)
- `last_seen_at`
- `last_ip` (optional)
- `updated_at`

## 7. Matching/Confirmation Safety Rule

To avoid fatal confirmation mistakes when amounts are equal between users:

- Never auto-confirm by amount alone.
- Require `android_id + transaction unique key (UTR/RRN/txnId)` at minimum.
- If unique key missing, route to manual review.

## 8. Security (Simple, Non-Overdesigned)

V1 baseline controls only:

- `POST /device/owner/update` requires valid Android login auth.
- `POST /phonepe/snapshot` rate limit by `android_id` and IP.
- Enforce `request_id` dedupe window (anti simple replay).
- Log ownership changes and upload assignment decisions.

Not in V1:

- No long custom crypto protocol.
- No phonepe UI confirmation flow.
- No strict anti-root guarantees.

## 9. Known Tradeoffs (Accepted)

- If attacker fully controls a rooted device, perfect prevention is not guaranteed in V1.
- Ownership is "current pointer" model; historical reclassification is not done.
- After Android logout, owner pointer remains until next login/switch update.

These tradeoffs are acceptable for the current "ship core feature first" target.

## 10. Implementation Checklist

1. Android: collect `ANDROID_ID` and call `/device/owner/update` on login/switch.
2. PhonePe: keep upload payload with `android_id`, add `request_id`.
3. Server: add `device_owner_current` table and assignment on ingest.
4. Server: expose `/device/status` for Android UI online indicator.
5. Android: add fallback "Open PhonePe" action when status is offline.
6. Server: enforce minimal rate-limit + dedupe.
7. Backend: update order confirmation rule to include transaction unique key.

## 11. Future Hardening (Optional, Later)

- Add short-lived upload token bound to `android_id` + `owner_version`.
- Add Play Integrity check for ownership updates.
- Add risk scoring for suspicious ownership churn.

These are explicitly deferred to keep V1 simple.
