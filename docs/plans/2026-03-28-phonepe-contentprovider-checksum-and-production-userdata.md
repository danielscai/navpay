# PhonePe ContentProvider Checksum & Production UserData Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a ContentProvider checksum service interface (while keeping existing checksum HTTP service) and make `user_data` payload conform to the same structure used by `navpay-admin` phonepehelper device view.

**Architecture:** Keep `com.phonepe.navpay.provider` as the on-device IPC boundary for app-to-app reads while preserving the existing local checksum HTTP service for compatibility. Expose checksum as provider RPC (`ContentProvider.call`) that mirrors the `/checksum` contract (`path/body/uuid -> ok/data.checksum/uuid`). Persist `user_data` as an admin-compatible view object (same top-level schema as `GET /api/admin/resources/devices/[deviceId]/phonepehelper`) so Android-side and admin-side can evolve against one canonical shape.

**Tech Stack:** Android ContentProvider, SQLiteOpenHelper, Java (phonepehelper), Kotlin (android reader smoke checks), Gradle/JUnit, phonepehelper compile/merge pipeline.

---

### Task 1: Define provider contract for checksum RPC + production user_data schema

**Files:**
- Modify: `navpay-phonepe/src/apk/phonepehelper/src/main/java/com/phonepehelper/NavpayBridgeContract.java`
- Create: `navpay-phonepe/src/apk/phonepehelper/src/main/java/com/phonepehelper/PhonePehelperDeviceViewBuilder.java`

**Step 1: Write the failing test**

```text
Use symbol checks to prove contract constants and builder class do not yet exist.
```

**Step 2: Run check to verify it fails**

Run: `rg -n "METHOD_CHECKSUM|EXTRA_PATH|PhonePehelperDeviceViewBuilder" navpay-phonepe/src/apk/phonepehelper/src/main/java/com/phonepehelper`
Expected: no matches.

**Step 3: Write minimal implementation**

```java
// NavpayBridgeContract: add checksum call method and extras constants.
public static final String METHOD_CHECKSUM = "checksum";
public static final String EXTRA_PATH = "path";
public static final String EXTRA_BODY = "body";
public static final String EXTRA_UUID = "uuid";
public static final String EXTRA_RESPONSE_JSON = "response_json";

// PhonePehelperDeviceViewBuilder: build JSON with admin-compatible shape:
// ok, deviceId, deviceOnline, deviceLastSeenAtMs, uploadMode, tokenCheckIntervalMs,
// summary, totalUploadCount, latestSample, events, keySnapshot, rawSamples, rows, lastCollectedAtMs.
```

**Step 4: Run check to verify it passes**

Run: `rg -n "METHOD_CHECKSUM|EXTRA_PATH|PhonePehelperDeviceViewBuilder|tokenCheckIntervalMs|rawSamples" navpay-phonepe/src/apk/phonepehelper/src/main/java/com/phonepehelper`
Expected: all constants and builder symbols exist.

**Step 5: Commit**

```bash
git -C navpay-phonepe add src/apk/phonepehelper/src/main/java/com/phonepehelper/NavpayBridgeContract.java src/apk/phonepehelper/src/main/java/com/phonepehelper/PhonePehelperDeviceViewBuilder.java
git -C navpay-phonepe commit -m "feat(phonepehelper): define checksum provider contract and user_data view schema"
```

### Task 2: Implement checksum ContentProvider service endpoint (keep HTTP endpoint)

**Files:**
- Modify: `navpay-phonepe/src/apk/phonepehelper/src/main/java/com/phonepehelper/ChecksumServer.java`
- Modify: `navpay-phonepe/src/apk/phonepehelper/src/main/java/com/phonepehelper/NavpayBridgeProvider.java`

**Step 1: Write the failing test**

```text
Use symbol checks to assert provider has no checksum call handler and checksum service API is not exposed for provider RPC.
```

**Step 2: Run check to verify it fails**

Run: `rg -n "METHOD_CHECKSUM|call\(|handleChecksumCall|computeChecksumForProvider" navpay-phonepe/src/apk/phonepehelper/src/main/java/com/phonepehelper`
Expected: checksum call handler symbols missing.

**Step 3: Write minimal implementation**

```java
// ChecksumServer: keep existing HTTP /health /checksum behavior unchanged.
// Also expose reusable static method for provider side:
// JSONObject computeChecksumResponse(Context context, String path, String body, String uuid)
// returns same shape as HTTP /checksum: {ok:true,data:{checksum,uuid}} or {ok:false,error:"..."}

// NavpayBridgeProvider.call(method,arg,extras):
// if method == METHOD_CHECKSUM, read path/body/uuid from extras,
// call ChecksumServer.computeChecksumResponse(...), and return Bundle with EXTRA_RESPONSE_JSON.
```

**Step 4: Run check to verify it passes**

Run: `rg -n "METHOD_CHECKSUM|call\(|computeChecksumResponse|EXTRA_RESPONSE_JSON" navpay-phonepe/src/apk/phonepehelper/src/main/java/com/phonepehelper`
Expected: checksum provider call path exists.

**Step 5: Commit**

