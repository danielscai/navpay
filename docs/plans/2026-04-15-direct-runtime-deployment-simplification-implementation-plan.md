# Direct Runtime Deployment Simplification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 `navpay-admin` 运行态从 Docker runtime 切换为 direct runtime（pm2 + nginx），并在保持 release/deploy 契约与版本规则不变前提下，按 `admin -> android -> phonepe` 顺序完成最小复杂度发布链路。

**Architecture:** 仅保留 `checksum/pg/redis` 容器；`admin/reverse-proxy/download-site` 改为宿主机 direct runtime。统一入口继续使用 `yarn release <product>` 与 `yarn deploy <product> [--version]`。逐仓改造与验收，单阶段通过后再进入下一阶段。

**Tech Stack:** TypeScript (`tsx`) + Bash + PM2 + Nginx + Git tags + rsync/scp + Docker Compose (infra only).

---

### Task 1: 定义 direct runtime 服务器契约（admin）

**Files:**
- Create: `navpay-admin/docs/deploy/direct-runtime-contract.md`
- Modify: `navpay-admin/deploy/README.md`
- Test: `rg` 文档命中检查

**Step 1: Write the failing doc expectation**

- 预期文档缺失以下明确项（当前应不完整）：
  - pm2 管理 admin
  - nginx 多 conf 分站点
  - admin 不再使用 docker runtime

**Step 2: Verify expectation (fails)**

Run:
```bash
cd navpay-admin && rg -n "pm2|direct runtime|nginx conf|no docker runtime" deploy/README.md docs/deploy/direct-runtime-contract.md
```
Expected: 命中不足或文件不存在。

**Step 3: Write minimal contract docs**

- 新增 direct runtime contract，定义：
  - `/opt/navpay/admin`
  - `/opt/navpay/download-site`
  - `/etc/nginx/conf.d/navpay-admin.conf`
  - `/etc/nginx/conf.d/navpay-download.conf`
  - `pm2 reload/start` + `nginx -t && nginx -s reload`
- 在 `deploy/README.md` 标注 admin runtime 已切 direct。

**Step 4: Verify docs updated**

Run:
```bash
cd navpay-admin && rg -n "pm2|direct runtime|nginx conf|no docker runtime|/opt/navpay/admin|/opt/navpay/download-site" deploy/README.md docs/deploy/direct-runtime-contract.md
```
Expected: 命中新增段落。

**Step 5: Commit**

```bash
git -C navpay-admin add docs/deploy/direct-runtime-contract.md deploy/README.md
git -C navpay-admin commit -m "docs(deploy): define direct runtime contract for admin"
```

### Task 2: 增加 admin direct runtime 部署脚本（pm2 + nginx）

**Files:**
- Create: `navpay-admin/scripts/remote-deploy-admin-direct.sh`
- Create: `navpay-admin/scripts/templates/ecosystem.config.cjs`
- Create: `navpay-admin/scripts/templates/nginx/navpay-admin.conf`
- Create: `navpay-admin/scripts/templates/nginx/navpay-download.conf`
- Test: `bash -n` + dry-run

**Step 1: Write failing check**

Run:
```bash
cd navpay-admin && test -f scripts/remote-deploy-admin-direct.sh
```
Expected: 非 0（文件不存在）。

**Step 2: Implement minimal scripts/templates**

- `remote-deploy-admin-direct.sh` 功能：
  - 参数：`--tag`、`--host`、`--workdir`、`--dry-run`
  - 服务器端：
    1. `git fetch --tags --force origin`
    2. `git checkout -f tags/<tag>`
    3. `yarn install --immutable`
    4. `yarn build`
    5. `pm2 startOrReload ecosystem.config.cjs --env production`
    6. `nginx -t && nginx -s reload`
- 提供 pm2/nginx 模板文件用于下发。

**Step 3: Syntax verification**

Run:
```bash
cd navpay-admin && bash -n scripts/remote-deploy-admin-direct.sh
```
Expected: PASS.

**Step 4: Dry-run verification**

Run:
```bash
cd navpay-admin && bash scripts/remote-deploy-admin-direct.sh --tag v26.04.15.0 --dry-run
```
Expected: 打印 direct runtime 步骤，不执行真实远端变更。

**Step 5: Commit**

```bash
git -C navpay-admin add scripts/remote-deploy-admin-direct.sh scripts/templates/ecosystem.config.cjs scripts/templates/nginx/navpay-admin.conf scripts/templates/nginx/navpay-download.conf
git -C navpay-admin commit -m "feat(admin-deploy): add direct runtime deploy script with pm2 and nginx"
```

### Task 3: 将 release-core admin hooks 切到 direct runtime

**Files:**
- Modify: `navpay-admin/scripts/release-core/products/admin.ts`
- Modify: `navpay-admin/scripts/release-core/products/checksum.ts` (确保 checksum 保持容器路径)
- Modify: `navpay-admin/scripts/release-core/products/index.ts`
- Test: `navpay-admin/tests/unit/scripts/release-core-products-admin.test.ts`

