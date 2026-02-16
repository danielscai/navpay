# Navpay WhatsApp OTP (navpay-otp) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a standalone `navpay-otp` service that sends and verifies OTP codes via WhatsApp, and wire `navpay-android` (Android) registration flow to call it via HTTP API.

**Architecture:** `navpay-android` calls `navpay-otp` over HTTP (`/v1/otp/send` then `/v1/otp/verify`). `navpay-otp` generates a 6-digit OTP, stores only a hash + expiry + attempt counters, and sends the OTP via a pluggable WhatsApp provider (dev fake provider; prod Meta WhatsApp Cloud API). Rate limiting is enforced per-IP and per-phone to reduce abuse.

**Tech Stack:** Node.js + TypeScript, Fastify (HTTP), Zod (validation), Vitest (tests), SQLite (persistence; via `better-sqlite3`), WhatsApp Cloud API (provider implementation), OkHttp (Android client, already used).

---

## Decisions (Make Once, Early)

1. **WhatsApp sending provider**
   - MVP: `FakeWhatsappProvider` (logs OTP to server logs; used locally/tests).
   - Production: Meta WhatsApp Cloud API (requires `WA_ACCESS_TOKEN`, `WA_PHONE_NUMBER_ID`, approved template).
2. **Who calls navpay-otp**
   - Current requirement: Android client calls `navpay-otp` directly.
   - Note (security): This is inherently abusable. Even with an API key in the app, it can be extracted. Rate limiting and per-phone quotas are mandatory. A stronger production architecture is: app -> your backend -> `navpay-otp`.

---

## API Contract (navpay-otp)

### POST `/healthz`
Response: `200 { "ok": true }`

### POST `/v1/otp/send`
Request:
```json
{
  "phoneE164": "+14155552671",
  "purpose": "register",
  "locale": "en"
}
```
Response:
```json
{
  "ok": true,
  "otpId": "otp_01HT...",
  "expiresAtMs": 1700000000000,
  "resendAfterSec": 60,
  "maskedTo": "+1******2671"
}
```

### POST `/v1/otp/verify`
Request:
```json
{
  "otpId": "otp_01HT...",
  "code": "123456"
}
```
Response:
```json
{
  "ok": true,
  "verified": true,
  "verificationToken": "vfy_01HT..."
}
```

Error shape (all non-2xx):
```json
{ "ok": false, "error": "bad_request" }
```

---

## Data Model (SQLite)

Table: `otp_requests`
- `id` (TEXT, PK)
- `phone_e164` (TEXT, indexed)
- `purpose` (TEXT)
- `code_hash` (TEXT) - HMAC/SHA-256 of (salt + code) with server secret
- `salt` (TEXT)
- `created_at_ms` (INTEGER)
- `expires_at_ms` (INTEGER)
- `verified_at_ms` (INTEGER, nullable)
- `attempts` (INTEGER)
- `max_attempts` (INTEGER)
- `last_sent_at_ms` (INTEGER)

---

## Task 1: Create `navpay-otp` Git Remote (Local Bare Repo)

**Files:**
- Create: `navpay-otp/` (new project directory)

**Step 1: Create bare remote**

Run:
```bash
mkdir -p ~/git-remote
git init --bare ~/git-remote/navpay-otp
```
Expected: `Initialized empty Git repository .../git-remote/navpay-otp/`

**Step 2: Create project directory + init git**

Run:
```bash
mkdir -p navpay-otp
cd navpay-otp
git init
git remote add origin ~/git-remote/navpay-otp
git remote -v
```
Expected: `origin  ~/git-remote/navpay-otp (fetch)` and `(push)`

**Step 3: Commit empty scaffolding**

Run:
```bash
touch README.md
git add README.md
git commit -m "chore: init navpay-otp repo"
git push -u origin main || git push -u origin master
```
Expected: first push succeeds (branch name depends on git default)

---

## Task 2: Bootstrap Node/TS Service Skeleton (Fastify + Vitest)

**Files:**
- Create: `navpay-otp/package.json`
- Create: `navpay-otp/tsconfig.json`
- Create: `navpay-otp/vitest.config.ts`
- Create: `navpay-otp/src/server.ts`
- Create: `navpay-otp/src/index.ts`
- Create: `navpay-otp/tests/health.test.ts`

**Step 1: Write failing test (health endpoint)**

