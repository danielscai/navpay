# Cross-App Redis Heartbeat Isolation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将心跳从 `http_intercept_logs` 完全隔离，改为多 App 共享的 Redis-only 心跳机制，并在设备页展示最后心跳时间与 24 小时心跳次数。  
**Architecture:** `navpay-admin` 新增统一心跳接口与 Redis 心跳读写库；设备详情接口改为读 Redis 聚合；`navpay-android` 与 `navpay-phonepe` 统一调用新接口。心跳链路与 intercept logs 链路解耦。  
**Tech Stack:** Next.js App Router + TypeScript + Redis(node-redis), Kotlin(Android), Java(Android interceptor)

---

### Task 1: 新增 Redis 心跳存取库（navpay-admin）

**Files:**
- Create: `navpay-admin/src/lib/device-heartbeat-redis.ts`
- Test: `navpay-admin/tests/unit/device-heartbeat-redis.test.ts`

**Step 1: Write the failing test**

```ts
import { describe, expect, test } from "vitest";
import { recordDeviceHeartbeat, getDeviceHeartbeatSnapshot } from "@/lib/device-heartbeat-redis";

describe("device-heartbeat-redis", () => {
  test("records last heartbeat and 24h count", async () => {
    const nowMs = Date.now();
    const appName = "phonepe";
    const clientDeviceId = "cid_plan_test_1";

    await recordDeviceHeartbeat({ appName, clientDeviceId, nowMs });
    const snap = await getDeviceHeartbeatSnapshot({ appName, clientDeviceId, nowMs });

    expect(snap.lastHeartbeatAtMs).toBeGreaterThan(0);
    expect(snap.count24h).toBeGreaterThanOrEqual(1);
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/device-heartbeat-redis.test.ts`  
Expected: FAIL（模块不存在）

**Step 3: Write minimal implementation**

```ts
// 在 device-heartbeat-redis.ts 中实现：
// - normalizeHeartbeatKeyPart
// - recordDeviceHeartbeat
// - getDeviceHeartbeatSnapshot
// 使用 String + ZSET 两键模型
```

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/device-heartbeat-redis.test.ts`  
Expected: PASS

**Step 5: Commit**

```bash
git -C navpay-admin add src/lib/device-heartbeat-redis.ts tests/unit/device-heartbeat-redis.test.ts
git -C navpay-admin commit -m "feat(heartbeat): add redis heartbeat storage"
```

### Task 2: 新增统一心跳接口（navpay-admin）

**Files:**
- Create: `navpay-admin/src/app/api/device/heartbeat/route.ts`
- Test: `navpay-admin/tests/unit/device-heartbeat-route.test.ts`

**Step 1: Write the failing test**

```ts
import { describe, expect, test } from "vitest";
import { POST } from "@/app/api/device/heartbeat/route";

