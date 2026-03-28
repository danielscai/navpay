# PhonePe ContentProvider Bridge Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a local on-device bridge where `navpay-phonepe` writes latest snapshot into an exported `ContentProvider`, and `navpay-android` reads it on foreground resume.

**Architecture:** `navpay-phonepe` persists a single latest snapshot row (versioned + timestamped) in a Provider-backed SQLite table and updates it whenever helper snapshot/token state changes. `navpay-android` queries the provider URI in `onResume()` through a dedicated reader class, validates freshness/version metadata, and updates UI/state if payload changed. Provider registration is injected into patched PhonePe manifest during merge.

**Tech Stack:** Android ContentProvider, SQLiteOpenHelper, Kotlin (navpay-android), Java (phonepehelper), Gradle/JUnit, helper compile+merge scripts.

---

### Task 1: Add NavPay snapshot provider contract and storage in phonepehelper

**Files:**
- Create: `navpay-phonepe/src/apk/phonepehelper/src/main/java/com/phonepehelper/NavpayBridgeContract.java`
- Create: `navpay-phonepe/src/apk/phonepehelper/src/main/java/com/phonepehelper/NavpayBridgeDbHelper.java`
- Create: `navpay-phonepe/src/apk/phonepehelper/src/main/java/com/phonepehelper/NavpayBridgeProvider.java`
- Modify: `navpay-phonepe/src/apk/phonepehelper/src/main/java/com/PhonePeTweak/Def/PhonePeHelper.java`

**Step 1: Write the failing test**

```text
No formal unit harness exists in phonepehelper; use compile-and-symbol checks as executable failing checks.
```

**Step 2: Run check to verify it fails**

Run: `rg -n "NavpayBridgeProvider|content://com.phonepe.navpay.provider/user_data" navpay-phonepe/src/apk/phonepehelper/src/main/java`
Expected: no provider/contract definitions found.

**Step 3: Write minimal implementation**

```java
// Contract constants: authority, path, columns, content URI
// SQLite helper: table navpay_user_data with single-row upsert by _id=1
// Provider: query/getType/insert/update; exported read access for NavPay app package
// PhonePeHelper: write latest snapshot payload + version + updated_at into provider DB helper entrypoint
```

**Step 4: Run check to verify it passes**

Run: `rg -n "class NavpayBridgeProvider|AUTHORITY = \"com.phonepe.navpay.provider\"|TABLE_USER_DATA" navpay-phonepe/src/apk/phonepehelper/src/main/java`
Expected: provider + contract + db symbols exist.

**Step 5: Commit**

```bash
git -C navpay-phonepe add src/apk/phonepehelper/src/main/java/com/phonepehelper/NavpayBridgeContract.java src/apk/phonepehelper/src/main/java/com/phonepehelper/NavpayBridgeDbHelper.java src/apk/phonepehelper/src/main/java/com/phonepehelper/NavpayBridgeProvider.java src/apk/phonepehelper/src/main/java/com/PhonePeTweak/Def/PhonePeHelper.java
git -C navpay-phonepe commit -m "feat(phonepehelper): persist navpay snapshot via content provider"
```

### Task 2: Inject provider declaration during phonepehelper merge

**Files:**
- Modify: `navpay-phonepe/src/apk/phonepehelper/scripts/merge.sh`

**Step 1: Write the failing test**

```text
Add a shell-level verification block expecting provider authority insertion in target AndroidManifest.xml.
```

**Step 2: Run check to verify it fails**

Run: `rg -n "com\.phonepe\.navpay\.provider|NavpayBridgeProvider" navpay-phonepe/src/apk/phonepehelper/scripts/merge.sh`
Expected: no manifest injection for provider.

**Step 3: Write minimal implementation**

```bash
# In merge.sh: patch AndroidManifest.xml with xml.etree python snippet to append provider if absent
# provider name: com.phonepehelper.NavpayBridgeProvider
# authorities: com.phonepe.navpay.provider
# exported: true, grantUriPermissions: true
```

**Step 4: Run check to verify it passes**

Run: `rg -n "com\.phonepe\.navpay\.provider|NavpayBridgeProvider|grantUriPermissions" navpay-phonepe/src/apk/phonepehelper/scripts/merge.sh`
Expected: manifest patch logic present.

**Step 5: Commit**

```bash
git -C navpay-phonepe add src/apk/phonepehelper/scripts/merge.sh
git -C navpay-phonepe commit -m "feat(phonepehelper): inject navpay bridge provider manifest entry"
```

### Task 3: Add navpay-android reader and onResume trigger (TDD)

**Files:**
- Create: `navpay-android/app/src/main/java/com/navpay/phonepe/PhonePeBridgeReader.kt`
- Create: `navpay-android/app/src/test/java/com/navpay/phonepe/PhonePeBridgeReaderTest.kt`
- Modify: `navpay-android/app/src/main/java/com/navpay/MainActivity.kt`

**Step 1: Write the failing test**

```kotlin
@Test
fun `extractLatest returns null when cursor empty`() { ... }

@Test
fun `extractLatest maps payload version updatedAt correctly`() { ... }
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-android && ./gradlew test --tests com.navpay.phonepe.PhonePeBridgeReaderTest`
Expected: FAIL with unresolved `PhonePeBridgeReader`.

**Step 3: Write minimal implementation**

```kotlin
object PhonePeBridgeReader {
  val CONTENT_URI = Uri.parse("content://com.phonepe.navpay.provider/user_data")
  data class Snapshot(...)
  fun readLatest(context: Context): Snapshot?
  internal fun extractLatest(cursor: Cursor): Snapshot?
}
```

```kotlin
// MainActivity.onResume()
// query provider and log/update local state only when payload changed
```

**Step 4: Run test to verify it passes**

Run: `cd navpay-android && ./gradlew test --tests com.navpay.phonepe.PhonePeBridgeReaderTest`
Expected: PASS.

**Step 5: Commit**

```bash
git -C navpay-android add app/src/main/java/com/navpay/phonepe/PhonePeBridgeReader.kt app/src/main/java/com/navpay/MainActivity.kt app/src/test/java/com/navpay/phonepe/PhonePeBridgeReaderTest.kt
git -C navpay-android commit -m "feat(android): read phonepe shared snapshot on resume"
```

### Task 4: End-to-end build verification for both repos

**Files:**
- Modify: `navpay-phonepe/src/apk/phonepehelper/README.md`
- Modify: `docs/plans/2026-03-28-phonepe-contentprovider-bridge.md` (verification notes section)

**Step 1: Write the failing test**

```text
Run project verification commands before docs update; capture failures if any.
```

**Step 2: Run checks to verify current status**

Run: `cd navpay-phonepe/src/apk/phonepehelper && ./scripts/compile.sh`
Expected: PASS and generated smali includes new provider classes.

Run: `cd navpay-android && ./gradlew test`
Expected: PASS.

**Step 3: Write minimal documentation update**

```markdown
Add provider URI/columns and navpay-android onResume read expectations.
```

**Step 4: Re-run checks**

Run: same commands above.
Expected: PASS again.

**Step 5: Commit**

```bash
git -C navpay-phonepe add src/apk/phonepehelper/README.md
git -C navpay commit docs/plans/2026-03-28-phonepe-contentprovider-bridge.md -m "docs(plan): add phonepe content provider bridge execution notes"
```