```bash
git -C navpay-phonepe add src/apk/phonepehelper/src/main/java/com/phonepehelper/ChecksumServer.java src/apk/phonepehelper/src/main/java/com/phonepehelper/NavpayBridgeProvider.java
git -C navpay-phonepe commit -m "feat(phonepehelper): expose checksum via contentprovider call"
```

### Task 3: Persist user_data as admin-compatible production structure

**Files:**
- Modify: `navpay-phonepe/src/apk/phonepehelper/src/main/java/com/phonepehelper/NavpayBridgeDbHelper.java`
- Modify: `navpay-phonepe/src/apk/phonepehelper/src/main/java/com/PhonePeTweak/Def/PhonePeHelper.java`

**Step 1: Write the failing test**

```text
Use content query + key checks to show payload does not yet contain admin-compatible top-level keys.
```

**Step 2: Run check to verify it fails**

Run: `adb -s emulator-5554 shell content query --uri content://com.phonepe.navpay.provider/user_data`
Expected: payload currently is raw snapshot shape (requestMeta/upis/collectedAtMs), not admin phonepehelper view shape.

**Step 3: Write minimal implementation**

```java
// NavpayBridgeDbHelper.persistSnapshot(...):
// build admin-compatible view JSON via PhonePehelperDeviceViewBuilder and store it as payload.
// version/updated_at continue to track monotonic freshness.

// PhonePeHelper upload/publish paths continue calling persistNavpaySnapshot(snapshot)
// so both server upload and local provider stay consistent.
```

**Step 4: Run check to verify it passes**

Run: 
- `cd navpay-phonepe && yarn test`
- `adb -s emulator-5554 shell content query --uri content://com.phonepe.navpay.provider/user_data`
Expected: payload JSON contains keys `summary/events/keySnapshot/rawSamples/rows/latestSample`.

**Step 5: Commit**

```bash
git -C navpay-phonepe add src/apk/phonepehelper/src/main/java/com/phonepehelper/NavpayBridgeDbHelper.java src/apk/phonepehelper/src/main/java/com/PhonePeTweak/Def/PhonePeHelper.java
git -C navpay-phonepe commit -m "feat(phonepehelper): store production-shape phonepehelper user_data"
```

### Task 4: Add Android-side checksum provider client smoke path (optional but recommended)

**Files:**
- Create: `navpay-android/app/src/main/java/com/navpay/phonepe/PhonePeBridgeChecksumClient.kt`
- Create: `navpay-android/app/src/test/java/com/navpay/phonepe/PhonePeBridgeChecksumClientTest.kt`

**Step 1: Write the failing test**

```kotlin
@Test
fun `buildRequestBundle maps checksum fields`() { ... }

@Test
fun `parseResponseJson returns checksum and uuid when ok`() { ... }
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-android && ./gradlew :app:testDebugUnitTest --tests com.navpay.phonepe.PhonePeBridgeChecksumClientTest`
Expected: FAIL with unresolved `PhonePeBridgeChecksumClient`.

**Step 3: Write minimal implementation**

```kotlin
object PhonePeBridgeChecksumClient {
  fun buildExtras(path: String, body: String, uuid: String?): Bundle
  fun parseResponseJson(json: String): Result
}
```

**Step 4: Run test to verify it passes**

Run: `cd navpay-android && ./gradlew :app:testDebugUnitTest --tests com.navpay.phonepe.PhonePeBridgeChecksumClientTest`
Expected: PASS.

**Step 5: Commit**

```bash
git -C navpay-android add app/src/main/java/com/navpay/phonepe/PhonePeBridgeChecksumClient.kt app/src/test/java/com/navpay/phonepe/PhonePeBridgeChecksumClientTest.kt
git -C navpay-android commit -m "feat(android): add contentprovider checksum client"
```

### Task 5: Update architecture doc with canonical schema + provider services

**Files:**
- Modify: `docs/architecture/projects-and-deps.md`
- Modify: `docs/plans/2026-03-28-phonepe-contentprovider-checksum-and-production-userdata.md`

**Step 1: Write the failing test**

```text
Doc has no explicit section describing checksum contentprovider RPC and canonical user_data schema alignment with navpay-admin phonepehelper route.
```

**Step 2: Run check to verify it fails**

Run: `rg -n "METHOD_CHECKSUM|canonical schema|phonepehelper route|ContentProvider.call" docs/architecture/projects-and-deps.md`
Expected: no matching design details.

**Step 3: Write minimal implementation**

```markdown
Add architecture section:
- checksum service via ContentProvider.call("checksum")
- no health endpoint in provider contract
- user_data payload is canonical admin phonepehelper view shape
- schema compatibility contract and evolution rules
```

**Step 4: Run check to verify it passes**

Run: `rg -n "ContentProvider.call|checksum|user_data|phonepehelper" docs/architecture/projects-and-deps.md`
Expected: matches present.

**Step 5: Commit**

```bash
git -C /Users/danielscai/Documents/workspace/navpay add docs/architecture/projects-and-deps.md docs/plans/2026-03-28-phonepe-contentprovider-checksum-and-production-userdata.md
git -C /Users/danielscai/Documents/workspace/navpay commit -m "docs(architecture): define contentprovider checksum and canonical user_data schema"
```
