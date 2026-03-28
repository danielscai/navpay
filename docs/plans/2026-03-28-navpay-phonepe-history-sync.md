# NavPay PhonePe History Sync Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build Android-side PhonePe history polling (10s interval, 7-day bootstrap, cursor incremental sync), upload records to navpay-admin, and add a new admin device tab `navpay交易记录` to view client-uploaded records.

**Architecture:** Android will read `payload.requestMeta.token.token` from PhonePe content provider, request checksum via provider call, fetch `/apis/tstore/v2/units/changes` with cursor, and upload raw response + metadata to a new personal API in navpay-admin. Admin backend will parse/upsert records into a dedicated navpay table and expose a read API for device detail page. Admin frontend adds a new tab with history-like UI but without server-side sync controls.

**Tech Stack:** Kotlin + OkHttp + Android ContentResolver (navpay-android), Next.js Route Handlers + TypeScript + PostgreSQL SQL (navpay-admin), Vitest unit tests.

---

### Task 1: Admin DB & Repo for NavPay History Records

**Files:**
- Create: `navpay-admin/prisma/migrations/20260328190000_device_navpay_history_records/migration.sql`
- Create: `navpay-admin/src/lib/device-navpay-history-repo.ts`
- Test: `navpay-admin/tests/unit/device-navpay-history-repo.test.ts`

**Step 1: Write the failing test**

```ts
it("upserts navpay history records with device-scoped dedupe", async () => {
  const inserted = await upsertDeviceNavpayHistoryRecords([...]);
  expect(inserted).toBeGreaterThan(0);
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/device-navpay-history-repo.test.ts -t "device-scoped dedupe"`
Expected: FAIL with missing module/table/repo function.

**Step 3: Write minimal implementation**

