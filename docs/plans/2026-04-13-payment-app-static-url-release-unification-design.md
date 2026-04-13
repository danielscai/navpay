# Payment App Static URL Release Unification Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 phonepe 与 download-site 的 APK 发布统一为“静态文件 URL 发布 + admin 注册激活”模式，彻底绕开大文件 HTTP 上传链路，保留幂等、可回滚、审计能力。

**Architecture:** 发布流程拆为两个阶段：`build bundle`（纯本地产物）与 `publish bundle`（上传静态目录并向 admin 提交 manifestUrl）。admin 新增 `from-manifest` 接口做服务端校验与入库，客户端继续通过 admin 既有分发接口获取稳定 manifest 结构，避免 Android 端同步大改。静态目录采用不可变路径，回滚只做 release 切换或 pointer 切换，不覆盖历史文件。

**Tech Stack:** `navpay-phonepe` orch (Python), `navpay-admin` Next.js Route Handlers + PostgreSQL, download-site + Nginx + Cloudflare。

---

## 1. 现状与问题

### 1.1 现状链路
- `orch release phonepe` 当前是“一体化”：创建 release -> 上传 artifacts -> activate（HTTP multipart）。
- admin 发布模型当前以“上传二进制并落盘”为核心。
- download-site 当前仍有“镜像内置 APK”的发布路径，不是统一的产物目录 copy 模式。

### 1.2 主要问题
- 大文件上传链路易触发网关超时/502。
- 发布模型存在双路径（admin 上传 vs download-site 镜像打包），维护成本高。
- manifest 结构存在“输入 manifest”与“客户端消费 manifest”潜在分叉风险。
- 幂等键若不带环境维度，test/prod 可能冲突。

## 2. 统一后目标架构（简化版）

### 2.1 核心原则
- `orch release` 只做本地构建，不触网。
- `orch publish` 负责上传静态文件 + 调 admin 注册发布。
- admin 对发布输入只接受 `manifestUrl`，服务端拉取并校验。
- 静态目录不可变，只新增不覆盖。
- Android 客户端消费协议保持稳定，由 admin 统一输出。

### 2.2 统一发布流程
1. 本地构建：`orch release <app>` 生成 bundle 目录。
2. 上传静态文件：`orch publish <app> --bundle ... --test|--prod`（固定 ssh 上传）。
3. orch 调 admin：`POST /api/publisher/payment-apps/{appId}/releases/from-manifest`。
4. admin 拉取 manifest 校验，入库 release/artifacts，按参数决定是否 activate。
5. 客户端仍通过 admin 现有 personal manifest endpoint 获取可安装清单。

### 2.3 目录与 URL 规范
- 宿主机根目录：`/data/download-site/payment-apps`
- 不可变发布目录：`/<appId>/releases/<versionName>/<baseSha256>/`
- 目录内标准文件：
  - `manifest.json`
  - `base.apk`（若该 app 存在 base）
  - `split_config.*.apk`（可选多个）
  - `checksums.txt`（可选，仅排障）
- 外网 URL 形态：
  - `https://download.navpay.site/payment-apps/<appId>/releases/<versionName>/<baseSha256>/manifest.json`

## 3. 数据契约（单一真相）

### 3.1 发布输入 manifest（上传侧）
- 必填：
  - `schemaVersion`
  - `appId`
  - `versionName`
  - `versionCode`
  - `packageName`
  - `baseSha256`
  - `signingDigest`
  - `artifacts[]`（`name/type/url/sha256/size`）
  - `constraints.requiredArtifactTypes`（例如 `["base","abi","density"]`）
  - `createdAt`
- 约束：
  - `artifacts[].url` 全可访问。
  - base 与所有 split 签名一致。
  - required types 在当前 release 中齐全。

### 3.2 客户端消费 manifest（下载侧）
- 保持当前 Android 已消费结构：`files + rules + fallbackPolicy`。
- admin 内部将上传 manifest 映射为客户端 manifest，避免客户端联动改造。

## 4. API 设计

### 4.1 新增 publisher 接口
- `POST /api/publisher/payment-apps/{appId}/releases/from-manifest`
- 请求体：
  - `manifestUrl`
  - `releaseKey`
  - `targetEnv`（`test|prod`）
  - `activate`（可选，默认 `true`）

### 4.2 服务端行为
1. 校验 manifest URL（域名白名单、协议限制、禁止私网地址）。
2. 拉取并解析 manifest，做 schema 校验。
3. 探测 artifacts 可达性并校验 hash/size/signingDigest。
4. 幂等检查并写库（release + artifacts + events）。
5. `activate=true` 时执行激活流程。

### 4.3 错误码
- `manifest_fetch_failed`
- `manifest_invalid`
- `artifact_unreachable`
- `split_missing`
- `signature_mismatch`
- `release_idempotent_conflict`

### 4.4 幂等键
- `appId + targetEnv + versionCode + baseSha256`

## 5. CLI 设计（orch）

### 5.1 `orch release <app>`
- 默认纯本地出包，输出 bundle 路径与 `manifest.json`。
- 不调用 admin，不上传。

### 5.2 `orch publish <app>`
- 仅支持 `ssh` 上传模式，不支持 HTTP 上传回退。
- 推荐参数：
  - `--bundle <path>`
  - `--test | --prod`
  - `--remote-host`
  - `--remote-base-dir`
  - `--download-base-url`
  - `--yes-prod`
- `prod` 发布必须显式 `--prod --yes-prod` 双确认。

