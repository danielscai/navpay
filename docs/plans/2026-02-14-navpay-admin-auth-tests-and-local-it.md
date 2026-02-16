# NavPay Admin Auth Tests + Local Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 `navpay-admin/.wt/ws1-auth` worktree 合并最新 `main` 后，补齐“personal/mobile auth + register/OTP 代理化”相关单元测试，并新增可在本机跑的集成测试脚本。

**Architecture:** 单测用 Vitest 直接 import route handlers / lib，并通过 sqlite 测试库做隔离；集成测试用 Node 脚本在本机启动 `navpay-otp` + `navpay-admin`（独立临时 DB + 固定 OTP code），通过 HTTP 走完整注册链路。

**Tech Stack:** Next.js route handlers, TypeScript, Zod, Drizzle + SQLite, Vitest, Node 20+ (`fetch`, `child_process`).

---

## Constraints / Guardrails

- 只改 `navpay-admin`（以及 monorepo 根目录下的本计划文档）；不要改 `payout/locks/landing/rewards/referral` 相关文件。
- 单测仍然只跑 `tests/unit/**/*.test.ts`（保持 `vitest.config.ts` include 不变）。
- 集成测试脚本默认不进 `yarn test`，用单独命令跑，避免 CI/本机慢。

## Preflight

- Worktree: `cd navpay-admin/.wt/ws1-auth`
- Baseline: `yarn test`

---

### Task 0: 合并最新 main 到 worktree（merge，不是 rebase）

**Files:**
- None (git operation)

**Step 1: Fetch**

Run:
```bash
cd navpay-admin/.wt/ws1-auth
git fetch origin
```

**Step 2: Merge**

Run:
```bash
git merge origin/main
```

Expected: fast-forward 或产生一个 merge commit。

**Step 3: If conflicts**

Run:
```bash
git status
```

Resolve conflicts (only in allowed files), then:
```bash
git add -A
git commit
```

**Step 4: Verify**

Run:
```bash
yarn test
```
Expected: PASS.

---

# Unit Tests (Auth)

> Coverage target: personal auth routes + register start/verify/complete + otp-client + token registry + /me + logout/login happy + main failure modes.

### Task 1: otp-client 错误处理与请求形状单测补齐

**Files:**
- Modify: `navpay-admin/src/lib/otp-client.ts`
- Test: `navpay-admin/tests/unit/otp-client.test.ts`

**Step 1: Write failing tests**

Add tests for:
- baseUrl 末尾 `/` 能正常拼接
- 非 2xx：返回 `{ ok:false, status:<http status>, error:<string> }`
- `json()` 解析失败时：返回 `otp_*_failed`
- `fetch` 抛异常（network）：返回 `{ ok:false, status:0, error:"network_error" }`

**Step 2: Run test to verify it fails**

Run:
```bash
cd navpay-admin/.wt/ws1-auth
yarn test tests/unit/otp-client.test.ts -v
```
Expected: FAIL.

**Step 3: Minimal implementation**

Update `otp-client.ts`:
- `fetch` 包一层 `try/catch`
- JSON parse 失败也要返回稳定 error

**Step 4: Run test to verify it passes**

Run:
```bash
yarn test tests/unit/otp-client.test.ts -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-admin/src/lib/otp-client.ts navpay-admin/tests/unit/otp-client.test.ts
git commit -m "test(admin): harden otp client error handling"
```

---

### Task 2: register-verification registry 行为单测补齐（TTL/phone mismatch/prod disabled）

**Files:**
- Modify: `navpay-admin/src/lib/register-verification.ts`
- Test: `navpay-admin/tests/unit/register-verification.test.ts`

**Step 1: Write failing tests**

Add tests for:
- TTL 过期后 consume 返回 false
- phoneE164 不匹配时 consume 返回 false 且 token 仍不可重复使用（建议仍保留 token，或明确删除策略；测试锁定行为）
- `NODE_ENV=production` 时 remember/consume 都禁用（consume 一律 false）

**Step 2: Run test to verify it fails**

Run:
```bash
cd navpay-admin/.wt/ws1-auth
yarn test tests/unit/register-verification.test.ts -v
```
Expected: FAIL.

**Step 3: Minimal implementation**

实现方式建议：
- 给 `rememberRegisterVerificationToken/consumeRegisterVerificationToken` 增加可注入开关：`enabled?: boolean` 或 `nodeEnv?: string`
- 测试中不要污染全局 `process.env.NODE_ENV`（或用 `vi.resetModules()` + 临时设置后再恢复）

**Step 4: Run test to verify it passes**

