# NavPay Cross-Project Review + Personal Self-Service Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 打通 `navpay-admin` 与 Android `navpay-android` 的真实联调闭环：补齐代付审核入口与权限流，并扩展个人端 API/客户端能力，覆盖邀请码、改密、收益返利、上下级、设备状态、交易与余额流水可视化。

**Architecture:** 以后端 `navpay-admin` 作为唯一业务真相源，先补齐审核流（`REVIEW_PENDING -> APPROVED/REJECTED`）与审计权限，再新增 personal 聚合查询/改密 API，最后在 Android 侧接入并展示。联调验证分为自动化（Vitest + API smoke）和人工走查（真实数据 + UI 可见证据）两层，保证可重复复现。

**Tech Stack:** Next.js 16, TypeScript, Drizzle + SQLite, Vitest, Playwright, Android Kotlin, OkHttp, Gradle.

---

### Task 1: 固化联调基线与验收口径

**Files:**
- Create: `docs/manual/2026-02-13-navpay-full-flow-checklist.md`
- Modify: `navpay-admin/docs/PERSONAL_MOBILE_API_V1.md`
- Modify: `navpay-android/docs/TEST_ACCOUNTS.md`
- Test: `navpay-admin/tests/unit/personal-auth.test.ts`

**Step 1: Write the failing test**

```ts
// navpay-admin/tests/unit/personal-auth.test.ts
import { describe, expect, test } from "vitest";

describe("personal full-flow checklist reference", () => {
  test("must include payout review and personal self-service sections", () => {
    const required = ["payout review", "password reset", "team rebate", "bank transactions"];
    expect(required.length).toBe(4);
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/personal-auth.test.ts`
Expected: FAIL（缺少真实断言/文档契约）

**Step 3: Write minimal implementation**

补充文档中的“联调基线版本”“审核入口预期行为”“个人端字段契约”“人工验收截图清单”。

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/personal-auth.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add docs/manual/2026-02-13-navpay-full-flow-checklist.md navpay-admin/docs/PERSONAL_MOBILE_API_V1.md navpay-android/docs/TEST_ACCOUNTS.md navpay-admin/tests/unit/personal-auth.test.ts
git commit -m "docs(flow): define cross-project full-flow checklist and personal api contract"
```

### Task 2: 补齐代付审核入口（列表 + 详情）

**Files:**
- Modify: `navpay-admin/src/components/payout-orders-client.tsx`
- Modify: `navpay-admin/src/components/order-detail-client.tsx`
- Modify: `navpay-admin/src/lib/order-status.ts`
- Test: `navpay-admin/tests/e2e/payout-review-entry.spec.ts`

**Step 1: Write the failing test**

```ts
// navpay-admin/tests/e2e/payout-review-entry.spec.ts
import { test, expect } from "@playwright/test";

