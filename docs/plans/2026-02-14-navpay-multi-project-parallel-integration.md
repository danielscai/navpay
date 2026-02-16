# NavPay Multi-Project Parallel Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 串联 `navpay-android`(Android) + `navpay-admin`(API/管理台) + `navpay-otp`(OTP) + `navpay-landing`(落地页) + `navpay-tgbot`(TG bot)，打通注册登录、OTP 模拟、心跳、银行 App 下载管理、Mine(余额/明细/改密)、新手福利、三级返利、以及高并发抢单/刷新压力治理，并形成可多 agent 并行开发的任务拆分与契约。

**Architecture:**
1) **唯一后端入口**：移动端只调用 `navpay-admin` 的 `/api/personal/*`，由 admin 去调用 `navpay-otp`、并统一鉴权、限流、审计。
2) **契约先行**：把“移动端需要的 API 形状”沉淀为一个版本化的契约文档（JSON + Markdown），作为多 agent 并行的对齐点。
3) **高并发治理**：对“列表刷新/抢单/写入”采用 DB 原子更新 + 幂等键 + 热路径缓存/限流，避免 SQLite 写锁/热点 count 查询造成雪崩。

**Tech Stack:**
- Android: Kotlin + OkHttp + Gradle (`navpay-android/`)
- Admin: Next.js route handlers + TypeScript + Drizzle + SQLite (`navpay-admin/`)
- OTP: Fastify + TypeScript + SQLite (`navpay-otp/`)
- Landing: Next.js + TypeScript (`navpay-landing/`)
- TG Bot: Node/TS Telegram bot (`navpay-tgbot/`)

---

## 项目关系与依赖 (作为全体 agent 的共同上下文)

### 服务/项目清单
- `navpay-android/` (Android 客户端)
  - 调用：`navpay-admin` `/api/personal/*`
  - 心跳：每 5 秒调用一次 `/api/personal/device/heartbeat` (已存在)
- `navpay-admin/` (API + 管理台)
  - 对外：移动端 API `/api/personal/*`
  - 对外：落地页公有 API (后续新增 `/api/public/*`)
  - 对内：调用 `navpay-otp` 发送/校验 OTP
  - 对内：供 `navpay-tgbot` 调用 `/api/integrations/telegram/bind` (已存在)
- `navpay-otp/` (OTP 服务)
  - 提供：`/v1/otp/send`、`/v1/otp/verify`
  - dev/test：默认 `WA_PROVIDER=fake`，OTP 打到 stdout
- `navpay-landing/` (落地页)
  - 展示下载入口（NavPay APK + 未来银行 App APK）
  - 需要：可配置的下载清单（从 admin 拉取 manifest）
- `navpay-tgbot/` (TG 群机器人)
  - `/bind` 通过 inviteCode 绑定账号
  - 调用：admin `/api/integrations/telegram/bind` (已存在)

### 并行开发约束 (避免冲突)
- 共享高冲突文件：
  - `navpay-admin/src/db/schema.ts`
  - `navpay-admin/drizzle/*` migrations
- 并行策略：
  - Phase 1 尽量**不改 DB schema**：注册用 `payment_person_credentials.username = phoneE164` 规避新增 phone 字段。
  - 需要新增表时，集中在同一个 workstream 的 migration 里，其他 agent 不碰 migrations。

---

## Workstreams (可并行启动多个 agent)

- **WS-0: 项目关系+契约+本地联调脚本**（强烈建议先做，减少返工）
- **WS-1: 注册/登录/OTP 代理化（admin 统一入口）**
- **WS-2: Mine 模块（余额、余额明细、改密）**
- **WS-3: 银行 App 下载管理（admin 管理 + personal API + Android 对接）**
- **WS-4: 新手福利/活动（admin 活动管理 + personal API + Android 对接）**
- **WS-5: 三级返利/推荐系统（比例配置读取 + personal API）**
- **WS-6: 高并发抢单/刷新压力治理（available/mine/claim 路由优化 + 限流/缓存 + 负载测试）**
- **WS-7: Landing 下载页管理化（manifest + 管理页）**
- **WS-8: TG Bot 绑定闭环验证（bot -> admin -> DB -> admin review）**

每个 WS 内再拆成 2-5 分钟的 Task；除显式写明依赖外，可并行。

---

# WS-0: 项目关系+契约+本地联调脚本

### Task 0.1: 新增“项目关系图”文档

**Files:**
- Create: `docs/architecture/projects-and-deps.md`

**Step 1: Write the failing test**

不需要测试（文档任务）。

**Step 2: Create doc**

在 `docs/architecture/projects-and-deps.md` 写入（可直接复制以下内容）：

```markdown
# NavPay Projects & Dependencies

## Projects
- navpay-android (Android)
- navpay-admin (API + Admin UI)
- navpay-otp (OTP service)
- navpay-landing (Download landing)
- navpay-tgbot (Telegram bot)

## Runtime Dependencies
- navpay-android -> navpay-admin (HTTP)
- navpay-admin -> navpay-otp (HTTP)
- navpay-tgbot -> navpay-admin (HTTP)
- navpay-landing -> navpay-admin (HTTP, public manifest)

## Local Ports (dev defaults)
- navpay-admin: 3000
- navpay-otp: 19090
- navpay-landing: 3100 (suggested)
- navpay-tgbot: no port (outbound polling/webhook)

## API Prefixes
- Mobile: /api/personal/*
- Admin UI: /admin/*
- Integrations: /api/integrations/*
- Public: /api/public/*
```

**Step 3: Commit**

```bash
git add docs/architecture/projects-and-deps.md
git commit -m "docs: document navpay-android multi-project dependencies"
```

### Task 0.2: 新增“移动端 API 契约”占位文档

**Files:**
- Create: `docs/contracts/personal-api-v1.md`

