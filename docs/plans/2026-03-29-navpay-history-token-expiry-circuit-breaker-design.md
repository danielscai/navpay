# Navpay History Token 过期熔断与可观测性设计

## 背景与问题

当前链路中：
- `navpay-phonepe` 通过 content provider/phonepehelper 持续提供快照能力，但 PhonePe 长时间后台时 token 可能不更新。
- `navpay-android` 历史交易同步在 token 已过期时仍会继续周期请求，导致持续失败与无效流量。
- `navpay-admin` 的 `navpay_history_transactions` 页缺乏“token 过期时间、客户端策略状态、探测间隔、下次探测”等关键可视化信息。

现场表现（已确认）：
- 设备页最近 token 时间停留在过去时刻（例如 `2026/3/28 22:43:59（7小时前）`）。
- 手动同步时报错：`历史交易请求失败(412): 上游前提条件未满足; exception=PR003; expiredTokens=AUTH_TOKEN; requestedMethod=POST`。

## 目标

1. `navpay-android` 在 token 过期后立即熔断，停止正常同步轮询。  
2. 客户端采用“事件驱动优先”的探测恢复策略，且探测指数退避可视化上报。  
3. `navpay-admin` 在 `?tab=navpay_history_transactions` 一眼看清：
   - token 最近过期时间（绝对时间 + 相对时间）
   - 当前策略状态
   - 当前探测间隔、下一次失败后间隔、下次探测时间
   - 最近探测触发来源与结果
   - 客户端状态上报时间
4. 提供状态事件审计能力，并控制事件数据量与清理成本。

## 非目标

- 不尝试绕过 PhonePe 自身 token 生命周期策略。  
- 不把失败恢复逻辑下沉到 admin 主动代替客户端执行。  
- 不在本期引入复杂消息中间件。

## 总体方案

### 1) Android 端状态机

状态：
- `RUNNING`：正常同步。
- `TOKEN_EXPIRED_OPEN`：命中 token 过期硬失败，熔断打开。
- `WAITING_TOKEN_REFRESH`：等待 token 更新事件或定时探测。
- `RECOVERY_PROBING`：执行一次恢复探测。

状态迁移核心规则：
- 同步请求返回 `412 + exception=PR003 + expiredTokens=AUTH_TOKEN` -> `TOKEN_EXPIRED_OPEN`。
- 进入熔断后停止正常同步轮询，仅保留探测。
- 探测成功 -> 立即回 `RUNNING`。
- 探测失败且仍 token 过期 -> 回 `WAITING_TOKEN_REFRESH`。

### 2) 探测策略（事件驱动优先）

默认退避序列：`60s -> 120s -> 240s -> ... -> 900s(15m上限)`。

关键规则：
- 熔断期间若收到 content provider token 更新事件，立即触发一次探测（不等 timer）。
- 只要收到新 token 事件：
  - 立即探测；
  - 无论本次探测成功或失败，退避基线都重置为 `60s`；
  - 后续失败再按 `60s -> 120s -> ...` 递增。
- 探测成功立即恢复 `RUNNING`，并重置退避。

### 3) 服务端可观测性

在 `navpay-admin` 增加“客户端状态 + 事件”数据层：
- 当前状态（每设备 1 行，覆盖最新状态与策略参数）
- 状态事件流（追加写，用于排障与追踪）

页面 `navpay_history_transactions` 增加“同步策略状态卡”：
- Token 最近过期时间：`YYYY/M/D HH:mm:ss（X小时前）`
- 当前状态
- 当前探测间隔（友好文案：秒/分钟）
- 下一次失败后探测间隔
- 下次探测时间（绝对 + 相对）
- 最近探测触发来源（`timer`/`token_event`）
- 最近探测结果（恢复/仍过期/临时失败）
- 策略版本与参数
- 最后状态上报时间

## 数据模型

### A. 当前状态表（1行/设备）

表名：`device_navpay_history_client_state`

