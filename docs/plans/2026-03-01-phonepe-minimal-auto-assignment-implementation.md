# PhonePe Minimal Auto Assignment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the simplest production-safe flow where `phonepe` uploads are automatically assigned to the current Android logged-in user on the same device, with minimal security hardening and no phonepe UI confirmation.

**Architecture:** Use `ANDROID_ID` as `clientDeviceId` in Android report/heartbeat APIs, keep a server-side current owner pointer in `payment_devices.person_id`, and assign phonepe uploads at ingest time by resolving `android_id -> person_id`. Add a lightweight phonepe ingest endpoint and a device status endpoint; Android only shows offline state and a fallback "Open PhonePe" action.

**Tech Stack:** Next.js route handlers, Prisma (PostgreSQL), Zod validation, Vitest unit tests, Kotlin Android client.

**Status Notes (2026-03-01):**
- Task 1 completed: Android `clientDeviceId` now prefers `ANDROID_ID`, fallback only when unavailable.
- Task 2 completed: personal device report/heartbeat responses now expose explicit `ownerPersonId`, and latest heartbeat/report keeps ownership pointer semantics explicit.
- Task 3 completed: added `/api/intercept/phonepe/snapshot` ingest and auto-assignment via `androidId -> payment_devices.person_id`.
- Task 4 completed: added `/api/personal/device/status` endpoint for Android offline checks.
- Task 5 completed: Android added `deviceStatus` parser/API and PhonePe launcher fallback entry.
- Task 6 verification completed: targeted admin + android test suites pass.

**Known Limitations (V1):**
- No cryptographic signing between Android and PhonePe ingest payload.
- No binding token challenge/response flow.
- PhonePe snapshot ingestion currently returns `409 device_unassigned` when `androidId` has no active owner pointer.
- Android fallback entry is minimal and intentionally not a full guided recovery flow.

---

### Task 1: Lock Device Identity to ANDROID_ID on Android

**Files:**
- Modify: `navpay-android/app/src/main/java/com/navpay/DeviceManager.kt`
- Modify: `navpay-android/app/src/main/java/com/navpay/HeartbeatManager.kt`
- Test: `navpay-android/app/src/test/java/com/navpay/DeviceManagerAndroidIdTest.kt`

**Step 1: Write the failing test**

```kotlin
@Test
fun returnsAndroidIdAsClientDeviceId() {
    val id = DeviceManager.resolveClientDeviceIdForTest("android-id-123")
    assertEquals("android-id-123", id)
}
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-android && ./gradlew testDebugUnitTest --tests com.navpay.DeviceManagerAndroidIdTest`
Expected: FAIL with unresolved method or wrong returned ID.

**Step 3: Write minimal implementation**

```kotlin
fun getOrCreateClientDeviceId(): String {
    val androidId = Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID)
    return if (!androidId.isNullOrBlank()) androidId else fallbackStoredUuid()
}
```

**Step 4: Run test to verify it passes**

Run: `cd navpay-android && ./gradlew testDebugUnitTest --tests com.navpay.DeviceManagerAndroidIdTest`
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-android/app/src/main/java/com/navpay/DeviceManager.kt \
        navpay-android/app/src/main/java/com/navpay/HeartbeatManager.kt \
        navpay-android/app/src/test/java/com/navpay/DeviceManagerAndroidIdTest.kt
