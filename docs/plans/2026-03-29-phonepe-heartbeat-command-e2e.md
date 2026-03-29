# PhonePe Heartbeat Command + Snapshot Trigger E2E Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ensure the updated heartbeat downlink mechanism is fully active in `navpay-phonepe`, trigger a one-time snapshot from the admin `app_status` page, and verify snapshot data lands in DB.

**Architecture:** Keep request frequency unchanged and piggyback command delivery on existing heartbeat responses via semantic HTTP headers. Admin writes one-shot command state keyed by device/app and heartbeat ingest returns command header until ACK is received. PhonePe interceptor client consumes header, triggers helper snapshot upload once, and ACKs in next heartbeat request.

**Tech Stack:** Next.js route handlers + Prisma (navpay-admin), Android Java interceptor module (navpay-phonepe), ADB/emulator tooling, PostgreSQL validation queries.

---

### Task 1: Verify and lock server-side heartbeat command contract

**Files:**
- Modify: `navpay-admin/src/lib/intercept-log.ts`
- Modify: `navpay-admin/src/app/api/admin/intercept/logs/route.ts`
- Modify: `navpay-admin/src/lib/device-runtime-command.ts`
- Test: `navpay-admin/tests/unit/intercept/admin-intercept-logs-route.test.ts`

**Step 1: Write/adjust failing tests for heartbeat response minimal body + semantic command header + ACK clear**

```ts
expect(json).toEqual({ success: true });
expect(res.headers.get("x-navpay-device-command")).toContain("commandType=trigger_phonepe_snapshot_once");
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/intercept/admin-intercept-logs-route.test.ts`
Expected: FAIL because old response shape/header behavior mismatches.

**Step 3: Implement minimal server code**