Run:
```bash
yarn test tests/unit/register-verification.test.ts -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-admin/src/lib/register-verification.ts navpay-admin/tests/unit/register-verification.test.ts
git commit -m "test(admin): extend register verification registry coverage"
```

---

### Task 3: 注册 start route 单测补齐（bad_request / forward locale / otp error pass-through）

**Files:**
- Modify: `navpay-admin/src/app/api/personal/auth/register/start/route.ts`
- Test: `navpay-admin/tests/unit/api-personal-register-start.test.ts`

**Step 1: Write failing tests**

Add tests for:
- body 缺字段 => `400 bad_request`
- 传 `locale` 时，确认 `fetch` body 包含 locale
- otp 返回 `409 resend_too_soon` => admin 返回 `409`，并透传 `error` 与 `resendAfterSec`（至少 error）

**Step 2: Run**

```bash
cd navpay-admin/.wt/ws1-auth
yarn test tests/unit/api-personal-register-start.test.ts -v
```
Expected: FAIL.

**Step 3: Minimal implementation**

必要时让 route 在 `sendOtp` 失败时返回更多字段（例如 `resendAfterSec`），并补齐单测断言。

**Step 4: Re-run**

```bash
yarn test tests/unit/api-personal-register-start.test.ts -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-admin/src/app/api/personal/auth/register/start/route.ts navpay-admin/tests/unit/api-personal-register-start.test.ts
git commit -m "test(admin): strengthen personal register start route coverage"
```

---

### Task 4: 注册 verify route 单测补齐（only remember when verified; empty token guard）

**Files:**
- Modify: `navpay-admin/src/app/api/personal/auth/register/verify/route.ts`
- Test: `navpay-admin/tests/unit/api-personal-register-verify.test.ts`

**Step 1: Write failing tests**

Add tests for:
- otp 返回 `verified=false` 时，`complete` 必须失败（用 registry consume 验证）
- otp 返回 `verified=true` 但 `verificationToken=""` 时，route 返回 `400`（或至少不要 remember；二选一，先明确并写测试锁定）

**Step 2: Run**

```bash
cd navpay-admin/.wt/ws1-auth
yarn test tests/unit/api-personal-register-verify.test.ts -v
```
Expected: FAIL.

**Step 3: Minimal implementation**

在 route 中：
- `if (out.verified && out.verificationToken.trim()) remember...`
- 若 `verified && token empty`，返回 `{ ok:false, error:"bad_otp_response" }` + 502/500 或 400（选一种并锁定）

**Step 4: Re-run**

```bash
yarn test tests/unit/api-personal-register-verify.test.ts -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-admin/src/app/api/personal/auth/register/verify/route.ts navpay-admin/tests/unit/api-personal-register-verify.test.ts
git commit -m "test(admin): strengthen personal register verify route coverage"
```

---

### Task 5: 注册 complete route 单测补齐（otp_not_verified / username_taken / invalid_invite_code）

**Files:**
- Modify: `navpay-admin/src/app/api/personal/auth/register/complete/route.ts`
- Test: `navpay-admin/tests/unit/api-personal-register-complete.test.ts`

**Step 1: Write failing tests**

Add tests for:
- 没有 remember token => `400 otp_not_verified`
- remember token 但 phone 不匹配 => `400 otp_not_verified`
- username 已存在（先创建同 phoneE164 的 credentials）=> `409 username_taken`
- inviterCode 无效 => `400 invalid_invite_code`

**Step 2: Run**

```bash
cd navpay-admin/.wt/ws1-auth
yarn test tests/unit/api-personal-register-complete.test.ts -v
```
Expected: FAIL.

**Step 3: Minimal implementation**

Route 已有大部分映射；补齐缺的 status/error 映射并确保 deterministic。

**Step 4: Re-run**

```bash
yarn test tests/unit/api-personal-register-complete.test.ts -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-admin/src/app/api/personal/auth/register/complete/route.ts navpay-admin/tests/unit/api-personal-register-complete.test.ts
git commit -m "test(admin): strengthen personal register complete route coverage"
```

---

### Task 6: login/logout/me 三个 personal auth route 单测覆盖

**Files:**
- Test: `navpay-admin/tests/unit/api-personal-login.test.ts`
- Test: `navpay-admin/tests/unit/api-personal-logout.test.ts`
- Test: `navpay-admin/tests/unit/api-personal-me.test.ts`

**Step 1: Write failing tests (login)**

