# Payment Person Android Emulator Alignment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebuild the `navpay-admin` payment-person simulator UI to match `navpay-android` screens at near-1:1 fidelity, then embed this "real-device simulator" into the payment-person detail `账户详情` page.

**Architecture:** Split the simulator into a reusable Android-like shell + screen modules, driven by a typed screen-state model that mirrors Android flow (onboarding/login/home/buy/sell/task/record/mine/etc). Keep existing backend APIs for auth/report/payout actions, but remap frontend UI and interaction sequence to Android references. Mount the same simulator component both in `/admin/tools/payment-persons` and inside `/admin/payout/payment-persons/[personId]?tab=account` via a focused embed mode.

**Tech Stack:** Next.js App Router, React + TypeScript, Tailwind utility classes (existing NP tokens), Vitest, Playwright, Android XML/Kotlin reference assets.

---

References: @writing-plans @test-driven-development @frontend-design

## Scope Baseline (must be locked before implementation)
- Reference source of truth: `navpay-android/docs/ui/ui_spec.md` and Android layouts/fragments under `navpay-android/app/src/main/res/layout` + `navpay-android/app/src/main/java/com/navpay/ui/**`.
- Delivery scope target: payment-person-relevant Android screens first, then full-screen parity set if requested.
- Fidelity target: 99% visual parity at component spacing/typography/colors/states for selected scope.

### Task 1: Add Reference Inventory for Android-to-Web Screen Mapping

**Files:**
- Create: `navpay-admin/docs/ANDROID_SIMULATOR_SCREEN_MAPPING.md`
- Test: `navpay-admin/tests/unit/android-simulator-screen-mapping-doc.test.ts`

**Step 1: Write the failing test**

```ts
import { describe, expect, test } from "vitest";
import fs from "node:fs";
import path from "node:path";

describe("android simulator screen mapping doc", () => {
  test("contains required Android screen mapping entries", () => {
    const p = path.join(process.cwd(), "docs/ANDROID_SIMULATOR_SCREEN_MAPPING.md");
    const s = fs.readFileSync(p, "utf8");
    expect(s).toContain("fragment_login_movpay.xml");
    expect(s).toContain("fragment_home.xml");
    expect(s).toContain("fragment_buy_rp.xml");
    expect(s).toContain("fragment_mine.xml");
    expect(s).toContain("fragment_payment_task.xml");
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn vitest tests/unit/android-simulator-screen-mapping-doc.test.ts`
Expected: FAIL because mapping doc/test do not exist.

**Step 3: Write minimal implementation**

```md
# Android Simulator Screen Mapping
- Login: `fragment_login_movpay.xml` + `LoginMovpayFragment.kt` -> web simulator `screen=login`
- Home: `fragment_home.xml` + `HomeFragment.kt` -> web simulator `screen=home`
- Buy RP: `fragment_buy_rp.xml` + `BuyRpFragment.kt` -> web simulator `screen=buy_rp`
- Payment Task: `fragment_payment_task.xml` + `PaymentTaskFragment.kt` -> web simulator `screen=payment_task`
- Mine: `fragment_mine.xml` + `MineFragment.kt` -> web simulator `screen=mine`
```

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn vitest tests/unit/android-simulator-screen-mapping-doc.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-admin/docs/ANDROID_SIMULATOR_SCREEN_MAPPING.md navpay-admin/tests/unit/android-simulator-screen-mapping-doc.test.ts
git commit -m "docs(navpay-admin): add android-to-web simulator screen mapping"
```

### Task 2: Create Reusable Android Device Shell Component

**Files:**
- Create: `navpay-admin/src/components/simulator/android-device-shell.tsx`
- Modify: `navpay-admin/src/components/personal-channel-simulator-client.tsx`
- Test: `navpay-admin/tests/unit/android-device-shell.test.tsx`

**Step 1: Write the failing test**

```ts
import { describe, expect, test } from "vitest";
import fs from "node:fs";
import path from "node:path";