- heartbeat ingest response body fixed to `{ success: true }`
- downlink via `x-navpay-device-command`
- ACK ingest via `x-navpay-device-command-ack`
- command cleared after valid ACK

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/intercept/admin-intercept-logs-route.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
cd navpay-admin
git add src/lib/intercept-log.ts src/app/api/admin/intercept/logs/route.ts src/lib/device-runtime-command.ts tests/unit/intercept/admin-intercept-logs-route.test.ts
git commit -m "feat(intercept): downlink snapshot command via heartbeat headers"
```

### Task 2: Expose manual one-shot trigger from admin API and page

**Files:**
- Create: `navpay-admin/src/app/api/admin/resources/devices/[deviceId]/phonepehelper/trigger-snapshot/route.ts`
- Modify: `navpay-admin/src/components/device-phonepehelper-panel.tsx`
- Modify: `navpay-admin/tests/unit/device-phonepehelper-trigger-snapshot-route.test.ts`
- Modify: `navpay-admin/tests/unit/devices-client-observability-layout.test.ts`

**Step 1: Write failing tests**

```ts
expect(json.commandType).toBe("trigger_phonepe_snapshot_once");
expect(helperSrc).toContain("/phonepehelper/trigger-snapshot");
expect(helperSrc).toContain("触发上传");
```

**Step 2: Run tests to verify they fail**

Run: `cd navpay-admin && yarn test tests/unit/device-phonepehelper-trigger-snapshot-route.test.ts tests/unit/devices-client-observability-layout.test.ts`
Expected: FAIL before implementation.

**Step 3: Implement minimal API + UI**

- API issues one-shot command with bounded TTL
- UI button in `app_status` sends POST and reports result toast

**Step 4: Run tests to verify they pass**

Run: `cd navpay-admin && yarn test tests/unit/device-phonepehelper-trigger-snapshot-route.test.ts tests/unit/devices-client-observability-layout.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
cd navpay-admin
git add src/app/api/admin/resources/devices/[deviceId]/phonepehelper/trigger-snapshot/route.ts src/components/device-phonepehelper-panel.tsx tests/unit/device-phonepehelper-trigger-snapshot-route.test.ts tests/unit/devices-client-observability-layout.test.ts
git commit -m "feat(phonepehelper): add one-shot snapshot trigger action on device app status"
```

### Task 3: Document heartbeat protocol changes

**Files:**
- Modify: `navpay-admin/docs/manual/phonepehelper-device-tab.md`

**Step 1: Write doc assertions first (manual checklist as failing criteria)**

Checklist:
- heartbeat request minimal fields listed
- heartbeat response body minimal shape listed
- command/ack header names listed
- trigger API path listed

**Step 2: Update doc**

Add dedicated section for heartbeat lean protocol and command headers.

**Step 3: Verify doc coverage**

Run: `cd navpay-admin && rg -n "x-navpay-device-command|x-navpay-device-command-ack|trigger-snapshot|success" docs/manual/phonepehelper-device-tab.md`
Expected: lines found for all protocol pieces.

**Step 4: Commit**

```bash
cd navpay-admin
git add docs/manual/phonepehelper-device-tab.md
git commit -m "docs(phonepehelper): document lean heartbeat command protocol"
```

### Task 4: Ensure navpay-phonepe heartbeat client executes command

**Files:**
- Modify: `navpay-phonepe/src/apk/https_interceptor/app/src/main/java/com/httpinterceptor/interceptor/LogSender.java`

**Step 1: Write/adjust failing expectations (contract test or compile-level assertion)**

Add assertions/checks for:
- request includes semantic ACK header when pending
- response command header parsing
- trigger path invokes `PhonePeHelper.uploadSnapshotToNavpayAsync()`

**Step 2: Run targeted unit/build test to verify failure (if test exists) or compile check before code**

Run: `cd navpay-phonepe/src/apk/https_interceptor && ./gradlew :app:testDebugUnitTest --tests com.httpinterceptor.interceptor.RemoteLoggingCaptureContractTest`
Expected: fail if contract assertions missing; otherwise use compile+runtime verification in Task 5.

**Step 3: Implement minimal client behavior**

- parse `X-Navpay-Device-Command`
- trigger one-shot upload for `trigger_phonepe_snapshot_once`
- send `X-Navpay-Device-Command-Ack` next request
- keep heartbeat payload lean with `appName`

**Step 4: Run Android unit test/build verification**

Run: `cd navpay-phonepe/src/apk/https_interceptor && ./gradlew :app:testDebugUnitTest --tests com.httpinterceptor.interceptor.RemoteLoggingCaptureContractTest`
Expected: PASS.

**Step 5: Commit**

```bash
cd navpay-phonepe
git add src/apk/https_interceptor/app/src/main/java/com/httpinterceptor/interceptor/LogSender.java
git commit -m "feat(https): execute heartbeat downlink command and ack with semantic headers"
```

### Task 5: Emulator E2E validation from admin page + DB proof

**Files:**
- Verify runtime using existing code and DB tables (`payment_person_report_logs`, `system_configs`, `http_intercept_logs`)

**Step 1: Build/install updated phonepe package to emulator**

Run project-approved install workflow in `navpay-phonepe` (compile/merge/install path).

**Step 2: Open admin page and trigger from app_status UI**

URL: `http://localhost:3000/admin/resources/devices/dev_d88fb7ad-63e9-48fe-bc7f-56e525776876?tab=phonepe&view=app_status`
Action: click `触发上传`.

**Step 3: Verify heartbeat command lifecycle in DB**

Run (sample):
```sql
select key, value from system_configs where key = 'device_runtime_command:dev_d88fb7ad-63e9-48fe-bc7f-56e525776876:phonepe';
```
Expected: command row appears then disappears after ACK.

**Step 4: Verify snapshot ingestion row increased**

Run:
```sql
select id, entity_id, created_at_ms
from payment_person_report_logs
where type='PHONEPE_SNAPSHOT' and entity_id='dev_d88fb7ad-63e9-48fe-bc7f-56e525776876'
order by created_at_ms desc
limit 5;
```
Expected: new latest row after trigger time.

**Step 5: Verify page reflects new data**

Reload `app_status` page and confirm `最后上传时间`/timeline updated.

**Step 6: Final verification commands**

Run:
- `cd navpay-admin && yarn test tests/unit/intercept/admin-intercept-logs-route.test.ts tests/unit/device-phonepehelper-trigger-snapshot-route.test.ts tests/unit/devices-client-observability-layout.test.ts`
- `cd navpay-admin && yarn typecheck`
- `cd navpay-phonepe/src/apk/https_interceptor && ./gradlew :app:testDebugUnitTest --tests com.httpinterceptor.interceptor.RemoteLoggingCaptureContractTest`

Expected: all pass.