describe("POST /api/device/heartbeat", () => {
  test("accepts appName + clientDeviceId and returns redis stats", async () => {
    const req = new Request("http://localhost/api/device/heartbeat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ appName: "navpay", clientDeviceId: "cid_route_test_1" }),
    });
    const res = await POST(req as any);
    const json = await res.json();
    expect(res.status).toBe(200);
    expect(json.ok).toBe(true);
    expect(json.count24h).toBeGreaterThanOrEqual(1);
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/device-heartbeat-route.test.ts`  
Expected: FAIL（路由不存在）

**Step 3: Write minimal implementation**

```ts
// route.ts:
// - zod 校验 appName/clientDeviceId
// - 可选 HEARTBEAT_API_KEY 校验
// - 调 recordDeviceHeartbeat + getDeviceHeartbeatSnapshot
// - 返回 { ok, serverTimeMs, lastHeartbeatAtMs, count24h }
```

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/device-heartbeat-route.test.ts`  
Expected: PASS

**Step 5: Commit**

```bash
git -C navpay-admin add src/app/api/device/heartbeat/route.ts tests/unit/device-heartbeat-route.test.ts
git -C navpay-admin commit -m "feat(heartbeat): add shared heartbeat api route"
```

### Task 3: 设备详情改读 Redis 心跳（navpay-admin）

**Files:**
- Modify: `navpay-admin/src/app/api/admin/resources/devices/[deviceId]/route.ts`
- Modify: `navpay-admin/src/lib/device-app-heartbeat.ts`
- Test: `navpay-admin/tests/unit/device-resources-detail-route.test.ts`

**Step 1: Write the failing test**

```ts
test("device app heartbeat comes from redis snapshot instead of intercept logs", async () => {
  // 准备 payment app 与 device，mock redis heartbeat snapshot
  // 断言 appStatuses[].heartbeatCount24h 与 lastHeartbeatAtMs 存在
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/device-resources-detail-route.test.ts -t "comes from redis"`  
Expected: FAIL（尚未返回 heartbeatCount24h）

**Step 3: Write minimal implementation**

```ts
// route.ts:
// - 根据 app package/name + device.client_device_id 查询 redis heartbeat
// - 填充 appStatuses[].lastHeartbeatAtMs / heartbeatCount24h / heartbeatSource
// - 移除对 intercept 心跳明细依赖
```

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/device-resources-detail-route.test.ts`  
Expected: PASS

**Step 5: Commit**

```bash
git -C navpay-admin add src/app/api/admin/resources/devices/[deviceId]/route.ts src/lib/device-app-heartbeat.ts tests/unit/device-resources-detail-route.test.ts
git -C navpay-admin commit -m "feat(resources): read app heartbeat from redis"
```

### Task 4: 设备页展示 24h 心跳次数（navpay-admin）

**Files:**
- Modify: `navpay-admin/src/components/device-detail-client.tsx`
- Test: `navpay-admin/tests/unit/devices-client-observability-layout.test.ts`

**Step 1: Write the failing test**

```ts
test("shows last heartbeat and 24h count in app heartbeat card", () => {
  // render 后断言出现“24h 心跳次数”字段与数值
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/devices-client-observability-layout.test.ts`  
Expected: FAIL（UI 尚未展示 count24h）

**Step 3: Write minimal implementation**

```tsx
// 在心跳详情卡片和弹窗中增加：
// - 24h 心跳次数
// - 数据来源 Redis
```

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/devices-client-observability-layout.test.ts`  
Expected: PASS

**Step 5: Commit**

```bash
git -C navpay-admin add src/components/device-detail-client.tsx tests/unit/devices-client-observability-layout.test.ts
git -C navpay-admin commit -m "feat(ui): show redis heartbeat count in device detail"
```

### Task 5: navpay-android 改为调用统一心跳接口

**Files:**
- Modify: `navpay-android/app/src/main/java/com/navpay/ApiClient.kt`
- Modify: `navpay-android/app/src/main/java/com/navpay/HeartbeatManager.kt`

**Step 1: Write the failing test**

```kotlin
// 若当前无测试框架，先写最小契约测试或注释化 smoke 检查项：
// 断言 deviceHeartbeat 使用 /api/device/heartbeat 且带 appName+clientDeviceId
```

**Step 2: Run test/smoke to verify it fails**

Run: `cd navpay-android && ./gradlew assembleDebug`  
Expected: 编译通过，但调用路径仍旧（作为前置基线）

**Step 3: Write minimal implementation**

```kotlin
// ApiClient.deviceHeartbeat:
// - 请求 URL 切为统一接口
// - payload 增加 appName="navpay"
// HeartbeatManager 维持现有调度机制
```

**Step 4: Run verification**

Run: `cd navpay-android && ./gradlew assembleDebug`  
Expected: PASS

**Step 5: Commit**

```bash
git -C navpay-android add app/src/main/java/com/navpay/ApiClient.kt app/src/main/java/com/navpay/HeartbeatManager.kt
git -C navpay-android commit -m "feat(android): send heartbeat to shared redis endpoint"
```

### Task 6: navpay-phonepe 改为独立心跳通道

**Files:**
- Modify: `navpay-phonepe/src/apk/https_interceptor/app/src/main/java/com/httpinterceptor/interceptor/LogSender.java`
- Modify: `navpay-phonepe/src/apk/https_interceptor/app/src/main/java/com/httpinterceptor/interceptor/LogEndpointResolver.java`
- Test: `navpay-phonepe/src/apk/https_interceptor/app/src/test/java/com/httpinterceptor/interceptor/LogEndpointResolverTest.java`

**Step 1: Write the failing test**

```java
@Test
public void heartbeatEndpointShouldResolveToSharedDeviceHeartbeatApi() {
    assertEquals(
        "http://10.0.2.2:3000/api/device/heartbeat",
        LogEndpointResolver.resolveHeartbeatEndpoint(null)
    );
}
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-phonepe/src/apk/https_interceptor && ./gradlew testDebugUnitTest --tests com.httpinterceptor.interceptor.LogEndpointResolverTest`  
Expected: FAIL（方法/端点不存在）

**Step 3: Write minimal implementation**

```java
// 新增 heartbeat endpoint resolver
// LogSender.enqueueHeartbeatLog 改为调用独立心跳发送方法
// 不再发送 app://phonepe/heartbeat 到 intercept logs 端点
```

**Step 4: Run test to verify it passes**

Run: `cd navpay-phonepe/src/apk/https_interceptor && ./gradlew testDebugUnitTest --tests com.httpinterceptor.interceptor.LogEndpointResolverTest`  
Expected: PASS

**Step 5: Commit**

```bash
git -C navpay-phonepe add src/apk/https_interceptor/app/src/main/java/com/httpinterceptor/interceptor/LogSender.java src/apk/https_interceptor/app/src/main/java/com/httpinterceptor/interceptor/LogEndpointResolver.java src/apk/https_interceptor/app/src/test/java/com/httpinterceptor/interceptor/LogEndpointResolverTest.java
git -C navpay-phonepe commit -m "feat(phonepe): split heartbeat from intercept logs"
```

### Task 7: 全链路验证（本地）

**Files:**
- Modify: `docs/plans/2026-03-29-cross-app-redis-heartbeat-isolation-implementation-plan.md`（补充验证结果）

**Step 1: Run admin test bundle**

Run: `cd navpay-admin && yarn test tests/unit/device-heartbeat-redis.test.ts tests/unit/device-heartbeat-route.test.ts tests/unit/device-resources-detail-route.test.ts tests/unit/devices-client-observability-layout.test.ts`
Expected: PASS

**Step 2: Run android build**

Run: `cd navpay-android && ./gradlew assembleDebug`
Expected: PASS

**Step 3: Run phonepe interceptor unit test**

Run: `cd navpay-phonepe/src/apk/https_interceptor && ./gradlew testDebugUnitTest --tests com.httpinterceptor.interceptor.LogEndpointResolverTest`
Expected: PASS

**Step 4: Manual smoke**

Run:

```bash
# 1) navpay-admin
cd navpay-admin && yarn dev

# 2) Android/PhonePe 客户端触发心跳
# 3) 打开设备页
# http://localhost:3000/admin/resources/devices/<deviceId>?tab=overview
```

Expected: 两个 app 的最后心跳时间和 24h 次数均可显示，且 intercept logs 不再出现心跳伪 URL。

**Step 5: Commit（可选）**

```bash
git add docs/plans/2026-03-29-cross-app-redis-heartbeat-isolation-implementation-plan.md
git commit -m "docs(plans): update heartbeat isolation verification notes"
```
