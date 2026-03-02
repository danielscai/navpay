# Admin Device Observability + Intercept Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 `http://localhost:3000/admin/resources?tab=devices` 一处完成设备可观测性与上报集成：能看设备注册信息、当前归属、历史归属变化、归属账号的其他设备、在线状态、device id、硬件信息、时区、品牌、可选位置、PhonePe 信息，并能在资源页内完成上报查看与设备归属。

**Architecture:** 继续使用 `payment_devices.client_device_id(ANDROID_ID)` 作为设备唯一标识；新增设备归属历史表记录 `person_id` 变更轨迹；在 `http_intercept_logs` 增加设备归属字段（按客户端上报 `clientDeviceId` / `deviceId` 解析）；把原 `/admin/intercept` 控制台抽成可复用组件并挂到资源页右侧 tab。位置/CPU/内存采用“可选上报 + 可空存储”，不做额外采集 SDK。

**Tech Stack:** Next.js App Router, Prisma + PostgreSQL, Zod, React client components, Vitest, Playwright, Android Emulator (local manual integration check).

---

### Task 1: Add DB Contract for Device Ownership History + Intercept Device Link

**Files:**
- Create: `navpay-admin/tests/unit/device-observability-schema-contract.test.ts`
- Modify: `navpay-admin/prisma/schema.prisma`
- Create: `navpay-admin/prisma/migrations/20260302090000_device_observability_intercept_link/migration.sql`

**Step 1: Write the failing test**

```ts
import { readFileSync } from "node:fs";
import { describe, expect, test } from "vitest";

describe("device observability schema contract", () => {
  test("adds owner history and intercept-device link columns", () => {
    const schema = readFileSync("prisma/schema.prisma", "utf8");
    expect(schema).toContain("model payment_device_owner_history");
    expect(schema).toContain("cpu_abi");
    expect(schema).toContain("memory_mb");
    expect(schema).toContain("location_lat");
    expect(schema).toContain("source_client_device_id");
    expect(schema).toContain("source_device_id");
    expect(schema).toContain("source_app");
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/device-observability-schema-contract.test.ts`
Expected: FAIL with missing model/columns.

**Step 3: Write minimal implementation**

`prisma/schema.prisma` 最小新增：

```prisma
model payment_device_owner_history {
  id                String @id
  device_id         String
  client_device_id  String
  from_person_id    String?
  to_person_id      String?
  reason            String
  created_at_ms     BigInt

  @@index([device_id, created_at_ms(sort: Desc)], map: "pdev_owner_hist_device_created_idx")
  @@index([client_device_id, created_at_ms(sort: Desc)], map: "pdev_owner_hist_client_created_idx")
}

model payment_devices {
  // ...existing fields...
  cpu_abi          String?
  memory_mb        BigInt?
  location_lat     String?
  location_lng     String?
  location_accuracy_m String?
}

model http_intercept_logs {
  // ...existing fields...
  source_client_device_id String @default("")
  source_device_id        String @default("")
  source_app              String @default("")
  source_label            String @default("")
}
```

`migration.sql` 最小新增：