test("review_pending order should show approve/reject actions for reviewer", async ({ page }) => {
  await page.goto("/admin/orders/payout");
  await expect(page.getByRole("button", { name: "审核通过" })).toBeVisible();
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test:e2e tests/e2e/payout-review-entry.spec.ts`
Expected: FAIL（当前无审核按钮）

**Step 3: Write minimal implementation**

在代付列表/详情中，当状态为 `REVIEW_PENDING` 时展示“审核通过/驳回”操作按钮，并调用状态接口。

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test:e2e tests/e2e/payout-review-entry.spec.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add navpay-admin/src/components/payout-orders-client.tsx navpay-admin/src/components/order-detail-client.tsx navpay-admin/src/lib/order-status.ts navpay-admin/tests/e2e/payout-review-entry.spec.ts
git commit -m "feat(admin): add payout review actions in list and detail pages"
```

### Task 3: 强化审核权限与状态流转 API

**Files:**
- Modify: `navpay-admin/src/app/api/admin/orders/payout/[orderId]/status/route.ts`
- Modify: `navpay-admin/src/lib/payout-status.ts`
- Test: `navpay-admin/tests/unit/payout-review-permission.test.ts`

**Step 1: Write the failing test**

```ts
// navpay-admin/tests/unit/payout-review-permission.test.ts
import { describe, test, expect } from "vitest";

describe("payout review permissions", () => {
  test("APPROVED transition requires order.payout.review", async () => {
    expect(true).toBe(false);
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/payout-review-permission.test.ts`
Expected: FAIL

**Step 3: Write minimal implementation**

- 将 `REVIEW_PENDING -> APPROVED/REJECTED` 定义为标准审核动作（不依赖 debug tool 开关）。
- 保持 `SUCCESS/FAILED` 等高风险终态仍需 `order.payout.finalize`。
- 在 `audit_logs` 中记录 `from/to` 与操作者。

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/payout-review-permission.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add navpay-admin/src/app/api/admin/orders/payout/[orderId]/status/route.ts navpay-admin/src/lib/payout-status.ts navpay-admin/tests/unit/payout-review-permission.test.ts
git commit -m "fix(payout): enforce review transitions and permission boundaries"
```

### Task 4: 新增 Personal 聚合查询 API（自助中心）

**Files:**
- Create: `navpay-admin/src/app/api/personal/dashboard/route.ts`
- Modify: `navpay-admin/src/app/api/personal/me/route.ts`
- Create: `navpay-admin/src/lib/personal-dashboard.ts`
- Test: `navpay-admin/tests/unit/personal-dashboard.test.ts`

**Step 1: Write the failing test**

```ts
// navpay-admin/tests/unit/personal-dashboard.test.ts
import { describe, test, expect } from "vitest";

describe("personal dashboard api", () => {
  test("returns invite, earnings, team, devices, bank, tx, balance logs", async () => {
    expect(false).toBe(true);
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/personal-dashboard.test.ts`
Expected: FAIL

**Step 3: Write minimal implementation**

返回结构至少包含：
- `inviteCode`, `upline`, `downlineSummary`
- `todayEarnings`, `todayTeamRebate`
- `devices[]`（在线状态/最近心跳）
- `bankAccounts[]`, `bankTransactions[]`
- `balanceLogs[]`

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/personal-dashboard.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add navpay-admin/src/app/api/personal/dashboard/route.ts navpay-admin/src/lib/personal-dashboard.ts navpay-admin/src/app/api/personal/me/route.ts navpay-admin/tests/unit/personal-dashboard.test.ts
git commit -m "feat(personal): add dashboard aggregate api for mobile self-service"
```

### Task 5: 新增 Personal 改密 API（旧密码 + 新密码）

**Files:**
- Create: `navpay-admin/src/app/api/personal/auth/password/reset/route.ts`
- Modify: `navpay-admin/src/lib/personal-auth.ts`
- Test: `navpay-admin/tests/unit/personal-password-reset.test.ts`

**Step 1: Write the failing test**

```ts
// navpay-admin/tests/unit/personal-password-reset.test.ts
import { describe, test, expect } from "vitest";

describe("personal password reset", () => {
  test("requires old password and strong new password", async () => {
    expect(1).toBe(2);
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/personal-password-reset.test.ts`
Expected: FAIL

**Step 3: Write minimal implementation**

- 入参：`oldPassword`, `newPassword`
- 校验旧密码 + 强密码策略
- 更新 `payment_person_credentials.password_hash`
- 写入 `payment_person_login_logs` / `payment_person_report_logs` 审计事件

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/personal-password-reset.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add navpay-admin/src/app/api/personal/auth/password/reset/route.ts navpay-admin/src/lib/personal-auth.ts navpay-admin/tests/unit/personal-password-reset.test.ts
git commit -m "feat(personal): support self password reset with old-password verification"
```

### Task 6: Android 接入新 Personal API（数据模型 + APIClient）

**Files:**
- Modify: `navpay-android/app/src/main/java/com/phonepe/checksumclient/Models.kt`
- Modify: `navpay-android/app/src/main/java/com/phonepe/checksumclient/ApiClient.kt`
- Test: `navpay-android/app/src/test/java/com/phonepe/checksumclient/ApiClientPersonalDashboardTest.kt`

**Step 1: Write the failing test**

```kotlin
// navpay-android/app/src/test/java/com/phonepe/checksumclient/ApiClientPersonalDashboardTest.kt
import org.junit.Assert.assertEquals
import org.junit.Test

class ApiClientPersonalDashboardTest {
    @Test
    fun parseDashboardFields() {
        assertEquals(1, 1)
    }
}
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-android && ./gradlew test --tests '*ApiClientPersonalDashboardTest'`
Expected: FAIL（接口/模型未实现）

**Step 3: Write minimal implementation**

新增方法：
- `getDashboard()`
- `resetPassword(oldPassword, newPassword)`

并扩展模型：邀请码、收益、上下级、设备、网银、交易、余额流水。

**Step 4: Run test to verify it passes**

Run: `cd navpay-android && ./gradlew test --tests '*ApiClientPersonalDashboardTest'`
Expected: PASS

**Step 5: Commit**

```bash
git add navpay-android/app/src/main/java/com/phonepe/checksumclient/Models.kt navpay-android/app/src/main/java/com/phonepe/checksumclient/ApiClient.kt navpay-android/app/src/test/java/com/phonepe/checksumclient/ApiClientPersonalDashboardTest.kt
git commit -m "feat(android): consume personal dashboard and password reset apis"
```

### Task 7: Android 端补齐自助信息展示与手工验收入口

**Files:**
- Modify: `navpay-android/app/src/main/java/com/phonepe/checksumclient/ProfileFragment.kt`
- Modify: `navpay-android/app/src/main/java/com/phonepe/checksumclient/EarningsFragment.kt`
- Modify: `navpay-android/app/src/main/res/layout/fragment_profile.xml`
- Modify: `navpay-android/app/src/main/res/layout/fragment_earnings.xml`
- Create: `navpay-android/app/src/main/java/com/phonepe/checksumclient/TeamFragment.kt`
- Create: `navpay-android/app/src/main/res/layout/fragment_team.xml`
- Test: `navpay-android/app/src/test/java/com/phonepe/checksumclient/ProfileViewModelContractTest.kt`

**Step 1: Write the failing test**

```kotlin
// navpay-android/app/src/test/java/com/phonepe/checksumclient/ProfileViewModelContractTest.kt
import org.junit.Assert.assertTrue
import org.junit.Test

class ProfileViewModelContractTest {
    @Test
    fun shouldExposeInviteAndBalanceSections() {
        assertTrue(false)
    }
}
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-android && ./gradlew test --tests '*ProfileViewModelContractTest'`
Expected: FAIL

**Step 3: Write minimal implementation**

在客户端可查看并手工验证：
- 邀请码、上级、下级/返利摘要
- 今日收益、团队返利
- 手机在线状态、网银账户、交易记录、余额变动
- 改密入口（旧密码 + 新密码）

**Step 4: Run test to verify it passes**

Run: `cd navpay-android && ./gradlew test --tests '*ProfileViewModelContractTest'`
Expected: PASS

**Step 5: Commit**

```bash
git add navpay-android/app/src/main/java/com/phonepe/checksumclient/ProfileFragment.kt navpay-android/app/src/main/java/com/phonepe/checksumclient/EarningsFragment.kt navpay-android/app/src/main/java/com/phonepe/checksumclient/TeamFragment.kt navpay-android/app/src/main/res/layout/fragment_profile.xml navpay-android/app/src/main/res/layout/fragment_earnings.xml navpay-android/app/src/main/res/layout/fragment_team.xml navpay-android/app/src/test/java/com/phonepe/checksumclient/ProfileViewModelContractTest.kt
git commit -m "feat(android): add personal self-service views and manual verification surfaces"
```

### Task 8: 真实联调闭环脚本 + 可视化验收证据

**Files:**
- Create: `navpay-admin/scripts/smoke-personal-payout-flow.ts`
- Create: `navpay-android/tools/smoke_full_flow.sh`
- Create: `docs/manual/2026-02-13-navpay-real-env-evidence.md`
- Test: `navpay-admin/tests/e2e/personal-payout-realflow.spec.ts`

**Step 1: Write the failing test**

```ts
// navpay-admin/tests/e2e/personal-payout-realflow.spec.ts
import { test, expect } from "@playwright/test";

test("realflow: create->review->claim->complete should be visible in admin and android", async ({ page }) => {
  await page.goto("/admin/orders/payout");
  await expect(page.getByText("待审核")).toBeVisible();
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test:e2e tests/e2e/personal-payout-realflow.spec.ts`
Expected: FAIL（流程尚未贯通）

**Step 3: Write minimal implementation**

- `smoke-personal-payout-flow.ts` 自动执行：创建代付单 -> 审核通过 -> personal API 抢单 -> 完成。
- 脚本输出关键 ID：`orderId`, `personId`, `lockExpiresAtMs`, `finalStatus`。
- `docs/manual/...evidence.md` 记录 SQL/页面/API 三类证据截图与命令。

**Step 4: Run test to verify it passes**

Run:
- `cd navpay-admin && yarn tsx scripts/smoke-personal-payout-flow.ts`
- `cd navpay-android && bash tools/smoke_full_flow.sh`
- `cd navpay-admin && yarn test:e2e tests/e2e/personal-payout-realflow.spec.ts`

Expected: PASS，且证据文档包含真实 `orderId` 与状态流转记录。

**Step 5: Commit**

```bash
git add navpay-admin/scripts/smoke-personal-payout-flow.ts navpay-android/tools/smoke_full_flow.sh docs/manual/2026-02-13-navpay-real-env-evidence.md navpay-admin/tests/e2e/personal-payout-realflow.spec.ts
git commit -m "test(flow): add real-environment payout full-flow smoke scripts and evidence"
```

### Task 9: 回归与发布前检查

**Files:**
- Modify: `navpay-admin/docs/TEST_REPORT_V1.md`
- Modify: `navpay-admin/AGENTS.md`
- Modify: `navpay-android/AGENTS.md`

**Step 1: Write the failing test**

```ts
// use existing suites as release gate
```

**Step 2: Run test to verify it fails**

Run:
- `cd navpay-admin && yarn lint && yarn typecheck && yarn test`
- `cd navpay-android && ./gradlew test`
Expected: 如有失败先修复

**Step 3: Write minimal implementation**

修复回归，更新测试报告，补充“审核角色 + 个人端自助能力 + 联调脚本”维护说明。

**Step 4: Run test to verify it passes**

Run:
- `cd navpay-admin && yarn lint && yarn typecheck && yarn test && yarn test:e2e`
- `cd navpay-android && ./gradlew test && ./gradlew assembleDebug`
Expected: 全绿

**Step 5: Commit**

```bash
git add navpay-admin/docs/TEST_REPORT_V1.md navpay-admin/AGENTS.md navpay-android/AGENTS.md
git commit -m "chore(release): finalize docs and regression report for cross-project full flow"
```

## Manual Verification Script (必须走一遍)

1. `cd navpay-admin && yarn dev`，登录超级管理员。
2. 进入 `/admin/tools/order-simulator` 创建代付单，确认状态为 `REVIEW_PENDING`。
3. 在 `/admin/orders/payout` 或详情页执行“审核通过”，状态变为 `APPROVED`。
4. Android 登录后在抢单页看到订单，执行抢单与完成。
5. 回到 admin 验证：订单终态、回调记录、支付个人余额流水、团队返利流水。
6. 在 Android 个人页验证：邀请码、今日收益、团队返利、上下级、设备状态、交易记录、网银账户、余额变动、改密。

## Notes

- 相关技能：@test-driven-development @systematic-debugging @requesting-code-review
- 严格按任务顺序执行；每个任务必须先红后绿再提交。
- 对真实环境操作时，只使用测试账号与测试商户，避免污染生产数据。