`navpay-otp/tests/health.test.ts`
```ts
import { describe, expect, it } from "vitest";
import { buildServer } from "../src/server";

describe("healthz", () => {
  it("returns ok", async () => {
    const app = buildServer();
    const res = await app.inject({ method: "POST", url: "/healthz" });
    expect(res.statusCode).toBe(200);
    expect(res.json()).toEqual({ ok: true });
  });
});
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd navpay-otp
yarn test
```
Expected: FAIL (`buildServer` missing)

**Step 3: Minimal implementation**

`navpay-otp/src/server.ts`
```ts
import Fastify from "fastify";

export function buildServer() {
  const app = Fastify({ logger: true });
  app.post("/healthz", async () => ({ ok: true }));
  return app;
}
```

`navpay-otp/src/index.ts`
```ts
import { buildServer } from "./server";

const port = Number(process.env.PORT || 19090);
const host = process.env.HOST || "0.0.0.0";

buildServer().listen({ port, host });
```

**Step 4: Re-run test**

Run:
```bash
yarn test
```
Expected: PASS

**Step 5: Commit**

Run:
```bash
git add package.json tsconfig.json vitest.config.ts src/server.ts src/index.ts tests/health.test.ts
git commit -m "feat(navpay-otp): bootstrap fastify service with healthz"
```

---

## Task 3: Add Config + Env Template + Typed Validation (Zod)

**Files:**
- Create: `navpay-otp/.env.example`
- Create: `navpay-otp/src/config.ts`
- Test: `navpay-otp/tests/config.test.ts`

**Step 1: Write failing test**

`navpay-otp/tests/config.test.ts`
```ts
import { describe, expect, it } from "vitest";
import { parseConfig } from "../src/config";

describe("config", () => {
  it("requires OTP_SIGNING_SECRET", () => {
    expect(() => parseConfig({})).toThrow(/OTP_SIGNING_SECRET/);
  });
});
```

**Step 2: Run test to verify it fails**

Run: `yarn test`
Expected: FAIL (`parseConfig` missing)

**Step 3: Minimal implementation**

`navpay-otp/src/config.ts`
```ts
import { z } from "zod";

const ConfigSchema = z.object({
  PORT: z.coerce.number().default(19090),
  HOST: z.string().default("0.0.0.0"),
  OTP_SIGNING_SECRET: z.string().min(16),
  OTP_TTL_SEC: z.coerce.number().default(300),
  OTP_MAX_ATTEMPTS: z.coerce.number().default(5),
  SQLITE_PATH: z.string().default("data/navpay-otp.sqlite"),
  WA_PROVIDER: z.enum(["fake", "meta_cloud"]).default("fake"),
  WA_ACCESS_TOKEN: z.string().optional(),
  WA_PHONE_NUMBER_ID: z.string().optional(),
  WA_TEMPLATE_NAME: z.string().optional(),
  WA_TEMPLATE_LANG: z.string().default("en_US"),
});

export type Config = z.infer<typeof ConfigSchema>;

export function parseConfig(env: Record<string, unknown>): Config {
  return ConfigSchema.parse(env);
}
```

`.env.example`
```bash
PORT=19090
HOST=0.0.0.0
OTP_SIGNING_SECRET=change-me-please-change-me
OTP_TTL_SEC=300
OTP_MAX_ATTEMPTS=5
SQLITE_PATH=data/navpay-otp.sqlite

# fake | meta_cloud
WA_PROVIDER=fake

# Meta WhatsApp Cloud API (when WA_PROVIDER=meta_cloud)
WA_ACCESS_TOKEN=
WA_PHONE_NUMBER_ID=
WA_TEMPLATE_NAME=
WA_TEMPLATE_LANG=en_US
```

**Step 4: Re-run test**

Run: `yarn test`
Expected: PASS

**Step 5: Commit**

Run:
```bash
git add .env.example src/config.ts tests/config.test.ts
git commit -m "feat(navpay-otp): add validated config and env template"
```

---

## Task 4: OTP Core (Generate, Hash, Verify) With Unit Tests

**Files:**
- Create: `navpay-otp/src/otp/otp-core.ts`
- Test: `navpay-otp/tests/otp-core.test.ts`

**Step 1: Write failing test**

