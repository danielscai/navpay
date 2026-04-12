# Android Current Points Wallet Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver a WeChat-style Current Points wallet experience on Android with no tabs: wallet home, dedicated withdraw apply screen, recent withdraw progress, recent balance logs, and full balance-log list page under existing `/api/personal` contracts.

**Architecture:** Keep existing backend contracts and `ApiClient` endpoints stable; refactor the Current Points UI into a sectioned wallet home and split secondary flows into dedicated fragments. Reuse existing withdraw detail bottom sheet and withdraw API methods, while adding balance-log list rendering and dedicated navigation routes. Implement incrementally with UI-state mapping tests first, then minimal fragment/layout changes, and targeted API/client regression checks.

**Tech Stack:** Kotlin, Android Fragments, RecyclerView, Material Components, Navigation Component, OkHttp `ApiClient`, JUnit4.

---

### Task 1: Freeze UI State Mapping For Wallet Home Sections

**Files:**
- Create: `navpay-android/app/src/test/java/com/navpay/ui/points/WalletHomeSectionMapperTest.kt`
- Create: `navpay-android/app/src/main/java/com/navpay/ui/points/WalletHomeSectionMapper.kt`

**Step 1: Write the failing test**

```kotlin
@Test
fun mapsSummaryAndRecentDataToWalletSections() {
    val ui = WalletHomeSectionMapper.map(
        summary = WalletSummary("100.00", "20.00", "5.00", "80.00", 1),
        recentWithdrawRows = listOf(sampleWithdraw(status = "ACCUMULATING")),
        recentLogs = listOf(sampleLog(delta = "+10.00")),
    )

    assertEquals("100.00", ui.available)
    assertEquals(1, ui.recentWithdraw.size)
    assertEquals(1, ui.recentLogs.size)
}
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-android && ./gradlew :app:testDebugUnitTest --tests "com.navpay.ui.points.WalletHomeSectionMapperTest"`
Expected: FAIL because mapper does not exist yet.

**Step 3: Write minimal implementation**

Implement `WalletHomeSectionMapper.map(...)` and minimal UI models in `WalletHomeSectionMapper.kt`.

**Step 4: Run test to verify it passes**

Run: `cd navpay-android && ./gradlew :app:testDebugUnitTest --tests "com.navpay.ui.points.WalletHomeSectionMapperTest"`
Expected: PASS.

**Step 5: Commit**

```bash
cd /Users/danielscai/Documents/workspace/navpay/navpay-android
git add app/src/main/java/com/navpay/ui/points/WalletHomeSectionMapper.kt app/src/test/java/com/navpay/ui/points/WalletHomeSectionMapperTest.kt
git commit -m "test(points): freeze wallet-home section mapping"
```

### Task 2: Restructure Current Points Layout To WeChat-Style Wallet Home

**Files:**
- Modify: `navpay-android/app/src/main/res/layout/fragment_points_details.xml`
- Modify: `navpay-android/app/src/main/java/com/navpay/ui/points/PointsDetailsFragment.kt`
- Modify: `navpay-android/app/src/main/res/values/strings.xml`

**Step 1: Write the failing UI test for key IDs/state hooks**

```kotlin
@Test
fun walletHome_containsCoreSections() {
    val ids = listOf(
        R.id.wallet_available_value,
        R.id.withdraw_entry_btn,
        R.id.balance_details_entry_btn,
        R.id.recent_withdraw_list,
        R.id.recent_balance_logs_list,
        R.id.balance_logs_view_all_btn,
    )
    ids.forEach { assertNotNull(root.findViewById<View>(it)) }
}
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-android && ./gradlew :app:testDebugUnitTest --tests "com.navpay.ui.points.*"`
Expected: FAIL due to missing IDs/new layout sections.

**Step 3: Implement minimal layout + binding changes**

- Replace old tab-like/stats-button grouping with sectioned wallet home blocks:
  - balance hero card
  - dual entry buttons (`Withdraw`, `Balance Details`)
  - recent withdraw list container
  - recent balance logs list container + `View All`
- Wire click handlers in `PointsDetailsFragment`:
  - `withdraw_entry_btn` -> navigate to withdraw apply fragment
  - `balance_details_entry_btn` and `balance_logs_view_all_btn` -> navigate to balance logs fragment

**Step 4: Run tests to verify pass**

Run: `cd navpay-android && ./gradlew :app:testDebugUnitTest --tests "com.navpay.ui.points.*"`
Expected: PASS.

**Step 5: Commit**

```bash
cd /Users/danielscai/Documents/workspace/navpay/navpay-android
git add app/src/main/res/layout/fragment_points_details.xml app/src/main/java/com/navpay/ui/points/PointsDetailsFragment.kt app/src/main/res/values/strings.xml
git commit -m "feat(points): redesign current-points wallet home without tabs"
```

### Task 3: Add Dedicated Withdraw Apply Fragment (Amount-Only)

