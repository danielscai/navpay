# Payout Claim Payment App Upload & Admin Display Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 `navpay-android` 抢单时把所选支付方式随 claim API 上传，并在 `navpay-admin` 的 `/admin/orders/payout` 列表新增“支付app”列显示名称与 icon。

**Architecture:** 在服务端 `payout_orders` 表新增 `payment_app_id`，claim 接口接收 `paymentAppId` 并在抢单原子更新里一起写入。安卓端把“点击 receive”流程改为“先选支付方式，再调用 claim(orderId, paymentAppId)”。admin 列表查询联表拿 `payment_apps` 的 `name/icon_url`，在表格与移动端卡片展示“支付app”。

**Tech Stack:** Next.js App Router + TypeScript + Prisma/PostgreSQL + Kotlin Android + Vitest

---

### Task 1: DB Schema + Claim Domain Write Path

**Files:**
- Create: `navpay-admin/prisma/migrations/20260328223000_payout_order_payment_app_id/migration.sql`
- Modify: `navpay-admin/prisma/schema.prisma`
- Modify: `navpay-admin/src/lib/payout-claim.ts`
- Test: `navpay-admin/tests/unit/payout-claim-concurrency.test.ts`

**Step 1: Write the failing test**

```ts
const a = await claimPayoutOrderAtomic({
  orderId,
  personId,
  paymentAppId: "pa_phonepe",
  nowMs: now + 1,
  lockTimeoutMinutes: 10,
});
const row = await sqlOne(
  "SELECT payment_app_id FROM payout_orders WHERE id = $1",
  [orderId],
);
expect(row.payment_app_id).toBe("pa_phonepe");
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/payout-claim-concurrency.test.ts -t payment_app_id`  
Expected: FAIL（`payment_app_id` 列不存在或断言失败）

**Step 3: Write minimal implementation**

```sql
ALTER TABLE payout_orders ADD COLUMN IF NOT EXISTS payment_app_id text;
CREATE INDEX IF NOT EXISTS payout_orders_payment_app_idx ON payout_orders(payment_app_id);
```

```prisma
model payout_orders {
  ...
  payment_app_id String?
  ...
  @@index([payment_app_id], map: "payout_orders_payment_app_idx")
}
```

```ts
export async function claimPayoutOrderAtomic(opts: {
  orderId: string;
  personId: string;
  paymentAppId?: string | null;
  nowMs: number;
  lockTimeoutMinutes: number;
}) {
  ...
  payment_app_id = $6
  ...
}
```

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/payout-claim-concurrency.test.ts`  
Expected: PASS

**Step 5: Commit**

```bash
git -C navpay-admin add prisma/migrations/20260328223000_payout_order_payment_app_id/migration.sql prisma/schema.prisma src/lib/payout-claim.ts tests/unit/payout-claim-concurrency.test.ts
git -C navpay-admin commit -m "feat(payout): persist payment app id on claim"
```

### Task 2: Personal Claim API Accepts paymentAppId

**Files:**
- Modify: `navpay-admin/src/app/api/personal/payout/orders/[orderId]/claim/route.ts`
- (Optional) Create: `navpay-admin/tests/unit/personal-payout-claim-route.test.ts`

**Step 1: Write the failing test**

```ts
const req = new NextRequest("http://localhost/api/personal/payout/orders/po_1/claim", {
  method: "POST",
  body: JSON.stringify({ paymentAppId: "pa_phonepe" }),
});
expect(claimPayoutOrderAtomic).toHaveBeenCalledWith(
  expect.objectContaining({ paymentAppId: "pa_phonepe" }),
);
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/personal-payout-claim-route.test.ts`  
Expected: FAIL（`paymentAppId` 未透传）

**Step 3: Write minimal implementation**

```ts
const body = z.object({ paymentAppId: z.string().min(1) }).safeParse(await req.json().catch(() => null));
if (!body.success) return NextResponse.json({ ok: false, error: "bad_request" }, { status: 400 });
...
claimPayoutOrderAtomic({ ..., paymentAppId: body.data.paymentAppId })
```

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/personal-payout-claim-route.test.ts`  
Expected: PASS

**Step 5: Commit**

```bash
git -C navpay-admin add src/app/api/personal/payout/orders/[orderId]/claim/route.ts tests/unit/personal-payout-claim-route.test.ts
git -C navpay-admin commit -m "feat(personal-api): require payment app id on payout claim"
```

### Task 3: Admin Payout List Shows 支付app Name + Icon

**Files:**
- Modify: `navpay-admin/src/app/api/admin/orders/payout/route.ts`
- Modify: `navpay-admin/src/components/payout-orders-client.tsx`
- Modify: `navpay-admin/tests/unit/payout-orders-columns.test.ts`
- Modify: `navpay-admin/tests/unit/payout-orders-responsive-layout.test.ts`
- (Optional) Modify: `navpay-admin/tests/unit/admin-payout-orders-route-performance-contract.test.ts`

