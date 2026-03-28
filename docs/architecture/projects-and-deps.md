# NavPay Projects & Dependencies

## Projects
- navpay-android (Android)
- navpay-phonepe (PhonePe helper injection module)
- navpay-admin (API + Admin UI)
- navpay-otp (OTP service)
- navpay-landing (Download landing)
- navpay-tgbot (Telegram bot)

## Runtime Dependencies
- navpay-phonepe -> navpay-android (same-device ContentProvider bridge, local IPC)
- navpay-android -> navpay-admin (HTTP)
- navpay-admin -> navpay-otp (HTTP)
- navpay-tgbot -> navpay-admin (HTTP)
- navpay-landing -> navpay-admin (HTTP, public manifest)

## On-Device PhonePe Bridge (Implemented)

### Goal
- Ensure `navpay-android` can read latest PhonePe snapshot even when PhonePe is backgrounded.

### Design
- Single IPC boundary:
  - `ContentProvider` authority: `com.phonepe.navpay.provider`
- Service 1: checksum (production)
  - Exposed via `ContentProvider.call("checksum", ...)`.
  - Input contract: `path`, `body`, `uuid`.
  - Output contract (JSON-equivalent): `ok`, `data.checksum`, `data.uuid` or `ok=false,error`.
  - Existing HTTP service (`127.0.0.1:19090`) remains available for compatibility and tooling.
- Service 2: user_data (production)
  - Exposed via `content://com.phonepe.navpay.provider/user_data`.
  - Stored payload uses the same top-level schema as admin route:
    - `GET /api/admin/resources/devices/[deviceId]/phonepehelper`
  - Required top-level keys: `ok`, `deviceId`, `deviceOnline`, `deviceLastSeenAtMs`, `uploadMode`, `tokenCheckIntervalMs`, `summary`, `totalUploadCount`, `latestSample`, `events`, `keySnapshot`, `rawSamples`, `rows`, `lastCollectedAtMs`.
- Reader side (`navpay-android`):
  - Query `user_data` on `MainActivity.onResume()`.
  - Use checksum service through `ContentResolver.call(...)` when checksum is needed.
- Android package visibility:
  - `navpay-android` manifest declares:
    - `<queries><provider android:authorities="com.phonepe.navpay.provider" /></queries>`
  - Required on Android 11+ to avoid provider visibility blocking.

### Data Flow
1. User opens PhonePe and triggers operations.
2. `navpay-phonepe` computes/collects data and persists `user_data` payload with admin-compatible schema.
3. User switches to NavPay.
4. `navpay-android` enters `onResume()` and reads latest `user_data` from provider.
5. If checksum is required, `navpay-android` calls provider method `checksum` with `path/body/uuid` and consumes returned checksum.

### Why This Works
- No network dependency in the cross-app handoff path.
- No localhost HTTP coupling between apps; IPC is explicit and permission-governed.
- One canonical `user_data` schema between device-side provider and admin-side API reduces drift and maintenance cost.
- Read timing remains deterministic (`onResume()` on app switch).

### Validation Status
- Verified on emulator AVD `phonepe_nologin` (March 28, 2026):
  - `navpay-phonepe` `yarn test` passed (inject/install/start validation).
  - Provider query returned valid `payload/version/updated_at`.
  - `navpay-android` logged successful read on `onResume()`.

## Local Ports (dev defaults)
- navpay-admin: 3000
- navpay-otp: 19090
- navpay-landing: 3100 (suggested)
- navpay-tgbot: no port (outbound polling/webhook)

## API Prefixes
- Mobile: /api/personal/*
- Admin UI: /admin/*
- Integrations: /api/integrations/*
- Public: /api/public/*