```sql
ALTER TABLE payment_devices ADD COLUMN IF NOT EXISTS cpu_abi text;
ALTER TABLE payment_devices ADD COLUMN IF NOT EXISTS memory_mb bigint;
ALTER TABLE payment_devices ADD COLUMN IF NOT EXISTS location_lat text;
ALTER TABLE payment_devices ADD COLUMN IF NOT EXISTS location_lng text;
ALTER TABLE payment_devices ADD COLUMN IF NOT EXISTS location_accuracy_m text;

CREATE TABLE IF NOT EXISTS payment_device_owner_history (
  id text PRIMARY KEY,
  device_id text NOT NULL,
  client_device_id text NOT NULL,
  from_person_id text,
  to_person_id text,
  reason text NOT NULL,
  created_at_ms bigint NOT NULL
);
CREATE INDEX IF NOT EXISTS pdev_owner_hist_device_created_idx ON payment_device_owner_history(device_id, created_at_ms DESC);
CREATE INDEX IF NOT EXISTS pdev_owner_hist_client_created_idx ON payment_device_owner_history(client_device_id, created_at_ms DESC);

ALTER TABLE http_intercept_logs ADD COLUMN IF NOT EXISTS source_client_device_id text NOT NULL DEFAULT '';
ALTER TABLE http_intercept_logs ADD COLUMN IF NOT EXISTS source_device_id text NOT NULL DEFAULT '';
ALTER TABLE http_intercept_logs ADD COLUMN IF NOT EXISTS source_app text NOT NULL DEFAULT '';
ALTER TABLE http_intercept_logs ADD COLUMN IF NOT EXISTS source_label text NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS http_intercept_logs_source_device_idx ON http_intercept_logs(source_device_id);
CREATE INDEX IF NOT EXISTS http_intercept_logs_source_client_device_idx ON http_intercept_logs(source_client_device_id);
```

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/device-observability-schema-contract.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-admin/tests/unit/device-observability-schema-contract.test.ts \
        navpay-admin/prisma/schema.prisma \
        navpay-admin/prisma/migrations/20260302090000_device_observability_intercept_link/migration.sql
