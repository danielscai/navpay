# Phone Device Observability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ensure PhonePe startup automatically registers/upserts device info in `devices`, each intercept log carries device identity, and the intercept detail panel shows device info above request URL.

**Architecture:** Enrich interceptor payload on Android side with stable device identity + metadata, then persist/upsert that metadata into `payment_devices` during admin intercept ingestion. Finally, render device identity in the intercept detail UI and auto-refresh devices list so newly online phones become visible quickly.

**Tech Stack:** Android Java (`LogSender`), Next.js + TypeScript (`navpay-admin`), Prisma/Postgres, Vitest/Playwright, Yarn.

---

### Task 1: Android Payload Enrichment For Device Identity

**Files:**
- Modify: `navpay-phonepe/src/apk/https_interceptor/app/src/main/java/com/httpinterceptor/interceptor/LogSender.java`
- Modify: `navpay-phonepe/src/apk/https_interceptor/scripts/compile.sh` (only if new class deps require it)
- Test: `navpay-phonepe/src/apk/https_interceptor/app/src/test/java/com/httpinterceptor/interceptor/LogEndpointResolverTest.java`

**Step 1: Write/extend failing test (where practical)**

```java
// Keep existing resolver tests; add assertions only if endpoint behavior changed.
```

**Step 2: Run current tests to establish baseline**

Run: `cd navpay-phonepe/src/apk/https_interceptor && ./gradlew test`
Expected: PASS baseline before enrichment changes.

**Step 3: Implement minimal payload enrichment in LogSender**

```java
// Add fields when missing:
// - androidId + clientDeviceId
// - deviceName, brand, model
// - osVersion, sdkInt
// - timezone, locale
// Also avoid permanently caching "unknown" androidId when app context is not ready.
```

**Step 4: Rebuild interceptor artifacts and run tests**

Run: `cd navpay-phonepe && src/apk/https_interceptor/scripts/compile.sh`
Expected: PASS, smali generated.

