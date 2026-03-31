# Navpay Android Claim AndroidId Adaptation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复 `navpay-android` 点击订单 `Receive` 时因 claim 接口参数变更导致的 `400`，并通过单元测试、JVM 集成测试、模拟器真机流程与服务端状态核验确认抢单闭环可用。

**Architecture:** 当前客户端 claim 请求只提交 `paymentAppId`，而服务端 `POST /api/personal/payout/orders/{orderId}/claim` 已要求 `androidId` + `paymentAppId`。本次改造在 `ApiClient.claimOrder` 增加 `androidId` 参数并传递到请求体，UI 发起抢单处统一通过 `DeviceManager` 提供稳定设备 ID。测试分三层：请求体单测/JVM 集成测试/模拟器端到端手动验证，确保行为与线上接口约束一致。

**Tech Stack:** Kotlin, Android Fragments, OkHttp, JUnit4, MockWebServer, Gradle, Android Emulator (AVD phonepe1)

---

### Task 1: 在 ApiClient 适配 claim 新参数（androidId）

**Files:**
- Modify: `navpay-android/app/src/main/java/com/navpay/ApiClient.kt`
- Test: `navpay-android/app/src/test/java/com/navpay/ApiClientJvmIntegrationTest.kt`

**Step 1: Write the failing test**

```kotlin
@Test
fun claimOrder_postsPaymentAppIdAndAndroidIdJson() = runBlocking {
    val auth = FakeAuthStore(tokenValue = "t_1")
    server.enqueue(MockResponse().setResponseCode(200).setBody("""{"ok":true}"""))

    val api = newClient(auth)
    api.claimOrder(orderId = "order_1", paymentAppId = "pa_1", androidId = "android_123456")

    val req = server.takeRequest()
    val body = JSONObject(req.body.readUtf8())
    assertEquals("pa_1", body.getString("paymentAppId"))
    assertEquals("android_123456", body.getString("androidId"))
}
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-android && ./gradlew testDebugUnitTest --tests com.navpay.ApiClientJvmIntegrationTest.claimOrder_postsPaymentAppIdAndAndroidIdJson`
Expected: FAIL（当前 `claimOrder` 没有 `androidId` 参数或请求体缺少该字段）

**Step 3: Write minimal implementation**

```kotlin
suspend fun claimOrder(orderId: String, paymentAppId: String, androidId: String): Order = withContext(Dispatchers.IO) {
    val payload = JSONObject().apply {
        put("paymentAppId", paymentAppId)
        put("androidId", androidId)
    }
    val json = postAuthedJson("${baseUrl}/payout/orders/${orderId}/claim", payload)
    ...
}
```

**Step 4: Run test to verify it passes**

Run: `cd navpay-android && ./gradlew testDebugUnitTest --tests com.navpay.ApiClientJvmIntegrationTest.claimOrder_postsPaymentAppIdAndAndroidIdJson`
Expected: PASS

**Step 5: Commit**

```bash
git -C navpay-android add app/src/main/java/com/navpay/ApiClient.kt app/src/test/java/com/navpay/ApiClientJvmIntegrationTest.kt
git -C navpay-android commit -m "fix(android): include androidId in payout claim payload"
```

### Task 2: 更新所有 claim 调用点，统一携带 DeviceManager.androidId

**Files:**
- Modify: `navpay-android/app/src/main/java/com/navpay/ui/buy/BuyRpFragment.kt`
- Modify: `navpay-android/app/src/main/java/com/navpay/OrdersFragment.kt`
- Test: `navpay-android/app/src/test/java/com/navpay/BuyRpClaimFlowUnitTest.kt` (create)

**Step 1: Write the failing test**

```kotlin
@Test
fun claimFlow_requiresAndroidIdFromDeviceManager_beforeCallingApiClient() {
    // Fake DeviceManager returns android-id-xyz
    // Fake ApiClient captures claimOrder args
    // Trigger receive action
    // Assert apiClient.claimOrder(..., androidId = "android-id-xyz") was used
}
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-android && ./gradlew testDebugUnitTest --tests com.navpay.BuyRpClaimFlowUnitTest`
Expected: FAIL（当前调用未传 `androidId`）

**Step 3: Write minimal implementation**

```kotlin
val deviceManager = DeviceManager(requireContext())
val androidId = deviceManager.getOrCreateAndroidId()
apiClient.claimOrder(order.orderId, paymentAppId, androidId)
```

同样在 `OrdersFragment` 的 `claimOrder` 路径补齐 `androidId`。

**Step 4: Run test to verify it passes**

Run: `cd navpay-android && ./gradlew testDebugUnitTest --tests com.navpay.BuyRpClaimFlowUnitTest`
Expected: PASS

**Step 5: Commit**

```bash
git -C navpay-android add app/src/main/java/com/navpay/ui/buy/BuyRpFragment.kt app/src/main/java/com/navpay/OrdersFragment.kt app/src/test/java/com/navpay/BuyRpClaimFlowUnitTest.kt
git -C navpay-android commit -m "fix(android): pass device androidId when claiming payout orders"
```

### Task 3: 扩展 JVM 集成测试，覆盖 claim 400 场景与成功场景

**Files:**
- Modify: `navpay-android/app/src/test/java/com/navpay/ApiClientJvmIntegrationTest.kt`
- Modify: `navpay-android/app/src/test/java/com/navpay/InviteCommissionJvmIntegrationTest.kt` (如签名更新影响调用)

**Step 1: Write the failing test**