git commit -m "feat(navpay-admin): add schema for device ownership history and intercept device link"
```

### Task 2: Persist Ownership Change History on Report/Heartbeat

**Files:**
- Modify: `navpay-admin/src/app/api/personal/device/report/route.ts`
- Modify: `navpay-admin/src/app/api/personal/device/heartbeat/route.ts`
- Create: `navpay-admin/src/lib/device-ownership-history.ts`
- Modify: `navpay-admin/tests/unit/device-heartbeat.test.ts`

**Step 1: Write the failing test**

```ts
test("writes ownership history when owner switches for same clientDeviceId", async () => {
  // personA report -> personB heartbeat same clientDeviceId
  // expect payment_device_owner_history has from=personA to=personB
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/device-heartbeat.test.ts -t "writes ownership history"`
Expected: FAIL with missing history row.

**Step 3: Write minimal implementation**

Create helper `device-ownership-history.ts`:

```ts
export async function recordDeviceOwnerChange(opts: {
  deviceId: string;
  clientDeviceId: string;
  fromPersonId?: string | null;
  toPersonId?: string | null;
  reason: "report" | "heartbeat";
  nowMs: number;
}) {
  if ((opts.fromPersonId ?? null) === (opts.toPersonId ?? null)) return;
  await prisma.payment_device_owner_history.create({
    data: {
      id: id("pdevh"),
      device_id: opts.deviceId,
      client_device_id: opts.clientDeviceId,
      from_person_id: opts.fromPersonId ?? null,
      to_person_id: opts.toPersonId ?? null,
      reason: opts.reason,
      created_at_ms: BigInt(opts.nowMs),
    },
  });
}
```

在 `report/heartbeat` 更新 owner 前调用该 helper（仅当 owner 变化时记录）。

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/device-heartbeat.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-admin/src/app/api/personal/device/report/route.ts \
        navpay-admin/src/app/api/personal/device/heartbeat/route.ts \
        navpay-admin/src/lib/device-ownership-history.ts \
        navpay-admin/tests/unit/device-heartbeat.test.ts
git commit -m "feat(navpay-admin): persist device ownership change history"
```

### Task 3: Make Intercept Ingestion Device-Aware (clientDeviceId/deviceId)

**Files:**
- Modify: `navpay-admin/src/app/api/intercept/log/route.ts`
- Modify: `navpay-admin/src/lib/intercept-db.ts`
- Modify: `navpay-admin/src/app/api/admin/intercept/logs/route.ts`
- Modify: `navpay-admin/src/app/api/admin/intercept/search/route.ts`
- Create: `navpay-admin/tests/unit/intercept/log-device-assignment.test.ts`

**Step 1: Write the failing test**

```ts
test("ingest binds log to device by clientDeviceId and returns sourceDeviceId", async () => {
  // seed payment_devices with client_device_id=android-id-001
  // post /api/intercept/log body includes clientDeviceId/androidId
  // expect http_intercept_logs.source_device_id == seeded device id
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/intercept/log-device-assignment.test.ts`
Expected: FAIL with missing source fields.

**Step 3: Write minimal implementation**

在 ingest 路由中新增解析逻辑：

```ts
const sourceClientDeviceId = str(body.clientDeviceId ?? body.androidId ?? body.device_id);
const sourceApp = str(body.sourceApp ?? body.appType ?? "phonepe");

const device = sourceClientDeviceId
  ? await prisma.payment_devices.findFirst({ where: { client_device_id: sourceClientDeviceId }, select: { id: true, name: true } })
  : null;

await prisma.http_intercept_logs.create({
  data: {
    // ...existing fields...
    source_client_device_id: sourceClientDeviceId,
    source_device_id: device?.id ? String(device.id) : "",
    source_app: sourceApp,
    source_label: device?.name ? `${sourceApp}:${device.name}` : sourceApp,
  },
});
```

`formatLogForClient` 返回新增字段，并在 admin `logs/search` 支持 `deviceId` 过滤参数：

```ts
const deviceId = u.searchParams.get("deviceId") ?? "";
where: {
  ...(deviceId ? { source_device_id: deviceId } : {}),
  // existing OR conditions for q
}
```

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/intercept/log-device-assignment.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-admin/src/app/api/intercept/log/route.ts \
        navpay-admin/src/lib/intercept-db.ts \
        navpay-admin/src/app/api/admin/intercept/logs/route.ts \
        navpay-admin/src/app/api/admin/intercept/search/route.ts \
        navpay-admin/tests/unit/intercept/log-device-assignment.test.ts
git commit -m "feat(navpay-admin): bind intercept logs to device by client device id"
```

### Task 4: Add Device Observability APIs (details, owner history, related devices, logs)

**Files:**
- Modify: `navpay-admin/src/app/api/admin/resources/devices/route.ts`
- Create: `navpay-admin/src/app/api/admin/resources/devices/[deviceId]/route.ts`
- Create: `navpay-admin/src/app/api/admin/resources/devices/[deviceId]/logs/route.ts`
- Create: `navpay-admin/tests/unit/device-resources-detail-route.test.ts`

**Step 1: Write the failing test**

```ts
test("device detail includes owner history, owner other devices, phonepe app info, and logs", async () => {
  // seed device/person/payment_device_apps/payment_apps/http_intercept_logs/payment_device_owner_history
  // GET /api/admin/resources/devices/:deviceId
  // expect history + related devices + phonepe info + latest log summary
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/device-resources-detail-route.test.ts`
Expected: FAIL with missing route.

**Step 3: Write minimal implementation**

`GET /api/admin/resources/devices` 补全字段（device id、clientDeviceId、硬件、时区、品牌、online）。

`GET /api/admin/resources/devices/[deviceId]` 返回：

```ts
{
  ok: true,
  device: {
    id, clientDeviceId, name, online, lastSeenAtMs,
    brand, model, osVersion, sdkInt, timezone, locale,
    cpuAbi, memoryMb, locationLat, locationLng, locationAccuracyM,
    personId, personName, username,
  },
  ownerHistory: [{ fromPersonId, toPersonId, reason, createdAtMs }],
  ownerOtherDevices: [{ id, name, online, lastSeenAtMs }],
  phonepe: { installed: true, packageName: "com.phonepe.app", versionCode, updatedAtMs },
}
```

`GET /api/admin/resources/devices/[deviceId]/logs`：按 `source_device_id=deviceId` 返回上报日志列表，并包含 `sourceApp`。

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/device-resources-detail-route.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-admin/src/app/api/admin/resources/devices/route.ts \
        navpay-admin/src/app/api/admin/resources/devices/[deviceId]/route.ts \
        navpay-admin/src/app/api/admin/resources/devices/[deviceId]/logs/route.ts \
        navpay-admin/tests/unit/device-resources-detail-route.test.ts
git commit -m "feat(navpay-admin): expose device observability detail and device-scoped logs"
```

### Task 5: Integrate Intercept Console into Resources Right-Side Tab (Remove Standalone Menu Entry)

**Files:**
- Create: `navpay-admin/src/components/intercept-console.tsx`
- Modify: `navpay-admin/src/app/admin/intercept/page.tsx`
- Modify: `navpay-admin/src/components/resources-client.tsx`
- Modify: `navpay-admin/src/components/admin-shell.tsx`
- Modify: `navpay-admin/tests/unit/admin-shell-reporting-nav.test.ts`
- Create: `navpay-admin/tests/unit/resources-intercept-tab.test.ts`

**Step 1: Write the failing test**

```ts
test("resources tab includes 上报 and admin shell no longer shows standalone /admin/intercept menu", () => {
  const resources = readFileSync("src/components/resources-client.tsx", "utf8");
  const shell = readFileSync("src/components/admin-shell.tsx", "utf8");
  expect(resources).toContain("上报日志");
  expect(shell).not.toContain('href: "/admin/intercept"');
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/admin-shell-reporting-nav.test.ts tests/unit/resources-intercept-tab.test.ts`
Expected: FAIL.

**Step 3: Write minimal implementation**

- 把原 `src/app/admin/intercept/page.tsx` 主体迁移到 `src/components/intercept-console.tsx`。
- `resources-client.tsx` 新增 tab：`intercept_logs`（右侧面板载入 `<InterceptConsole />`）。
- `src/app/admin/intercept/page.tsx` 改为 redirect 到 `/admin/resources?tab=intercept_logs`。
- `admin-shell.tsx` 移除单独 `/admin/intercept` 菜单。

```tsx
// src/app/admin/intercept/page.tsx
import { redirect } from "next/navigation";
export default function InterceptRedirectPage() {
  redirect("/admin/resources?tab=intercept_logs");
}
```

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/admin-shell-reporting-nav.test.ts tests/unit/resources-intercept-tab.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-admin/src/components/intercept-console.tsx \
        navpay-admin/src/app/admin/intercept/page.tsx \
        navpay-admin/src/components/resources-client.tsx \
        navpay-admin/src/components/admin-shell.tsx \
        navpay-admin/tests/unit/admin-shell-reporting-nav.test.ts \
        navpay-admin/tests/unit/resources-intercept-tab.test.ts
git commit -m "feat(navpay-admin): embed intercept console into resources tab"
```

### Task 6: Upgrade Devices UI to Show Detail, History, Related Devices, PhonePe, and Device Logs

**Files:**
- Modify: `navpay-admin/src/components/devices-client.tsx`
- Create: `navpay-admin/tests/e2e/resources-devices-observability.spec.ts`
- Create: `navpay-admin/tests/unit/devices-client-observability-layout.test.ts`

**Step 1: Write the failing test**

```ts
test("devices client renders detail sections: 归属历史 / 同账号其他设备 / PhonePe / 上报日志", () => {
  const src = readFileSync("src/components/devices-client.tsx", "utf8");
  expect(src).toContain("归属历史");
  expect(src).toContain("同账号其他设备");
  expect(src).toContain("PhonePe");
  expect(src).toContain("上报日志");
});
```

E2E failing test skeleton:

```ts
test("resources devices tab shows online device and linked phonepe log", async ({ request, page }) => {
  // seed device + log via API
  // loginQa(page)
  // goto /admin/resources?tab=devices
  // assert online badge + device id + source app=phonepe visible
});
```

**Step 2: Run test to verify it fails**

Run:
- `cd navpay-admin && yarn test tests/unit/devices-client-observability-layout.test.ts`
- `cd navpay-admin && yarn test:e2e tests/e2e/resources-devices-observability.spec.ts`

Expected: FAIL.

**Step 3: Write minimal implementation**

`devices-client.tsx` 改为“左列表 + 右详情”结构：
- 左侧：设备列表（在线状态、device id、clientDeviceId）。
- 右侧：
  - 注册信息（品牌、机型、系统、时区、CPU、内存、位置）
  - 当前归属支付账号
  - 归属历史
  - 同账号其他设备
  - PhonePe 信息（安装状态/版本）
  - 设备上报日志（标注 `sourceApp=phonepe`）

**Step 4: Run test to verify it passes**

Run:
- `cd navpay-admin && yarn test tests/unit/devices-client-observability-layout.test.ts`
- `cd navpay-admin && yarn test:e2e tests/e2e/resources-devices-observability.spec.ts`

Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-admin/src/components/devices-client.tsx \
        navpay-admin/tests/unit/devices-client-observability-layout.test.ts \
        navpay-admin/tests/e2e/resources-devices-observability.spec.ts
git commit -m "feat(navpay-admin): add device observability details and linked logs in resources"
```

### Task 7: End-to-End Validation + Local Emulator Runbook

**Files:**
- Create: `docs/runbooks/2026-03-02-local-emulator-device-observability-e2e.md`
- Create: `navpay-admin/scripts/it-device-observability.sh`
- Create: `navpay-admin/tests/e2e/resources-intercept-integration.spec.ts`

**Step 1: Write the failing test**

```ts
test("ingested log with clientDeviceId appears under same device in resources", async ({ request, page }) => {
  // report/heartbeat create online device
  // intercept ingest with same clientDeviceId
  // open /admin/resources?tab=devices and assert log appears in selected device panel
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test:e2e tests/e2e/resources-intercept-integration.spec.ts`
Expected: FAIL before UI/API integration is complete.

**Step 3: Write minimal implementation**

- `it-device-observability.sh`：一键执行迁移、seed、关键测试。
- runbook 写清本地模拟器流程：
  1) 启动 `phonepe1` 模拟器
  2) 启动 `navpay-admin` (`yarn dev`)
  3) Android 登录触发 `report/heartbeat`
  4) 拦截客户端上报含 `clientDeviceId`
  5) 在 `http://localhost:3000/admin/resources?tab=devices` 检查在线状态/归属/日志