**Step 1: Write failing test expectation**

在 `release-core-products-admin.test.ts` 增加断言：
- admin deploy/release 目标命令不再依赖 `remote-deploy-admin.sh`（docker runtime）。

**Step 2: Run test to verify fail**

Run:
```bash
cd navpay-admin && yarn test tests/unit/scripts/release-core-products-admin.test.ts
```
Expected: FAIL（行为未更新）。

**Step 3: Minimal implementation**

- admin hooks 改为调用 direct runtime 脚本。
- checksum hooks 保持现有容器路径调用。

**Step 4: Run test to verify pass**

Run:
```bash
cd navpay-admin && yarn test tests/unit/scripts/release-core-products-admin.test.ts
```
Expected: PASS.

**Step 5: Commit**

```bash
git -C navpay-admin add scripts/release-core/products/admin.ts scripts/release-core/products/checksum.ts scripts/release-core/products/index.ts tests/unit/scripts/release-core-products-admin.test.ts
git -C navpay-admin commit -m "feat(release-core): switch admin hooks to direct runtime deploy"
```

### Task 4: 下线 admin runtime 的 docker compose 调用路径

**Files:**
- Modify: `navpay-admin/scripts/remote-deploy-admin.sh`
- Modify: `navpay-admin/scripts/release-manager.ts`
- Test: `navpay-admin/tests/unit/scripts/release-manager-cli.test.ts`

**Step 1: Write failing expectation**

- 增加测试：`deploy admin` 不应拼接 `docker compose ... admin/reverse-proxy`。

**Step 2: Run targeted test (expect fail)**

Run:
```bash
cd navpay-admin && yarn test tests/unit/scripts/release-manager-cli.test.ts
```
Expected: FAIL.

**Step 3: Minimal implementation**

- 保留 checksum/infra compose 流程。
- admin profile 改为 direct runtime 路径转发。

**Step 4: Re-run test (expect pass)**

Run:
```bash
cd navpay-admin && yarn test tests/unit/scripts/release-manager-cli.test.ts
```
Expected: PASS.

**Step 5: Commit**

```bash
git -C navpay-admin add scripts/remote-deploy-admin.sh scripts/release-manager.ts tests/unit/scripts/release-manager-cli.test.ts
git -C navpay-admin commit -m "refactor(admin-deploy): remove docker runtime path for admin service"
```

### Task 5: admin 阶段链路验收（先过再推进下一仓）

**Files:**
- Create: `docs/reports/2026-04-15-direct-runtime-admin-verification.md`

**Step 1: Dry-run checks**

Run:
```bash
cd navpay-admin && yarn release admin --dry-run
cd navpay-admin && yarn deploy admin --dry-run
```
Expected: PASS，步骤日志显示 pm2/nginx direct runtime。

**Step 2: Real-run checks**

Run:
```bash
cd navpay-admin && yarn release admin
cd navpay-admin && yarn deploy admin
```
Expected: PASS 或明确外部阻塞（远端连接/权限），且 `releases/admin/<version>/` 记录完整。

**Step 3: Failure injection check**

Run:
```bash
cd navpay-admin && yarn deploy admin --version 99.99.99.9 --dry-run
```
Expected: 因 origin 不存在 tag 阻断。

**Step 4: Write report**

- 落盘命令、结果摘要、阻塞点、恢复建议。

**Step 5: Commit**

```bash
git add docs/reports/2026-04-15-direct-runtime-admin-verification.md
git commit -m "docs: add admin direct-runtime deployment verification report"
```

### Task 6: 简化 navpay-android 发布链路（仅打包+copy）

**Files:**
- Modify: `navpay-android/tools/release_entry.sh`
- Modify: `navpay-android/tools/deploy_entry.sh`
- Modify: `navpay-android/tools/remote_release.sh`
- Modify: `navpay-android/package.json`
- Test: bash syntax + dry-run

**Step 1: Write failing check**

Run:
```bash
cd navpay-android && yarn release android --dry-run
```
Expected: FAIL 或输出包含远端构建分支（待移除）。

**Step 2: Minimal implementation**

- release(android)：本地打包 + tag +记录。
- deploy(android)：copy + atomic current.json +记录。
- 去除对 `/opt/navpay/build-runner/...` 的默认依赖。

**Step 3: Syntax checks**

Run:
```bash
cd navpay-android && bash -n tools/release_entry.sh
cd navpay-android && bash -n tools/deploy_entry.sh
```
Expected: PASS.

**Step 4: Dry-run checks**

Run:
```bash
cd navpay-android && yarn release android --dry-run
cd navpay-android && yarn deploy android --dry-run
```
Expected: PASS，且仅包含打包+copy逻辑。

**Step 5: Commit**