**Step 1: Write the failing test**

```ts
expect(src).toContain("支付app");
expect(src).toContain("paymentAppName");
expect(src).toContain("paymentAppIconUrl");
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/payout-orders-columns.test.ts tests/unit/payout-orders-responsive-layout.test.ts`  
Expected: FAIL（列与字段不存在）

**Step 3: Write minimal implementation**

```ts
// route.ts rows
paymentAppId: o.payment_app_id,
paymentAppName: o.payment_app_id ? (appById.get(o.payment_app_id)?.name ?? null) : null,
paymentAppIconUrl: o.payment_app_id ? (appById.get(o.payment_app_id)?.icon_url ?? null) : null,
```

```tsx
<ThTrunc ...>支付app</ThTrunc>
...
{o.paymentAppIconUrl ? <img ... src={o.paymentAppIconUrl} /> : <span className="h-5 w-5 ..." />}
<span>{o.paymentAppName || "-"}</span>
```

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/payout-orders-columns.test.ts tests/unit/payout-orders-responsive-layout.test.ts tests/unit/admin-payout-orders-route-performance-contract.test.ts`  
Expected: PASS

**Step 5: Commit**

```bash
git -C navpay-admin add src/app/api/admin/orders/payout/route.ts src/components/payout-orders-client.tsx tests/unit/payout-orders-columns.test.ts tests/unit/payout-orders-responsive-layout.test.ts tests/unit/admin-payout-orders-route-performance-contract.test.ts
git -C navpay-admin commit -m "feat(admin-orders): show claimed payment app in payout list"
```

### Task 4: Android Claim Flow Uploads Selected Payment App

**Files:**
- Modify: `navpay-android/app/src/main/java/com/navpay/Models.kt`
- Modify: `navpay-android/app/src/main/java/com/navpay/ApiClient.kt`
- Modify: `navpay-android/app/src/main/java/com/navpay/ui/buy/BuyRpFragment.kt`
- Modify: `navpay-android/app/src/main/java/com/navpay/ui/paymentapps/PaymentAppNormalizer.kt`

**Step 1: Write the failing test (manual contract check)**

```text
预期：点击 receive -> 先弹支付方式；选择后才发 claim，且 request body 包含 paymentAppId
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-android && yarn apk`  
Expected: 编译可过，但行为仍是“先 claim 再选方式”

**Step 3: Write minimal implementation**

```kotlin
data class PaymentApp(
  val id: String,
  ...
)
```

```kotlin
suspend fun claimOrder(orderId: String, paymentAppId: String): Order {
  val payload = JSONObject().apply { put("paymentAppId", paymentAppId) }
  val json = postAuthedJson("${baseUrl}/payout/orders/${orderId}/claim", payload)
}
```

```kotlin
// BuyRpFragment
// receive 点击后先 showPaymentMethodSheet
// 选中后 claimOrder(order.orderId, selected.appId) 成功再导航 paymentTaskFragment
```

**Step 4: Run test to verify it passes**

Run: `cd navpay-android && yarn apk`  
Expected: PASS（编译通过）  

Manual smoke:
`yarn emu1 && yarn i1`，登录后进入 buy rp，点 receive 选择方式后可进入任务页，服务端订单显示支付 app。

**Step 5: Commit**

```bash
git -C navpay-android add app/src/main/java/com/navpay/Models.kt app/src/main/java/com/navpay/ApiClient.kt app/src/main/java/com/navpay/ui/buy/BuyRpFragment.kt app/src/main/java/com/navpay/ui/paymentapps/PaymentAppNormalizer.kt
git -C navpay-android commit -m "feat(android): send selected payment app in payout claim"
```

### Task 5: End-to-End Verification

**Files:**
- Modify: `docs/plans/2026-03-28-payout-claim-payment-app.md`（补充验证记录）

**Step 1: Run admin checks**

Run:
`cd navpay-admin && yarn typecheck && yarn lint && yarn test tests/unit/payout-claim-concurrency.test.ts tests/unit/payout-orders-columns.test.ts tests/unit/payout-orders-responsive-layout.test.ts tests/unit/admin-payout-orders-route-performance-contract.test.ts`

Expected: PASS

**Step 2: Run android build check**

Run: `cd navpay-android && yarn apk`  
Expected: PASS

**Step 3: Manual E2E**

Run:
1. 启动 `navpay-admin` 本地服务  
2. 安卓端登录并在 Buy RP 点 `receive` 选择支付方式  
3. 打开 `/admin/orders/payout`，确认出现“支付app”列，显示名称+icon

Expected: PASS

**Step 4: Commit verification note**

```bash
git add docs/plans/2026-03-28-payout-claim-payment-app.md
git commit -m "docs(plan): record payout claim payment app verification"
```