`navpay-otp/tests/otp-core.test.ts`
```ts
import { describe, expect, it } from "vitest";
import { hashOtp, verifyOtp } from "../src/otp/otp-core";

describe("otp-core", () => {
  it("verifies correct code and rejects wrong code", () => {
    const secret = "0123456789abcdef0123456789abcdef";
    const salt = "salt1";
    const good = "123456";
    const bad = "000000";
    const h = hashOtp({ secret, salt, code: good });
    expect(verifyOtp({ secret, salt, code: good, codeHash: h })).toBe(true);
    expect(verifyOtp({ secret, salt, code: bad, codeHash: h })).toBe(false);
  });
});
```

**Step 2: Run test (should fail)**

Run: `yarn test`
Expected: FAIL (missing exports)

**Step 3: Minimal implementation**

`navpay-otp/src/otp/otp-core.ts`
```ts
import { createHmac, randomBytes } from "node:crypto";

export function genOtpCode(): string {
  const n = Math.floor(Math.random() * 1_000_000);
  return String(n).padStart(6, "0");
}

export function genSalt(): string {
  return randomBytes(16).toString("hex");
}

export function hashOtp(opts: { secret: string; salt: string; code: string }): string {
  return createHmac("sha256", opts.secret).update(`${opts.salt}:${opts.code}`).digest("hex");
}

export function verifyOtp(opts: { secret: string; salt: string; code: string; codeHash: string }): boolean {
  return hashOtp({ secret: opts.secret, salt: opts.salt, code: opts.code }) === opts.codeHash;
}
```

**Step 4: Re-run tests**

Run: `yarn test`
Expected: PASS

**Step 5: Commit**

Run:
```bash
git add src/otp/otp-core.ts tests/otp-core.test.ts
git commit -m "feat(navpay-otp): implement otp hashing and verification"
```

---

## Task 5: SQLite Store (Persist OTP Requests) With Integration Tests

**Files:**
- Create: `navpay-otp/src/db/migrate.ts`
- Create: `navpay-otp/src/db/store.ts`
- Test: `navpay-otp/tests/store.test.ts`

**Step 1: Write failing test**

`navpay-otp/tests/store.test.ts`
```ts
import { describe, expect, it } from "vitest";
import { createStore } from "../src/db/store";

describe("store", () => {
  it("can insert and read otp request", () => {
    const store = createStore(":memory:");
    const row = store.insertOtp({
      id: "otp_test",
      phoneE164: "+14155552671",
      purpose: "register",
      codeHash: "hash",
      salt: "salt",
      createdAtMs: 1,
      expiresAtMs: 2,
      maxAttempts: 5,
    });
    expect(row.id).toBe("otp_test");
    const loaded = store.getOtpById("otp_test");
    expect(loaded?.phoneE164).toBe("+14155552671");
  });
});
```

**Step 2: Run test (should fail)**

Run: `yarn test`
Expected: FAIL (`createStore` missing)

**Step 3: Minimal implementation**

Create the table on init and implement `insertOtp/getOtpById/incrementAttempts/markVerified/updateLastSentAt`.

**Step 4: Re-run tests**

Run: `yarn test`
Expected: PASS

**Step 5: Commit**

Run:
```bash
git add src/db/migrate.ts src/db/store.ts tests/store.test.ts
git commit -m "feat(navpay-otp): add sqlite store for otp requests"
```

---

## Task 6: WhatsApp Provider Abstraction + Fake Provider

**Files:**
- Create: `navpay-otp/src/whatsapp/provider.ts`
- Create: `navpay-otp/src/whatsapp/fake-provider.ts`
- Test: `navpay-otp/tests/fake-provider.test.ts`

**Step 1: Write failing test**

`navpay-otp/tests/fake-provider.test.ts`
```ts
import { describe, expect, it } from "vitest";
import { FakeWhatsappProvider } from "../src/whatsapp/fake-provider";

describe("FakeWhatsappProvider", () => {
  it("returns a message id", async () => {
    const p = new FakeWhatsappProvider();
    const id = await p.sendText({ to: "+14155552671", text: "otp 123456" });
    expect(id).toMatch(/^fake_/);
  });
});
```

**Step 2: Run test (should fail)**

Run: `yarn test`
Expected: FAIL

**Step 3: Minimal implementation**

`navpay-otp/src/whatsapp/provider.ts`
```ts
export interface WhatsappProvider {
  sendText(input: { to: string; text: string }): Promise<string>;
}
```

