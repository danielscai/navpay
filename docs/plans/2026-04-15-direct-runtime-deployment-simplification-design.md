# Direct Runtime Deployment Simplification Design (2026-04-15)

## 1. 背景

当前半自动发布链路已经统一了 `yarn release <product>` / `yarn deploy <product> [--version]` 与版本规则，但 `admin` 运行态仍依赖远端 Docker Runtime（admin/reverse-proxy/download-site），导致部署链路出现与业务无关的阻塞点：

1. 远端 SSH 链路不稳定导致发布中断。
2. 远端目录权限与容器编排耦合，排障路径过长。
3. Nginx/静态站点与应用 runtime 同时存在容器与宿主机路径，维护成本高。

本设计目标是将运行态复杂度降低到“直接部署 + 进程管理 + 单机 nginx 多配置”。

---

## 2. 目标与非目标

## 2.1 目标

1. `admin` 运行态从 Docker 切换为宿主机直接运行：`pm2 + next start`。
2. `nginx` 不再走容器，改为同一个宿主机 nginx，通过多个 conf 管不同站点。
3. `download-site` 作为宿主机静态目录，独立 nginx conf。
4. 保留发布契约与版本规则：
   - `yarn release <product>`
   - `yarn deploy <product> [--version]`
   - `YY.MM.DD.N` + `vYY.MM.DD.N`
   - preflight 强制：`git fetch --tags --force origin` 与 `git pull --ff-only origin main`
5. `android` / `phonepe` 保持极简：打包 -> copy ->（phonepe 额外调用 admin API）。
6. `checksum`、`postgres`、`redis` 继续保留容器运行。

## 2.2 非目标

1. 不改变 release/deploy 命令契约。
2. 不引入全自动 CI 触发发布。
3. 不在本阶段移除 checksum/pg/redis 容器。
4. 不引入多节点高可用方案。

---

## 3. 架构决策

## 3.1 Admin Runtime 形态

采用“服务器构建 + 服务器部署”：

1. release(admin): 在服务器 `git checkout tag` 后执行 `yarn install --immutable && yarn build`。
2. deploy(admin): 在服务器执行 `pm2 reload/start`，再执行 `nginx -t && nginx -s reload`。

## 3.2 Nginx 形态

1. 单一 nginx 服务进程。
2. 多 conf 文件分站点：
   - `site-admin.conf`（反代 admin）
   - `site-download.conf`（静态 download-site）
3. 通过 `include` 合并管理，保持部署与回滚简单。

## 3.3 Infra 保留容器

仅保留容器场景：

1. `phonepe-checksum`
2. `postgres`
3. `redis`

admin/reverse-proxy/download-site 不再由 compose 负责 runtime。

---

## 4. 目录与运行约定（服务器）

建议固定：

1. `/opt/navpay/admin`：admin 代码与构建目录。
2. `/opt/navpay/download-site`：静态文件根目录。
3. `/etc/nginx/conf.d/navpay-admin.conf`：admin 站点配置。
4. `/etc/nginx/conf.d/navpay-download.conf`：download 站点配置。
5. `/opt/navpay/admin/ecosystem.config.cjs`：pm2 配置。

---

## 5. 各仓库职责

## 5.1 navpay-admin

支持：`release admin/checksum`、`deploy admin/checksum`。

1. `release admin`：
   - main + preflight
   - 计算/推送 tag
   - 服务器执行 build（非容器）
2. `deploy admin`：
   - pm2 reload/start
   - nginx reload
3. `release/deploy checksum`：继续现有容器路径。

## 5.2 navpay-android

支持：`release android`、`deploy android`。

1. release：打包 APK + tag。
2. deploy：复制到 download-site 版本目录，原子更新 `current.json`。

## 5.3 navpay-phonepe

支持：`release phonepe`、`deploy phonepe`。

1. release：打包产物 + tag。
2. deploy：复制到 download-site + 调 admin 发布 API（带 `releaseKey`）。

---

## 6. 数据与发布记录

保持统一记录目录：

- `releases/<product>/<version>/metadata.json`
- `releases/<product>/<version>/steps.log`
- `releases/<product>/<version>/result.json`

失败路径必须记录错误摘要，不做静默恢复。

---

## 7. 风险与缓解

1. 风险：服务器 Node/pm2/nginx 版本漂移。
   - 缓解：固定运行时版本基线与安装脚本。
2. 风险：pm2 进程配置漂移。
   - 缓解：`ecosystem.config.cjs` 入库并由 deploy 脚本校验。
3. 风险：nginx 配置变更导致站点不可用。
   - 缓解：部署时强制 `nginx -t`，失败不 reload。
4. 风险：迁移期双路径（docker runtime 与 direct runtime）并存。
   - 缓解：按仓库分阶段切换，保留短期回滚开关。

---

## 8. 分阶段实施顺序

1. Phase 1：`navpay-admin`（先切 runtime）
2. Phase 2：`navpay-android`（验证 copy + pointer）
3. Phase 3：`navpay-phonepe`（验证 copy + activate API）
4. Phase 4：文档/runbook/最终验收

原则：每一阶段通过真实链路验证后再进入下一阶段。

---

## 9. 验收标准

每产品必须至少满足：

1. `yarn release <product>` 能完成或在明确外部阻塞处停止并落盘。
2. `yarn deploy <product>` 能完成或在明确外部阻塞处停止并落盘。
3. 不传 `--version` 时，默认版本推导与 origin tag 校验有效。
4. 失败注入（origin 不存在 tag）可稳定阻断。
5. 发布记录完整可追溯。
