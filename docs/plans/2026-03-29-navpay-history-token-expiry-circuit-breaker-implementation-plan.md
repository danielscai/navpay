# Navpay History Token Expiry Circuit Breaker Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement Android token-expiry circuit breaker with event-driven probe recovery, and surface live client strategy state in navpay-admin `navpay_history_transactions` with DB-backed evidence.

**Architecture:** Add a dedicated Android sync-policy state machine to `NavpayHistorySyncManager` and a new personal API status-report route in navpay-admin. Persist latest per-device strategy state plus bounded event timeline, expose both in admin read API, and render a status card + event list in the existing panel. Use deterministic unit tests first, then emulator + DB + page validation for end-to-end proof.

**Tech Stack:** Kotlin + coroutines (Android), Next.js route handlers (TypeScript), PostgreSQL SQL migrations, Vitest, Gradle/JUnit, Playwright/manual E2E, adb/emulator.

---

### Task 1: Add navpay-admin DB schema for client state and events

**Files:**
- Create: `navpay-admin/prisma/migrations/20260329xxxxxx_device_navpay_history_client_state/migration.sql`
- Modify: `navpay-admin/src/lib/device-navpay-history-repo.ts`
- Test: `navpay-admin/tests/unit/device-navpay-history-client-state-repo.test.ts`

**Step 1: Write the failing test**

```ts
import { describe, expect, test } from "vitest";
import {
  upsertDeviceNavpayHistoryClientState,
  appendDeviceNavpayHistoryClientEvent,
  getDeviceNavpayHistoryClientState,
  listDeviceNavpayHistoryClientEvents,
} from "@/lib/device-navpay-history-repo";

describe("device navpay history client state repo", () => {
  test("persists latest state and bounded events", async () => {
    await upsertDeviceNavpayHistoryClientState({
      deviceId: "dev_1",
      sourceClientDeviceId: "android_1",
      strategyVersion: "android.history_sync.v1",
      policyJson: "{\"initialProbeMs\":60000}",
      currentState: "WAITING_TOKEN_REFRESH",
      stateChangedAtMs: 1000,
      tokenExpiredAtMs: 900,
      backoffCurrentMs: 60000,
      backoffNextMs: 120000,
      nextProbeAtMs: 61000,
      lastReportAtMs: 1000,
    });
    await appendDeviceNavpayHistoryClientEvent({
      deviceId: "dev_1",
      sourceClientDeviceId: "android_1",
      eventType: "TOKEN_EXPIRED_OPENED",
      stateFrom: "RUNNING",
      stateTo: "TOKEN_EXPIRED_OPEN",
      atMs: 900,
      payloadJson: "{}",
    });

    const state = await getDeviceNavpayHistoryClientState("dev_1");
    const events = await listDeviceNavpayHistoryClientEvents("dev_1", 20);

    expect(state?.current_state).toBe("WAITING_TOKEN_REFRESH");
    expect(events[0]?.event_type).toBe("TOKEN_EXPIRED_OPENED");
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/device-navpay-history-client-state-repo.test.ts -v`
Expected: FAIL with missing table/repo methods.

**Step 3: Write minimal implementation**

- Add two tables:
  - `device_navpay_history_client_state`
  - `device_navpay_history_client_events`
- Add repo methods for upsert/get/list/append and low-frequency cleanup entrypoint.

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/device-navpay-history-client-state-repo.test.ts -v`
Expected: PASS.

**Step 5: Commit**

```bash
git -C navpay-admin add prisma/migrations src/lib/device-navpay-history-repo.ts tests/unit/device-navpay-history-client-state-repo.test.ts
git -C navpay-admin commit -m "feat(history): add navpay client state and events persistence"
```

### Task 2: Add personal API status report route with event retention cleanup

**Files:**
- Create: `navpay-admin/src/app/api/personal/device/navpay-history-transactions/status/route.ts`
- Modify: `navpay-admin/src/lib/device-navpay-history-repo.ts`
- Test: `navpay-admin/tests/unit/personal-navpay-history-status-route.test.ts`

**Step 1: Write the failing test**

```ts
import { describe, expect, test } from "vitest";
import { POST } from "@/app/api/personal/device/navpay-history-transactions/status/route";

