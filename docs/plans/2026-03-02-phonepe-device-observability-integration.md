# PhonePe Device Observability Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让 `navpay-phonepe` 的真实模拟器上报能够自动落入 `navpay-admin` 的手机设备列表，并在设备详情关联到真实上报日志。  

**Architecture:** 在 PhonePe 拦截上报 payload 中补齐稳定设备标识（`androidId`），`navpay-admin` 在 `POST /api/intercept/log` 入库时基于该标识做“设备自动 upsert + 日志绑定”。这样不依赖 `navpay-android` 的 `/api/personal/device/report`，也不需要 mock 数据；真实 PhonePe 流量即可驱动设备列表出现与更新。  

**Tech Stack:** Java (Android hook module), Next.js App Router, TypeScript, Prisma/PostgreSQL, Vitest, ADB/Emulator.

---

### Task 1: Lock Admin Contract with Failing Tests

**Files:**
- Modify: `navpay-admin/tests/unit/intercept/log-device-assignment.test.ts`
- Test: `navpay-admin/tests/unit/intercept/log-device-assignment.test.ts`

**Step 1: Write failing test for auto-create by androidId**

```ts
test("ingest auto-creates device when androidId is provided and no existing device", async () => {
  const res = await ingestLog(new Request("http://localhost/api/intercept/log", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      method: "GET",
      url: "https://apicp1.phonepe.com/apis/users/v1/signin/init",
      protocol: "HTTP/1.1",
      status_code: 200,
      androidId: "pp-android-id-001",
      sourceApp: "phonepe",
    }),
  }) as any);

  const json: any = await res.json();
  expect(res.status).toBe(200);
  expect(json.success).toBe(true);
  expect(json.sourceClientDeviceId).toBe("pp-android-id-001");
  expect(json.sourceDeviceId).toMatch(/^dev_/);

  const dev = await prisma.payment_devices.findFirst({ where: { client_device_id: "pp-android-id-001" } });
  expect(dev).toBeTruthy();
  expect(dev?.person_id).toBeNull();
});
```

**Step 2: Write failing test for update path (existing device)**

```ts
test("ingest updates existing device timestamp and binds log to existing device", async () => {
  const now = Date.now();
  const deviceId = id("dev");
  await prisma.payment_devices.create({
    data: {
      id: deviceId,
      person_id: null,
      name: "PhonePe Device",
      client_device_id: "pp-android-id-002",
      platform: "android",
      created_at_ms: BigInt(now - 10_000),
      updated_at_ms: BigInt(now - 10_000),
    },
  });

  const res = await ingestLog(new Request("http://localhost/api/intercept/log", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      method: "GET",
      url: "https://apicp1.phonepe.com/apis/chimera/pz/v1/whitelisted/Apps/evaluate/bulk",
      protocol: "HTTP/1.1",
      status_code: 200,
      androidId: "pp-android-id-002",
      sourceApp: "phonepe",
    }),
  }) as any);

  const json: any = await res.json();
  expect(json.sourceDeviceId).toBe(deviceId);

  const row = await prisma.http_intercept_logs.findUnique({ where: { id: Number(json.id) } });
  expect(row?.source_device_id).toBe(deviceId);
});
```

**Step 3: Run tests to verify they fail**

Run: `cd navpay-admin && yarn test tests/unit/intercept/log-device-assignment.test.ts -v`  
Expected: FAIL（当前实现不会自动创建设备）。

**Step 4: Commit test-only red state**

```bash
git -C navpay-admin add tests/unit/intercept/log-device-assignment.test.ts
git -C navpay-admin commit -m "test(intercept): require device auto-upsert from androidId"
```

---

### Task 2: Implement Admin Device Auto-Upsert in Intercept Ingest

**Files:**
- Modify: `navpay-admin/src/app/api/intercept/log/route.ts`
- Modify: `navpay-admin/tests/unit/intercept/log-device-assignment.test.ts` (only if assertion tuning needed)
- Test: `navpay-admin/tests/unit/intercept/log-device-assignment.test.ts`

**Step 1: Add minimal helper in route for device resolution/upsert**