**Step 1: Create doc**

内容建议（先列出清单，后续 WS 按章节补齐）：

```markdown
# Personal API v1 (Mobile)

Base: /api/personal

## Auth
- POST /auth/login
- POST /auth/register/start
- POST /auth/register/verify
- POST /auth/register/complete
- POST /auth/logout
- POST /auth/password/reset

## Me & Mine
- GET /me
- GET /mine/balance-logs

## Device
- POST /device/report
- POST /device/heartbeat

## Payout Orders
- GET /payout/orders/available
- POST /payout/orders/{orderId}/claim
- POST /payout/orders/{orderId}/complete
- GET /payout/orders/mine

## Bank Apps
- GET /payment-apps

## Rewards / Activities
- GET /rewards/newbie

## Referral / Rebates
- GET /referral/summary
- GET /referral/downlines
```

**Step 2: Commit**

```bash
git add docs/contracts/personal-api-v1.md
git commit -m "docs: add personal api v1 contract outline"
```

### Task 0.3: 新增“本地一键启动”脚本骨架

**Files:**
- Create: `tools/dev-up.sh`
- Create: `tools/dev-down.sh`
- Create: `tools/dev-status.sh`

**Step 1: Write minimal scripts**

`tools/dev-up.sh`（最小可用：分别在后台启动 3 个 Next/Fastify；端口按各自项目默认）：

```bash
#!/usr/bin/env bash
set -euo pipefail

# Start navpay-admin, navpay-otp, navpay-landing for local integration.
# Note: Use separate terminals for logs if you prefer; this is a convenience runner.

( cd navpay-otp && yarn dev ) > /tmp/navpay-otp.log 2>&1 &
( cd navpay-admin && yarn dev ) > /tmp/navpay-admin.log 2>&1 &
( cd navpay-landing && PORT=3100 yarn dev ) > /tmp/navpay-landing.log 2>&1 &

echo "otp:     http://127.0.0.1:19090"
echo "admin:   http://127.0.0.1:3000"
echo "landing: http://127.0.0.1:3100"
echo "logs: /tmp/navpay-otp.log /tmp/navpay-admin.log /tmp/navpay-landing.log"
```

`tools/dev-down.sh`（用 `lsof` 查端口并 kill）：

```bash
#!/usr/bin/env bash
set -euo pipefail

for p in 19090 3000 3100; do
  ids=$(lsof -ti ":$p" || true)
  if [ -n "${ids}" ]; then
    kill ${ids} || true
  fi
done
```

`tools/dev-status.sh`：

```bash
#!/usr/bin/env bash
set -euo pipefail

for p in 19090 3000 3100; do
  if lsof -ti ":$p" >/dev/null 2>&1; then
    echo "$p: up"
  else
    echo "$p: down"
  fi
done
```

**Step 2: Make executable**

Run:
```bash
chmod +x tools/dev-up.sh tools/dev-down.sh tools/dev-status.sh
```

**Step 3: Commit**

```bash
git add tools/dev-up.sh tools/dev-down.sh tools/dev-status.sh
git commit -m "chore: add local dev runner scripts"
```

### Task 0.4: 增加机器可读的“服务地图”(让项目可感知关系)

**Files:**
- Create: `ref/service-map.v1.json`
- Create: `tools/print-service-map.sh`

**Step 1: Create `ref/service-map.v1.json`**

```json
{
  "version": 1,
  "projects": [
    { "id": "navpay-android", "type": "android", "path": "navpay-android" },
    { "id": "navpay-admin", "type": "nextjs", "path": "navpay-admin", "devPort": 3000 },
    { "id": "navpay-otp", "type": "fastify", "path": "navpay-otp", "devPort": 19090 },
    { "id": "navpay-landing", "type": "nextjs", "path": "navpay-landing", "devPort": 3100 },
    { "id": "navpay-tgbot", "type": "telegram-bot", "path": "navpay-tgbot" }
  ],
  "dependencies": [
    { "from": "navpay-android", "to": "navpay-admin", "kind": "http", "notes": "Mobile personal API" },
    { "from": "navpay-admin", "to": "navpay-otp", "kind": "http", "notes": "OTP send/verify" },
    { "from": "navpay-tgbot", "to": "navpay-admin", "kind": "http", "notes": "Telegram bind integration" },
    { "from": "navpay-landing", "to": "navpay-admin", "kind": "http", "notes": "Public downloads manifest" }
  ]
}
```

**Step 2: Create helper script**

`tools/print-service-map.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
cat ref/service-map.v1.json | python3 -m json.tool
```

**Step 3: Run**

```bash
./tools/print-service-map.sh
```
Expected: pretty-printed JSON.

**Step 4: Commit**

```bash
git add ref/service-map.v1.json tools/print-service-map.sh
git commit -m "docs: add machine-readable service map"
```

---

# WS-1: 注册/登录/OTP 代理化（admin 统一入口）

## 目标行为 (Mobile)
- 注册页：输入印度手机号(建议存 E164, +91...) + 密码 + (可选) 邀请码
- 点击注册：
  1) admin 发 OTP（admin -> otp）
  2) 用户输入 OTP
  3) admin 校验 OTP（admin -> otp）
  4) admin 创建支付账户(payment person) + 下发 personal token
- Android 不再直连 `navpay-otp`。

### Task 1.1: 在 admin 增加 OTP client（封装 navpay-otp 调用）

**Files:**
- Create: `navpay-admin/src/lib/otp-client.ts`
- Test: `navpay-admin/tests/unit/otp-client.test.ts`

**Step 1: Write the failing test**

