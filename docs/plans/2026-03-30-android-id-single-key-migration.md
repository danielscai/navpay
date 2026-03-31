# Android ID Single-Key Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `android_id` the only device identity key across `navpay-admin`, `navpay-android`, and `navpay-phonepe`, remove DB/device-resource `device_id` dependence, and fix cross-device mismatch in transactions/history lookup.

**Architecture:** Current mismatch happens because PhonePe history/query paths still key by `payment_devices.id`/`source_device_id`, while upload/binding can move under the same `clientDeviceId`. We will migrate to a single canonical key (`android_id`) at schema, API, and client payload layers, then remove legacy `device_id` columns and route semantics. Rollout is test-first per vertical slice, with strict compatibility window only inside this branch until all three repos are switched.

**Tech Stack:** Next.js + TypeScript + Prisma/PostgreSQL (`navpay-admin`), Kotlin Android app (`navpay-android`), Java Android helper modules (`navpay-phonepe`), Vitest/JUnit.

---

### Task 1: Reproduce and Lock the Current Mismatch (PhonePe Transactions Tab)

**Files:**
- Modify: `navpay-admin/tests/unit/device-history/device-history-detail-route.test.ts`
- Modify: `navpay-admin/src/lib/device-history-repo.ts`
- Modify: `navpay-admin/src/lib/device-history-sync.ts`
- Test: `navpay-admin/tests/unit/device-history/device-history-detail-route.test.ts`

**Step 1: Write the failing test**

```ts
// tests/unit/device-history/device-history-detail-route.test.ts
// new case: current android_id maps to new resource row, but history rows sit on old resource id
// expected: GET /history-transactions returns rows by same android_id
expect(json.total).toBe(1)
expect(json.rows[0].txId).toBe("unit_hist_rebind_1")
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn vitest tests/unit/device-history/device-history-detail-route.test.ts -t "same android_id"`
Expected: FAIL, route returns `total=0` because query is still `WHERE device_id = $1`.

**Step 3: Write minimal implementation**

```ts
// src/lib/device-history-repo.ts (shape)
export async function listDeviceHistoryRecords(androidId: string, page: number, pageSize: number) {
  return sqlQuery(`SELECT * FROM device_history_records WHERE android_id = $1 ...`, [androidId])
}
```

Also change template seed lookup from intercept logs to key by `source_android_id` instead of `source_device_id`.

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn vitest tests/unit/device-history/device-history-detail-route.test.ts -t "same android_id"`
Expected: PASS.

**Step 5: Commit**

```bash
cd navpay-admin
git add tests/unit/device-history/device-history-detail-route.test.ts src/lib/device-history-repo.ts src/lib/device-history-sync.ts
git commit -m "fix(admin): aggregate phonepe history by android_id instead of device_id"
```

### Task 2: Add Database Migration to Promote `android_id` as Canonical Key

**Files:**
- Create: `navpay-admin/prisma/migrations/20260330100000_android_id_single_key/migration.sql`
- Modify: `navpay-admin/prisma/schema.prisma`
- Test: `navpay-admin/tests/unit/device-observability-schema-contract.test.ts`

**Step 1: Write the failing schema contract test**

```ts
// assert no payment_devices.client_device_id remains
expect(schema).toContain("android_id")
expect(schema).not.toContain("client_device_id")
expect(schema).not.toContain("source_device_id")
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn vitest tests/unit/device-observability-schema-contract.test.ts -t "android_id"`
Expected: FAIL because schema still contains legacy columns.

**Step 3: Write minimal implementation**

```sql
-- migration.sql (core pattern)
ALTER TABLE payment_devices ADD COLUMN android_id text;
UPDATE payment_devices SET android_id = COALESCE(NULLIF(client_device_id, ''), id);
ALTER TABLE payment_devices ALTER COLUMN android_id SET NOT NULL;
CREATE UNIQUE INDEX payment_devices_android_id_ux ON payment_devices(android_id);