### 5.3 SSH 模式流程
1. 校验本地 bundle 与 manifest 自洽。
2. `rsync/scp` 上传到不可变目录。
3. 拼接 `manifestUrl`。
4. 调用 admin `from-manifest`。

## 6. download-site 改造（并轨）

### 6.1 新模型
- download-site 不再承载“镜像内置 APK 发布职责”。
- download-site 仅负责静态目录托管与缓存策略。
- 发布动作变为 `copy/rsync` 新目录，必要时更新 pointer（如 `current.json`）。

### 6.2 Nginx/缓存
- 不可变路径（APK + manifest）：`Cache-Control: public, max-age=31536000, immutable`
- pointer 文件（`current.json`）：短缓存（`max-age=60`）
- `etag on`
- `autoindex off`（禁止目录遍历）

## 7. 安全与审计

- 仅允许白名单域名作为 `manifestUrl` 来源。
- 阻断 SSRF：禁止解析到内网/回环/链路本地地址。
- 上传目录仅发布账号可写，对外只读。
- 发布全链路记录 `requestId` 与审计事件。

## 8. 分阶段实施计划

### 8.0 当前落地状态（2026-04-13）

- Task 1：已完成（设计文档 + 两份 runbook 已更新为静态 URL/pointer 模型）。
- Task 2：已完成（`from-manifest` 路由、服务、错误码映射、单测覆盖）。
- Task 3：已完成（`orch release` 本地化、`orch publish` 固定 SSH、无 HTTP fallback）。
- Task 4：已完成（download-site 静态托管并轨，发布改为 rsync/copy，不再依赖内置 APK 镜像构建）。
- Task 5：代码与文档已完成；灰度演练与连续 10 次稳定性回归属于环境执行项，需在 test/prod 环境按 runbook 执行留痕。

### Task 1: 固化设计与契约

**Files:**
- Create: `docs/plans/2026-04-13-payment-app-static-url-release-unification-design.md`
- Update: `docs/runbooks/android-release-pointer-publish.md`
- Update: `docs/runbooks/cloudflare-origin-cache-policy.md`

**Steps:**
1. 明确统一流程、接口契约、幂等键与错误码。
2. 将不可变路径与 pointer 缓存策略分层写入 runbook。
3. 明确 download-site 并轨规则（去镜像内置 APK）。

**验收:**
- 文档中可直接提取 API 契约与 CLI 参数，不依赖口头约定。

### Task 2: admin 增加 from-manifest 发布入口

**Files:**
- Create: `navpay-admin/src/app/api/publisher/payment-apps/[appId]/releases/from-manifest/route.ts`
- Modify: `navpay-admin/src/lib/payment-app-release-service.ts`
- Test: `navpay-admin/tests/unit/publisher-payment-app-release-routes.test.ts`

**Steps:**
1. 新增 route handler 与 schema 校验。
2. 实现 manifest 拉取、artifact 校验、幂等写库。
3. 接入激活逻辑与错误码映射。
4. 补充缺字段/hash 不匹配/split 缺失/签名不一致/幂等冲突测试。

**验收:**
- `yarn test` 对新增用例通过。
- 同一幂等键重复请求返回同一 release（或明确幂等冲突）。

### Task 3: orch 拆分 release/publish

**Files:**
- Modify: `navpay-phonepe/src/pipeline/orch/orchestrator.py`
- Modify: `navpay-phonepe/src/pipeline/orch/README.md`
- Test: `navpay-phonepe/src/pipeline/orch/tests/test_cli_contract.py`

**Steps:**
1. 将现有 `release` 改为仅生成 bundle。
2. 新增 `publish` 子命令（默认 ssh）。
3. 增加 `--test|--prod` + `--yes-prod` 保护。
4. 对接 admin `from-manifest`。

**验收:**
- `release` 不触发网络请求。
- `publish --test` 可完成 e2e 发布注册。

### Task 4: download-site 并轨为静态托管

**Files:**
- Modify: `navpay-admin/download-site/nginx.conf`
- Modify: `navpay-admin/scripts/release-manager.ts`
- Test: `navpay-admin/tests/unit/download-site/versioned-apk-build-contract.test.ts`

**Steps:**
1. 移除/弱化“镜像内置 APK”流程。
2. 保留 Nginx 纯静态与缓存职责。
3. 调整脚本为目录 copy/同步。

**验收:**
- download-site 发布不再依赖重建包含 APK 的镜像。

### Task 5: 灰度与回归

**Files:**
- Update: `docs/runbooks/prod-rollout-checklist-navpay.md`
- Update: `navpay-admin/docs/ops/payment-app-release-runbook.md`

**Steps:**
1. 在 `--test` 环境完成灰度演练。
2. 跑稳定性回归（连续 10 次发布）。
3. 通过后再放开 `--prod --yes-prod`。

**验收:**
- 无 502 上传失败。
- 回滚仅切 active release/pointer，不改历史静态目录。

## 9. 测试清单（最小闭环）

- 本地 bundle 完整性测试（manifest + artifacts + checksum）。
- `publish --test` 端到端发布测试。
- 负例：字段缺失、sha 不匹配、split 缺失、签名不一致。
- 幂等：同幂等键重复发布。
- 稳定性：连续 10 次发布无中断。
- 缓存与可访问性：immutable 路径命中缓存，pointer 可快速切换。

## 10. 迁移与回滚策略

- 迁移期直接切换到 `ssh/static + from-manifest`，不保留 HTTP 上传 fallback。
- 旧 `multipart artifacts` 发布入口标记废弃并尽快回收代码，避免双路径长期共存。
- 业务回滚只做 release 激活切换，不覆盖静态目录历史文件。