```ts
import { describe, expect, test, vi } from "vitest";
import { sendOtp, verifyOtp } from "@/lib/otp-client";

describe("otp client", () => {
  test("sendOtp forwards request and parses response", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch" as any).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ok: true, otpId: "otp_1", expiresAtMs: 1, resendAfterSec: 60, maskedTo: "+91******1234" }),
    } as any);

    const r = await sendOtp({ baseUrl: "http://otp", apiKey: "k", phoneE164: "+919999999999", purpose: "register", locale: "en" });
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.otpId).toBe("otp_1");

    fetchSpy.mockRestore();
  });

  test("verifyOtp forwards request and parses response", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch" as any).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ok: true, verified: true, verificationToken: "v_1" }),
    } as any);

    const r = await verifyOtp({ baseUrl: "http://otp", apiKey: "k", otpId: "otp_1", code: "123456" });
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.verificationToken).toBe("v_1");

    fetchSpy.mockRestore();
  });
});
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd navpay-admin && yarn test tests/unit/otp-client.test.ts -v
```
Expected: FAIL (module not found).

**Step 3: Write minimal implementation**

```ts
// navpay-admin/src/lib/otp-client.ts

export type OtpPurpose = "register" | "login" | "reset_password";

export async function sendOtp(opts: {
  baseUrl: string;
  apiKey: string;
  phoneE164: string;
  purpose: OtpPurpose;
  locale?: string;
}): Promise<{ ok: true; otpId: string; expiresAtMs: number; resendAfterSec: number; maskedTo: string } | { ok: false; error: string; status: number }> {
  const r = await fetch(`${opts.baseUrl}/v1/otp/send`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "X-Navpay-Otp-Key": opts.apiKey,
    },
    body: JSON.stringify({ phoneE164: opts.phoneE164, purpose: opts.purpose, locale: opts.locale ?? "en" }),
  });

  const j = await r.json().catch(() => null);
  if (!r.ok) return { ok: false, error: String(j?.error ?? "otp_send_failed"), status: r.status };
  if (!j?.ok) return { ok: false, error: String(j?.error ?? "otp_send_failed"), status: r.status };
  return { ok: true, otpId: String(j.otpId), expiresAtMs: Number(j.expiresAtMs), resendAfterSec: Number(j.resendAfterSec ?? 60), maskedTo: String(j.maskedTo ?? "") };
}

export async function verifyOtp(opts: {
  baseUrl: string;
  apiKey: string;
  otpId: string;
  code: string;
}): Promise<{ ok: true; verified: boolean; verificationToken: string } | { ok: false; error: string; status: number }> {
  const r = await fetch(`${opts.baseUrl}/v1/otp/verify`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "X-Navpay-Otp-Key": opts.apiKey,
    },
    body: JSON.stringify({ otpId: opts.otpId, code: opts.code }),
  });

  const j = await r.json().catch(() => null);
  if (!r.ok) return { ok: false, error: String(j?.error ?? "otp_verify_failed"), status: r.status };
  if (!j?.ok) return { ok: false, error: String(j?.error ?? "otp_verify_failed"), status: r.status };
  return { ok: true, verified: !!j.verified, verificationToken: String(j.verificationToken ?? "") };
}
```

**Step 4: Run test to verify it passes**

Run:
```bash
cd navpay-admin && yarn test tests/unit/otp-client.test.ts -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-admin/src/lib/otp-client.ts navpay-admin/tests/unit/otp-client.test.ts
git commit -m "feat(admin): add otp client wrapper"
```

### Task 1.2: admin 增加 env 配置：OTP_BASE_URL/OTP_API_KEY

**Files:**
- Modify: `navpay-admin/src/lib/env.ts`
- Modify: `navpay-admin/.env.example`
- Test: `navpay-admin/tests/unit/env-otp.test.ts`

**Step 1: Write failing test**

```ts
import { describe, expect, test } from "vitest";
import { parseEnv } from "@/lib/env";

describe("env otp", () => {
  test("parses otp config", () => {
    const env = parseEnv({
      AUTH_SECRET: "x".repeat(32),
      TOTP_ENCRYPTION_KEY: "x".repeat(32),
      APIKEY_ENCRYPTION_KEY: "x".repeat(32),
      OTP_BASE_URL: "http://127.0.0.1:19090",
      OTP_API_KEY: "dev-otp-key",
    } as any);
    expect(env.OTP_BASE_URL).toContain("19090");
    expect(env.OTP_API_KEY).toBe("dev-otp-key");
  });
});
```

**Step 2: Run test (expect fail)**

Run:
```bash
cd navpay-admin && yarn test tests/unit/env-otp.test.ts -v
```
Expected: FAIL (missing fields in schema).

**Step 3: Implement env fields**

在 `navpay-admin/src/lib/env.ts` 的 zod schema 增加：

```ts
OTP_BASE_URL: z.string().min(6).default("http://127.0.0.1:19090"),
OTP_API_KEY: z.string().min(1).default("dev-otp-key"),
```

并确保 `parseEnv` 导出（若目前只导出 env 常量，则补一个可测的 `parseEnv`）。

**Step 4: Update .env.example**

增加：

```bash
OTP_BASE_URL=http://127.0.0.1:19090
OTP_API_KEY=dev-otp-key
```

**Step 5: Run test (expect pass)**

```bash
cd navpay-admin && yarn test tests/unit/env-otp.test.ts -v
```

**Step 6: Commit**

```bash
git add navpay-admin/src/lib/env.ts navpay-admin/.env.example navpay-admin/tests/unit/env-otp.test.ts
git commit -m "chore(admin): add otp env config"
```

### Task 1.3: admin 新增注册 OTP: start（发送 OTP）

**Files:**
- Create: `navpay-admin/src/app/api/personal/auth/register/start/route.ts`
- Test: `navpay-admin/tests/unit/api-personal-register-start.test.ts`

**Step 1: Write failing test**

参考已有 API 测试风格（例如 `navpay-admin/tests/unit/api-telegram-bind.test.ts`），写一个最小的 route handler 测试：