**Files:**
- Create: `navpay-android/app/src/main/java/com/navpay/ui/wallet/WithdrawApplyFragment.kt`
- Create: `navpay-android/app/src/main/res/layout/fragment_withdraw_apply.xml`
- Modify: `navpay-android/app/src/main/res/navigation/nav_graph.xml`
- Modify: `navpay-android/app/src/main/java/com/navpay/ui/points/PointsDetailsFragment.kt`
- Test: `navpay-android/app/src/test/java/com/navpay/ui/wallet/WithdrawFlowUiTest.kt`

**Step 1: Write the failing test for amount-only submit behavior**

```kotlin
@Test
fun withdrawApply_submitUsesAmountOnlyPayload() {
    val payload = buildWithdrawCreatePayload("88.00")
    assertTrue(payload.has("amount"))
    assertTrue(payload.has("requestKey"))
    assertFalse(payload.has("bankAccount"))
}
```

**Step 2: Run test to verify it fails (if new flow hook absent)**

Run: `cd navpay-android && ./gradlew :app:testDebugUnitTest --tests "com.navpay.ui.wallet.WithdrawFlowUiTest"`
Expected: FAIL if submit entry path not yet wired from fragment.

**Step 3: Implement minimal fragment and navigation**

- Add `withdrawApplyFragment` destination.
- Build form with amount input + available balance hint + submit button.
- On submit, call existing `apiClient.createWithdraw(...)`.
- On success, navigate up with a refresh signal (SavedStateHandle or `onResume` refresh trigger).

**Step 4: Run test to verify pass**

Run: `cd navpay-android && ./gradlew :app:testDebugUnitTest --tests "com.navpay.ui.wallet.WithdrawFlowUiTest"`
Expected: PASS.

**Step 5: Commit**

```bash
cd /Users/danielscai/Documents/workspace/navpay/navpay-android
git add app/src/main/java/com/navpay/ui/wallet/WithdrawApplyFragment.kt app/src/main/res/layout/fragment_withdraw_apply.xml app/src/main/res/navigation/nav_graph.xml app/src/main/java/com/navpay/ui/points/PointsDetailsFragment.kt app/src/test/java/com/navpay/ui/wallet/WithdrawFlowUiTest.kt
git commit -m "feat(wallet): add dedicated withdraw apply screen"
```

### Task 4: Add Balance Logs Adapters And Full List Page

**Files:**
- Create: `navpay-android/app/src/main/java/com/navpay/ui/points/BalanceLogsAdapter.kt`
- Create: `navpay-android/app/src/main/java/com/navpay/ui/points/BalanceLogsFragment.kt`
- Create: `navpay-android/app/src/main/res/layout/fragment_balance_logs.xml`
- Create: `navpay-android/app/src/main/res/layout/item_balance_log.xml`
- Modify: `navpay-android/app/src/main/res/navigation/nav_graph.xml`
- Modify: `navpay-android/app/src/main/res/values/strings.xml`

**Step 1: Write failing adapter test for sign/color/meta formatting**

```kotlin
@Test
fun bindBalanceLog_formatsDeltaAndBalanceAfter() {
    val row = BalanceLog(id = "pbl_1", delta = "+10.00", balanceAfter = "100.00", reason = "manual_adjust", createdAtMs = 1L)
    val ui = BalanceLogRowMapper.map(row)
    assertEquals("+10.00", ui.deltaText)
    assertTrue(ui.metaText.contains("Balance"))
}
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-android && ./gradlew :app:testDebugUnitTest --tests "com.navpay.ui.points.*Balance*"`
Expected: FAIL due to missing adapter/mapper.

**Step 3: Implement minimal adapter + fragment**

- Home page recent logs uses `BalanceLogsAdapter` limited to 5 rows.
- `BalanceLogsFragment` fetches `getBalanceLogs(page=1,pageSize=20)`.
- Add pull-to-refresh and empty state text.

**Step 4: Run tests to verify pass**

Run: `cd navpay-android && ./gradlew :app:testDebugUnitTest --tests "com.navpay.ui.points.*Balance*"`
Expected: PASS.

**Step 5: Commit**

```bash
cd /Users/danielscai/Documents/workspace/navpay/navpay-android
git add app/src/main/java/com/navpay/ui/points/BalanceLogsAdapter.kt app/src/main/java/com/navpay/ui/points/BalanceLogsFragment.kt app/src/main/res/layout/fragment_balance_logs.xml app/src/main/res/layout/item_balance_log.xml app/src/main/res/navigation/nav_graph.xml app/src/main/res/values/strings.xml
git commit -m "feat(points): add balance logs list and recent logs section"
```

### Task 5: Wire Home Refresh Strategy And Partial-Failure Handling

**Files:**
- Modify: `navpay-android/app/src/main/java/com/navpay/ui/points/PointsDetailsFragment.kt`
- Modify: `navpay-android/app/src/test/java/com/navpay/ui/wallet/SellRpFragmentStateTest.kt`
- Create: `navpay-android/app/src/test/java/com/navpay/ui/points/PointsDetailsStateReducerTest.kt`

