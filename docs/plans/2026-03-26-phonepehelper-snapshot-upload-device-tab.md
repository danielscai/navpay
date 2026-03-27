# PhonePeHelper Snapshot Upload + Device Detail Tab Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 `navpay-phonepe` 的 phonepehelper 采集字段上传到 `navpay-admin`，并在设备详情页 `/admin/resources/devices/[deviceId]` 新增 Tab 展示最近采集结果和最后采集时间。

**Architecture:** 复用现有 `POST /api/intercept/phonepe/snapshot` 入库链路（`payment_person_report_logs`，type=`PHONEPE_SNAPSHOT`），在 phonepehelper 侧新增异步 uploader，把文档定义的快照统一上报。admin 侧新增设备级查询 API + 新 Tab 面板，按 `entity_id=deviceId` 查询快照并提取 `metaBuiltAt/created_at_ms` 作为“最后采集时间”。采用 `@test-driven-development` 的顺序：先补 route/UI 合约测试，再落地实现，最后执行 `@verification-before-completion`。

**Tech Stack:** Android Java（phonepehelper 注入模块）、Next.js App Router、TypeScript、Prisma(PostgreSQL)、Vitest、Playwright。

---

### Task 1: Define Snapshot Payload Contract and Add Android Uploader

**Files:**
- Create: `navpay-phonepe/src/apk/phonepehelper/src/main/java/com/phonepehelper/NavpaySnapshotUploader.java`
- Modify: `navpay-phonepe/src/apk/phonepehelper/src/main/java/com/PhonePeTweak/Def/PhonePeHelper.java`
- Modify: `navpay-phonepe/src/apk/phonepehelper/src/main/java/com/phonepehelper/ModuleInit.java`
- Modify: `navpay-phonepe/src/apk/phonepehelper/README.md`

**Step 1: Write the failing test**

```bash
# 合约测试（源码级，先失败）：要求存在 uploader、endpoint、调用点
rg -n "class NavpaySnapshotUploader|/api/intercept/phonepe/snapshot|uploadSnapshotAsync\(|metaBuiltAt" \
  navpay-phonepe/src/apk/phonepehelper/src/main/java
```

Expected: FAIL（找不到 uploader 类和调用点）。

**Step 2: Run test to verify it fails**

Run: `rg -n "NavpaySnapshotUploader|uploadSnapshotAsync" navpay-phonepe/src/apk/phonepehelper/src/main/java`
Expected: no matches / 非 0 退出码。

**Step 3: Write minimal implementation**

```java
// navpay-phonepe/src/apk/phonepehelper/src/main/java/com/phonepehelper/NavpaySnapshotUploader.java
package com.phonepehelper;

import android.util.Log;
import org.json.JSONObject;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

final class NavpaySnapshotUploader {
    private static final String TAG = "PPHelperUploader";
    // Emulator -> host machine mapping (per AGENTS guidance)
    private static final String ENDPOINT = "http://10.0.2.2:3000/api/intercept/phonepe/snapshot";
    private static final ExecutorService EXECUTOR = Executors.newSingleThreadExecutor();

    private NavpaySnapshotUploader() {}

    static void uploadSnapshotAsync(String androidId, JSONObject payload) {
        if (androidId == null || androidId.trim().isEmpty() || payload == null) return;
        EXECUTOR.execute(() -> uploadSnapshot(androidId.trim(), payload));
    }

    private static void uploadSnapshot(String androidId, JSONObject payload) {
        HttpURLConnection conn = null;
        try {
            JSONObject req = new JSONObject();
            req.put("androidId", androidId);
            req.put("payload", payload);
            byte[] body = req.toString().getBytes(StandardCharsets.UTF_8);

            conn = (HttpURLConnection) new URL(ENDPOINT).openConnection();
            conn.setRequestMethod("POST");
            conn.setConnectTimeout(3000);
            conn.setReadTimeout(5000);
            conn.setDoOutput(true);
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setRequestProperty("Accept", "application/json");

            try (OutputStream os = conn.getOutputStream()) {
                os.write(body);
            }

            int code = conn.getResponseCode();
            Log.i(TAG, "snapshot upload done: code=" + code + ", androidId=" + androidId);
        } catch (Throwable t) {
            Log.w(TAG, "snapshot upload failed", t);
        } finally {
            if (conn != null) conn.disconnect();
        }
    }
}
```