```kotlin
@Test
fun claimOrder_whenServerReturnsBadRequest_throwsRuntimeException() = runBlocking {
    val auth = FakeAuthStore(tokenValue = "t_1")
    server.enqueue(MockResponse().setResponseCode(400).setBody("""{"ok":false,"error":"bad_request"}"""))

    val api = newClient(auth)
    val ex = assertThrows(RuntimeException::class.java) {
        runBlocking { api.claimOrder("order_1", "pa_1", "android_123456") }
    }
    assertTrue(ex.message!!.contains("400"))
}
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-android && ./gradlew testDebugUnitTest --tests com.navpay.ApiClientJvmIntegrationTest.claimOrder_whenServerReturnsBadRequest_throwsRuntimeException`
Expected: FAIL（若当前断言或实现与新行为不一致）

**Step 3: Write minimal implementation**

- 调整测试与调用签名。
- 仅在必要时微调错误信息断言（例如统一 `request failed` 格式）。

**Step 4: Run test to verify it passes**

Run: `cd navpay-android && ./gradlew testDebugUnitTest --tests com.navpay.ApiClientJvmIntegrationTest`
Expected: PASS（含 claim 新参数与错误分支）

**Step 5: Commit**

```bash
git -C navpay-android add app/src/test/java/com/navpay/ApiClientJvmIntegrationTest.kt app/src/test/java/com/navpay/InviteCommissionJvmIntegrationTest.kt
git -C navpay-android commit -m "test(android): cover claim androidId payload and bad request handling"
```

### Task 4: 运行全量相关测试回归

**Files:**
- Modify: none
- Test: existing Android JVM tests

**Step 1: Write the failing test**

N/A（回归任务）

**Step 2: Run test to verify it fails**

N/A

**Step 3: Write minimal implementation**

N/A

**Step 4: Run test to verify it passes**

Run:

```bash
cd navpay-android
./gradlew testDebugUnitTest \
  --tests com.navpay.ApiClientJvmIntegrationTest \
  --tests com.navpay.InviteCommissionJvmIntegrationTest \
  --tests com.navpay.BuyRpClaimFlowUnitTest
```

Expected: PASS

**Step 5: Commit**

```bash
# no-op if no code change
```

### Task 5: 模拟器端到端验证抢单闭环 + 服务端状态核验

**Files:**
- Modify: none (unless发现阻断性问题)
- Verify: local runtime + server observable state

**Step 1: Write the failing test**

N/A（手工集成验证）

**Step 2: Run test to verify it fails**

先复现场景（旧包或改造前）记录 `Receive -> 400` 证据。

**Step 3: Write minimal implementation**

使用任务 1~3 的修复包执行。

**Step 4: Run test to verify it passes**

Run:

```bash
# Terminal A: 启动 personal API
cd navpay-admin
yarn dev

# Terminal B: 启动模拟器 + 安装 app
cd navpay-android
yarn emu1
yarn i1

# App 内流程
# 1) 登录测试账号
# 2) 进入 Buy RP 列表
# 3) 点击某个可抢订单 Receive
# 4) 选择支付方式
# 5) 观察无 400 错误并进入后续支付任务页

# 服务端核验（示例）
# 查询后台订单状态确认该 order 已 LOCKED 且 claim_android_id 不为空
```

Expected:
- 客户端：不再出现 400，UI 进入抢单后流程。
- 服务端：目标订单状态变为 `LOCKED`/已被该账号锁单，可在管理端列表看到对应记录（含 claim device 信息）。

**Step 5: Commit**

```bash
git -C navpay-android commit --allow-empty -m "chore(android): verify emulator claim flow and server lock evidence"
```

### Task 6: 补充验证记录文档

**Files:**
- Create: `navpay-android/docs/claim-androidid-verification-2026-03-31.md`

**Step 1: Write the failing test**

N/A

**Step 2: Run test to verify it fails**

N/A

**Step 3: Write minimal implementation**

文档记录：
- 触发问题的旧行为（400）
- 修复点（payload 增加 `androidId`）
- 单测/JVM 集成测试命令与结果
- 模拟器流程截图/关键日志
- 服务端订单状态证据（orderId、状态、claim device）

**Step 4: Run test to verify it passes**

Run: `cd navpay-android && ls docs/claim-androidid-verification-2026-03-31.md`
Expected: 文件存在且内容完整

**Step 5: Commit**

```bash
git -C navpay-android add docs/claim-androidid-verification-2026-03-31.md
git -C navpay-android commit -m "docs(android): record claim androidId adaptation verification"
```

---

## Parallel Subagent Execution Strategy (@superpowers:subagent-driven-development)

1. 子代理 A（API/TDD）：Task 1 + Task 3（`ApiClient` 和 `ApiClientJvmIntegrationTest`）。
2. 子代理 B（UI 调用点）：Task 2（`BuyRpFragment` + `OrdersFragment` + 单测）。
3. 主代理串行集成：接入两边改动，执行 Task 4 全量回归。
4. 主代理执行 Task 5 模拟器实跑 + 服务端核验并收证。
5. 子代理 C（文档）：Task 6 验证记录整理（在 Task 5 证据就绪后执行）。

## Definition of Done

- Claim 请求体包含 `paymentAppId` + `androidId`，与服务端 schema 一致。
- 单元测试与 JVM 集成测试通过，覆盖成功和 400 错误路径。
- 模拟器实跑点击订单 `Receive` 流程无 400，可进入后续支付任务页。
- 服务端可观察到目标订单被当前账号抢到（状态与 claim 设备信息可见）。