-- per-table backfill examples
ALTER TABLE device_history_records ADD COLUMN android_id text;
UPDATE device_history_records r
SET android_id = d.android_id
FROM payment_devices d
WHERE r.device_id = d.id;
```

Then switch Prisma models from `device_id`/`client_device_id` to `android_id`/`source_android_id` equivalents.

**Step 4: Run migration and schema tests**

Run: `cd navpay-admin && yarn db:migrate && yarn vitest tests/unit/device-observability-schema-contract.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
cd navpay-admin
git add prisma/migrations/20260330100000_android_id_single_key/migration.sql prisma/schema.prisma tests/unit/device-observability-schema-contract.test.ts
git commit -m "feat(admin-db): migrate device identity to android_id single key"
```

### Task 3: Replace Admin API Contracts from `clientDeviceId/deviceId` to `androidId`

**Files:**
- Modify: `navpay-admin/src/app/api/device/heartbeat/route.ts`
- Modify: `navpay-admin/src/app/api/personal/device/report/route.ts`
- Modify: `navpay-admin/src/app/api/personal/device/status/route.ts`
- Modify: `navpay-admin/src/app/api/personal/device/navpay-history-transactions/{template,status,upload}/route.ts`
- Modify: `navpay-admin/src/lib/personal-report.ts`
- Modify: `navpay-admin/src/lib/intercept-log.ts`
- Test: `navpay-admin/tests/unit/device-heartbeat.test.ts`
- Test: `navpay-admin/tests/unit/personal-device-navpay-history-upload-route.test.ts`

**Step 1: Write failing contract tests**

```ts
expect(body).toEqual(expect.objectContaining({ androidId: expect.any(String) }))
expect(body).not.toHaveProperty("clientDeviceId")
expect(body).not.toHaveProperty("deviceId")
```

**Step 2: Run tests to verify failure**

Run: `cd navpay-admin && yarn vitest tests/unit/device-heartbeat.test.ts tests/unit/personal-device-navpay-history-upload-route.test.ts`
Expected: FAIL on response/request field assertions.

**Step 3: Write minimal implementation**

```ts
const schema = z.object({ androidId: z.string().trim().min(6).max(128) })
await prisma.payment_devices.findUnique({ where: { android_id: body.data.androidId } })
return NextResponse.json({ ok: true, androidId: body.data.androidId, serverTimeMs })
```

Also rename persistence fields to `source_android_id` in history rows/events.

**Step 4: Run tests to verify pass**

Run: `cd navpay-admin && yarn vitest tests/unit/device-heartbeat.test.ts tests/unit/personal-device-navpay-history-upload-route.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
cd navpay-admin
git add src/app/api/device/heartbeat/route.ts src/app/api/personal/device/report/route.ts src/app/api/personal/device/status/route.ts src/app/api/personal/device/navpay-history-transactions src/lib/personal-report.ts src/lib/intercept-log.ts tests/unit/device-heartbeat.test.ts tests/unit/personal-device-navpay-history-upload-route.test.ts
git commit -m "refactor(admin-api): rename device identity contract to androidId"
```

### Task 4: Remove `device_id` from Runtime Task/Command Pipeline

**Files:**
- Modify: `navpay-admin/src/lib/device-runtime-task.ts`
- Modify: `navpay-admin/src/lib/device-runtime-command.ts`
- Modify: `navpay-admin/src/app/api/device/runtime-tasks/[taskId]/route.ts`
- Modify: `navpay-admin/src/app/api/device/runtime-tasks/delivered/route.ts`
- Modify: `navpay-admin/src/app/api/device/runtime-tasks/result/route.ts`
- Test: `navpay-admin/tests/unit/device-runtime-task.test.ts`
- Test: `navpay-admin/tests/unit/device-runtime-task-api-route.test.ts`

**Step 1: Write failing tests**

```ts
expect(row.androidId).toBe("android-123")
expect(sql).not.toContain("device_id")
```

**Step 2: Run tests to verify failure**

Run: `cd navpay-admin && yarn vitest tests/unit/device-runtime-task.test.ts tests/unit/device-runtime-task-api-route.test.ts`
Expected: FAIL due legacy column and field usage.

**Step 3: Write minimal implementation**

```ts
// rename storage key and SQL bindings
INSERT INTO device_runtime_tasks (id, android_id, source_app, ...)
WHERE android_id = $1
```

**Step 4: Run tests to verify pass**

Run: `cd navpay-admin && yarn vitest tests/unit/device-runtime-task.test.ts tests/unit/device-runtime-task-api-route.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
cd navpay-admin
git add src/lib/device-runtime-task.ts src/lib/device-runtime-command.ts src/app/api/device/runtime-tasks tests/unit/device-runtime-task.test.ts tests/unit/device-runtime-task-api-route.test.ts
git commit -m "refactor(admin-runtime): switch runtime command channel to android_id"
```

### Task 5: Rename Admin UI Routes and View Models to `androidId`

**Files:**
- Modify: `navpay-admin/src/app/admin/resources/devices/[deviceId]/page.tsx`
- Modify: `navpay-admin/src/components/device-detail-client.tsx`
- Modify: `navpay-admin/src/components/device-history-transactions-panel.tsx`
- Modify: `navpay-admin/src/components/device-navpay-history-transactions-panel.tsx`
- Modify: `navpay-admin/src/components/device-phonepehelper-panel.tsx`
- Modify: `navpay-admin/src/components/devices-client.tsx`
- Test: `navpay-admin/tests/unit/device-detail-tabs-order.test.ts`
- Test: `navpay-admin/tests/unit/devices-client-observability-layout.test.ts`

**Step 1: Write failing tests**

```ts
expect(linkHref).toContain("/admin/resources/devices/android-")
expect(payload.androidId).toBeDefined()
```

**Step 2: Run tests to verify failure**

Run: `cd navpay-admin && yarn vitest tests/unit/device-detail-tabs-order.test.ts tests/unit/devices-client-observability-layout.test.ts`
Expected: FAIL on prop/URL names.

**Step 3: Write minimal implementation**

```tsx
// use androidId in props and request params naming
fetch(`/api/admin/resources/devices/${encodeURIComponent(props.androidId)}/history-transactions`)
```

**Step 4: Run tests to verify pass**

Run: `cd navpay-admin && yarn vitest tests/unit/device-detail-tabs-order.test.ts tests/unit/devices-client-observability-layout.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
cd navpay-admin
git add src/app/admin/resources/devices/[deviceId]/page.tsx src/components/device-detail-client.tsx src/components/device-history-transactions-panel.tsx src/components/device-navpay-history-transactions-panel.tsx src/components/device-phonepehelper-panel.tsx src/components/devices-client.tsx tests/unit/device-detail-tabs-order.test.ts tests/unit/devices-client-observability-layout.test.ts
git commit -m "refactor(admin-ui): expose androidId-only device resource identity"
```

### Task 6: Update `navpay-android` to Use `androidId` End-to-End

**Files:**
- Modify: `navpay-android/app/src/main/java/com/navpay/DeviceManager.kt`
- Modify: `navpay-android/app/src/main/java/com/navpay/ApiClient.kt`
- Modify: `navpay-android/app/src/main/java/com/navpay/HeartbeatManager.kt`
- Modify: `navpay-android/app/src/main/java/com/navpay/Models.kt`
- Modify: `navpay-android/app/src/main/java/com/navpay/phonepe/NavpayHistorySyncManager.kt`
- Test: `navpay-android/app/src/test/java/com/navpay/ApiClientNavpayHistoryUploadTest.kt`
- Test: `navpay-android/app/src/test/java/com/navpay/ApiClientNavpayHistoryStatusTest.kt`

**Step 1: Write failing tests**

```kotlin
assertTrue(body.contains("\"androidId\":\"android-id-1\""))
assertFalse(body.contains("clientDeviceId"))
```

**Step 2: Run tests to verify failure**

Run: `cd navpay-android && ./gradlew test --tests "com.navpay.ApiClientNavpayHistory*Test"`
Expected: FAIL because payload still sends `clientDeviceId`.

**Step 3: Write minimal implementation**

```kotlin
fun getOrCreateAndroidId(): String
payload.put("androidId", androidId)
```

Rename result field usages from `deviceId` to `androidId` where returned identity is device identity.

**Step 4: Run tests to verify pass**

Run: `cd navpay-android && ./gradlew test --tests "com.navpay.ApiClientNavpayHistory*Test"`
Expected: PASS.

**Step 5: Commit**

```bash
cd navpay-android
git add app/src/main/java/com/navpay/DeviceManager.kt app/src/main/java/com/navpay/ApiClient.kt app/src/main/java/com/navpay/HeartbeatManager.kt app/src/main/java/com/navpay/Models.kt app/src/main/java/com/navpay/phonepe/NavpayHistorySyncManager.kt app/src/test/java/com/navpay/ApiClientNavpayHistoryUploadTest.kt app/src/test/java/com/navpay/ApiClientNavpayHistoryStatusTest.kt
git commit -m "refactor(android): rename clientDeviceId contract to androidId"
```

### Task 7: Update `navpay-phonepe` Heartbeat/Interceptor Payload Identity to `androidId`

**Files:**
- Modify: `navpay-phonepe/src/apk/heartbeat_bridge/src/main/java/com/heartbeatbridge/HeartbeatBridgeContract.java`
- Modify: `navpay-phonepe/src/apk/heartbeat_bridge/src/main/java/com/heartbeatbridge/HeartbeatSender.java`
- Modify: `navpay-phonepe/src/apk/phonepehelper/src/main/java/com/phonepehelper/NavpayHeartbeatSender.java`
- Modify: `navpay-phonepe/src/apk/https_interceptor/app/src/main/java/com/httpinterceptor/interceptor/DeviceInfoEnricher.java`
- Modify: `navpay-phonepe/src/apk/https_interceptor/app/src/main/java/com/httpinterceptor/interceptor/DeviceSnapshot.java`
- Test: `navpay-phonepe/src/apk/https_interceptor/app/src/test/java/com/httpinterceptor/interceptor/DeviceInfoEnricherTest.java`
- Test: `navpay-phonepe/src/pipeline/orch/tests/test_heartbeat_bridge_contract.py`

**Step 1: Write failing tests**

```java
assertEquals("existing-android-id", enriched.get("androidId"));
assertFalse(enriched.containsKey("clientDeviceId"));
```

**Step 2: Run tests to verify failure**

Run: `cd navpay-phonepe/src/pipeline/orch && pytest tests/test_heartbeat_bridge_contract.py -q`
Expected: FAIL because contract still references `clientDeviceId`.

**Step 3: Write minimal implementation**

```java
public static final String EXTRA_ANDROID_ID = "androidId";
payload.put("androidId", resolveAndroidId(context));
```

**Step 4: Run tests to verify pass**

Run: `cd navpay-phonepe/src/pipeline/orch && pytest tests/test_heartbeat_bridge_contract.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
cd navpay-phonepe
git add src/apk/heartbeat_bridge/src/main/java/com/heartbeatbridge/HeartbeatBridgeContract.java src/apk/heartbeat_bridge/src/main/java/com/heartbeatbridge/HeartbeatSender.java src/apk/phonepehelper/src/main/java/com/phonepehelper/NavpayHeartbeatSender.java src/apk/https_interceptor/app/src/main/java/com/httpinterceptor/interceptor/DeviceInfoEnricher.java src/apk/https_interceptor/app/src/main/java/com/httpinterceptor/interceptor/DeviceSnapshot.java src/apk/https_interceptor/app/src/test/java/com/httpinterceptor/interceptor/DeviceInfoEnricherTest.java src/pipeline/orch/tests/test_heartbeat_bridge_contract.py
git commit -m "refactor(phonepe): heartbeat and log identity key renamed to androidId"
```

### Task 8: Data Backfill + Drop Legacy Columns (`device_id`/`client_device_id`)

**Files:**
- Modify: `navpay-admin/prisma/migrations/20260330100000_android_id_single_key/migration.sql`
- Modify: `navpay-admin/scripts/export-intercept-checksum-fixture.ts`
- Test: `navpay-admin/tests/unit/intercept/export-intercept-checksum-fixture.test.ts`

**Step 1: Write failing test for exported field names**

```ts
expect(sample.sourceAndroidId).toBeDefined()
expect(sample.sourceDeviceId).toBeUndefined()
expect(sample.sourceClientDeviceId).toBeUndefined()
```

**Step 2: Run test to verify failure**

Run: `cd navpay-admin && yarn vitest tests/unit/intercept/export-intercept-checksum-fixture.test.ts`
Expected: FAIL with old field names.

**Step 3: Write minimal implementation**

```sql
ALTER TABLE http_intercept_logs RENAME COLUMN source_client_device_id TO source_android_id;
ALTER TABLE http_intercept_logs DROP COLUMN source_device_id;

