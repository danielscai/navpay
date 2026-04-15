# Semi-Manual Release/Deploy Unification Design (2026-04-14)

## 1. 背景与目标

当前多仓库发布流程存在入口不一致、版本规则不一致、自动化链路过重且不易验证的问题。目标是将发布改为“半自动化 + 人工触发验证”：

- 人工登录发布机器后手动执行命令。
- 统一命令入口与版本策略。
- 保留各产品差异化发布动作，但共享同一套前置与版本规则。
- 优先保证可理解、可验证、可追踪，而不是追求全自动触发。

## 2. 统一命令契约

所有仓库统一提供以下命令：

- `yarn release <product>`
- `yarn deploy <product> [--version <version>]`

`product` 全集统一为：`admin | checksum | android | phonepe`。

约束：每个仓库只实现自己负责的 product 子集；不支持的 product 必须明确报错并退出；不支持 `all` 这类多产品聚合入口。

## 3. 版本规则（全仓统一）

### 3.1 版本格式

- 业务版本：`YY.MM.DD.N`（例：`26.04.14.0`）
- Git Tag：`vYY.MM.DD.N`（例：`v26.04.14.0`）

说明：Tag 保留 `v` 前缀以兼容现有脚本和 tag 校验逻辑；对外展示与业务字段使用不带 `v` 的版本号。

### 3.2 `release` 版本生成

统一流程：

1. 强制校验当前分支必须是 `main`。
2. 执行 `git fetch --tags --force origin`。
3. 执行 `git pull --ff-only origin main`。
4. 从本仓库 tag 中筛选当天前缀 `vYY.MM.DD.*`。
5. 当天不存在 tag 时取 `YY.MM.DD.0`；存在时取最大 `N + 1`。
6. 自动创建并推送 tag：
   - `git tag -a vYY.MM.DD.N -m "release: vYY.MM.DD.N"`
   - `git push origin refs/tags/vYY.MM.DD.N`

### 3.3 `deploy` 默认版本选择

- 允许手动指定：`--version 26.04.14.0` 或 `--version v26.04.14.0`。
- 未指定时，默认从“本仓库最新 tag”解析部署版本。
- 在默认解析前，必须先执行：
  - `git fetch --tags --force origin`
  - `git pull --ff-only origin main`
- 无论手动还是默认，部署前必须校验目标 tag 在 `origin` 存在，否则报错退出。

## 4. 并发与失败策略

不对并发发布做自动重试，不做静默修复：

- `release` 推送 tag 失败时直接失败并暴露冲突。
- `deploy` 版本不存在/远端校验失败时直接失败。
- 错误信息必须定位到步骤、命令与退出码。

## 5. 发布核心代码组织策略

不引入独立 `navpay-release-core` 仓库。改为：

- 将共享发布核心维护在 `navpay-admin/scripts/release-core/`。
- 其他仓库通过手动同步命令 copy 到本仓库使用。
- 同步策略为“手动极简同步”，不做每次发布前自动同步。

建议附加约束（防漂移）：

- 每仓库保存 `release-core-version.json`，记录来源仓库、来源 commit、同步时间。
- `yarn release/deploy` 启动时打印当前 core 版本来源。

## 6. 各仓库职责边界

### 6.1 `navpay-admin`

支持：`release admin`、`release checksum`、`deploy admin`、`deploy checksum`。

- `release admin`：
  - 编译迁移到宿主机进行。
  - 发布前检查宿主机依赖，缺失时自动安装。
  - Docker 仅做“注入已构建产物 + 最小化镜像步骤”。
- `release checksum`：保持当前“编译一次可复用较久”的模式。
- `deploy admin/checksum`：
  - 仅复制 compose/配置到远端并执行 `docker compose up -d`。
  - 由 Docker 自身决定是否拉取新镜像并更新对应服务。

### 6.2 `navpay-android`

支持：`release android`、`deploy android`。

- `release android`：保持现有 APK 打包流程；继续把版本写入既有版本信息文件。
- `deploy android`：
  - 复制 APK 到 download-site 对应版本目录。
  - 更新 `current.json` 指向最新版本。
  - 生成本地发布记录 JSON。

### 6.3 `navpay-phonepe`

支持：`release phonepe`、`deploy phonepe`。

- `release phonepe`：保留现有“版本打入产物”的机制。
- `deploy phonepe`：
  - 复制发布产物到 download-site。
  - 调用 admin 接口上报当前版本与下载 URL，完成激活/发布。

## 7. 统一目录与发布记录

每仓库统一发布记录目录：

- `releases/<product>/<version>/`

最小记录文件：

- `metadata.json`：版本、tag、仓库、commit、触发时间。
- `steps.log`：步骤执行日志。
- `result.json`：成功/失败结果与错误摘要。

## 8. 运维与可靠性约束

### 8.1 `current.json` 原子更新

更新指针文件必须使用“临时文件 + 原子替换（mv）”模式，避免中断导致指针损坏。

### 8.2 admin 宿主机依赖管理

依赖清单必须固定（工具名 + 最低版本）。脚本仅在缺失时安装，避免隐式升级导致不可控变化。

### 8.3 phonepe 发布接口幂等

建议接口请求携带稳定 `releaseKey`（如 `phonepe:<version>`），重复发布同一版本返回同一发布结果，避免重复激活。

## 9. 端到端验收标准

每个产品最少完成一次真实手工链路验证：

1. `yarn release <product>` 成功。
2. `yarn deploy <product>` 成功。
3. 线上/目标环境验证产物可用。
4. `releases/<product>/<version>/` 记录完整。
5. 失败场景可从日志直接定位具体步骤与错误。

## 10. 非目标（本阶段不做）

- 不引入全自动触发发布（CI 自动触发）。
- 不做跨会话并发自动冲突重试。
- 不引入独立 release-core 新仓库。
- 不改变各产品后半段差异化业务发布流程。