Create `api-personal-login.test.ts`:
- 成功：seed `createPaymentPersonWithCredentials({ username, password })`，调用 `POST /api/personal/auth/login`，返回 `token/person`
- 失败：密码错 => 401 + `invalid_credentials`
- bad_request：缺字段 => 400

**Step 2: Run**

```bash
cd navpay-admin/.wt/ws1-auth
yarn test tests/unit/api-personal-login.test.ts -v
```
Expected: PASS/FAIL（按缺失情况修复）。

**Step 3: Write failing tests (logout)**

Create `api-personal-logout.test.ts`:
- 无 Bearer => 401
- token 不存在 => 400 + `not_found`
- token 存在 => 200 + ok，并检查 `personal_api_tokens.revoked_at_ms` 被设置

**Step 4: Run**

```bash
yarn test tests/unit/api-personal-logout.test.ts -v
```

**Step 5: Write failing tests (me)**

Create `api-personal-me.test.ts`:
- 无 Bearer => expect 401（`requirePersonalToken` 会 throw；测试里捕获并断言 route 响应或直接测试 `requirePersonalToken` 行为）
- 有 token => 200 + `me.username` 正确

**Step 6: Run**

```bash
yarn test tests/unit/api-personal-me.test.ts -v
```

**Step 7: Commit**

```bash
git add navpay-admin/tests/unit/api-personal-login.test.ts navpay-admin/tests/unit/api-personal-logout.test.ts navpay-admin/tests/unit/api-personal-me.test.ts
git commit -m "test(admin): add personal auth route coverage (login/logout/me)"
```

---

# Local Integration Test (Machine)

### Task 7: 本机集成测试脚本 it-auth-local（启动 otp + admin 并走完整注册）

**Files:**
- Create: `navpay-admin/scripts/it-auth-local.ts`
- Modify: `navpay-admin/package.json`
- Docs: `navpay-admin/docs/manual/personal-register-smoke.md` (optional: link to the script)

**Step 1: Write the failing script (skeleton)**

`it-auth-local.ts` 目标行为：
- 自动选择空闲端口（otp/admin）
- otp 环境：
  - `PORT=<otpPort>`
  - `OTP_API_KEY=dev-otp-key`
  - `OTP_SIGNING_SECRET=<32+ chars>`
  - `OTP_FIXED_CODE=123456`
  - `WA_PROVIDER=fake`
- admin 环境（独立临时 DB 文件）：
  - `DATABASE_URL=file:/tmp/navpay-admin-it-<pid>.db`
  - `AUTH_SECRET/TOTP_ENCRYPTION_KEY/APIKEY_ENCRYPTION_KEY` 提供非空值
  - `OTP_BASE_URL=http://127.0.0.1:<otpPort>`
  - `OTP_API_KEY=dev-otp-key`
- 启动前先对该 DB 跑 migrate：`yarn db:migrate`（带上 DATABASE_URL）
- 启动 admin：`yarn dev -- -p <adminPort>`
- wait for readiness（循环请求 start endpoint 直到 200/400 之一）
- 通过 HTTP 走流程：
  1) `POST /api/personal/auth/register/start` => `otpId`
  2) `POST /api/personal/auth/register/verify` with code `123456` => `verificationToken`
  3) `POST /api/personal/auth/register/complete` => `token`
  4) `GET /api/personal/me` Bearer token => ok
- finally: 确保 kill 子进程 + 清理临时 db（至少 best-effort）

**Step 2: Add npm script**

In `navpay-admin/package.json` add:
```json
{
  "scripts": {
    "it:auth": "tsx scripts/it-auth-local.ts"
  }
}
```

**Step 3: Run it**

Run:
```bash
cd navpay-admin/.wt/ws1-auth
yarn it:auth
```
Expected: 退出码 0，并输出每一步 ok（例如 `start ok`, `verify ok`, `complete ok`, `me ok`）。

**Step 4: Commit**

```bash
git add navpay-admin/scripts/it-auth-local.ts navpay-admin/package.json
git commit -m "test(admin): add local integration test for personal register"
```

---

### Task 8: 全量回归

**Files:**
- None

**Step 1: Run unit tests**

```bash
cd navpay-admin/.wt/ws1-auth
yarn test
```
Expected: PASS.

**Step 2: Run local integration**

```bash
yarn it:auth
```
Expected: PASS.

---

Plan complete and saved to `docs/plans/2026-02-14-navpay-admin-auth-tests-and-local-it.md`. Two execution options:

1. Subagent-Driven (this session) - I dispatch fresh subagent per task, review between tasks, fast iteration
2. Parallel Session (separate) - Open new session in the worktree with executing-plans, batch execution with checkpoints

Which approach?