```java
// PhonePeHelper.java (core idea)
public static JSONObject buildSnapshotForNavpay() {
    JSONObject snapshot = new JSONObject();
    try {
        snapshot.put("requestMeta", getRequestMetaInfoObj());
        snapshot.put("upis", getUPIs());
        snapshot.put("lastMpinLength", getLastMpin().length());
        snapshot.put("collectedAtMs", System.currentTimeMillis());
    } catch (JSONException ignored) {}
    return snapshot;
}

public static void uploadSnapshotToNavpayAsync() {
    String androidId = getAndroidId();
    JSONObject payload = buildSnapshotForNavpay();
    NavpaySnapshotUploader.uploadSnapshotAsync(androidId, payload);
}
```

```java
// ModuleInit.java (call point)
PhonePeHelper.publishTokenUpdateIfNeeded(true);
PhonePeHelper.uploadSnapshotToNavpayAsync();
```

Also in `publishTokenUpdateIfNeeded(true/false)` changed branch, trigger `uploadSnapshotToNavpayAsync()` when snapshot changed。

**Step 4: Run test to verify it passes**

Run: `rg -n "NavpaySnapshotUploader|uploadSnapshotToNavpayAsync|/api/intercept/phonepe/snapshot|collectedAtMs" navpay-phonepe/src/apk/phonepehelper/src/main/java`
Expected: PASS（命中 uploader + endpoint + 调用点）。

**Step 5: Commit**

```bash
git -C navpay-phonepe add \
  src/apk/phonepehelper/src/main/java/com/phonepehelper/NavpaySnapshotUploader.java \
  src/apk/phonepehelper/src/main/java/com/PhonePeTweak/Def/PhonePeHelper.java \
  src/apk/phonepehelper/src/main/java/com/phonepehelper/ModuleInit.java \
  src/apk/phonepehelper/README.md
git -C navpay-phonepe commit -m "feat(phonepehelper): upload collected snapshot to navpay-admin"
```

### Task 2: Enrich Snapshot Ingest Route With Stable Collected Timestamp

**Files:**
- Modify: `navpay-admin/src/app/api/intercept/phonepe/snapshot/route.ts`
- Test: `navpay-admin/tests/unit/intercept/phonepe-snapshot-route.test.ts`

**Step 1: Write the failing test**

```ts
// navpay-admin/tests/unit/intercept/phonepe-snapshot-route.test.ts
import { describe, expect, test, vi } from "vitest";
import { prisma } from "@/lib/prisma";
import { POST as postSnapshot } from "@/app/api/intercept/phonepe/snapshot/route";

vi.mock("@/lib/phonepe-assignment", () => ({
  resolvePhonePeAssignmentByAndroidId: async () => ({ deviceId: "dev_1", personId: "pp_1" }),
}));

describe("phonepe snapshot ingest", () => {
  test("stores PHONEPE_SNAPSHOT with device entity and collectedAtMs in meta", async () => {
    const req = new Request("http://localhost/api/intercept/phonepe/snapshot", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        androidId: "android-1",
        payload: { requestMeta: { metaBuiltAt: "2026-03-26 13:00:00" }, collectedAtMs: 1774510800000 },
      }),
    });

    const res = await postSnapshot(req as any);
    const json: any = await res.json();

    expect(res.status).toBe(200);
    expect(json.ok).toBe(true);

    const row = await prisma.payment_person_report_logs.findUnique({ where: { id: json.logId } });
    const meta = JSON.parse(String(row?.meta_json ?? "{}"));
    expect(row?.type).toBe("PHONEPE_SNAPSHOT");
    expect(row?.entity_id).toBe("dev_1");
    expect(meta.collectedAtMs).toBe(1774510800000);
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/intercept/phonepe-snapshot-route.test.ts`
Expected: FAIL（尚未写入 `collectedAtMs` 标准字段）。