```ts
async function resolveOrCreateDeviceByClientId(clientDeviceId: string, sourceApp: string, now: number) {
  if (!clientDeviceId) return null;

  const existing = await prisma.payment_devices.findFirst({
    where: { client_device_id: clientDeviceId },
    select: { id: true, name: true },
  });
  if (existing) {
    await prisma.payment_devices.update({
      where: { id: existing.id },
      data: {
        updated_at_ms: BigInt(now),
        last_seen_at_ms: BigInt(now),
        online: BigInt(1),
      },
    });
    return { id: String(existing.id), name: String(existing.name ?? "") };
  }

  const created = await prisma.payment_devices.create({
    data: {
      id: id("dev"),
      person_id: null,
      name: sourceApp === "phonepe" ? "PhonePe (auto)" : "Intercept Device (auto)",
      client_device_id: clientDeviceId,
      platform: "android",
      last_seen_at_ms: BigInt(now),
      online: BigInt(1),
      created_at_ms: BigInt(now),
      updated_at_ms: BigInt(now),
    },
    select: { id: true, name: true },
  });

  return { id: String(created.id), name: String(created.name ?? "") };
}
```

**Step 2: Replace old lookup with helper call**

```ts
const sourceClientDeviceId = str(body.clientDeviceId ?? body.androidId ?? body.device_id ?? body.deviceId).trim();
const sourceApp = str(body.sourceApp ?? body.appType).trim() || "phonepe";
const now = Date.now();
const sourceDevice = await resolveOrCreateDeviceByClientId(sourceClientDeviceId, sourceApp, now);
```

**Step 3: Keep response and row shape backward-compatible**

- 保持 `success/id/sourceDeviceId/sourceClientDeviceId/sourceApp` 字段不变。
- 仅增强：当传了设备标识时，`sourceDeviceId` 保证可回填。

**Step 4: Run tests to verify pass**

Run: `cd navpay-admin && yarn test tests/unit/intercept/log-device-assignment.test.ts -v`  
Expected: PASS。

**Step 5: Run nearby regression tests**

Run:
- `cd navpay-admin && yarn test tests/unit/device-resources-list-route.test.ts -v`
- `cd navpay-admin && yarn test tests/unit/resources-intercept-tab.test.ts -v`

Expected: PASS。

**Step 6: Commit admin implementation**

```bash
git -C navpay-admin add src/app/api/intercept/log/route.ts tests/unit/intercept/log-device-assignment.test.ts
git -C navpay-admin commit -m "feat(intercept): auto-upsert device from androidId during log ingest"
```

---

### Task 3: Add Device Identifier to PhonePe Interceptor Payload

**Files:**
- Modify: `navpay-phonepe/src/https_interceptor/app/src/main/java/com/httpinterceptor/interceptor/LogSender.java`
- Modify: `navpay-phonepe/src/https_interceptor/app/src/main/java/com/httpinterceptor/interceptor/RemoteLoggingInterceptor.java`

**Step 1: Add Android ID resolver in LogSender (minimal, no new dependency graph changes)**

```java
private static String resolveAndroidId() {
    try {
        Context ctx = (Context) Class.forName("android.app.ActivityThread")
            .getMethod("currentApplication")
            .invoke(null);
        if (ctx == null) return "";
        String id = Settings.Secure.getString(ctx.getContentResolver(), Settings.Secure.ANDROID_ID);
        return id == null ? "" : id;
    } catch (Throwable t) {
        return "";
    }
}
```

**Step 2: Ensure each outbound payload includes device id + source app**

```java
if (!log.has("androidId") || log.optString("androidId", "").isEmpty()) {
    log.put("androidId", resolveAndroidId());
}
if (!log.has("sourceApp") || log.optString("sourceApp", "").isEmpty()) {
    log.put("sourceApp", "phonepe");
}
```

**Step 3: Keep existing body untouched otherwise (YAGNI)**

- 不改 URL、重试策略、队列策略。
- 不引入新的上报 endpoint。

**Step 4: Rebuild patched APK via existing workflow**

Run: `cd navpay-phonepe && python3 src/cache-manager/cache_manager.py phonepehelper test`  
Expected: SUCCESS（含安装和 `PPHelper` 注入检测）。

**Step 5: Commit phonepe payload enhancement**

```bash
git -C navpay-phonepe add src/https_interceptor/app/src/main/java/com/httpinterceptor/interceptor/LogSender.java src/https_interceptor/app/src/main/java/com/httpinterceptor/interceptor/RemoteLoggingInterceptor.java
git -C navpay-phonepe commit -m "feat(phonepe): include androidId in intercept payload"
```

