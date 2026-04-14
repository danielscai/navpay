# Semi-Manual Multi-Repo Release Unification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 `navpay-admin`、`navpay-android`、`navpay-phonepe` 三个仓库落地统一的半自动发布契约：`yarn release <product>` 与 `yarn deploy <product>`，并统一版本规则与手工可验证发布记录。

**Architecture:** 共享核心逻辑只维护在 `navpay-admin/scripts/release-core/`，其余仓库通过手动同步命令复制核心文件并调用本仓库 hooks。`release` 负责版本计算、tag 推送与产物准备；`deploy` 负责按产品类型执行单产品部署。统一前置强制 `main + fetch tags + ff-only pull`，版本从仓库 tags 推导。

**Tech Stack:** TypeScript (`tsx`) + Bash + Git + Yarn 4 + Docker Compose + rsync/scp。

---

### Task 1: 固化核心契约与 CLI 参数解析（admin）

**Files:**
- Create: `navpay-admin/scripts/release-core/contracts.ts`
- Create: `navpay-admin/scripts/release-core/cli.ts`
- Test: `navpay-admin/tests/unit/scripts/release-core-cli-contract.test.ts`

**Step 1: Write the failing test**

```ts
import { parseArgs } from "../../../scripts/release-core/cli";

test("parses release admin", () => {
  expect(parseArgs(["release", "admin"]).product).toBe("admin");
});

test("rejects unsupported product", () => {
  expect(() => parseArgs(["release", "foo"]))
    .toThrow(/unsupported product/i);
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/scripts/release-core-cli-contract.test.ts`
Expected: FAIL because parser module does not exist.

**Step 3: Write minimal implementation**

- 在 `contracts.ts` 定义：
  - `Product = "admin" | "checksum" | "android" | "phonepe"`
  - `Command = "release" | "deploy"`
  - `ParsedArgs`（包含 `command/product/version?`）
- 在 `cli.ts` 实现参数解析：
  - `release <product>`
  - `deploy <product> [--version <v|plain>]`
  - 统一 normalize 版本字符串（允许 `v` 前缀输入）

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/scripts/release-core-cli-contract.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git -C navpay-admin add scripts/release-core/contracts.ts scripts/release-core/cli.ts tests/unit/scripts/release-core-cli-contract.test.ts
git -C navpay-admin commit -m "feat(release-core): add unified cli contract parser"
```

### Task 2: 实现统一版本计算与 tag 规则（admin core）

**Files:**
- Create: `navpay-admin/scripts/release-core/version.ts`
- Test: `navpay-admin/tests/unit/scripts/release-core-version.test.ts`

**Step 1: Write the failing test**

```ts
import { nextVersionForDate, normalizeVersionInput } from "../../../scripts/release-core/version";

test("starts from .0 when date tags absent", () => {
  expect(nextVersionForDate("26.04.14", [])).toBe("26.04.14.0");
});

test("increments max suffix", () => {
  expect(nextVersionForDate("26.04.14", ["v26.04.14.0", "v26.04.14.2"]))
    .toBe("26.04.14.3");
});