describe("android device shell", () => {
  test("extracts frame/notch/system bar into reusable component", () => {
    const p = path.join(process.cwd(), "src/components/simulator/android-device-shell.tsx");
    const s = fs.readFileSync(p, "utf8");
    expect(s).toContain("data-device-notch");
    expect(s).toContain("data-device-camera");
    expect(s).toContain("data-device-power-key");
    expect(s).toContain("data-device-volume-key");
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn vitest tests/unit/android-device-shell.test.tsx`
Expected: FAIL because component does not exist.

**Step 3: Write minimal implementation**

```tsx
export default function AndroidDeviceShell(props: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-[430px]">{/* existing frame markup */}</div>
  );
}
```

Move frame/notch/system header/footer markup from `personal-channel-simulator-client.tsx` into this component.

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn vitest tests/unit/android-device-shell.test.tsx`
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-admin/src/components/simulator/android-device-shell.tsx navpay-admin/src/components/personal-channel-simulator-client.tsx navpay-admin/tests/unit/android-device-shell.test.tsx
git commit -m "refactor(navpay-admin): extract reusable android device shell"
```

### Task 3: Add Typed Screen-State Model and Navigation Reducer

**Files:**
- Create: `navpay-admin/src/lib/simulator/android-screen-state.ts`
- Create: `navpay-admin/src/lib/simulator/android-screen-reducer.ts`
- Test: `navpay-admin/tests/unit/android-screen-reducer.test.ts`

**Step 1: Write the failing test**

```ts
import { describe, expect, test } from "vitest";
import { reduceScreenState, initialScreenState } from "@/lib/simulator/android-screen-reducer";

describe("android screen reducer", () => {
  test("navigates onboarding -> login -> home", () => {
    let s = initialScreenState();
    s = reduceScreenState(s, { type: "GO_LOGIN" });
    s = reduceScreenState(s, { type: "LOGIN_SUCCESS" });
    expect(s.screen).toBe("home");
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn vitest tests/unit/android-screen-reducer.test.ts`
Expected: FAIL with module not found.

**Step 3: Write minimal implementation**

```ts
export type AndroidScreen = "onboarding" | "login" | "home" | "buy_rp" | "payment_task" | "record" | "sell_rp" | "mine" | "points" | "official_channel";
```

Add pure reducer for deterministic screen switches and tab state.

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn vitest tests/unit/android-screen-reducer.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-admin/src/lib/simulator/android-screen-state.ts navpay-admin/src/lib/simulator/android-screen-reducer.ts navpay-admin/tests/unit/android-screen-reducer.test.ts
git commit -m "feat(navpay-admin): add android simulator screen state reducer"
```

### Task 4: Build Android-Style Screen Components (Login/Home/Buy/Sell/Mine)

**Files:**
- Create: `navpay-admin/src/components/simulator/screens/login-screen.tsx`
- Create: `navpay-admin/src/components/simulator/screens/home-screen.tsx`
- Create: `navpay-admin/src/components/simulator/screens/buy-rp-screen.tsx`
- Create: `navpay-admin/src/components/simulator/screens/sell-rp-screen.tsx`
- Create: `navpay-admin/src/components/simulator/screens/mine-screen.tsx`
- Test: `navpay-admin/tests/unit/android-simulator-core-screens.test.tsx`

**Step 1: Write the failing test**

```ts
import { describe, expect, test } from "vitest";
import fs from "node:fs";
import path from "node:path";

describe("android simulator core screens", () => {
  test("contains key Android labels and structures", () => {
    const p = path.join(process.cwd(), "src/components/simulator/screens/login-screen.tsx");
    const s = fs.readFileSync(p, "utf8");
    expect(s).toContain("Login");
    expect(s).toContain("密码");
    expect(s).toContain("邀请码");
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn vitest tests/unit/android-simulator-core-screens.test.tsx`
Expected: FAIL because files do not exist.

**Step 3: Write minimal implementation**

Each screen module renders Android-parity layout blocks referencing `navpay-android` screen structure and uses shared style tokens.

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn vitest tests/unit/android-simulator-core-screens.test.tsx`
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-admin/src/components/simulator/screens/*.tsx navpay-admin/tests/unit/android-simulator-core-screens.test.tsx
git commit -m "feat(navpay-admin): add android-like core simulator screens"
```

### Task 5: Build Android-Style Task/Record/Points/Official Channel Screens

**Files:**
- Create: `navpay-admin/src/components/simulator/screens/payment-task-screen.tsx`
- Create: `navpay-admin/src/components/simulator/screens/buy-rp-record-screen.tsx`
- Create: `navpay-admin/src/components/simulator/screens/points-details-screen.tsx`
- Create: `navpay-admin/src/components/simulator/screens/official-channel-screen.tsx`
- Test: `navpay-admin/tests/unit/android-simulator-extended-screens.test.tsx`

**Step 1: Write the failing test**

```ts
describe("android simulator extended screens", () => {
  test("renders payment task critical blocks", () => {
    const p = path.join(process.cwd(), "src/components/simulator/screens/payment-task-screen.tsx");
    const s = fs.readFileSync(p, "utf8");
    expect(s).toContain("Go to payment");
    expect(s).toContain("Lock order");
    expect(s).toContain("Submit UTR");
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn vitest tests/unit/android-simulator-extended-screens.test.tsx`
Expected: FAIL.

**Step 3: Write minimal implementation**

Implement extended screens and modal states matching Android references (`dialog_go_to_payment.xml`, `dialog_lock_order.xml`, `dialog_submit_utr.xml`).

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn vitest tests/unit/android-simulator-extended-screens.test.tsx`
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-admin/src/components/simulator/screens/*.tsx navpay-admin/tests/unit/android-simulator-extended-screens.test.tsx
git commit -m "feat(navpay-admin): add payment task and record simulator screens"
```

### Task 6: Compose New Android Parity Simulator Container

**Files:**
- Create: `navpay-admin/src/components/payment-person-android-simulator.tsx`
- Modify: `navpay-admin/src/components/personal-channel-simulator-client.tsx`
- Test: `navpay-admin/tests/unit/payment-person-android-simulator-composition.test.ts`

**Step 1: Write the failing test**

```ts
describe("payment person android simulator composition", () => {
  test("uses shared simulator container", () => {
    const p = path.join(process.cwd(), "src/components/personal-channel-simulator-client.tsx");
    const s = fs.readFileSync(p, "utf8");
    expect(s).toContain("PaymentPersonAndroidSimulator");
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn vitest tests/unit/payment-person-android-simulator-composition.test.ts`
Expected: FAIL.

**Step 3: Write minimal implementation**

Create `PaymentPersonAndroidSimulator` as orchestrator:
- props: `mode: "tool" | "detail"`
- wires existing login/sync/payout API calls
- renders Android shell + screen modules
- keeps existing scenario panel only in `mode="tool"`

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn vitest tests/unit/payment-person-android-simulator-composition.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-admin/src/components/payment-person-android-simulator.tsx navpay-admin/src/components/personal-channel-simulator-client.tsx navpay-admin/tests/unit/payment-person-android-simulator-composition.test.ts
git commit -m "feat(navpay-admin): compose android parity simulator container"
```

### Task 7: Embed Real-Device Simulator in Payment Person 账户详情 Tab

**Files:**
- Modify: `navpay-admin/src/components/payment-person-detail-client.tsx`
- Modify: `navpay-admin/src/app/admin/payout/payment-persons/[personId]/page.tsx`
- Test: `navpay-admin/tests/unit/payment-person-detail-simulator-embed.test.ts`

**Step 1: Write the failing test**

```ts
describe("payment person detail simulator embed", () => {
  test("renders android simulator in account tab", () => {
    const p = path.join(process.cwd(), "src/components/payment-person-detail-client.tsx");
    const s = fs.readFileSync(p, "utf8");
    expect(s).toContain("PaymentPersonAndroidSimulator");
    expect(s).toContain("mode=\"detail\"");
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn vitest tests/unit/payment-person-detail-simulator-embed.test.ts`
Expected: FAIL.

**Step 3: Write minimal implementation**

In `tab=account`, add a simulator card section:
- title: `真机模拟器`
- render `<PaymentPersonAndroidSimulator mode="detail" personId={props.personId} />`
- keep original account stats/actions below, no regression.

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn vitest tests/unit/payment-person-detail-simulator-embed.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-admin/src/components/payment-person-detail-client.tsx navpay-admin/src/app/admin/payout/payment-persons/[personId]/page.tsx navpay-admin/tests/unit/payment-person-detail-simulator-embed.test.ts
git commit -m "feat(navpay-admin): embed android simulator into payment person account tab"
```

### Task 8: Introduce Android Fidelity Design Tokens + Shared Styles

**Files:**
- Modify: `navpay-admin/src/app/globals.css`
- Create: `navpay-admin/src/components/simulator/android-simulator-tokens.ts`
- Test: `navpay-admin/tests/unit/android-simulator-style-token.test.ts`

**Step 1: Write the failing test**

```ts
describe("android simulator style tokens", () => {
  test("defines dedicated simulator tokens", () => {
    const p = path.join(process.cwd(), "src/components/simulator/android-simulator-tokens.ts");
    const s = fs.readFileSync(p, "utf8");
    expect(s).toContain("ANDROID_SIM_COLORS");
    expect(s).toContain("primaryBlue");
    expect(s).toContain("surface");
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn vitest tests/unit/android-simulator-style-token.test.ts`
Expected: FAIL.

**Step 3: Write minimal implementation**

Define tokens from Android references and consume via CSS vars/classes in simulator components only.

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn vitest tests/unit/android-simulator-style-token.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-admin/src/app/globals.css navpay-admin/src/components/simulator/android-simulator-tokens.ts navpay-admin/tests/unit/android-simulator-style-token.test.ts
git commit -m "style(navpay-admin): add android simulator fidelity tokens"
```

### Task 9: Preserve and Rewire Existing Simulator Behaviors

**Files:**
- Modify: `navpay-admin/src/components/payment-person-android-simulator.tsx`
- Modify: `navpay-admin/src/components/personal-channel-simulator-client.tsx`
- Test: `navpay-admin/tests/unit/payment-person-simulator-behavior-regression.test.ts`

**Step 1: Write the failing test**

```ts
describe("payment person simulator behavior regression", () => {
  test("still supports login/sync/payout/clear flows", () => {
    const p = path.join(process.cwd(), "src/components/payment-person-android-simulator.tsx");
    const s = fs.readFileSync(p, "utf8");
    expect(s).toContain("/api/personal/auth/login");
    expect(s).toContain("/api/personal/report/simulate");
    expect(s).toContain("/api/personal/payout/orders/available");
    expect(s).toContain("/api/admin/tools/payment-persons/clear");
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn vitest tests/unit/payment-person-simulator-behavior-regression.test.ts`
Expected: FAIL.

**Step 3: Write minimal implementation**

Ensure all existing APIs are still wired; only UI shell and interaction layout change.

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn vitest tests/unit/payment-person-simulator-behavior-regression.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-admin/src/components/payment-person-android-simulator.tsx navpay-admin/src/components/personal-channel-simulator-client.tsx navpay-admin/tests/unit/payment-person-simulator-behavior-regression.test.ts
git commit -m "refactor(navpay-admin): keep simulator behaviors after android UI alignment"
```

### Task 10: Add E2E Coverage for Tool Page + Detail Page Embed

**Files:**
- Modify: `navpay-admin/tests/e2e/personal-scenario-panel.spec.ts`
- Create: `navpay-admin/tests/e2e/payment-person-detail-simulator-embed.spec.ts`

**Step 1: Write the failing test**

```ts
import { test, expect } from "@playwright/test";
import { loginQa } from "./login-helpers";

test("payment person detail includes android-like simulator", async ({ page }) => {
  await loginQa(page);
  // create/find person then open detail page
  await expect(page.getByText("真机模拟器")).toBeVisible();
  await expect(page.getByText("Login")).toBeVisible();
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn playwright test tests/e2e/payment-person-detail-simulator-embed.spec.ts`
Expected: FAIL before embed exists.

**Step 3: Write minimal implementation**

Finish selectors/fixtures and add assertions for both `/admin/tools/payment-persons` and detail embed entry.

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn playwright test tests/e2e/personal-scenario-panel.spec.ts tests/e2e/payment-person-detail-simulator-embed.spec.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-admin/tests/e2e/personal-scenario-panel.spec.ts navpay-admin/tests/e2e/payment-person-detail-simulator-embed.spec.ts
git commit -m "test(navpay-admin): add e2e coverage for android simulator tool and detail embed"
```

### Task 11: Add Manual Pixel-Parity QA Checklist (99% Fidelity Gate)

**Files:**
- Create: `navpay-admin/docs/ANDROID_SIMULATOR_VISUAL_QA_CHECKLIST.md`

**Step 1: Write the failing test**

```ts
describe("android simulator visual qa checklist", () => {
  test("contains per-screen acceptance criteria", () => {
    const p = path.join(process.cwd(), "docs/ANDROID_SIMULATOR_VISUAL_QA_CHECKLIST.md");
    const s = fs.readFileSync(p, "utf8");
    expect(s).toContain("Login screen");
    expect(s).toContain("Home screen");
    expect(s).toContain("Payment Task screen");
    expect(s).toContain("Allowed diff threshold");
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn vitest tests/unit/android-simulator-visual-qa-doc.test.ts`
Expected: FAIL until checklist/test are added.

**Step 3: Write minimal implementation**

Document per-screen visual checks against Android references:
- typography scale
- spacing margins/padding
- button shape/height
- status bar/notch frame
- modal layouts
- bottom tab/nav behaviors

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn vitest tests/unit/android-simulator-visual-qa-doc.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-admin/docs/ANDROID_SIMULATOR_VISUAL_QA_CHECKLIST.md navpay-admin/tests/unit/android-simulator-visual-qa-doc.test.ts
git commit -m "docs(navpay-admin): add android simulator visual parity qa checklist"
```

### Task 12: Full Verification and Release Notes

**Files:**
- Modify: `navpay-admin/docs/plans/2026-02-18-payment-person-scenario-trace-v1.md` (append rollout note) OR create new result note
- Optional Create: `navpay-admin/docs/release-notes/2026-02-18-payment-person-android-simulator.md`

**Step 1: Run targeted unit tests**

Run: `cd navpay-admin && yarn vitest tests/unit/android-*.test.ts tests/unit/payment-person-*.test.ts`
Expected: PASS.

**Step 2: Run e2e tests**

Run: `cd navpay-admin && yarn playwright test tests/e2e/personal-scenario-panel.spec.ts tests/e2e/payment-person-detail-simulator-embed.spec.ts`
Expected: PASS.

**Step 3: Run quality gates**

Run: `cd navpay-admin && yarn lint && yarn typecheck`
Expected: PASS.

**Step 4: Record verification output**

Capture exact command/date/commit hash and any known deviations in release note.

**Step 5: Commit**

```bash
git add navpay-admin/docs/release-notes/2026-02-18-payment-person-android-simulator.md
git commit -m "docs(navpay-admin): add verification and rollout notes for android simulator alignment"
```

## Open Risks to Track During Execution
- Existing simulator currently mixes tool/debug features and app-like shell in one file (`personal-channel-simulator-client.tsx`); refactor risk is medium.
- 99% visual parity without screenshot diff tooling is subjective; must enforce with checklist and side-by-side QA.
- Embedding simulator into detail account tab may affect page performance; lazy mount may be needed.
- Android has 44 screenshot references; full parity may exceed single-iteration scope unless we lock “must-have screens” first.