**Step 3: Write minimal implementation**

```ts
// route.ts core
function resolveCollectedAtMs(payload: unknown, fallbackNow: number): number {
  const p = (payload && typeof payload === "object") ? (payload as Record<string, unknown>) : {};
  const direct = Number(p.collectedAtMs);
  if (Number.isFinite(direct) && direct > 0) return Math.trunc(direct);
  const requestMeta = p.requestMeta && typeof p.requestMeta === "object" ? (p.requestMeta as Record<string, unknown>) : {};
  const metaBuiltAt = String(requestMeta.metaBuiltAt ?? "").trim();
  // "yyyy-MM-dd HH:mm:ss" -> epoch ms (local)
  const parsed = Date.parse(metaBuiltAt.replace(" ", "T"));
  if (Number.isFinite(parsed) && parsed > 0) return Math.trunc(parsed);
  return fallbackNow;
}

const collectedAtMs = resolveCollectedAtMs(body.data.payload, now);
const meta = {
  androidId: body.data.androidId,
  collectedAtMs,
  payload: body.data.payload,
};
```

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/intercept/phonepe-snapshot-route.test.ts`
Expected: PASS。

**Step 5: Commit**

```bash
git -C navpay-admin add \
  src/app/api/intercept/phonepe/snapshot/route.ts \
  tests/unit/intercept/phonepe-snapshot-route.test.ts
git -C navpay-admin commit -m "feat(intercept): persist stable collected timestamp for phonepe snapshots"
```

### Task 3: Add Device-Level Snapshot Query API for New Tab

**Files:**
- Create: `navpay-admin/src/app/api/admin/resources/devices/[deviceId]/phonepehelper/route.ts`
- Test: `navpay-admin/tests/unit/device-phonepehelper-route.test.ts`

**Step 1: Write the failing test**

```ts
// navpay-admin/tests/unit/device-phonepehelper-route.test.ts
import { beforeEach, describe, expect, test, vi } from "vitest";
import { sqlExec } from "@/lib/db";
import { prisma } from "@/lib/prisma";
import { id } from "@/lib/id";
import { GET as getPhonepeHelper } from "@/app/api/admin/resources/devices/[deviceId]/phonepehelper/route";

vi.mock("@/lib/api", () => ({ requireApiPerm: async () => ({ uid: "u_test" }) }));

beforeEach(async () => {
  await sqlExec("delete from payment_person_report_logs");
  await sqlExec("delete from payment_devices");
});