**Step 4: Run test to verify it passes**

Run:
- `cd navpay-admin && yarn test tests/unit/device-heartbeat.test.ts tests/unit/intercept/log-device-assignment.test.ts tests/unit/device-resources-detail-route.test.ts tests/unit/resources-intercept-tab.test.ts tests/unit/devices-client-observability-layout.test.ts`
- `cd navpay-admin && yarn test:e2e tests/e2e/resources-devices-observability.spec.ts tests/e2e/resources-intercept-integration.spec.ts`
- `cd navpay-admin && bash scripts/it-device-observability.sh`

Expected: PASS.

**Step 5: Commit**

```bash
git add docs/runbooks/2026-03-02-local-emulator-device-observability-e2e.md \
        navpay-admin/scripts/it-device-observability.sh \
        navpay-admin/tests/e2e/resources-intercept-integration.spec.ts
git commit -m "test(navpay-admin): add local emulator e2e validation for device observability"
```

## Guardrails

- DRY: 设备归属历史统一复用 `recordDeviceOwnerChange` helper。
- YAGNI: 不引入设备指纹服务、地图服务、复杂地理反查；位置只存客户端上报原值。
- TDD-first: 每个任务先红后绿。
- 兼容未来多 App：日志以 `source_app` 区分（当前主标记 `phonepe`）。

## Skill References

- Use `@test-driven-development` for each coding task.
- Use `@systematic-debugging` if a test fails unexpectedly.
- Use `@requesting-code-review` after Task 7 before merge.