`navpay-otp/src/whatsapp/fake-provider.ts`
```ts
import { WhatsappProvider } from "./provider";

export class FakeWhatsappProvider implements WhatsappProvider {
  async sendText(input: { to: string; text: string }): Promise<string> {
    // Local dev behavior: log OTP to server logs
    // eslint-disable-next-line no-console
    console.log(`[FAKE_WHATSAPP] to=${input.to} text=${input.text}`);
    return `fake_${Date.now()}`;
  }
}
```

**Step 4: Re-run tests**

Run: `yarn test`
Expected: PASS

**Step 5: Commit**

Run:
```bash
git add src/whatsapp/provider.ts src/whatsapp/fake-provider.ts tests/fake-provider.test.ts
git commit -m "feat(navpay-otp): add whatsapp provider abstraction and fake provider"
```

---

## Task 7: Meta WhatsApp Cloud API Provider (Optional, But Planned)

**Files:**
- Create: `navpay-otp/src/whatsapp/meta-cloud-provider.ts`
- Test: `navpay-otp/tests/meta-cloud-provider.test.ts`

**Step 1: Write failing test**

Use dependency injection for `fetch` so tests can stub it (no real network).

**Step 2: Implement minimal provider**

Send a template message that includes the OTP in a variable (your template must be approved in Meta).

**Step 3: Commit**

`git commit -m "feat(navpay-otp): implement meta cloud whatsapp provider"`

---

## Task 8: OTP Send Endpoint (Validation + Rate Limits + Store + Provider)

**Files:**
- Modify: `navpay-otp/src/server.ts`
- Create: `navpay-otp/src/routes/otp.ts`
- Create: `navpay-otp/src/phone/normalize.ts`
- Test: `navpay-otp/tests/otp-send.test.ts`

**Step 1: Write failing integration test**

`navpay-otp/tests/otp-send.test.ts`
```ts
import { describe, expect, it } from "vitest";
import { buildServer } from "../src/server";

describe("POST /v1/otp/send", () => {
  it("returns otpId and expiry", async () => {
    const app = buildServer();
    const res = await app.inject({
      method: "POST",
      url: "/v1/otp/send",
      payload: { phoneE164: "+14155552671", purpose: "register", locale: "en" },
    });
    expect(res.statusCode).toBe(200);
    const json = res.json();
    expect(json.ok).toBe(true);
    expect(json.otpId).toMatch(/^otp_/);
    expect(typeof json.expiresAtMs).toBe("number");
  });
});
```

**Step 2: Run test (should fail)**

Run: `yarn test`
Expected: FAIL (route missing)

**Step 3: Minimal implementation**

Implement:
- validate inputs (Zod)
- normalize phone to E.164 (reject invalid)
- generate `otpId`, `salt`, `code`, `codeHash`, store row
- send WhatsApp message via provider
- return response with `maskedTo`, `expiresAtMs`, `resendAfterSec`

**Step 4: Re-run tests**

Run: `yarn test`
Expected: PASS

**Step 5: Commit**

Run:
```bash
git add src/routes/otp.ts src/phone/normalize.ts src/server.ts tests/otp-send.test.ts
git commit -m "feat(navpay-otp): add otp send endpoint"
```

---

## Task 9: OTP Verify Endpoint (Attempt Limits + Expiry + Verification Token)

**Files:**
- Modify: `navpay-otp/src/routes/otp.ts`
- Test: `navpay-otp/tests/otp-verify.test.ts`

**Step 1: Write failing test**

Test: wrong code increments attempts; correct code verifies; expired code rejects.

**Step 2: Implement minimal behavior**

Rules:
- If expired: `410 { ok:false, error:"otp_expired" }`
- If too many attempts: `429 { ok:false, error:"too_many_attempts" }`
- If ok: mark verified + return `verificationToken` (random id stored in db row)

**Step 3: Commit**

`git commit -m "feat(navpay-otp): add otp verify endpoint with attempt limits"`

---

## Task 10: Abuse Controls (Per-IP + Per-Phone Rate Limits)

**Files:**
- Modify: `navpay-otp/src/server.ts`
- Modify: `navpay-otp/src/routes/otp.ts`
- Test: `navpay-otp/tests/rate-limit.test.ts`

**Step 1: Write failing test**

Call `/v1/otp/send` repeatedly and expect `429` after threshold.

**Step 2: Implement**