```ts
import { describe, expect, test, vi } from "vitest";
import { POST } from "@/app/api/personal/auth/register/start/route";

describe("POST /api/personal/auth/register/start", () => {
  test("returns otpId", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, status: 200, json: async () => ({ ok: true, otpId: "otp_1", expiresAtMs: 1, resendAfterSec: 60, maskedTo: "+91******0000" }) })) as any);

    const req = new Request("http://localhost/api/personal/auth/register/start", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ phoneE164: "+919999999999" }),
    });
    const resp = await POST(req as any);
    const j = await resp.json();
    expect(j.ok).toBe(true);
    expect(j.otpId).toBe("otp_1");
  });
});
```

**Step 2: Run test (expect fail)**

```bash
cd navpay-admin && yarn test tests/unit/api-personal-register-start.test.ts -v
```

**Step 3: Implement route**

`route.ts` 最小实现（zod 校验 + 调用 `sendOtp`）：

```ts
import { NextResponse, type NextRequest } from "next/server";
import { z } from "zod";
import { env } from "@/lib/env";
import { sendOtp } from "@/lib/otp-client";

const schema = z.object({
  phoneE164: z.string().trim().min(6).max(20),
  locale: z.string().trim().min(2).max(10).optional(),
});

export async function POST(req: NextRequest) {
  const body = schema.safeParse(await req.json().catch(() => null));
  if (!body.success) return NextResponse.json({ ok: false, error: "bad_request" }, { status: 400 });

  const out = await sendOtp({
    baseUrl: env.OTP_BASE_URL,
    apiKey: env.OTP_API_KEY,
    phoneE164: body.data.phoneE164,
    purpose: "register",
    locale: body.data.locale ?? "en",
  });
  if (!out.ok) return NextResponse.json({ ok: false, error: out.error }, { status: out.status });

  return NextResponse.json({ ok: true, otpId: out.otpId, expiresAtMs: out.expiresAtMs, resendAfterSec: out.resendAfterSec, maskedTo: out.maskedTo });
}
```

**Step 4: Run test (expect pass)**

```bash
cd navpay-admin && yarn test tests/unit/api-personal-register-start.test.ts -v
```

**Step 5: Commit**

```bash
git add navpay-admin/src/app/api/personal/auth/register/start/route.ts navpay-admin/tests/unit/api-personal-register-start.test.ts
git commit -m "feat(admin): add personal register otp start"
```

### Task 1.4: admin 新增注册 OTP: verify（校验 OTP）

**Files:**
- Create: `navpay-admin/src/app/api/personal/auth/register/verify/route.ts`
- Test: `navpay-admin/tests/unit/api-personal-register-verify.test.ts`

**Steps:**
1) 写失败测试：stub `fetch` 返回 `{ ok:true, verified:true, verificationToken:"v_1" }`，断言 response 包含 `verificationToken`。
2) `yarn test ...` 确认失败。
3) 实现 route：接收 `{ otpId, code }`，调用 `verifyOtp`。
4) 测试通过。
5) commit: `feat(admin): add personal register otp verify`。

### Task 1.5: admin 新增注册 complete（创建支付账户 + 下发 token）

**Files:**
- Create: `navpay-admin/src/app/api/personal/auth/register/complete/route.ts`
- Modify: `navpay-admin/src/lib/payment-person.ts`
- Test: `navpay-admin/tests/unit/api-personal-register-complete.test.ts`

**Design (Phase 1 不改 DB schema):**
- `username` 直接使用 `phoneE164`（例如 `+919999999999`）。
- `name` 可默认：`NavPay User` 或基于手机号后 4 位。
- `password` 使用用户输入。
- 邀请码：可选，用 `inviterCode` 走现有 `createPaymentPersonWithCredentials`。
- `verificationToken`：Phase 1 简化，不存 DB，仅要求 verify 步骤已通过的 token 在短 TTL 内可用（实现方式见 Task 1.6）。

**Step 1: Write failing test**

测试目标：给 `verificationToken` + `phoneE164` + `password`，返回 `{ ok:true, token, person }`。

**Step 2: Implement verification token registry (see next task) and route**

route 伪代码（最终应完整实现）：

```ts
import { NextResponse, type NextRequest } from "next/server";
import { z } from "zod";
import { consumeRegisterVerificationToken } from "@/lib/register-verification";
import { createPaymentPersonWithCredentials } from "@/lib/payment-person";
import { issuePersonalToken } from "@/lib/personal-auth";

const schema = z.object({
  phoneE164: z.string().trim().min(6).max(20),
  password: z.string().min(6).max(200),
  inviterCode: z.string().trim().min(1).max(20).optional(),
  verificationToken: z.string().trim().min(8).max(200),
});

export async function POST(req: NextRequest) {
  const body = schema.safeParse(await req.json().catch(() => null));
  if (!body.success) return NextResponse.json({ ok: false, error: "bad_request" }, { status: 400 });

  const ok = consumeRegisterVerificationToken({
    verificationToken: body.data.verificationToken,
    phoneE164: body.data.phoneE164,
  });
  if (!ok) return NextResponse.json({ ok: false, error: "otp_not_verified" }, { status: 400 });

  await createPaymentPersonWithCredentials({
    name: `User ${body.data.phoneE164.slice(-4)}`,
    username: body.data.phoneE164,
    password: body.data.password,
    inviterCode: body.data.inviterCode,
  });

  const out = await issuePersonalToken({ username: body.data.phoneE164, password: body.data.password });
  if (!out.ok) return NextResponse.json({ ok: false, error: out.error }, { status: 401 });

  return NextResponse.json({ ok: true, token: out.token, person: out.person });
}
```

**Step 3: Run unit test + commit**

Run:
```bash
cd navpay-admin && yarn test tests/unit/api-personal-register-complete.test.ts -v
```