ALTER TABLE payment_devices DROP COLUMN id;
ALTER TABLE payment_devices DROP COLUMN client_device_id;
```

Then update script mapping to `source_android_id` only.

**Step 4: Run test to verify pass**

Run: `cd navpay-admin && yarn vitest tests/unit/intercept/export-intercept-checksum-fixture.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
cd navpay-admin
git add prisma/migrations/20260330100000_android_id_single_key/migration.sql scripts/export-intercept-checksum-fixture.ts tests/unit/intercept/export-intercept-checksum-fixture.test.ts
git commit -m "chore(admin-db): drop legacy device_id/client_device_id columns"
```

### Task 9: Full Verification and Cleanup Gate (No Legacy Keys Left)

**Files:**
- Modify: `navpay-admin/docs/personal-device-heartbeat.md`
- Modify: `navpay-android/docs/plans/2026-02-12-android-personal-mobile-api-heartbeat-payout.md`
- Modify: `navpay-phonepe/src/apk/phonepehelper/README.md`
- Test: cross-repo grep gate (new script or CI step)

**Step 1: Add failing verification gate**

```bash
# fail if legacy identity names remain in production code
rg -n "clientDeviceId|client_device_id|source_client_device_id|source_device_id|\bdevice_id\b" navpay-admin/src navpay-android/app/src navpay-phonepe/src/apk
```

**Step 2: Run gate and verify it fails initially**

Run: `rg -n "clientDeviceId|client_device_id|source_client_device_id|source_device_id|\bdevice_id\b" navpay-admin/src navpay-android/app/src navpay-phonepe/src/apk`
Expected: FAIL (non-empty output).

**Step 3: Finish cleanup and docs**

```md
- all APIs use `androidId`
- DB identity key is `android_id`
- no `deviceId/clientDeviceId` in payload contracts
```

**Step 4: Run full verification**

Run:
- `cd navpay-admin && yarn lint && yarn typecheck && yarn test`
- `cd navpay-android && ./gradlew test`
- `cd navpay-phonepe/src/pipeline/orch && pytest -q`
- `cd /Users/danielscai/Documents/workspace/navpay && rg -n "clientDeviceId|client_device_id|source_client_device_id|source_device_id|\bdevice_id\b" navpay-admin/src navpay-android/app/src navpay-phonepe/src/apk`

Expected: all tests pass; final grep has no production-code matches.

**Step 5: Commit**

```bash
git -C navpay-admin add docs/personal-device-heartbeat.md
git -C navpay-admin commit -m "docs(admin): update heartbeat/device identity contract to android_id"

git -C navpay-android add docs/plans/2026-02-12-android-personal-mobile-api-heartbeat-payout.md
git -C navpay-android commit -m "docs(android): align API payload naming with androidId"

git -C navpay-phonepe add src/apk/phonepehelper/README.md
git -C navpay-phonepe commit -m "docs(phonepe): align heartbeat identity naming with androidId"
```

## Worktree and Execution Notes

- Use separate worktrees (required by workspace policy):
  - `git -C navpay-admin worktree add worktrees/navpay-admin/android-id-single-key main -b codex/android-id-single-key`
  - `git -C navpay-android worktree add worktrees/navpay-android/android-id-single-key main -b codex/android-id-single-key`
  - `git -C navpay-phonepe worktree add worktrees/navpay-phonepe/android-id-single-key main -b codex/android-id-single-key`
- For `navpay-admin` worktree, set isolated `.env.local`, DB, Redis per AGENTS policy before running tests.
- Execution discipline: @test-driven-development, @systematic-debugging, @verification-before-completion.

