# Cross-App Redis Heartbeat Isolation Design

**Date:** 2026-03-29  
**Scope:** `navpay-admin`, `navpay-android`, `navpay-phonepe`

## 1. 背景与目标

当前支付 App 心跳（如 `app://phonepe/heartbeat`）会进入 `http_intercept_logs`，再由后台页面从该日志表反推在线状态和最后心跳时间。这会造成两类问题：

1. 心跳语义与请求拦截日志耦合，无法做到独立演进。
2. 心跳读取路径依赖数据库写入，和“轻量在线探活”目标不一致。

本方案将心跳能力完全隔离为 Redis-only 机制：

- 心跳不再进入 `http_intercept_logs`。
- 心跳不落数据库。
- 心跳 key 采用 `appName + clientDeviceId`（设备维度）。
- `navpay-admin` 暴露统一心跳接口，支持多个 App 复用。
- 设备详情页可展示每个支付 App 的：
  - 最后一次心跳时间
  - 24 小时心跳次数

## 2. 非目标（明确边界）

- 不重构普通请求上报（`/api/admin/intercept/logs`）的数据链路。
- 不新增心跳数据库表。
- 不将心跳历史明细长期持久化（仅维护 Redis 24h 窗口统计）。
- 不改变支付账户/人员归属逻辑，心跳统计仅按设备维度。

## 3. 总体架构

### 3.1 服务端统一接口

新增统一接口（建议路径）：

- `POST /api/device/heartbeat`

请求体（统一契约）：

- `appName: string`（示例：`navpay`, `phonepe`）
- `clientDeviceId: string`
- `ts?: number`（可选，服务端以接收时间为准）

响应体：

- `ok: true`
- `serverTimeMs: number`
- `lastHeartbeatAtMs: number`
- `count24h: number`

说明：

- 接口不依赖 `http_intercept_logs`。
- 允许多 App 共用。
- 可选支持轻量鉴权（如 `HEARTBEAT_API_KEY`）；未配置时默认开发态开放。

### 3.2 Redis 数据模型

为保证简单与可维护，使用“两键模型”：

1. 最后心跳时间（String）
- Key: `hb:last:{appName}:{clientDeviceId}`
- Value: `serverTimeMs`
- TTL: 48h（避免孤儿 key）

2. 24h 心跳计数窗口（ZSET）
- Key: `hb:24h:{appName}:{clientDeviceId}`
- Member: 唯一值（`${serverTimeMs}:${random}`）
- Score: `serverTimeMs`
- 每次心跳处理：
  - `ZADD key score member`
  - `ZREMRANGEBYSCORE key -inf (now-24h)`
  - `ZCOUNT key (now-24h) +inf` 作为 `count24h`
  - `EXPIRE key 172800`

该模型支持精确 24h 滑窗计数，且查询成本可控。

## 4. 与 intercept 完全隔离策略

### 4.1 ingest 层隔离

`/api/admin/intercept/logs` 与 `/api/intercept/log` 继续只处理 HTTP 拦截日志，不承担心跳职责。

### 4.2 客户端隔离

- `navpay-android`：心跳发送从个人端心跳接口切到统一 `/api/device/heartbeat`。
- `navpay-phonepe`：`LogSender` 现有“伪日志心跳”（`app://phonepe/heartbeat`）改为独立心跳 POST，不再作为日志写入。

### 4.3 展示层隔离

`navpay-admin` 设备详情中的支付 App 心跳信息改为读取 Redis 聚合结果，不再从 `http_intercept_logs` 的 `app://.../heartbeat` 查询。

## 5. Admin 展示设计

目标页面：

- `http://localhost:3000/admin/resources/devices/<deviceId>?tab=overview`

交互与数据：

- 用户点击每个支付 App 的“心跳信息”按钮时，展示：
  - 最后心跳时间（绝对时间 + 相对时间）
  - 24h 心跳次数
  - 数据来源标记：`Redis`（便于和日志体系区分）

后端返回字段（设备详情接口扩展）：

- `appStatuses[].lastHeartbeatAtMs`
- `appStatuses[].heartbeatCount24h`
- `appStatuses[].heartbeatSource = "redis"`

## 6. 错误处理与降级

- Redis 不可用时：
  - 心跳接口返回 `ok: false, error: "redis_unavailable"`（5xx）。
  - 设备详情接口对单个 app 返回心跳字段为空，页面显示 `-`，不阻断设备基础信息渲染。
- `appName/clientDeviceId` 非法：返回 400。
- 高频心跳：采用固定节奏（客户端 5~10s）+ 服务端 O(logN) ZSET 操作。

## 7. 测试策略

### 7.1 navpay-admin

- Unit:
  - Redis 心跳存取与 24h 滑窗计数逻辑
  - `/api/device/heartbeat` 参数校验/写入/返回
  - 设备详情接口 app 心跳读取改为 Redis
- Integration/E2E:
  - 设备详情页显示“最后心跳时间 + 24h 次数”
  - 断言不依赖 `http_intercept_logs` 心跳伪 URL

### 7.2 navpay-android

- 单元/契约：`ApiClient.deviceHeartbeat` 新接口 payload 正确。
- 手工 smoke：登录后持续上报心跳，后台设备详情可看到 Redis 计数增长。

### 7.3 navpay-phonepe

- 单元：`LogSender` 心跳分支不再向 intercept logs 端点写伪日志。
- 手工 smoke：拦截日志与心跳链路互不影响；心跳统计在 admin 可见。

## 8. 迁移与兼容

- 迁移期允许旧逻辑短暂并存（代码中不再写入伪日志心跳）。
- 设备页仅展示 Redis 心跳；旧日志心跳不再参与在线判定。
- 无数据库迁移。

## 9. 预期结果

实现后，心跳机制将成为真正独立的“设备在线信号通道”：

- 发送端：`navpay-android` 与 `navpay-phonepe` 一致化。
- 服务端：统一接口、Redis-only 存储。
- 管理端：按设备维度展示每个支付 App 的最后心跳和 24h 次数。
- 观测日志：`http_intercept_logs` 仅用于请求拦截，不再混入心跳语义。