Commit:
```bash
git add navpay-admin/src/app/api/personal/auth/register/complete/route.ts navpay-admin/src/lib/payment-person.ts navpay-admin/tests/unit/api-personal-register-complete.test.ts
git commit -m "feat(admin): add personal register complete"
```

### Task 1.6: 实现“注册验证码 token”短期存储（仅 dev/test 可用）

**Files:**
- Create: `navpay-admin/src/lib/register-verification.ts`
- Test: `navpay-admin/tests/unit/register-verification.test.ts`

**Step 1: Write failing test**

```ts
import { describe, expect, test } from "vitest";
import { rememberRegisterVerificationToken, consumeRegisterVerificationToken } from "@/lib/register-verification";

describe("register verification", () => {
  test("token can be remembered then consumed once", () => {
    rememberRegisterVerificationToken({ token: "v_1", phoneE164: "+919999999999", nowMs: 1000 });
    expect(consumeRegisterVerificationToken({ verificationToken: "v_1", phoneE164: "+919999999999", nowMs: 1001 })).toBe(true);
    expect(consumeRegisterVerificationToken({ verificationToken: "v_1", phoneE164: "+919999999999", nowMs: 1002 })).toBe(false);
  });
});
```

**Step 2: Implement**

```ts
type Row = { phoneE164: string; expiresAtMs: number };
const mem = new Map<string, Row>();
const TTL_MS = 5 * 60_000;

export function rememberRegisterVerificationToken(opts: { token: string; phoneE164: string; nowMs?: number }) {
  const now = opts.nowMs ?? Date.now();
  mem.set(opts.token, { phoneE164: opts.phoneE164, expiresAtMs: now + TTL_MS });
}

export function consumeRegisterVerificationToken(opts: { verificationToken: string; phoneE164: string; nowMs?: number }): boolean {
  const now = opts.nowMs ?? Date.now();
  const r = mem.get(opts.verificationToken);
  if (!r) return false;
  if (now > r.expiresAtMs) {
    mem.delete(opts.verificationToken);
    return false;
  }
  if (r.phoneE164 !== opts.phoneE164) return false;
  mem.delete(opts.verificationToken);
  return true;
}
```

**Step 3: Hook it into Task 1.4**

在 `register/verify` route 里，当 `verified=true` 时调用 `rememberRegisterVerificationToken`。

**Step 4: Run tests + commit**

```bash
cd navpay-admin && yarn test tests/unit/register-verification.test.ts -v
```

```bash
git add navpay-admin/src/lib/register-verification.ts navpay-admin/tests/unit/register-verification.test.ts navpay-admin/src/app/api/personal/auth/register/verify/route.ts
git commit -m "feat(admin): add register verification token registry"
```

### Task 1.7: Android: 注册流程改为调用 admin（不直连 OTP）

**Files:**
- Modify: `navpay-android/app/src/main/java/com/navpay/ApiClient.kt`
- Modify: `navpay-android/app/src/main/java/com/navpay/ui/auth/RegisterFragment.kt`
- Test: `navpay-android/app/src/test/java/...` (新增最小单测，可选)

**Step 1: Update ApiClient**

把现有 `sendRegisterOtp/verifyRegisterOtp` 改为：
- `sendRegisterOtp` -> POST `${BASE_URL}/auth/register/start`
- `verifyRegisterOtp` -> POST `${BASE_URL}/auth/register/verify`
- 新增 `completeRegister(phoneE164, password, inviterCode?, verificationToken)` -> POST `${BASE_URL}/auth/register/complete`

**Step 2: Update RegisterFragment**

流程改为：
1) send OTP
2) verify OTP -> 拿到 `verificationToken`
3) complete register -> 拿到 `token + person` -> `authManager.saveToken(...)` -> 进入主页

**Step 3: Run Android unit tests**

```bash
cd navpay-android && ./gradlew test
```
Expected: PASS.

**Step 4: Commit**

```bash
git add navpay-android/app/src/main/java/com/navpay/ApiClient.kt navpay-android/app/src/main/java/com/navpay/ui/auth/RegisterFragment.kt
git commit -m "feat(android): register via admin personal api"
```

### Task 1.8: 端到端手工联调脚本（curl）

**Files:**
- Create: `docs/manual/personal-register-smoke.md`

**Step 1: Add manual steps**

包含：
1) `tools/dev-up.sh`
2) curl start/verify/complete
3) 登录/获取 `/api/personal/me`

**Step 2: Commit**

```bash
git add docs/manual/personal-register-smoke.md
git commit -m "docs: add personal register smoke test"
```

### Task 1.9: OTP 测试模拟增强：增加 dev peek 接口（仅 dev/test）

**Files:**
- Modify: `navpay-otp/src/routes/otp.ts`
- Test: `navpay-otp/tests/unit/dev-peek.test.ts`
- Modify: `navpay-otp/README.md`

**Goal:** 在测试环境里不依赖 WhatsApp，能够通过 API 取回某手机号最近一次 OTP（用于自动化联调/回归）。\n
安全约束：\n
- 必须携带 `X-Navpay-Otp-Key`\n
- 仅当 `WA_PROVIDER=fake` 或 `NODE_ENV!=\"production\"` 时启用\n

**Step 1: Write failing test**