test("accepts v and plain version", () => {
  expect(normalizeVersionInput("v26.04.14.3")).toBe("26.04.14.3");
  expect(normalizeVersionInput("26.04.14.3")).toBe("26.04.14.3");
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/scripts/release-core-version.test.ts`
Expected: FAIL because functions are missing.

**Step 3: Write minimal implementation**

- `nextVersionForDate(dateYYMMDD, tags)`:
  - 仅处理 `vYY.MM.DD.N`。
  - 筛选当天 tag，取最大 `N`，无则 `0`。
- `toTag(version)` -> `v${version}`。
- `normalizeVersionInput()`：剥离 `v` 并校验格式 `YY.MM.DD.N`。

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/scripts/release-core-version.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git -C navpay-admin add scripts/release-core/version.ts tests/unit/scripts/release-core-version.test.ts
git -C navpay-admin commit -m "feat(release-core): unify date version policy"
```

### Task 3: 实现统一 Git 前置与远端 tag 校验（admin core）

**Files:**
- Create: `navpay-admin/scripts/release-core/git.ts`
- Test: `navpay-admin/tests/unit/scripts/release-core-git.test.ts`

**Step 1: Write the failing test**

```ts
import { buildPreflightCommands, buildTagPushCommands, buildTagVerifyCommand } from "../../../scripts/release-core/git";

test("preflight commands are fetch-tags then ff-only pull", () => {
  expect(buildPreflightCommands("origin", "main")).toEqual([
    ["git", ["fetch", "--tags", "--force", "origin"]],
    ["git", ["pull", "--ff-only", "origin", "main"]],
  ]);
});

test("verify command checks origin tag", () => {
  expect(buildTagVerifyCommand("v26.04.14.0")).toEqual([
    "git",
    ["ls-remote", "--exit-code", "--tags", "origin", "refs/tags/v26.04.14.0"],
  ]);
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/scripts/release-core-git.test.ts`
Expected: FAIL because module missing.

**Step 3: Write minimal implementation**

- 提供纯函数输出命令数组，避免测试依赖真实 git。
- 提供运行器封装用于 CLI 主流程调用。
- 错误消息统一：
  - 非 `main` 拒绝发布。
  - tag 不在 origin 拒绝部署。

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/scripts/release-core-git.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git -C navpay-admin add scripts/release-core/git.ts tests/unit/scripts/release-core-git.test.ts
git -C navpay-admin commit -m "feat(release-core): add git preflight and origin tag validation"
```

### Task 4: 组装 admin 核心 CLI 入口与发布记录目录

**Files:**
- Create: `navpay-admin/scripts/release-core/index.ts`
- Create: `navpay-admin/scripts/release-core/runner.ts`
- Modify: `navpay-admin/package.json`
- Test: `navpay-admin/tests/unit/scripts/release-core-runner.test.ts`

**Step 1: Write the failing test**

```ts
import { releaseOutputDir } from "../../../scripts/release-core/runner";

test("writes records under releases/<product>/<version>", () => {
  expect(releaseOutputDir("admin", "26.04.14.0"))
    .toContain("releases/admin/26.04.14.0");
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/scripts/release-core-runner.test.ts`
Expected: FAIL.

**Step 3: Write minimal implementation**

- `index.ts` 作为统一入口：
  - `release <product>`
  - `deploy <product> [--version]`
- `runner.ts` 负责：
  - 创建 `releases/<product>/<version>/`
  - 写 `metadata.json`、`steps.log`、`result.json`
- `package.json` 新增：
  - `"release": "tsx scripts/release-core/index.ts release"`
  - `"deploy": "tsx scripts/release-core/index.ts deploy"`
  - `"release-core:sync": "tsx scripts/release-core/sync.ts"`

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/scripts/release-core-runner.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git -C navpay-admin add scripts/release-core/index.ts scripts/release-core/runner.ts package.json tests/unit/scripts/release-core-runner.test.ts
git -C navpay-admin commit -m "feat(release-core): add unified release/deploy entry with release records"
```

### Task 5: admin product hooks（admin/checksum）接入 core

**Files:**
- Create: `navpay-admin/scripts/release-core/products/admin.ts`
- Create: `navpay-admin/scripts/release-core/products/checksum.ts`
- Modify: `navpay-admin/scripts/release-manager.ts`
- Test: `navpay-admin/tests/unit/scripts/release-core-products-admin.test.ts`

**Step 1: Write the failing test**

```ts
import { getSupportedProducts } from "../../../scripts/release-core/products";

test("admin repo supports admin and checksum only", () => {
  expect(getSupportedProducts()).toEqual(["admin", "checksum"]);
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/scripts/release-core-products-admin.test.ts`
Expected: FAIL.

**Step 3: Write minimal implementation**

- 为 `admin` 与 `checksum` 分别实现：
  - `release(product, context)`
  - `deploy(product, context)`
- `admin` release 内置宿主机依赖检查/安装钩子。
- `deploy` 只做 compose 文件下发 + `docker compose up -d`。

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/scripts/release-core-products-admin.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git -C navpay-admin add scripts/release-core/products/admin.ts scripts/release-core/products/checksum.ts scripts/release-manager.ts tests/unit/scripts/release-core-products-admin.test.ts
git -C navpay-admin commit -m "feat(admin-release): wire admin/checksum hooks into unified core"
```

### Task 6: 增加 core 同步工具（admin -> other repos）

**Files:**
- Create: `navpay-admin/scripts/release-core/sync.ts`
- Create: `navpay-admin/scripts/release-core/sync.manifest.json`
- Create: `navpay-android/tools/release-core-version.json`
- Create: `navpay-phonepe/scripts/release-core-version.json`
- Test: `navpay-admin/tests/unit/scripts/release-core-sync.test.ts`

**Step 1: Write the failing test**

```ts
import { planSyncTargets } from "../../../scripts/release-core/sync";

test("sync manifest includes android and phonepe", () => {
  const plan = planSyncTargets();
  expect(plan.map((x) => x.repo)).toEqual(expect.arrayContaining(["navpay-android", "navpay-phonepe"]));
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/scripts/release-core-sync.test.ts`
Expected: FAIL.

**Step 3: Write minimal implementation**

- `sync.manifest.json` 声明复制源/目标路径。
- `sync.ts` 执行 copy，并更新目标仓库 `release-core-version.json`。
- 输出同步摘要（文件数、目标仓库、来源 commit）。

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/scripts/release-core-sync.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git -C navpay-admin add scripts/release-core/sync.ts scripts/release-core/sync.manifest.json tests/unit/scripts/release-core-sync.test.ts
git -C navpay-admin commit -m "feat(release-core): add manual sync command for downstream repos"
```

### Task 7: 在 `navpay-android` 接入统一 release/deploy 入口

**Files:**
- Create: `navpay-android/tools/release_entry.sh`
- Create: `navpay-android/tools/deploy_entry.sh`
- Modify: `navpay-android/package.json`
- Modify: `navpay-android/tools/remote_release.sh`
- Test: `navpay-android/tools/release_entry.sh` (`bash -n` + dry-run)

**Step 1: Write the failing check**

Run: `cd navpay-android && yarn release android --dry-run`
Expected: FAIL because unified entry does not exist.

**Step 2: Implement minimal scripts**

- `release_entry.sh`：
  - 仅支持 `android`。
  - 执行 core preflight + version/tag。
  - 调用现有 apk release 流程并写版本信息文件。
- `deploy_entry.sh`：
  - 仅支持 `android`。
  - 支持 `--version`（可选）。
  - 拷贝 APK 到 download-site，原子更新 `current.json`，写本地记录。

**Step 3: Syntax verification**

Run:
- `cd navpay-android && bash -n tools/release_entry.sh`
- `cd navpay-android && bash -n tools/deploy_entry.sh`
Expected: PASS.

**Step 4: Dry-run verification**

Run:
- `cd navpay-android && yarn release android --dry-run`
- `cd navpay-android && yarn deploy android --dry-run`
Expected: 输出统一步骤日志，且不执行真实部署。

**Step 5: Commit**

```bash
git -C navpay-android add tools/release_entry.sh tools/deploy_entry.sh tools/remote_release.sh package.json tools/release-core-version.json
git -C navpay-android commit -m "feat(android-release): add unified release/deploy commands"
```

### Task 8: 在 `navpay-phonepe` 接入统一 release/deploy 入口

**Files:**
- Create: `navpay-phonepe/scripts/release_entry.sh`
- Create: `navpay-phonepe/scripts/deploy_entry.sh`
- Modify: `navpay-phonepe/package.json`
- Modify: `navpay-phonepe/scripts/remote_release.sh`
- Test: `navpay-phonepe/src/pipeline/orch/tests/test_cli_contract.py`

**Step 1: Write the failing test/check**

Run: `cd navpay-phonepe && yarn release phonepe --dry-run`
Expected: FAIL because unified entry does not exist.

**Step 2: Implement minimal scripts**

- `release_entry.sh`：
  - 仅支持 `phonepe`。
  - 调 core preflight + version/tag + orch release。
- `deploy_entry.sh`：
  - 仅支持 `phonepe`。
  - 拷贝至 download-site 后调用 admin 接口发布 URL。
  - 支持 `--version`，不传时走“本地最新 tag + origin 校验”。

**Step 3: Run syntax and contract checks**

Run:
- `cd navpay-phonepe && bash -n scripts/release_entry.sh`
- `cd navpay-phonepe && bash -n scripts/deploy_entry.sh`
- `cd navpay-phonepe && python3 -m pytest src/pipeline/orch/tests/test_cli_contract.py -q`
Expected: PASS.

**Step 4: Dry-run verification**

Run:
- `cd navpay-phonepe && yarn release phonepe --dry-run`
- `cd navpay-phonepe && yarn deploy phonepe --dry-run`
Expected: PASS with no remote side effects.

**Step 5: Commit**

```bash
git -C navpay-phonepe add scripts/release_entry.sh scripts/deploy_entry.sh scripts/remote_release.sh package.json scripts/release-core-version.json
git -C navpay-phonepe commit -m "feat(phonepe-release): add unified release/deploy commands"
```

### Task 9: 文档与 runbook 同步

**Files:**
- Modify: `navpay-admin/deploy/README.md`
- Modify: `docs/runbooks/prod-rollout-checklist-navpay.md`
- Modify: `docs/runbooks/android-release-pointer-publish.md`
- Modify: `docs/plans/2026-04-14-semi-manual-release-unification-design.md`

**Step 1: Write docs assertions (failing expectation)**

- 缺失 `yarn release <product>`/`yarn deploy <product>` 标准命令说明。
- 缺失版本策略 `YY.MM.DD.N` 与 `vYY.MM.DD.N` 的双格式说明。

**Step 2: Update docs minimally**

- 新增统一操作示例与失败排查。
- 明确“单产品部署、手工触发、无并发重试”。

**Step 3: Verify doc grep checks**

Run:
```bash
rg -n "yarn release <product>|yarn deploy <product>|YY\.MM\.DD\.N|vYY\.MM\.DD\.N" docs navpay-admin/deploy/README.md
```
Expected: 命中更新段落。

**Step 4: Commit**

```bash
git add navpay-admin/deploy/README.md docs/runbooks/prod-rollout-checklist-navpay.md docs/runbooks/android-release-pointer-publish.md docs/plans/2026-04-14-semi-manual-release-unification-design.md
git commit -m "docs(release): align runbooks with unified semi-manual flow"
```

### Task 10: 真实链路验收（手工半自动）

**Files:**
- Create: `docs/reports/2026-04-14-semi-manual-release-unification-verification.md`

**Step 1: Admin release/deploy dry-run and real-run**

Run:
- `cd navpay-admin && yarn release admin --dry-run`
- `cd navpay-admin && yarn deploy admin --dry-run`
- `cd navpay-admin && yarn release admin`
- `cd navpay-admin && yarn deploy admin`

Expected: tag 创建推送成功，部署日志完整，`releases/admin/<version>/` 存在三类记录文件。

**Step 2: Android release/deploy dry-run and real-run**

Run:
- `cd navpay-android && yarn release android --dry-run`
- `cd navpay-android && yarn deploy android --dry-run`
- `cd navpay-android && yarn release android`
- `cd navpay-android && yarn deploy android`

Expected: APK 产物可见，`current.json` 正确切换，记录文件完整。

**Step 3: PhonePe release/deploy dry-run and real-run**

Run:
- `cd navpay-phonepe && yarn release phonepe --dry-run`
- `cd navpay-phonepe && yarn deploy phonepe --dry-run`
- `cd navpay-phonepe && yarn release phonepe`
- `cd navpay-phonepe && yarn deploy phonepe`

Expected: 远端发布目录与 admin 接口激活均成功。

**Step 4: Publish verification report**

- 记录每个产品的版本号、tag、关键日志、结果截图/链接。
- 记录失败注入（例如 tag 不在 origin）验证确实阻断。

**Step 5: Commit**

```bash
git add docs/reports/2026-04-14-semi-manual-release-unification-verification.md
git commit -m "docs: add verification report for unified semi-manual release flow"
```