Run: `cd navpay-phonepe/src/apk/https_interceptor && ./gradlew test`
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-phonepe/src/apk/https_interceptor/app/src/main/java/com/httpinterceptor/interceptor/LogSender.java navpay-phonepe/src/apk/https_interceptor/scripts/compile.sh
# commit later with all tasks after integrated verification
```

### Task 2: Admin Ingestion Upserts Rich Device Info Into `payment_devices`

**Files:**
- Modify: `navpay-admin/src/lib/intercept-log.ts`
- Test: `navpay-admin/tests/unit/intercept/log-ingestion.test.ts`
- Test: `navpay-admin/tests/unit/intercept/log-device-assignment.test.ts`

**Step 1: Write failing unit tests**

```ts
// Add test payload containing:
// clientDeviceId, deviceName, brand, model, osVersion, sdkInt, timezone, locale.
// Assert ingest creates/updates payment_devices with these fields.
```

**Step 2: Run targeted tests to verify fail first**

Run: `cd navpay-admin && yarn test tests/unit/intercept/log-ingestion.test.ts tests/unit/intercept/log-device-assignment.test.ts`
Expected: FAIL before implementation due missing mapping/upsert behavior.

**Step 3: Implement minimal normalization + upsert mapping**

```ts
// normalizeInterceptLogPayload: parse optional device metadata.
// bindSourceDevice: update existing row metadata when provided; create new row with rich defaults.
// Keep existing source_device_id/source_label contract unchanged.
```

**Step 4: Re-run targeted tests**

Run: `cd navpay-admin && yarn test tests/unit/intercept/log-ingestion.test.ts tests/unit/intercept/log-device-assignment.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-admin/src/lib/intercept-log.ts navpay-admin/tests/unit/intercept/log-ingestion.test.ts navpay-admin/tests/unit/intercept/log-device-assignment.test.ts
# commit later with all tasks after integrated verification
```

### Task 3: Intercept Detail UI Shows Device Info Above URL

**Files:**
- Modify: `navpay-admin/src/components/intercept-console.tsx`
- Test: `navpay-admin/tests/e2e/intercept-log-data-visible.spec.ts`
- Test: `navpay-admin/tests/unit/resources-intercept-tab.test.ts` (only if contract text changes)

**Step 1: Write failing UI expectation (if needed)**

```ts
// In e2e/visible spec, assert source device label/client id text appears
// in detail panel before URL editor area.
```

**Step 2: Run targeted UI test to capture failure**

Run: `cd navpay-admin && yarn test:e2e tests/e2e/intercept-log-data-visible.spec.ts`
Expected: FAIL before rendering device line.

**Step 3: Implement minimal UI rendering**

```tsx
// Extend InterceptLog type with sourceClientDeviceId/sourceDeviceId/sourceLabel.
// In RequestEditor/LogDetail area, render one line above URL row:
// 设备: <sourceLabel> | Client ID: <sourceClientDeviceId> | Device ID: <sourceDeviceId>
```

**Step 4: Re-run UI test + type checks**

Run: `cd navpay-admin && yarn typecheck`
Expected: PASS.

Run: `cd navpay-admin && yarn test:e2e tests/e2e/intercept-log-data-visible.spec.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-admin/src/components/intercept-console.tsx navpay-admin/tests/e2e/intercept-log-data-visible.spec.ts
# commit later with all tasks after integrated verification
```

### Task 4: Devices Tab Visibility For Newly Online Phone

**Files:**
- Modify: `navpay-admin/src/components/devices-client.tsx`
- Test: `navpay-admin/tests/unit/devices-client-observability-layout.test.ts`

**Step 1: Write failing expectation**

```ts
// Assert devices page contains periodic refresh hook semantics or refresh trigger text markers.
```

**Step 2: Run targeted test to verify fail**

Run: `cd navpay-admin && yarn test tests/unit/devices-client-observability-layout.test.ts`
Expected: FAIL before polling logic is added.

**Step 3: Implement minimal periodic reload**

```tsx
// Keep existing manual refresh/search.
// Add 2s~5s interval polling calling existing load() to reflect newly online devices.
```

**Step 4: Re-run targeted test + lint/typecheck**

Run: `cd navpay-admin && yarn test tests/unit/devices-client-observability-layout.test.ts`
Expected: PASS.

Run: `cd navpay-admin && yarn typecheck && yarn lint`
Expected: PASS (existing warnings acceptable if unchanged).

**Step 5: Commit**

```bash
git add navpay-admin/src/components/devices-client.tsx navpay-admin/tests/unit/devices-client-observability-layout.test.ts
# commit later with all tasks after integrated verification
```

### Task 5: End-to-End Verification Across Both Repos

**Files:**
- Verify only: `navpay-phonepe` runtime + `navpay-admin` runtime

**Step 1: Build and deploy patched APK via orchestrator**

Run: `cd navpay-phonepe && yarn test`
Expected: PASS and app starts with hooks active.

**Step 2: Verify admin DB receives device-linked logs**

Run:
`psql '<DATABASE_URL>' -Atc "select id, source_client_device_id, source_device_id, source_label from http_intercept_logs order by id desc limit 10;"`
Expected: non-empty source device fields.

**Step 3: Verify devices list includes auto-created/updated phone row**

Run:
`psql '<DATABASE_URL>' -Atc "select id, name, client_device_id, brand, model, os_version, last_seen_at_ms from payment_devices order by updated_at_ms desc limit 10;"`
Expected: phone row visible and last_seen updates on new logs.

**Step 4: Manual UI verification**

- Open `http://localhost:3000/admin/resources?tab=devices` and confirm phone appears/refreshes.
- Open `http://localhost:3000/admin/resources?tab=intercept_logs` and confirm right detail panel shows device info line above URL.

**Step 5: Final commit**

```bash
git add navpay-phonepe navpay-admin docs/plans/2026-03-24-phone-device-observability.md
git commit -m "feat(observability): link intercept logs with device identity and surface in resources UI"
```