```ts
import { describe, expect, test } from "vitest";
import { buildServer } from "../../src/server";
import { parseConfig } from "../../src/config";

describe("dev otp peek", async () => {
  test("returns last otp for phone (dev only)", async () => {
    const app = buildServer({ config: parseConfig({ OTP_API_KEY: "k", OTP_SIGNING_SECRET: "x".repeat(32), WA_PROVIDER: "fake" } as any) });
    await app.ready();

    const send = await app.inject({
      method: "POST",
      url: "/v1/otp/send",
      headers: { "x-navpay-otp-key": "k", "content-type": "application/json" },
      payload: { phoneE164: "+919999999999", purpose: "register" }
    });
    expect(send.statusCode).toBe(200);

    const peek = await app.inject({
      method: "POST",
      url: "/v1/dev/otp/peek",
      headers: { "x-navpay-otp-key": "k", "content-type": "application/json" },
      payload: { phoneE164: "+919999999999" }
    });
    const j = peek.json();
    expect(j.ok).toBe(true);
    expect(String(j.code)).toMatch(/^[0-9]{6}$/);

    await app.close();
  });
});
```

**Step 2: Run test to verify it fails**

```bash
cd navpay-otp && yarn test tests/unit/dev-peek.test.ts -v
```
Expected: FAIL (route missing).

**Step 3: Implement route**

在 `navpay-otp/src/routes/otp.ts` 里新增：
- `POST /v1/dev/otp/peek` body `{ phoneE164 }`
- 查询 store 中该手机号最近的 OTP（按 createdAtMs desc）
- 返回 `{ ok:true, otpId, code, expiresAtMs }`

**Step 4: Run test to verify it passes**

```bash
cd navpay-otp && yarn test tests/unit/dev-peek.test.ts -v
```

**Step 5: Update README**

补充一段 dev peek 的 curl 示例与安全说明。

**Step 6: Commit**

```bash
git add navpay-otp/src/routes/otp.ts navpay-otp/tests/unit/dev-peek.test.ts navpay-otp/README.md
git commit -m "feat(otp): add dev otp peek endpoint"
```

---

# WS-2: Mine 模块（余额、余额明细、改密）

### Task 2.1: personal API 增加余额明细列表（payment_person_balance_logs）

**Files:**
- Create: `navpay-admin/src/app/api/personal/mine/balance-logs/route.ts`
- Test: `navpay-admin/tests/unit/api-personal-balance-logs.test.ts`

**Step 1: Write failing test**

- 先在 test DB 创建一个 payment person + token + balance log
- 请求 GET `/api/personal/mine/balance-logs?page=1&pageSize=20`
- 断言 rows 有数据

**Step 2: Implement route**

- `requirePersonalToken`
- 支持分页、按 `createdAtMs desc`
- 返回 `{ ok:true, rows:[{id, delta, balanceAfter, reason, createdAtMs}], page, pageSize, total? }`

**Step 3: Run test + commit**

```bash
cd navpay-admin && yarn test tests/unit/api-personal-balance-logs.test.ts -v
```

```bash
git add navpay-admin/src/app/api/personal/mine/balance-logs/route.ts navpay-admin/tests/unit/api-personal-balance-logs.test.ts
git commit -m "feat(admin): add personal balance logs api"
```

### Task 2.2: Android: ApiClient 增加 getBalanceLogs()

**Files:**
- Modify: `navpay-android/app/src/main/java/com/navpay/ApiClient.kt`

**Step 1: Write failing unit test (optional but recommended)**

Create: `navpay-android/app/src/test/java/com/navpay/BalanceLogsParseTest.kt`

```kotlin
package com.navpay

import org.json.JSONObject
import org.junit.Test
import kotlin.test.assertEquals

class BalanceLogsParseTest {
    @Test fun parseBalanceLogs() {
        val json = JSONObject(\"\"\"{ \"ok\": true, \"rows\": [ {\"id\":\"ppl_1\",\"delta\":\"1.00\",\"balanceAfter\":\"2.00\",\"reason\":\"x\",\"createdAtMs\": 1} ] }\"\"\")
        val rows = ApiClient.parseBalanceLogsForTest(json)
        assertEquals(1, rows.size)
        assertEquals(\"1.00\", rows[0].delta)
    }
}
```

**Step 2: Implement getBalanceLogs + parse helper**

- Add data class in `navpay-android/app/src/main/java/com/navpay/Models.kt`:

```kotlin
data class BalanceLog(
    val id: String,
    val delta: String,
    val balanceAfter: String,
    val reason: String,
    val createdAtMs: Long,
)
```

- Add API call in `navpay-android/app/src/main/java/com/navpay/ApiClient.kt`:

```kotlin
suspend fun getBalanceLogs(page: Int = 1, pageSize: Int = 50): List<BalanceLog> = withContext(Dispatchers.IO) {
    val json = getAuthedJson(\"${BASE_URL}/mine/balance-logs?page=$page&pageSize=$pageSize\")
    if (!json.optBoolean(\"ok\", false)) throw RuntimeException(\"request failed: ${json.optString(\"error\",\"unknown\")}\")
    val arr = json.getJSONArray(\"rows\")
    val out = ArrayList<BalanceLog>()
    for (i in 0 until arr.length()) {
        val o = arr.getJSONObject(i)
        out.add(
            BalanceLog(
                id = o.getString(\"id\"),
                delta = o.getString(\"delta\"),
                balanceAfter = o.getString(\"balanceAfter\"),
                reason = o.getString(\"reason\"),
                createdAtMs = o.getLong(\"createdAtMs\"),
            )
        )
    }
    out
}
```

If you added the unit test above, expose a test-only helper:

```kotlin
companion object {
  fun parseBalanceLogsForTest(json: JSONObject): List<BalanceLog> { /* same parsing */ }
}
```

**Step 3: Run tests**

```bash
cd navpay-android && ./gradlew test
```
Expected: PASS.

**Step 4: Commit**

```bash
git add navpay-android/app/src/main/java/com/navpay/ApiClient.kt navpay-android/app/src/main/java/com/navpay/Models.kt navpay-android/app/src/test/java/com/navpay/BalanceLogsParseTest.kt
git commit -m "feat(android): add balance logs api client"
```

### Task 2.3: Android: PointsDetailsFragment 用真实余额明细替换 fake