**Step 1: Write failing state test for partial failure tolerance**

```kotlin
@Test
fun partialFailure_doesNotBlockOtherSections() {
    val state = reduce(
        summary = Result.success(sampleSummary()),
        withdraw = Result.failure(RuntimeException("boom")),
        logs = Result.success(sampleLogs()),
    )
    assertTrue(state.showSummary)
    assertTrue(state.showLogs)
    assertTrue(state.showWithdrawError)
}
```

**Step 2: Run tests to verify fail**

Run: `cd navpay-android && ./gradlew :app:testDebugUnitTest --tests "com.navpay.ui.points.PointsDetailsStateReducerTest"`
Expected: FAIL because reducer/state separation not implemented.

**Step 3: Implement minimal reducer and refresh wiring**

- Extract sectioned UI state reducer.
- Ensure create-withdraw success triggers home refresh.
- Keep 401 handling consistent with existing login redirect.

**Step 4: Run tests to verify pass**

Run: `cd navpay-android && ./gradlew :app:testDebugUnitTest --tests "com.navpay.ui.points.PointsDetailsStateReducerTest" --tests "com.navpay.ui.wallet.SellRpFragmentStateTest"`
Expected: PASS.

**Step 5: Commit**

```bash
cd /Users/danielscai/Documents/workspace/navpay/navpay-android
git add app/src/main/java/com/navpay/ui/points/PointsDetailsFragment.kt app/src/test/java/com/navpay/ui/points/PointsDetailsStateReducerTest.kt app/src/test/java/com/navpay/ui/wallet/SellRpFragmentStateTest.kt
git commit -m "fix(points): make wallet home refresh resilient with partial failures"
```

### Task 6: API Contract Regression Checks For `/api/personal` Compatibility

**Files:**
- Modify: `navpay-android/app/src/test/java/com/navpay/WalletWithdrawApiClientTest.kt`
- Modify: `navpay-admin/tests/unit/personal-mine-balance-logs-alias-route.test.ts` (only if contract drift is detected)

**Step 1: Write failing Android client contract assertions**

```kotlin
@Test
fun usesPersonalPathForBalanceLogsAndWithdraw() {
    api.getBalanceLogs(page = 1, pageSize = 5)
    api.createWithdraw(amount = "10.00", requestKey = "rk_1")
    assertTrue(paths.any { it.contains("/api/personal/mine/balance-logs") })
    assertTrue(paths.any { it.contains("/api/personal/withdraw/orders") })
}
```

**Step 2: Run test to verify expected behavior**

Run: `cd navpay-android && ./gradlew :app:testDebugUnitTest --tests "com.navpay.WalletWithdrawApiClientTest"`
Expected: PASS; if FAIL, adjust URL builders only.

**Step 3: Apply minimal fixes (if needed)**

- Keep all wallet/withdraw/log endpoints under `/api/personal` base URL.
- No backend route rename in this task.

**Step 4: Re-run targeted tests**

Run: `cd navpay-android && ./gradlew :app:testDebugUnitTest --tests "com.navpay.WalletWithdrawApiClientTest"`
Expected: PASS.

**Step 5: Commit**

```bash
cd /Users/danielscai/Documents/workspace/navpay/navpay-android
git add app/src/test/java/com/navpay/WalletWithdrawApiClientTest.kt
git commit -m "test(wallet): lock personal api path compatibility"
```

### Task 7: End-to-End Verification Gate For This Feature

**Files:**
- Modify: `navpay-android/docs/plans/` (optional execution notes)
- Modify: `navpay-android/docs/testing/` (optional case notes)

**Step 1: Run Android fast gate**

Run: `cd navpay-android && yarn test:quick`
Expected: PASS.

**Step 2: Run Android full gate**

Run: `cd navpay-android && yarn test:gate`
Expected: PASS.

**Step 3: Build and install for manual smoke**

Run:

```bash
cd navpay-android
yarn i1
```

Expected: debug APK installs to emulator; wallet home renders new structure.

**Step 4: Manual walkthrough checklist**

1. Mine -> Current Points shows new no-tab layout.
2. Withdraw opens dedicated page and submit success returns + refreshes.
3. Recent withdraw row opens detail bottom sheet.
4. Balance Details opens full logs page.
5. Home recent logs and full logs are consistent with API.

**Step 5: Commit verification notes (optional)**

```bash
cd /Users/danielscai/Documents/workspace/navpay/navpay-android
git add docs/testing docs/plans
git commit -m "docs(test): record wallet redesign verification evidence"
```

---

## Cross-Repo Coordination Notes

1. This implementation plan assumes admin API contracts stay unchanged under `/api/personal`.
2. If Android discovers contract drift during Task 6, patch admin only with minimal compatibility fixes and add targeted unit tests in `navpay-admin/tests/unit`.
3. Avoid introducing new endpoint families; prefer aliasing existing routes if needed.