---

### Task 4: Real Emulator E2E Verification (No Mock Data)

**Files:**
- Modify: `navpay-admin/docs/reports/2026-03-02-phonepe-device-observability-integration.md` (new evidence report)

**Step 1: Start admin and record baseline counts**

Run:
- `cd navpay-admin && yarn dev`
- `cd navpay-admin && source .env.local && psql "$DATABASE_URL" -Atc "select coalesce(max(id),0) from http_intercept_logs;"`
- `cd navpay-admin && source .env.local && psql "$DATABASE_URL" -Atc "select count(*) from payment_devices;"`

Expected: capture baseline values.

**Step 2: Execute real PhonePe flow**

Run:
- `cd navpay-phonepe && python3 src/cache-manager/cache_manager.py phonepehelper test`
- `adb -s emulator-5554 reverse tcp:8088 tcp:3000`
- `adb -s emulator-5554 shell am force-stop com.phonepe.app`
- `adb -s emulator-5554 shell am start -n com.phonepe.app/.launch.core.main.ui.MainActivity`

Expected: app launch and background network traffic.

**Step 3: Verify new intercept logs are bound to device ids**

Run:

```bash
cd navpay-admin && source .env.local
psql "$DATABASE_URL" -P pager=off -c "
select id, source_app, source_client_device_id, source_device_id, url, status_code
from http_intercept_logs
order by id desc
limit 20;"
```

Expected: 至少 1 条 `source_client_device_id != ''` 且 `source_device_id != ''`。

**Step 4: Verify device row exists/updated from real phonepe data**

Run:

```bash
cd navpay-admin && source .env.local
psql "$DATABASE_URL" -P pager=off -c "
select id, client_device_id, name, person_id, last_seen_at_ms, updated_at_ms
from payment_devices
order by updated_at_ms desc
limit 10;"
```

Expected: 新设备行出现（可 `person_id` 为空，但必须存在且时间戳更新）。

**Step 5: Document evidence**

在报告中记录：
- 执行时间（绝对时间）
- 模拟器串号
- `before/after` 行数
- 样例 URL（`apicp1.phonepe.com/...`）
- 新设备行主键和 `client_device_id`

**Step 6: Commit evidence doc**

```bash
git -C navpay-admin add docs/reports/2026-03-02-phonepe-device-observability-integration.md
git -C navpay-admin commit -m "test(intercept): record phonepe device observability e2e evidence"
```

---

### Task 5: Final Verification Gate (Before Claiming Done)

**Files:**
- Modify: none
- Test: integration verification commands only

**Step 1: Run targeted unit tests**

Run:
- `cd navpay-admin && yarn test tests/unit/intercept/log-device-assignment.test.ts -v`
- `cd navpay-admin && yarn test tests/unit/device-resources-list-route.test.ts -v`

Expected: PASS。

**Step 2: Run one end-to-end command bundle and capture output**

Run:

```bash
cd /Users/danielscai/Documents/workspace/navpay
bash -lc '
set -e
cd navpay-phonepe && python3 src/cache-manager/cache_manager.py phonepehelper test
adb -s emulator-5554 reverse tcp:8088 tcp:3000
adb -s emulator-5554 shell am start -n com.phonepe.app/.launch.core.main.ui.MainActivity
sleep 10
cd ../navpay-admin && source .env.local
psql "$DATABASE_URL" -Atc "select count(*) from http_intercept_logs where coalesce(source_device_id,'''')<>'''';"
'
```

Expected: 输出数字 `> 0`。

**Step 3: Sanity check no mock-only path is required**

- 确认验证步骤不包含 `/api/personal/report/simulate`。
- 确认设备出现来自真实 PhonePe 请求日志关联，而不是 seed/migration 脚本造数。

**Step 4: Final integration commit**

```bash
git -C navpay-admin status --short
git -C navpay-phonepe status --short
# 按仓库分别提交，避免跨仓库混杂
```

---

## Notes for Implementation Session

- Use `@test-driven-development` on admin-side behavior changes.
- Use `@verification-before-completion` before任何“完成/通过”表述。
- Keep changes DRY/YAGNI: 只补设备标识与设备 upsert，不扩展无关领域（如账号归属自动推断）。
- 如果模拟器偶发掉线，先重跑单条命令 `python3 src/cache-manager/cache_manager.py phonepehelper test` 再继续。