```bash
git -C navpay-android add tools/release_entry.sh tools/deploy_entry.sh tools/remote_release.sh package.json
git -C navpay-android commit -m "refactor(android-release): simplify to package and copy flow"
```

### Task 7: android 阶段链路验收

**Files:**
- Create: `docs/reports/2026-04-15-direct-runtime-android-verification.md`

**Step 1: Run admin-independent checks**

Run:
```bash
cd navpay-android && yarn release android --dry-run
cd navpay-android && yarn deploy android --dry-run
cd navpay-android && yarn release android
cd navpay-android && yarn deploy android
```
Expected: PASS 或明确阻塞并落盘。

**Step 2: Failure injection**

Run:
```bash
cd navpay-android && yarn deploy android --version 99.99.99.9 --dry-run
```
Expected: origin tag check block。

**Step 3: Write report**

**Step 4: Commit**

```bash
git add docs/reports/2026-04-15-direct-runtime-android-verification.md
git commit -m "docs: add android simplified deployment verification report"
```

### Task 8: 简化 navpay-phonepe 发布链路（打包+copy+activate API）

**Files:**
- Modify: `navpay-phonepe/scripts/release_entry.sh`
- Modify: `navpay-phonepe/scripts/deploy_entry.sh`
- Modify: `navpay-phonepe/scripts/remote_release.sh`
- Modify: `navpay-phonepe/package.json`
- Test: bash syntax + pytest contract + dry-run

**Step 1: Write failing check**

Run:
```bash
cd navpay-phonepe && yarn release phonepe --dry-run
```
Expected: FAIL 或仍走远端运行态路径。

**Step 2: Minimal implementation**

- release(phonepe)：本地打包 + tag +记录。
- deploy(phonepe)：copy + atomic current.json + 调 admin API +记录。

**Step 3: Syntax/contract checks**

Run:
```bash
cd navpay-phonepe && bash -n scripts/release_entry.sh
cd navpay-phonepe && bash -n scripts/deploy_entry.sh
cd navpay-phonepe && python3 -m pytest src/pipeline/orch/tests/test_cli_contract.py -q
```
Expected: PASS.

**Step 4: Dry-run checks**

Run:
```bash
cd navpay-phonepe && yarn release phonepe --dry-run
cd navpay-phonepe && yarn deploy phonepe --dry-run
```
Expected: PASS，输出简化链路步骤。

**Step 5: Commit**

```bash
git -C navpay-phonepe add scripts/release_entry.sh scripts/deploy_entry.sh scripts/remote_release.sh package.json
git -C navpay-phonepe commit -m "refactor(phonepe-release): simplify to package copy and activate flow"
```

### Task 9: phonepe 阶段链路验收

**Files:**
- Create: `docs/reports/2026-04-15-direct-runtime-phonepe-verification.md`

**Step 1: Run checks**

Run:
```bash
cd navpay-phonepe && yarn release phonepe --dry-run
cd navpay-phonepe && yarn deploy phonepe --dry-run
cd navpay-phonepe && yarn release phonepe
cd navpay-phonepe && yarn deploy phonepe
```
Expected: PASS 或明确阻塞并落盘。

**Step 2: Failure injection**

Run:
```bash
cd navpay-phonepe && yarn deploy phonepe --version 99.99.99.9 --dry-run
```
Expected: origin tag check block。

**Step 3: Write report**

**Step 4: Commit**

```bash
git add docs/reports/2026-04-15-direct-runtime-phonepe-verification.md
git commit -m "docs: add phonepe simplified deployment verification report"
```

### Task 10: 汇总 runbook 与最终验收

**Files:**
- Modify: `docs/runbooks/prod-rollout-checklist-navpay.md`
- Modify: `docs/runbooks/android-release-pointer-publish.md`
- Modify: `navpay-admin/deploy/README.md`
- Create: `docs/reports/2026-04-15-direct-runtime-deployment-final-verification.md`

**Step 1: Update runbooks**

- 标注 direct runtime + pm2 + nginx 多 conf。
- 标注 checksum/pg/redis 仍容器。

**Step 2: Verify doc consistency**

Run:
```bash
cd /Users/danielscai/Documents/workspace/navpay && rg -n "pm2|nginx|direct runtime|checksum|postgres|redis|yarn release <product>|yarn deploy <product>" docs navpay-admin/deploy/README.md
```
Expected: 命中更新条目。

**Step 3: Final report**

- 汇总三个仓库真实链路结果与阻塞点。
- 附回滚方案与下一步动作。

**Step 4: Commit**

```bash
git add docs/runbooks/prod-rollout-checklist-navpay.md docs/runbooks/android-release-pointer-publish.md navpay-admin/deploy/README.md docs/reports/2026-04-15-direct-runtime-deployment-final-verification.md
git commit -m "docs(deploy): finalize direct runtime rollout runbooks and verification"
```