describe("personal navpay history status route", () => {
  test("accepts state report and persists event", async () => {
    const req = new Request("http://localhost/api/personal/device/navpay-history-transactions/status", {
      method: "POST",
      headers: { "content-type": "application/json", authorization: "Bearer test" },
      body: JSON.stringify({
        clientDeviceId: "android_1",
        strategyVersion: "android.history_sync.v1",
        policy: { initialProbeMs: 60000, maxProbeMs: 900000, multiplier: 2 },
        state: "WAITING_TOKEN_REFRESH",
        stateChangedAtMs: 1000,
        tokenExpiredAtMs: 900,
        backoffCurrentMs: 60000,
        backoffNextMs: 120000,
        nextProbeAtMs: 61000,
        eventType: "PROBE_TRIGGERED_BY_TOKEN_EVENT",
        eventAtMs: 1000,
      }),
    });

    const resp = await POST(req as any);
    const json = await resp.json();
    expect(resp.status).toBe(200);
    expect(json.ok).toBe(true);
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/personal-navpay-history-status-route.test.ts -v`
Expected: FAIL due to missing route/validation.

**Step 3: Write minimal implementation**

- Implement zod schema and auth/device ownership checks.
- Upsert state + append event.
- Execute bounded cleanup (older than 7d + >500 per device) with low-frequency guard.

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/personal-navpay-history-status-route.test.ts -v`
Expected: PASS.

**Step 5: Commit**

```bash
git -C navpay-admin add src/app/api/personal/device/navpay-history-transactions/status/route.ts src/lib/device-navpay-history-repo.ts tests/unit/personal-navpay-history-status-route.test.ts
git -C navpay-admin commit -m "feat(history): add client status report api with event retention cleanup"
```

### Task 3: Extend admin read API to include client state and event timeline

**Files:**
- Modify: `navpay-admin/src/app/api/admin/resources/devices/[deviceId]/navpay-history-transactions/route.ts`
- Modify: `navpay-admin/src/lib/device-navpay-history-repo.ts`
- Test: `navpay-admin/tests/unit/device-navpay-history-transactions-route.test.ts`

**Step 1: Write the failing test**

```ts
test("returns client strategy meta for navpay history panel", async () => {
  const res = await GET(new Request("http://localhost/api/admin/resources/devices/dev_1/navpay-history-transactions") as any, {
    params: Promise.resolve({ deviceId: "dev_1" }),
  });
  const json = await res.json();
  expect(json.meta.clientState).toBeTruthy();
  expect(Array.isArray(json.meta.clientEvents)).toBe(true);
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/device-navpay-history-transactions-route.test.ts -v`
Expected: FAIL missing fields.

**Step 3: Write minimal implementation**

- Include `clientState` and recent `clientEvents` in route `meta`.

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/device-navpay-history-transactions-route.test.ts -v`
Expected: PASS.

**Step 5: Commit**

```bash
git -C navpay-admin add src/app/api/admin/resources/devices/[deviceId]/navpay-history-transactions/route.ts src/lib/device-navpay-history-repo.ts tests/unit/device-navpay-history-transactions-route.test.ts
git -C navpay-admin commit -m "feat(history): expose client strategy state in admin navpay history api"
```

### Task 4: Render strategy status card and timeline in panel UI

**Files:**
- Modify: `navpay-admin/src/components/device-navpay-history-transactions-panel.tsx`
- Test: `navpay-admin/tests/unit/device-navpay-history-panel-observability.test.tsx`

**Step 1: Write the failing test**

```tsx
it("shows token expired time with relative text and probe intervals", async () => {
  render(<DeviceNavpayHistoryTransactionsPanel deviceId="dev_1" timezone="Asia/Shanghai" />);
  expect(await screen.findByText(/Token最近过期时间/)).toBeInTheDocument();
  expect(screen.getByText(/当前探测间隔/)).toBeInTheDocument();
  expect(screen.getByText(/下一次失败后/)).toBeInTheDocument();
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/device-navpay-history-panel-observability.test.tsx -v`
Expected: FAIL missing UI.

**Step 3: Write minimal implementation**

- Add status card with:
  - token expiry absolute+relative time
  - current state
  - current/next backoff interval (friendly format)
  - next probe absolute+relative
  - last probe trigger/result
  - strategy version
  - last report time
- Add collapsible event timeline.

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/device-navpay-history-panel-observability.test.tsx -v`
Expected: PASS.

**Step 5: Commit**

```bash
git -C navpay-admin add src/components/device-navpay-history-transactions-panel.tsx tests/unit/device-navpay-history-panel-observability.test.tsx
git -C navpay-admin commit -m "feat(history-ui): show token expiry circuit breaker state and probe timeline"
```

### Task 5: Implement Android circuit-breaker state machine and status reporter

**Files:**
- Modify: `navpay-android/app/src/main/java/com/navpay/phonepe/NavpayHistorySyncManager.kt`
- Create: `navpay-android/app/src/main/java/com/navpay/phonepe/NavpayHistoryStatusReporter.kt`
- Test: `navpay-android/app/src/test/java/com/navpay/phonepe/NavpayHistorySyncManagerStateMachineTest.kt`

**Step 1: Write the failing test**

```kotlin
@Test
fun tokenExpired_412_pr003_authToken_opensCircuitAndSchedulesProbe() = runTest {
    val f = FakeHistorySyncDeps(...)
    f.enqueueSyncFailure(code = 412, exceptionCode = "PR003", expiredTokens = "AUTH_TOKEN")

    val out = f.manager.syncOnceForTest()

    assertFalse(out)
    assertEquals("WAITING_TOKEN_REFRESH", f.manager.currentStateForTest())
    assertEquals(60_000L, f.manager.currentBackoffMsForTest())
}
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-android && ./gradlew test --tests "*NavpayHistorySyncManagerStateMachineTest"`
Expected: FAIL due to missing state machine/reporter.

**Step 3: Write minimal implementation**

- Add state enum and transitions.
- Detect token-expired signature from error message/headers payload.
- Stop normal polling when circuit open.
- Add probe scheduler with backoff (60s base, x2, cap 15m).
- Emit status reports on every state transition and probe result.

**Step 4: Run test to verify it passes**

Run: `cd navpay-android && ./gradlew test --tests "*NavpayHistorySyncManagerStateMachineTest"`
Expected: PASS.

**Step 5: Commit**

```bash
git -C navpay-android add app/src/main/java/com/navpay/phonepe/NavpayHistorySyncManager.kt app/src/main/java/com/navpay/phonepe/NavpayHistoryStatusReporter.kt app/src/test/java/com/navpay/phonepe/NavpayHistorySyncManagerStateMachineTest.kt
git -C navpay-android commit -m "feat(android): add navpay history token-expiry circuit breaker and status reporting"
```

### Task 6: Add token-event immediate probe + backoff reset behavior

**Files:**
- Modify: `navpay-android/app/src/main/java/com/navpay/phonepe/NavpayHistorySyncManager.kt`
- Test: `navpay-android/app/src/test/java/com/navpay/phonepe/NavpayHistorySyncManagerTokenEventProbeTest.kt`

**Step 1: Write the failing test**

```kotlin
@Test
fun tokenEvent_triggersImmediateProbe_andResetsBackoffTo60s_evenWhenProbeFails() = runTest {
    val f = FakeHistorySyncDeps(...)
    f.forceStateWaitingWithBackoff(900_000L)

    f.manager.onTokenSnapshotUpdatedForTest(nowMs = 10_000L)

    assertEquals("RECOVERY_PROBING", f.manager.currentStateForTest())
    assertEquals(60_000L, f.manager.currentBackoffMsForTest())
}
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-android && ./gradlew test --tests "*NavpayHistorySyncManagerTokenEventProbeTest"`
Expected: FAIL.

**Step 3: Write minimal implementation**

- Add explicit token-event hook method.
- Trigger immediate probe and reset backoff baseline.
- On success return `RUNNING`; on failure continue from 60s sequence.

**Step 4: Run test to verify it passes**

Run: `cd navpay-android && ./gradlew test --tests "*NavpayHistorySyncManagerTokenEventProbeTest"`
Expected: PASS.

**Step 5: Commit**

```bash
git -C navpay-android add app/src/main/java/com/navpay/phonepe/NavpayHistorySyncManager.kt app/src/test/java/com/navpay/phonepe/NavpayHistorySyncManagerTokenEventProbeTest.kt
git -C navpay-android commit -m "feat(android): probe immediately on token event and reset backoff sequence"
```

### Task 7: Wire end-to-end status reporting contract and integration tests

**Files:**
- Modify: `navpay-admin/src/app/api/personal/device/navpay-history-transactions/status/route.ts`
- Modify: `navpay-android/app/src/main/java/com/navpay/ApiClient.kt`
- Modify: `navpay-android/app/src/main/java/com/navpay/phonepe/NavpayHistoryStatusReporter.kt`
- Test: `navpay-admin/tests/unit/personal-navpay-history-status-route.test.ts`
- Test: `navpay-android/app/src/test/java/com/navpay/ApiClientNavpayHistoryStatusTest.kt`

**Step 1: Write failing tests for request shape and persistence**

Add assertions for:
- `backoffCurrentMs/backoffNextMs/nextProbeAtMs`
- `tokenExpiredAtMs`
- `lastProbe.*`
- `eventType`

**Step 2: Run tests to confirm failure**

Run:
- `cd navpay-admin && yarn test tests/unit/personal-navpay-history-status-route.test.ts -v`
- `cd navpay-android && ./gradlew test --tests "*ApiClientNavpayHistoryStatusTest"`

Expected: FAIL.

**Step 3: Implement contract alignment**

- Add `ApiClient.reportNavpayHistoryStatus(...)`.
- Ensure reporter sends every transition/probe outcome.
- Ensure admin route validates and stores all fields.

**Step 4: Run tests to verify pass**

Run both commands again; expected PASS.

**Step 5: Commit**

```bash
git -C navpay-admin add src/app/api/personal/device/navpay-history-transactions/status/route.ts tests/unit/personal-navpay-history-status-route.test.ts
git -C navpay-admin commit -m "feat(history): persist probe interval telemetry from android client"

git -C navpay-android add app/src/main/java/com/navpay/ApiClient.kt app/src/main/java/com/navpay/phonepe/NavpayHistoryStatusReporter.kt app/src/test/java/com/navpay/ApiClientNavpayHistoryStatusTest.kt
git -C navpay-android commit -m "feat(android): report navpay history policy telemetry to admin"
```

### Task 8: End-to-end emulator + page + database validation

**Files:**
- Modify: `docs/plans/2026-03-29-navpay-history-token-expiry-circuit-breaker-implementation-plan.md` (verification notes append)

**Step 1: Start services and app**

Run:
- `cd navpay-admin && yarn db:migrate && yarn dev`
- `cd navpay-android && yarn emu1`
- `cd navpay-android && yarn i1`

Expected: admin running on `http://localhost:3000`, emulator online, app installed.

**Step 2: Trigger scenario matrix and capture evidence**

- Scenario A: normal running
- Scenario B: token expired -> circuit open
- Scenario C: timer probe fails and backoff increments
- Scenario D: token event triggers immediate probe + backoff reset to 60s
- Scenario E: probe success -> RUNNING

For each scenario collect:
- page screenshot/value from `?tab=navpay_history_transactions`
- DB rows from:
  - `device_navpay_history_client_state`
  - `device_navpay_history_client_events`

**Step 3: Verify data consistency**

Run SQL checks:

```sql
SELECT * FROM device_navpay_history_client_state WHERE device_id='dev_c5b8a148-f418-44b0-928d-874333d72e4b';
SELECT event_type, state_from, state_to, at_ms, payload_json
FROM device_navpay_history_client_events
WHERE device_id='dev_c5b8a148-f418-44b0-928d-874333d72e4b'
ORDER BY created_at_ms DESC
LIMIT 50;
```

Expected: page values match DB latest state and recent events.

**Step 4: Run full automated checks**

Run:
- `cd navpay-admin && yarn lint && yarn typecheck && yarn test`
- `cd navpay-android && ./gradlew test`

Expected: PASS.

**Step 5: Commit verification notes**

```bash
git add docs/plans/2026-03-29-navpay-history-token-expiry-circuit-breaker-implementation-plan.md
git commit -m "test: add e2e evidence for navpay history token-expiry circuit breaker"
```