**Files:**
- Modify: `navpay-android/app/src/main/java/com/navpay/ui/points/PointsDetailsFragment.kt`

**Step 1: Replace fake data with apiClient.getBalanceLogs()**

最小策略：进入页面时加载第 1 页，失败则 toast/显示空态。

**Step 2: Manual verify**

- 登录后进入 Mine -> Balance details
- 能看到服务端返回的 reason/delta

**Step 3: Commit**

```bash
git add navpay-android/app/src/main/java/com/navpay/ui/points/PointsDetailsFragment.kt
git commit -m "feat(android): wire points details to balance logs api"
```

### Task 2.4: personal API 增加“改密”接口

**Files:**
- Create: `navpay-admin/src/app/api/personal/auth/password/reset/route.ts`
- Modify: `navpay-admin/src/lib/password.ts` (若需要复用强度校验)
- Test: `navpay-admin/tests/unit/api-personal-password-reset.test.ts`

**Design:**
- 输入：`{ oldPassword, newPassword }`
- 鉴权：`requirePersonalToken`，然后找到 credentials 并校验 old password
- 更新：`payment_person_credentials.password_hash + password_updated_at_ms`

**Steps:**
1) 写失败测试：old 密码不对 -> 401；new 弱密码 -> 400；成功 -> ok。
2) 实现 route。
3) 跑 test。
4) commit。

### Task 2.5: Android: ApiClient 增加 resetPassword()

**Files:**
- Modify: `navpay-android/app/src/main/java/com/navpay/ApiClient.kt`

**Step 1: Implement API call**

```kotlin
suspend fun resetPassword(oldPassword: String, newPassword: String): Boolean = withContext(Dispatchers.IO) {
    val payload = JSONObject().apply {
        put(\"oldPassword\", oldPassword)
        put(\"newPassword\", newPassword)
    }
    val json = postAuthedJson(\"${BASE_URL}/auth/password/reset\", payload)
    json.optBoolean(\"ok\", false)
}
```

**Step 2: Commit**

```bash
git add navpay-android/app/src/main/java/com/navpay/ApiClient.kt
git commit -m "feat(android): add reset password api client"
```

### Task 2.6: Android Mine 页面联调“重置密码”

**Files:**
- Modify: `navpay-android/app/src/main/java/com/navpay/ui/mine/MineFragment.kt`

**Steps:**
1) 绑定点击事件 -> 弹出 old/new 输入框。\n
2) 调用 `apiClient.resetPassword`，成功提示并引导重新登录。\n
3) 手工验证：改密后退出再用新密码登录。\n
4) commit。

---

# WS-3: 银行 App 下载管理（admin 管理 + personal API + Android 对接）

### Task 3.1: personal API 暴露 payment apps（只读）

**Files:**
- Create: `navpay-admin/src/app/api/personal/payment-apps/route.ts`
- Test: `navpay-admin/tests/unit/api-personal-payment-apps.test.ts`

**Steps:**
1) 写失败测试：插入 2 条 `payment_apps`，GET 返回 enabled 列表。
2) 实现 route：`requirePersonalToken` + 返回 `{name, packageName, versionCode, downloadUrl, promoted}`。
3) 测试通过。
4) commit。

### Task 3.2: Android PaymentAppsFragment 对接 personal/payment-apps

**Files:**
- Modify: `navpay-android/app/src/main/java/com/navpay/ApiClient.kt`
- Modify: `navpay-android/app/src/main/java/com/navpay/ui/paymentapps/PaymentAppsFragment.kt`
- Modify: `navpay-android/app/src/main/java/com/navpay/ui/paymentapps/PaymentAppsAdapter.kt`

**Steps:**
1) 增加 `getPaymentApps()`。
2) Adapter download 按钮：打开 `downloadUrl`（浏览器 intent）。
3) commit。

### Task 3.3: admin 管理台完善 payment apps 字段校验/提示（若缺）

**Files:**
- Modify: `navpay-admin/src/components/payment-apps-client.tsx`
- Test: `navpay-admin/tests/unit/...` (可选)

---

# WS-4: 新手福利/活动（admin 活动管理 + personal API + Android 对接）

Phase 1 建议：先用 `system_configs` 存 1 个活动 JSON，避免 migration 冲突；Phase 2 再落表。

### Task 4.1: system_configs 增加 newbie rewards JSON key

**Files:**
- Modify: `navpay-admin/src/lib/system-config.ts`
- Test: `navpay-admin/tests/unit/system-config-newbie.test.ts`

**Steps:**
1) 写失败测试：get json default。
2) 实现 `getSystemConfigJson({ key, defaultValue })` helper。
3) commit。

### Task 4.2: personal API: GET /rewards/newbie

**Files:**
- Create: `navpay-admin/src/app/api/personal/rewards/newbie/route.ts`
- Test: `navpay-admin/tests/unit/api-personal-newbie-rewards.test.ts`

**Steps:**
1) 写失败测试：返回默认活动列表。
2) 实现：从 `system_configs` 读取 key `rewards.newbie.v1`。
3) commit。

### Task 4.3: Android NewbieRewardsFragment 对接

**Files:**
- Modify: `navpay-android/app/src/main/java/com/navpay/ApiClient.kt`
- Modify: `navpay-android/app/src/main/java/com/navpay/ui/rewards/NewbieRewardsFragment.kt`

---

# WS-5: 三级返利/推荐系统（比例配置读取 + personal API）

admin 已存在：`channel-commission.ts` 读取 `channel.rebate_l*_bps`。

### Task 5.1: personal API: GET /referral/summary

**Files:**
- Create: `navpay-admin/src/app/api/personal/referral/summary/route.ts`
- Test: `navpay-admin/tests/unit/api-personal-referral-summary.test.ts`