describe("device phonepehelper snapshots route", () => {
  test("returns latest snapshot and lastCollectedAtMs for device", async () => {
    const now = Date.now();
    const deviceId = id("dev");
    await prisma.payment_devices.create({ data: { id: deviceId, name: "D1", created_at_ms: BigInt(now), updated_at_ms: BigInt(now) } });

    await prisma.payment_person_report_logs.create({
      data: {
        id: id("pprlog"),
        person_id: "pp_1",
        type: "PHONEPE_SNAPSHOT",
        entity_type: "phonepe",
        entity_id: deviceId,
        meta_json: JSON.stringify({ collectedAtMs: now - 1000, payload: { requestMeta: { userPhone: "999" } } }),
        created_at_ms: BigInt(now - 900),
      },
    });

    const res = await getPhonepeHelper(new Request(`http://localhost/api/admin/resources/devices/${deviceId}/phonepehelper`) as any, {
      params: Promise.resolve({ deviceId }),
    } as any);
    const json: any = await res.json();

    expect(res.status).toBe(200);
    expect(json.ok).toBe(true);
    expect(json.lastCollectedAtMs).toBe(now - 1000);
    expect(json.rows.length).toBe(1);
    expect(json.rows[0].type).toBe("PHONEPE_SNAPSHOT");
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/device-phonepehelper-route.test.ts`
Expected: FAIL（route 不存在）。

**Step 3: Write minimal implementation**

```ts
// navpay-admin/src/app/api/admin/resources/devices/[deviceId]/phonepehelper/route.ts
import { NextResponse, type NextRequest } from "next/server";
import { requireApiPerm } from "@/lib/api";
import { prisma } from "@/lib/prisma";

export async function GET(req: NextRequest, ctx: { params: Promise<{ deviceId: string }> }) {
  await requireApiPerm(req, "payout.channel.read");
  const { deviceId } = await ctx.params;

  const rows = await prisma.payment_person_report_logs.findMany({
    where: { type: "PHONEPE_SNAPSHOT", entity_type: "phonepe", entity_id: deviceId },
    orderBy: { created_at_ms: "desc" },
    take: 20,
    select: { id: true, created_at_ms: true, meta_json: true, type: true },
  });

  const mapped = rows.map((r) => {
    const meta = JSON.parse(r.meta_json ?? "{}") as Record<string, unknown>;
    const collectedAtMs = Number(meta.collectedAtMs ?? Number(r.created_at_ms));
    return {
      id: r.id,
      type: r.type,
      createdAtMs: Number(r.created_at_ms),
      collectedAtMs: Number.isFinite(collectedAtMs) ? collectedAtMs : Number(r.created_at_ms),
      payload: meta.payload ?? null,
    };
  });

  return NextResponse.json({
    ok: true,
    lastCollectedAtMs: mapped.length ? mapped[0].collectedAtMs : null,
    rows: mapped,
  });
}
```

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/device-phonepehelper-route.test.ts`
Expected: PASS。

**Step 5: Commit**

```bash
git -C navpay-admin add \
  src/app/api/admin/resources/devices/[deviceId]/phonepehelper/route.ts \
  tests/unit/device-phonepehelper-route.test.ts
git -C navpay-admin commit -m "feat(devices): add phonepehelper snapshots query route"
```

### Task 4: Add Device Detail Tab for PhonePeHelper Snapshot + Last Collected Time

**Files:**
- Create: `navpay-admin/src/components/device-phonepehelper-panel.tsx`
- Modify: `navpay-admin/src/components/device-detail-client.tsx`
- Modify: `navpay-admin/tests/unit/devices-client-observability-layout.test.ts`
- Modify: `navpay-admin/tests/e2e/resources-devices-layout.spec.ts`

**Step 1: Write the failing test**

```ts
// devices-client-observability-layout.test.ts 追加断言
expect(src).toContain("?tab=phonepehelper");
expect(src).toContain("PhonePeHelper采集");
expect(src).toContain("DevicePhonePeHelperPanel");
expect(src).toContain("最后采集时间");
```

```ts
// resources-devices-layout.spec.ts 追加流程
await page.goto(`/admin/resources/devices/${deviceId}?tab=phonepehelper`);
await expect(page.getByText("PhonePeHelper采集")).toBeVisible();
await expect(page.getByText("最后采集时间")).toBeVisible();
```

**Step 2: Run test to verify it fails**

Run:
- `cd navpay-admin && yarn test tests/unit/devices-client-observability-layout.test.ts`
- `cd navpay-admin && yarn test:e2e tests/e2e/resources-devices-layout.spec.ts`

Expected: FAIL（新 tab 与 panel 尚未实现）。

**Step 3: Write minimal implementation**

```tsx
// src/components/device-phonepehelper-panel.tsx (核心结构)
"use client";

import { useEffect, useState } from "react";
import { DateTime2Line } from "@/components/table-kit";

export default function DevicePhonePeHelperPanel(props: { deviceId: string; timezone: string }) {
  const [data, setData] = useState<{ lastCollectedAtMs: number | null; rows: Array<any> } | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const res = await fetch(`/api/admin/resources/devices/${encodeURIComponent(props.deviceId)}/phonepehelper`);
      const json = await res.json().catch(() => null);
      if (!res.ok || !json?.ok) {
        setErr("PhonePeHelper 采集数据加载失败");
        return;
      }
      setData({ lastCollectedAtMs: json.lastCollectedAtMs ?? null, rows: json.rows ?? [] });
    })();
  }, [props.deviceId]);

  return (
    <section className="rounded-xl border border-white/10 bg-black/20 p-4" data-testid="device-phonepehelper-panel">
      <div className="text-sm font-semibold">PhonePeHelper采集</div>
      <div className="mt-2 text-xs text-[var(--np-muted)]">
        最后采集时间 {data?.lastCollectedAtMs ? <DateTime2Line ms={data.lastCollectedAtMs} timeZone={props.timezone} /> : "-"}
      </div>
      {err ? <div className="mt-3 text-xs text-[var(--np-danger)]">{err}</div> : null}
      {/* rows: requestMeta/tokens/upis/sms/runtime 摘要展示 */}
    </section>
  );
}
```

```tsx
// device-detail-client.tsx 关键变更
import DevicePhonePeHelperPanel from "@/components/device-phonepehelper-panel";

const tab = tabRaw === "intercept_logs" || tabRaw === "history_transactions" || tabRaw === "phonepehelper"
  ? tabRaw
  : "overview";

<Link href={`/admin/resources/devices/${props.deviceId}?tab=phonepehelper`}>PhonePeHelper采集</Link>

{tab === "phonepehelper" ? (
  <DevicePhonePeHelperPanel deviceId={props.deviceId} timezone={timezone} />
) : ...}
```

**Step 4: Run test to verify it passes**

Run:
- `cd navpay-admin && yarn test tests/unit/devices-client-observability-layout.test.ts`
- `cd navpay-admin && yarn test tests/unit/device-phonepehelper-route.test.ts tests/unit/intercept/phonepe-snapshot-route.test.ts`
- `cd navpay-admin && yarn test:e2e tests/e2e/resources-devices-layout.spec.ts`

Expected: PASS。

**Step 5: Commit**

```bash
git -C navpay-admin add \
  src/components/device-phonepehelper-panel.tsx \
  src/components/device-detail-client.tsx \
  tests/unit/devices-client-observability-layout.test.ts \
  tests/e2e/resources-devices-layout.spec.ts
git -C navpay-admin commit -m "feat(devices): add phonepehelper tab with last collected time"
```

### Task 5: End-to-End Validation and Operator Run Notes

**Files:**
- Modify: `navpay-phonepe/docs/phonepehelper_数据采集字段设计.md`
- Modify: `navpay-admin/docs/manual/` (add one runbook markdown if missing)

**Step 1: Write the failing test**

```bash
# 文档门禁：必须包含 endpoint、字段映射、最后采集时间定义
rg -n "api/intercept/phonepe/snapshot|lastCollectedAtMs|metaBuiltAt|10.0.2.2" \
  navpay-phonepe/docs/phonepehelper_数据采集字段设计.md
```

Expected: FAIL（未更新上传与展示章节）。

**Step 2: Run test to verify it fails**

Run: same `rg` command above.
Expected: no match 或不完整。

**Step 3: Write minimal implementation**

```md
- 上传地址：`http://10.0.2.2:3000/api/intercept/phonepe/snapshot`
- 上传结构：`{ androidId, payload }`
- admin 设备页 Tab：`?tab=phonepehelper`
- 最后采集时间计算：优先 `payload.collectedAtMs`，其次 `requestMeta.metaBuiltAt`，兜底 `created_at_ms`
```

**Step 4: Run test to verify it passes**

Run:
- `rg -n "api/intercept/phonepe/snapshot|lastCollectedAtMs|metaBuiltAt|10.0.2.2" navpay-phonepe/docs/phonepehelper_数据采集字段设计.md`
- `cd navpay-phonepe && ./src/apk/phonepehelper/scripts/compile.sh`
- `cd navpay-admin && yarn lint && yarn typecheck`

Expected: PASS（文档命中、phonepehelper 编译成功、admin 静态检查通过）。

**Step 5: Commit**

```bash
git -C navpay-phonepe add docs/phonepehelper_数据采集字段设计.md
git -C navpay-phonepe commit -m "docs(phonepehelper): document navpay snapshot upload contract"

git -C navpay-admin add docs/manual/phonepehelper-device-tab.md
git -C navpay-admin commit -m "docs(admin): add phonepehelper device tab runbook"
```