建议字段：
- `device_id` PK
- `source_client_device_id`
- `strategy_version`
- `policy_json`（`initialProbeMs/maxProbeMs/multiplier` 等）
- `current_state`
- `state_changed_at_ms`
- `token_expired_at_ms`
- `last_token_event_at_ms`
- `backoff_current_ms`
- `backoff_next_ms`
- `next_probe_at_ms`
- `last_probe_trigger`
- `last_probe_at_ms`
- `last_probe_result`
- `last_probe_http_status`
- `last_probe_exception_code`
- `last_probe_expired_tokens`
- `last_report_at_ms`
- `updated_at_ms`

### B. 状态事件表（多行/设备）

表名：`device_navpay_history_client_events`

建议字段：
- `id` PK
- `device_id`
- `source_client_device_id`
- `event_type`
- `state_from`
- `state_to`
- `at_ms`
- `payload_json`
- `created_at_ms`

事件类型（最小集合）：
- `TOKEN_EXPIRED_OPENED`
- `PROBE_TRIGGERED_BY_TIMER`
- `PROBE_TRIGGERED_BY_TOKEN_EVENT`
- `PROBE_BACKOFF_RESET_BY_TOKEN_EVENT`
- `PROBE_FAILED_TOKEN_EXPIRED`
- `PROBE_FAILED_TRANSIENT`
- `RECOVERED_TO_RUNNING`

## 事件表体量控制与清理

- 保留窗口：7天。
- 每设备上限：500条。
- 仅记录“状态变化 + 探测结果/触发”，不记录每次常规轮询。

清理策略：
- 写入事件后做低频触发（每设备每10分钟最多一次）。
- 分两步删除：
  1. 删除超过 7 天事件；
  2. 删除每设备超过 500 条的最旧事件。
- 索引：
  - `(device_id, created_at_ms DESC)`
  - `(created_at_ms)`
- 单次清理批量上限（如 200）以降低抖动。

## API 合约

### 1) Android -> Admin 状态上报

`POST /api/personal/device/navpay-history-transactions/status`

请求体核心字段：
- `clientDeviceId`
- `strategyVersion`
- `policy`
- `state`
- `stateChangedAtMs`
- `tokenExpiredAtMs`
- `backoffCurrentMs`
- `backoffNextMs`
- `nextProbeAtMs`
- `lastProbe.trigger/result/httpStatus/exceptionCode/expiredTokens/atMs`
- `tokenEventAtMs`（如本次由 token 更新触发）
- `eventType`
- `eventPayload`

服务端行为：
- 校验 token + 设备归属
- upsert 当前状态表
- append 事件表
- 低频触发清理

### 2) Admin 页面读取扩展

`GET /api/admin/resources/devices/:deviceId/navpay-history-transactions`

新增 `meta.clientState` 和 `meta.clientEvents`（最近 N 条，默认 20）。

## UI 展示

`/admin/resources/devices/:id?tab=navpay_history_transactions`

新增卡片模块：
- `Token最近过期时间: 2026/3/28 23:47:12（6小时前）`
- `当前状态: WAITING_TOKEN_REFRESH`
- `当前探测间隔: 60秒`
- `下一次失败后: 120秒`
- `下次探测: 2026/3/29 08:03:12（35秒后）`
- `最近探测触发: token_event`
- `最近探测结果: 仍过期(412 PR003 AUTH_TOKEN)`
- `策略版本: android.history_sync.v1`
- `状态上报: 2026/3/29 08:02:37（10秒前）`

并展示最近事件时间线（可折叠）。

## 测试与验收标准

### 单元测试
- Android：状态机迁移、退避重置规则、token_event 立即探测。
- Admin：状态上报 route、状态 upsert、事件落库、清理逻辑、读取聚合。

### 集成/E2E
- 模拟器上触发以下场景：
  1. 正常运行
  2. token 过期触发熔断
  3. timer 探测失败并退避递增
  4. token 事件触发立即探测并重置退避
  5. 探测成功恢复 RUNNING
- 校验：
  - 页面状态卡实时变化正确
  - DB 两张表字段变化与页面一致
  - `device_navpay_history_sync_state` 与新增状态表逻辑一致不冲突

### 成功判定
- 页面可见真实动态数据而非静态 mock。  
- 可在数据库查询到与页面一致的状态与事件轨迹。  
- token 过期后不再按原正常频率持续请求历史交易。