**Response 建议:**
- `inviteCode`
- `inviter`（上级）
- `downlineCounts`（直推/二级/三级）
- `rebateBps`（l1/l2/l3）
- `todayRebates`（可复用 `getTodayRebateStatsByPersonIds`）

### Task 5.2: personal API: GET /referral/downlines

**Files:**
- Create: `navpay-admin/src/app/api/personal/referral/downlines/route.ts`
- Test: `navpay-admin/tests/unit/api-personal-referral-downlines.test.ts`

---

# WS-6: 高并发抢单/刷新压力治理

目标：1000+ 并发 GET available + claim，保证：
- 抢单只成功一次（其他返回 409）
- 不产生多余 report log
- available 列表不做每次 sweep + count(*)

### Task 6.1: 修复 claim 并发：检查 update 影响行数

**Files:**
- Modify: `navpay-admin/src/app/api/personal/payout/orders/[orderId]/claim/route.ts`
- Test: `navpay-admin/tests/unit/api-personal-claim-concurrency.test.ts`

**Test 思路:**
- 插入 1 笔 APPROVED order
- 并发调用 claim 两次（Promise.all）
- 断言：一个 ok=true，一个 error=conflict (409)

**Implementation:**
- Drizzle update 后拿到结果（如无法直接拿 rowCount，可改为：先 update 再 select 检查 lockedPaymentPersonId 是否为当前人，若不是则 409）
- 只有 claim 成功才写 `paymentPersonReportLogs`

### Task 6.2: available 列表：移除每次 sweepExpiredPayoutLocks

**Files:**
- Modify: `navpay-admin/src/app/api/personal/payout/orders/available/route.ts`
- Modify: `navpay-admin/src/lib/payout-lock.ts`
- Test: `navpay-admin/tests/unit/payout-lock-sweep.test.ts`

**Implementation:**
- `sweepExpiredPayoutLocks` 改为批量 update（单 SQL），避免 for-loop 多次写
- available route 不主动 sweep；改为由定时任务/worker 触发（见 Task 6.4）

### Task 6.3: available 列表：加轻量缓存/限流

**Files:**
- Modify: `navpay-admin/src/app/api/personal/payout/orders/available/route.ts`
- Create: `navpay-admin/src/lib/simple-cache.ts`
- Test: `navpay-admin/tests/unit/simple-cache.test.ts`

**Implementation:**
- `simple-cache`：Map + TTL（比如 1s），key=`available:page:pageSize`
- 同一个 key 在 TTL 内直接返回缓存 JSON（避免 count + select 热点）

### Task 6.4: 增加后台 sweep worker（仅 dev/local）

**Files:**
- Create: `navpay-admin/scripts/payout-sweep-worker.ts`
- Modify: `navpay-admin/package.json`

**Implementation:**
- 每 10s 跑一次 `sweepExpiredPayoutLocks(Date.now())`
- script: `payout:sweep-worker`

### Task 6.5: 加压测脚本（k6 或 autocannon）

**Files:**
- Create: `tools/loadtest-available.sh`
- Create: `tools/loadtest-claim.sh`

---

# WS-7: Landing 下载页管理化（manifest + 管理页）

目标：landing 不硬编码下载 URL；从 admin 获取 manifest；admin 提供管理界面编辑。

### Task 7.1: admin 新增 public manifest API

**Files:**
- Create: `navpay-admin/src/app/api/public/downloads/manifest/route.ts`
- Test: `navpay-admin/tests/unit/api-public-downloads-manifest.test.ts`

**Phase 1 (不加表):**
- manifest 存在 `system_configs` key：`landing.downloads.manifest.v1` (JSON)

### Task 7.2: admin 管理页：编辑 manifest（最小表单）

**Files:**
- Create: `navpay-admin/src/app/admin/landing/downloads/page.tsx`
- Create: `navpay-admin/src/app/api/admin/landing/downloads/manifest/route.ts`
- Modify: `navpay-admin/src/components/admin-shell.tsx`
- Test: `navpay-admin/tests/e2e/...` (可选)

### Task 7.3: landing 读取 public manifest

**Files:**
- Modify: `navpay-landing/src/app/page.tsx`
- Create: `navpay-landing/src/lib/manifest.ts`
- Test: `navpay-landing/tests/unit/manifest.test.ts`

---

# WS-8: TG Bot 绑定闭环验证

（该链路大体已实现，重点是补齐 smoke test 与文档）

### Task 8.1: 增加 bot -> admin bind 的集成 smoke 文档

**Files:**
- Create: `docs/manual/tgbot-bind-smoke.md`

### Task 8.2: 为 integrations/telegram/bind 增加错误码契约注释

**Files:**
- Modify: `navpay-admin/src/app/api/integrations/telegram/bind/route.ts`
- Test: `navpay-admin/tests/unit/api-telegram-bind.test.ts` (补断言)

---

## 交付验收清单 (Definition of Done)

- 注册登录：Android 通过 admin 注册并拿到 token，`/me` 返回余额
- OTP：测试环境可用（至少 fake provider stdout；最好有 dev peek 方案）
- 心跳：Android 每 5s 成功调用 `/device/heartbeat`
- 银行 App 下载：admin 可配置；Android 可拉取并跳转下载
- Mine：余额明细可拉取；改密可用
- 返利：admin 配置比例；personal API 可读 summary/downlines
- 高并发：claim 并发返回 409；available 刷新可承受 1000 并发（本地压测脚本可复现）
- Landing：manifest 可管可读；落地页下载链接来自 manifest
- TG bot：bind 可写入 DB，admin 可审核

---

## 执行交接 (Multi-agent)

建议的并行启动顺序：
1) WS-0（契约/脚本）
2) WS-1（注册/OTP）与 WS-6（并发修复）并行
3) WS-2/3/7/8 并行
4) WS-4/5 最后（业务字段容易变）