Use Fastify plugin rate limiting (per-IP) and an additional store-based per-phone window:
- do not allow re-send within `resendAfterSec` (default 60s)
- daily cap per phone (configurable; start with 10/day)

**Step 3: Commit**

`git commit -m "feat(navpay-otp): add rate limiting for otp send"`

---

## Task 11: Developer Experience (README + Runbook)

**Files:**
- Modify: `navpay-otp/README.md`

**Step 1: Add README content**

Include:
- prerequisites (Node, yarn)
- `cp .env.example .env`
- `yarn dev` (port 19090)
- curl examples for send/verify
- how to switch provider to `meta_cloud`

**Step 2: Commit**

`git commit -m "docs(navpay-otp): add local runbook and api examples"`

---

## Task 12: Android Integration (navpay-android Register Uses Real OTP API)

**Files:**
- Modify: `navpay-android/app/src/main/java/com/navpay/ApiClient.kt`
- Modify: `navpay-android/app/src/main/java/com/navpay/ui/auth/RegisterFragment.kt`
- Modify: `navpay-android/app/src/main/res/layout/dialog_otp.xml`
- Test: `navpay-android/app/src/test/java/com/phonepe/checksumclient/ApiClientOtpUrlTest.kt`

**Step 1: Write failing unit test for URL/constants**

`navpay-android/app/src/test/java/com/phonepe/checksumclient/ApiClientOtpUrlTest.kt`
```kotlin
package com.navpay

import org.junit.Assert.assertTrue
import org.junit.Test

class ApiClientOtpUrlTest {
    @Test
    fun otpBaseUrlLooksLikeLocalDev() {
        assertTrue(ApiClient.OTP_BASE_URL.startsWith("http://10.0.2.2:"))
    }
}
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd navpay-android
./gradlew test
```
Expected: FAIL (`OTP_BASE_URL` missing)

**Step 3: Minimal implementation in ApiClient**

Add constants + two methods:
- `sendRegisterOtp(phoneE164: String): SendOtpResult`
- `verifyRegisterOtp(otpId: String, code: String): VerifyOtpResult`

Use OkHttp JSON calls (same style as existing `login()`).

**Step 4: Update `dialog_otp.xml` to accept input**

Add an `EditText` (numeric, maxLength=6) that fills the OTP boxes, and a `Resend` button (disabled until `resendAfterSec`).

**Step 5: Update `RegisterFragment.kt`**

Behavior:
1. On register button: call `sendRegisterOtp()` with phone from `phoneInput` (ensure E.164 formatting rule is applied consistently)
2. Show dialog: subtitle uses `maskedTo`
3. On confirm: call `verifyRegisterOtp()`; if ok navigate; if error show message and keep dialog open

**Step 6: Re-run tests**

Run:
```bash
cd navpay-android
./gradlew test
```
Expected: PASS

**Step 7: Commit**

Run:
```bash
git add navpay-android/app/src/main/java/com/navpay/ApiClient.kt navpay-android/app/src/main/java/com/navpay/ui/auth/RegisterFragment.kt navpay-android/app/src/main/res/layout/dialog_otp.xml navpay-android/app/src/test/java/com/phonepe/checksumclient/ApiClientOtpUrlTest.kt
git commit -m "feat(navpay-android): call navpay-otp api for whatsapp otp during register"
```

---

## Task 13: Manual End-to-End Verification (Local)

**Step 1: Start navpay-otp**

Run:
```bash
cd navpay-otp
cp .env.example .env
yarn dev
```
Expected: server listening on `0.0.0.0:19090`

**Step 2: Start navpay-admin (if needed) + Android emulator**

Run:
```bash
cd navpay-admin
yarn dev
```
Then:
```bash
cd navpay-android
yarn emu1
yarn i1
```

**Step 3: Register flow**
- Enter phone, password, invite code.
- Tap Register.
- Check `navpay-otp` logs for `[FAKE_WHATSAPP] ... otp ...`
- Enter OTP in dialog, confirm.
Expected: navigation to main tabs.

---

## Notes / Follow-ups (Not In MVP Unless Requested)

- Add OpenAPI/Swagger UI for `navpay-otp`.
- Add signed request auth (HMAC) and strict replay protection (still not a full solution for public mobile clients).
- Add support for OTP purpose scoping (`login`, `reset_password`).
- Add WhatsApp template management and locale mapping.
- Add observability: structured logs + request IDs.