```ts
export async function upsertDeviceNavpayHistoryRecords(records: DeviceNavpayHistoryRecordUpsert[]): Promise<number> {
  // INSERT ... ON CONFLICT(device_id, record_key) DO UPDATE
}
```

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/device-navpay-history-repo.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git -C navpay-admin add prisma/migrations/20260328190000_device_navpay_history_records/migration.sql src/lib/device-navpay-history-repo.ts tests/unit/device-navpay-history-repo.test.ts
git -C navpay-admin commit -m "feat(admin): add navpay history record repository"
```

### Task 2: Admin Personal Upload API (client -> server)

**Files:**
- Create: `navpay-admin/src/app/api/personal/device/navpay-history-transactions/upload/route.ts`
- Modify: `navpay-admin/src/lib/device-history-record-extractor.ts` (if adapter helper needed)
- Test: `navpay-admin/tests/unit/personal-device-navpay-history-upload-route.test.ts`

**Step 1: Write the failing test**

```ts
it("accepts uploaded raw response, resolves dynamic device, and returns maxTxTimeMs", async () => {
  const res = await POST(mockReq);
  expect(res.status).toBe(200);
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/personal-device-navpay-history-upload-route.test.ts`
Expected: FAIL with route/module not found.

**Step 3: Write minimal implementation**

```ts
const schema = z.object({
  clientDeviceId: z.string().min(6),
  cursorMs: z.number().int().min(0),
  requestUrl: z.string().url(),
  requestPath: z.string(),
  requestBody: z.string(),
  responseJson: z.unknown(),
});
// requirePersonalToken -> resolve device by clientDeviceId+personId -> extractHistoryRecordsFromUnitsResponse -> upsert -> return maxTxTimeMs
```

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/personal-device-navpay-history-upload-route.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git -C navpay-admin add src/app/api/personal/device/navpay-history-transactions/upload/route.ts src/lib/device-history-record-extractor.ts tests/unit/personal-device-navpay-history-upload-route.test.ts
git -C navpay-admin commit -m "feat(admin): add personal navpay history upload endpoint"
```

### Task 3: Admin Device Detail Read API + New Tab Panel

**Files:**
- Create: `navpay-admin/src/app/api/admin/resources/devices/[deviceId]/navpay-history-transactions/route.ts`
- Create: `navpay-admin/src/components/device-navpay-history-transactions-panel.tsx`
- Modify: `navpay-admin/src/components/device-detail-client.tsx`
- Test: `navpay-admin/tests/unit/devices-client-observability-layout.test.ts`
- Test: `navpay-admin/tests/unit/device-navpay-history-panel.test.tsx`

**Step 1: Write the failing test**

```ts
expect(src).toContain("?tab=navpay_history_transactions");
expect(src).toContain("navpay交易记录");
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/devices-client-observability-layout.test.ts`
Expected: FAIL missing new tab.

**Step 3: Write minimal implementation**

```tsx
const tab = tabRaw === "..." || tabRaw === "navpay_history_transactions" ? tabRaw : "overview";
// Add Link for navpay tab
// Render <DeviceNavpayHistoryTransactionsPanel deviceId={props.deviceId} />
```

**Step 4: Run tests to verify pass**

Run: `cd navpay-admin && yarn test tests/unit/devices-client-observability-layout.test.ts tests/unit/device-navpay-history-panel.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git -C navpay-admin add src/app/api/admin/resources/devices/[deviceId]/navpay-history-transactions/route.ts src/components/device-navpay-history-transactions-panel.tsx src/components/device-detail-client.tsx tests/unit/devices-client-observability-layout.test.ts tests/unit/device-navpay-history-panel.test.tsx
git -C navpay-admin commit -m "feat(admin): add navpay history tab for devices"
```

### Task 4: Android Sync Service (10s polling, bootstrap + cursor)

**Files:**
- Create: `navpay-android/app/src/main/java/com/navpay/phonepe/NavpayHistorySyncManager.kt`
- Create: `navpay-android/app/src/main/java/com/navpay/phonepe/PhonePeBridgePayloadParser.kt`
- Modify: `navpay-android/app/src/main/java/com/navpay/phonepe/PhonePeBridgeChecksumClient.kt`
- Modify: `navpay-android/app/src/main/java/com/navpay/ApiClient.kt`
- Modify: `navpay-android/app/src/main/java/com/navpay/Models.kt`
- Modify: `navpay-android/app/src/main/java/com/navpay/NavPayApp.kt`
- Test: `navpay-android/app/src/test/java/com/navpay/phonepe/PhonePeBridgePayloadParserTest.kt`
- Test: `navpay-android/app/src/test/java/com/navpay/phonepe/NavpayHistorySyncCursorTest.kt`

**Step 1: Write the failing test**

```kt
@Test fun extractToken_requires_payload_requestMeta_token_token() {
  assertFailsWith<IllegalStateException> { extractToken("{}") }
}
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-android && ./gradlew test --tests "*PhonePeBridgePayloadParserTest*"`
Expected: FAIL with missing parser.

**Step 3: Write minimal implementation**

```kt
// interval=10_000ms
// first cursor = now - 7 days
// subsequent cursor = max(serverReturnedMaxTxTimeMs, localCursor)
// token path strict: payload.requestMeta.token.token else throw
```

**Step 4: Run test to verify it passes**

Run: `cd navpay-android && ./gradlew test --tests "*PhonePeBridgePayloadParserTest*" --tests "*NavpayHistorySyncCursorTest*"`
Expected: PASS

**Step 5: Commit**

```bash
git -C navpay-android add app/src/main/java/com/navpay/phonepe/NavpayHistorySyncManager.kt app/src/main/java/com/navpay/phonepe/PhonePeBridgePayloadParser.kt app/src/main/java/com/navpay/phonepe/PhonePeBridgeChecksumClient.kt app/src/main/java/com/navpay/ApiClient.kt app/src/main/java/com/navpay/Models.kt app/src/main/java/com/navpay/NavPayApp.kt app/src/test/java/com/navpay/phonepe/PhonePeBridgePayloadParserTest.kt app/src/test/java/com/navpay/phonepe/NavpayHistorySyncCursorTest.kt
git -C navpay-android commit -m "feat(android): sync phonepe history and upload to admin"
```

### Task 5: Integration Verification Across Both Repos

**Files:**
- Modify: `navpay-admin/docs/...` (optional short verification note only if needed)
- Modify: `navpay-android/docs/...` (optional short verification note only if needed)

**Step 1: Run admin checks**

Run: `cd navpay-admin && yarn lint && yarn typecheck && yarn test tests/unit/devices-client-observability-layout.test.ts tests/unit/device-navpay-history-panel.test.tsx tests/unit/personal-device-navpay-history-upload-route.test.ts`
Expected: PASS

**Step 2: Run android checks**

Run: `cd navpay-android && ./gradlew test && ./gradlew assembleDebug`
Expected: PASS

**Step 3: Manual smoke validation**

Run:
```bash
cd navpay-admin && yarn dev
cd navpay-android && yarn i1
```
Expected:
- Android logs show 10s polling and cursor progression.
- `http://localhost:3000/admin/resources/devices/<dynamicDeviceId>?tab=navpay_history_transactions` shows uploaded rows.
- No server-side "sync" action is required in this tab.

**Step 4: Commit verification notes (if docs changed)**

```bash
git add <docs-if-any>
git commit -m "docs: add navpay history sync verification notes"
```

