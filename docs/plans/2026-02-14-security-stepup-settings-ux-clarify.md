# 安全验证设置页语义与提示改造 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将“安全验证”设置页改成单一总开关语义：关闭仅关闭总开关但保留配置且不可编辑；开启仅开启总开关并明确提示“全部开启/部分开启”状态。

**Architecture:** 前端设置页通过纯函数计算状态摘要与“全部/部分”判定，保证 UI 文案与逻辑一致且可单测；文档补充总开关语义与“全部/部分开启”的定义。

**Tech Stack:** Next.js (App Router), React, TypeScript, Vitest, Playwright

---

### Task 1: 抽出“状态摘要”纯函数并写单测

**Files:**
- Create: `navpay-admin/src/lib/security-stepup-summary.ts`
- Test: `navpay-admin/tests/unit/security-stepup-summary.test.ts`

**Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest";
import { computeSecurityStepUpSummary } from "@/lib/security-stepup-summary";

describe("computeSecurityStepUpSummary", () => {
  it("enabled=false -> mode off and explains config is preserved", () => {
    const s = computeSecurityStepUpSummary({
      enabled: false,
      ttlMs: 300_000,
      groups: { g1: { enabled: false, name: "平台系统" } } as any,
      ops: {},
      opsMeta: [],
    });
    expect(s.mode).toBe("off");
    expect(s.title).toContain("已关闭");
    expect(s.subtitle).toContain("配置已保留");
  });

  it("enabled=true + all groups on + all defaultRequired ops effective on -> on_all", () => {
    const s = computeSecurityStepUpSummary({
      enabled: true,
      ttlMs: 0,
      groups: { platform_system: { enabled: true, name: "平台系统" } } as any,
      ops: {},
      opsMeta: [{ opId: "op1", name: "新增平台用户", groupId: "platform_system", defaultRequired: true }],
    });
    expect(s.mode).toBe("on_all");
  });

  it("enabled=true + any required op disabled by override -> on_partial", () => {
    const s = computeSecurityStepUpSummary({
      enabled: true,
      ttlMs: 0,
      groups: { platform_system: { enabled: true, name: "平台系统" } } as any,
      ops: { op1: { enabled: false } } as any,
      opsMeta: [{ opId: "op1", name: "新增平台用户", groupId: "platform_system", defaultRequired: true }],
    });
    expect(s.mode).toBe("on_partial");
  });
});
```

**Step 2: Run test to verify it fails**

Run: `yarn -C navpay-admin test tests/unit/security-stepup-summary.test.ts`
Expected: FAIL with "Cannot find module" / "computeSecurityStepUpSummary is not a function"

**Step 3: Write minimal implementation**

```ts
export function computeSecurityStepUpSummary(input) {
  // compute: groupOn/groupTotal, requiredNeed/requiredTotal, ttlSec
}
```

**Step 4: Run test to verify it passes**

Run: `yarn -C navpay-admin test tests/unit/security-stepup-summary.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add navpay-admin/src/lib/security-stepup-summary.ts navpay-admin/tests/unit/security-stepup-summary.test.ts
git commit -m "test(stepup): add summary computation helper"
```

---

### Task 2: 设置页使用统一摘要与更明确的中文提示

**Files:**
- Modify: `navpay-admin/src/components/security-stepup-settings-client.tsx`

**Step 1: Update UI copy and summary logic**

- 摘要标题固定三态：
  - `已关闭`
  - `已开启（全部开启）`
  - `已开启（部分开启）`
- 当 `enabled=false`：
  - 显示“当前仅关闭总开关；下方配置已保留，重新开启后按下方配置生效”
  - 下方分组、TTL、细节操作全部 `disabled`
- 当 `enabled=true`：
  - 显示“开启总开关不会改变你之前的分组/细节配置，请在下方确认”
  - 额外高亮提示当前 `全部开启/部分开启`

**Step 2: Run typecheck**

Run: `yarn -C navpay-admin typecheck`
Expected: exit 0

**Step 3: Run e2e**

Run: `yarn -C navpay-admin test:e2e tests/e2e/security-stepup-hints.spec.ts`
Expected: PASS

**Step 4: Commit**

```bash
git add navpay-admin/src/components/security-stepup-settings-client.tsx
git commit -m "feat(stepup): clarify master toggle semantics and status hint"
```

---

### Task 3: 文档更新（语义与“全部/部分开启”定义）

**Files:**
- Modify: `navpay-admin/docs/security-stepup.md`

**Step 1: Update docs**

- 补充“总开关语义”：关闭保留配置但不生效；开启仅开启总开关，不自动修改配置
- 补充“全部/部分开启”判定口径
- 更新入口路径（如已移动到 `系统参数 -> 安全`）

**Step 2: Commit**

```bash
git add navpay-admin/docs/security-stepup.md
git commit -m "docs(stepup): document master toggle semantics and all/partial status"
```

---

### Task 4: 全量回归测试

**Step 1: Unit tests**

Run: `yarn -C navpay-admin test`
Expected: PASS

**Step 2: Playwright**

Run: `yarn -C navpay-admin test:e2e`
Expected: PASS