git commit -m "feat(navpay-android): use ANDROID_ID as client device id"
```

### Task 2: Keep Ownership Pointer Behavior Explicit in Personal Device APIs

**Files:**
- Modify: `navpay-admin/src/app/api/personal/device/report/route.ts`
- Modify: `navpay-admin/src/app/api/personal/device/heartbeat/route.ts`
- Test: `navpay-admin/tests/unit/device-heartbeat.test.ts`

**Step 1: Write the failing test**

```ts
test("device ownership switches to latest logged-in person for same clientDeviceId", async () => {
  // person A report -> person B heartbeat on same clientDeviceId
  // expect payment_devices.person_id to equal person B
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/device-heartbeat.test.ts -t "ownership switches"`
Expected: FAIL because ownership switch case is not asserted/implemented clearly.

**Step 3: Write minimal implementation**

```ts
await prisma.payment_devices.update({
  where: { id: deviceId },
  data: { person_id: personId, updated_at_ms: BigInt(now) },
});
```

Also keep response payload explicit:

```ts
return NextResponse.json({ ok: true, deviceId, ownerPersonId: personId, serverTimeMs: now });
```

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/device-heartbeat.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-admin/src/app/api/personal/device/report/route.ts \
        navpay-admin/src/app/api/personal/device/heartbeat/route.ts \
        navpay-admin/tests/unit/device-heartbeat.test.ts
git commit -m "feat(navpay-admin): enforce latest-owner pointer on device report/heartbeat"
```

### Task 3: Add PhonePe Snapshot Ingest With Auto Assignment

**Files:**
- Create: `navpay-admin/src/app/api/intercept/phonepe/snapshot/route.ts`
- Create: `navpay-admin/src/lib/phonepe-assignment.ts`
- Test: `navpay-admin/tests/unit/phonepe-snapshot-assignment.test.ts`

**Step 1: Write the failing test**

```ts
test("assigns phonepe snapshot to current owner by android_id", async () => {
  // arrange payment_devices row: client_device_id=androidId, person_id=personB
  // post snapshot with androidId
  // expect stored assigned person id == personB
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/phonepe-snapshot-assignment.test.ts`
Expected: FAIL with missing route/lib.

**Step 3: Write minimal implementation**

```ts
const device = await prisma.payment_devices.findFirst({
  where: { client_device_id: body.androidId },
  select: { id: true, person_id: true },
});

await prisma.payment_person_report_logs.create({
  data: {
    id: id("pprlog"),
    person_id: String(device?.person_id ?? ""),
    type: "PHONEPE_SNAPSHOT",
    entity_type: "phonepe",
    entity_id: String(device?.id ?? ""),
    meta_json: JSON.stringify({ androidId: body.androidId, payload: body.payload }),
    created_at_ms: BigInt(Date.now()),
  },
});
```

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/phonepe-snapshot-assignment.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-admin/src/app/api/intercept/phonepe/snapshot/route.ts \
        navpay-admin/src/lib/phonepe-assignment.ts \
        navpay-admin/tests/unit/phonepe-snapshot-assignment.test.ts
git commit -m "feat(navpay-admin): ingest phonepe snapshot and auto-assign by android_id"
```

### Task 4: Add Device Status Endpoint for Android Offline Indicator

**Files:**
- Create: `navpay-admin/src/app/api/personal/device/status/route.ts`
- Modify: `navpay-admin/src/lib/device-online.ts`
- Test: `navpay-admin/tests/unit/device-status-route.test.ts`

**Step 1: Write the failing test**

```ts
test("returns online=false when last_seen exceeds grace window", async () => {
  // create device with stale last_seen_at_ms
  // call /api/personal/device/status
  // expect online false
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/device-status-route.test.ts`
Expected: FAIL with missing route.

**Step 3: Write minimal implementation**

```ts
const device = await prisma.payment_devices.findFirst({ where: { client_device_id: clientDeviceId } });
const online = isDeviceOnline({ lastSeenAtMs: device?.last_seen_at_ms ? Number(device.last_seen_at_ms) : null });
return NextResponse.json({ ok: true, online, lastSeenAtMs: device?.last_seen_at_ms ? Number(device.last_seen_at_ms) : null });
```

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/device-status-route.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-admin/src/app/api/personal/device/status/route.ts \
        navpay-admin/src/lib/device-online.ts \
        navpay-admin/tests/unit/device-status-route.test.ts
git commit -m "feat(navpay-admin): add personal device status endpoint"
```

### Task 5: Minimal Android UX Fallback (Open PhonePe)

**Files:**
- Modify: `navpay-android/app/src/main/java/com/navpay/ApiClient.kt`
- Modify: `navpay-android/app/src/main/java/com/navpay/ToolsFragment.kt`
- Test: `navpay-android/app/src/test/java/com/navpay/ApiClientDeviceStatusTest.kt`

**Step 1: Write the failing test**

```kotlin
@Test
fun parsesDeviceStatusOnlineFlag() {
    val json = JSONObject("""{"ok":true,"online":false}""")
    val out = ApiClient.parseDeviceStatusForTest(json)
    assertFalse(out.online)
}
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-android && ./gradlew testDebugUnitTest --tests com.navpay.ApiClientDeviceStatusTest`
Expected: FAIL with missing parser/API.

**Step 3: Write minimal implementation**

```kotlin
suspend fun deviceStatus(clientDeviceId: String): DeviceStatusResult

fun openPhonePeFallback(context: Context) {
    val intent = context.packageManager.getLaunchIntentForPackage("com.phonepe.app")
    if (intent != null) context.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
}
```

**Step 4: Run test to verify it passes**

Run: `cd navpay-android && ./gradlew testDebugUnitTest --tests com.navpay.ApiClientDeviceStatusTest`
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-android/app/src/main/java/com/navpay/ApiClient.kt \
        navpay-android/app/src/main/java/com/navpay/ToolsFragment.kt \
        navpay-android/app/src/test/java/com/navpay/ApiClientDeviceStatusTest.kt
git commit -m "feat(navpay-android): add device status check and phonepe fallback launcher"
```

### Task 6: End-to-End Verification and Docs Sync

**Files:**
- Modify: `docs/plans/2026-03-01-phonepe-minimal-auto-assignment-implementation.md`
- Test: `navpay-admin/tests/unit/device-heartbeat.test.ts`
- Test: `navpay-admin/tests/unit/phonepe-snapshot-assignment.test.ts`
- Test: `navpay-admin/tests/unit/device-status-route.test.ts`
- Test: `navpay-android/app/src/test/java/com/navpay/DeviceManagerAndroidIdTest.kt`
- Test: `navpay-android/app/src/test/java/com/navpay/ApiClientDeviceStatusTest.kt`

**Step 1: Write the failing test**

```text
N/A (verification task)
```

**Step 2: Run test suite to verify current failures are understood**

Run:
- `cd navpay-admin && yarn test tests/unit/device-heartbeat.test.ts tests/unit/phonepe-snapshot-assignment.test.ts tests/unit/device-status-route.test.ts`
- `cd navpay-android && ./gradlew testDebugUnitTest --tests com.navpay.DeviceManagerAndroidIdTest --tests com.navpay.ApiClientDeviceStatusTest`

Expected: all PASS after Task 1-5.

**Step 3: Write minimal implementation**

```text
N/A (only update plan status notes + known limitations section)
```

**Step 4: Run tests to verify pass state remains stable**

Run the same commands again.
Expected: PASS.

**Step 5: Commit**

```bash
git add docs/plans/2026-03-01-phonepe-minimal-auto-assignment-implementation.md
git commit -m "docs(plans): finalize minimal phonepe auto-assignment rollout plan"
```

## Guardrails

- DRY: reuse existing `payment_devices` pointer instead of adding new relation tables in V1.
- YAGNI: defer cryptographic hardening and binding-token protocol to V2.
- TDD-first for every backend and Android change.
- Keep commits small and task-scoped.

## Skill References

- Use `@test-driven-development` while executing each task.
- Use `@systematic-debugging` if any test behaves unexpectedly.
