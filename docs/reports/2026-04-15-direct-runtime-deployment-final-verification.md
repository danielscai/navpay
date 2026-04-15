# Direct Runtime Deployment Final Verification (2026-04-15)

## Scope
- Plan: `2026-04-15-direct-runtime-deployment-simplification-implementation-plan.md`
- Execution order: Task 1 -> Task 10 (serial)
- Contract kept:
  - single-product release/deploy only
  - preflight: `git fetch --tags --force origin` + `git pull --ff-only origin main`
  - version/tag: `YY.MM.DD.N` + `vYY.MM.DD.N`
  - deploy default version from local latest valid tag + origin tag existence validation
  - unified release records under `releases/<product>/<version>/`

## Per-Repo Summary

### navpay-admin
- Completed:
  - direct runtime contract docs
  - direct deploy script (`pm2` + `nginx`)
  - release-core hook switch for admin
  - docker runtime path removed for admin service path
- Verification:
  - dry-run release/deploy passed
  - failure injection (`--version 99.99.99.9 --dry-run`) correctly blocked by origin tag check
- Blockers in real-run:
  1. release blocked by remote typecheck errors (`TS2737 BigInt target mismatch`, `TS2322`)
  2. deploy blocked because real-run requires host config for `remote-deploy-admin-direct.sh`

### navpay-android
- Completed:
  - release simplified to local package flow
  - deploy simplified to copy + atomic `current.json`
  - removed default dependency on `/opt/navpay/build-runner/...`
- Verification:
  - dry-run release/deploy passed
  - real-run release/deploy passed
  - failure injection correctly blocked by origin tag check

### navpay-phonepe
- Completed:
  - release path defaults to local package flow (no default remote host/runtime)
  - deploy path keeps copy + atomic pointer + activate API
- Verification:
  - dry-run release/deploy passed
  - failure injection correctly blocked by origin tag check
- Blockers in real-run:
  1. release blocked: missing `scripts/release_check.py`
  2. deploy blocked: missing local artifact `cache/profiles/full/build/patched_signed.apk`

## Cross-Cutting Findings
- “本地与远端 typecheck 差异”排查结果：核心不是命令差异，而是检查入口与代码/配置状态；`tsconfig target=ES2017` 与 BigInt 字面量冲突会在本地 `yarn typecheck` 复现。
- admin 连接问题中的本地 SOCKS5 代理已排除，SSH 直连可用。

## Rollback Guidance
1. admin: 回滚到上一稳定 tag，执行 `pm2 startOrReload ecosystem.config.cjs --env production`，再 `nginx -t && nginx -s reload`。
2. android/phonepe: 仅回滚 `download-site` 下 `current.json` pointer，不覆盖历史版本目录。
3. checksum/pg/redis: 按容器镜像 tag 回滚。

## Next Actions
1. 修复 navpay-admin typecheck 阻塞（ES target 与 BigInt/TS2322）。
2. 为 admin real deploy 提供稳定 host 配置注入（`NAVPAY_ADMIN_HOST` 或脚本参数透传）。
3. 修复 navpay-phonepe release quality-gate 脚本路径并确保 release 产物路径与 deploy 对齐。
