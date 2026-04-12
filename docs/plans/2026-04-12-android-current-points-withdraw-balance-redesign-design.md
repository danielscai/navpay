# Android Current Points 提现与流水重设计（微信钱包风格）

**Date:** 2026-04-12  
**Scope:** `navpay-android` Mine -> Current Points 页面重构；对齐 `navpay-admin` 既有 `/api/personal` 能力  
**Status:** Approved

---

## 1. 目标与约束

### 1.1 目标

在 `navpay-android` 的 Mine -> Current Points 页面中完成两项能力并优化信息结构：

1. 增加余额变更流水查看能力（最近流水 + 全量流水页）。
2. 提现入口改为独立申请页面（不再使用弹窗作为主入口）。

### 1.2 明确约束

1. 所有提现/流水相关 API 必须在现有 `/api/personal` 体系下，与当前 Android 与 admin 契约兼容。
2. 页面结构不使用 Tab。
3. UI 参考微信钱包“提现 + 零钱明细”信息架构。

---

## 2. 现状盘点

### 2.1 Android 现状

现有 `PointsDetailsFragment` 已接入：

1. `GET /wallet/summary`
2. `GET /withdraw/orders`
3. `POST /withdraw/orders`
4. `GET /withdraw/orders/{id}`
5. `GET /wallet/stats`

同时 `ApiClient` 已存在 `getBalanceLogs(page, pageSize)`，调用 `GET /mine/balance-logs`，但 Current Points 页面尚未展示流水区域。

### 2.2 Admin 现状

`navpay-admin` 已提供并测试覆盖：

1. `GET /api/personal/mine/balance-logs`
2. `GET /api/personal/balance/logs`（同结构）
3. `GET /api/personal/wallet/summary`
4. `POST /api/personal/withdraw/orders`
5. `GET /api/personal/withdraw/orders`
6. `GET /api/personal/withdraw/orders/[orderId]`
7. `GET /api/personal/wallet/stats`

结论：后端能力可支撑本次 Android 重设计，不需要新开后端域。

---

## 3. 方案对比与选型

### 3.1 方案 A（最终选择）

钱包首页 + 双入口 + 最近流水 + 最近提现进度（无 Tab）。

- 顶部显示可用余额与冻结/处理中。
- 中部两个主入口：`Withdraw`、`Balance Details`。
- 展示最近 1-2 条提现进度。
- 展示最近 5 条余额流水，并提供 `View All`。

### 3.2 方案 B

钱包首页仅操作入口，流水全部放二级页。

### 3.3 方案 C

单页长列表拼接（操作区 + 全量流水）。

### 3.4 选型理由

1. 最接近微信钱包认知模型，学习成本最低。
2. 避免 Tab 在当前信息密度下的交互割裂。
3. 兼顾“快速操作”（提现）与“快速核对”（最近流水/最近进度）。

---

## 4. 信息架构与导航

## 4.1 Current Points（钱包首页）

1. 顶部主卡：
   - `Available Balance`（主数字）
   - `Frozen`（辅助）
   - `Processing Orders`（辅助）
2. 主操作区：
   - `Withdraw`（主按钮，进入提现申请页）
   - `Balance Details`（进入流水全量页）
3. 最近提现进度区：
   - 1-2 条（金额、状态、进度%、更新时间）
   - 点击进入现有提现详情 BottomSheet
4. 最近流水区：
   - 5 条（delta、reason、createdAt、balanceAfter）
   - 底部 `View All` 进入全量流水页

## 4.2 Withdraw Apply（新增独立页面）

1. Amount 输入框（仅金额，2 位小数约束）。
2. 可用余额提示。
3. `Submit Withdraw` 主按钮。
4. 成功后返回首页并刷新相关区块。

## 4.3 Balance Details（新增全量流水页）

1. 流水列表（首版 page=1,pageSize=20）。
2. 支持下拉刷新。
3. 预留分页能力（接口已支持 page/pageSize）。

---

## 5. 数据流与接口映射

## 5.1 钱包首页加载

并发请求：

1. `GET /api/personal/wallet/summary`
2. `GET /api/personal/withdraw/orders?page=1&pageSize=2`
3. `GET /api/personal/mine/balance-logs?page=1&pageSize=5`
4. `GET /api/personal/wallet/stats?range={today|7d|30d}`（保留现有统计文案能力）

## 5.2 提现申请

1. 提交：`POST /api/personal/withdraw/orders`（`amount + requestKey`）
2. 成功：返回首页并刷新 `summary + recentWithdraw + recentLogs (+ stats)`
3. 失败：错误码映射用户提示

## 5.3 提现详情

1. 点击最近提现进度行：`GET /api/personal/withdraw/orders/{orderId}`
2. 沿用现有 BottomSheet 与 timeline 展示

## 5.4 流水全量页

1. `GET /api/personal/mine/balance-logs?page=x&pageSize=20`
2. 可后续兼容切换 `/api/personal/balance/logs`，但首版保持 Android 现有路径稳定

---

## 6. Android UI 设计规范（Material 3）

1. 列表与卡片采用统一圆角与间距体系（12dp/16dp 主间距）。
2. 关键按钮最小触达高度 48dp。
3. 金额颜色规则：
   - 收入 `+`：正向色（绿色）
   - 支出/冻结相关：中性深色
4. 状态展示统一：
   - `RISK_CHECKING`
   - `REVIEW_PENDING`
   - `ACCUMULATING`
   - `SUCCESS`
   - `REVIEW_REJECTED`
5. 时间与金额格式保持与现有 wallet 模块一致。

---

## 7. 错误处理与兼容策略

1. 提现错误码映射：
   - `insufficient_balance`
   - `duplicate_request`
   - `invalid_target_amount`
   - 其他走通用失败提示
2. 局部容错：
   - 首页分块失败不阻断全页渲染
   - 每个区块支持重试
3. 鉴权失效：
   - 继续沿用现有 401 -> 重新登录流程

---

## 8. 验收标准

1. Mine -> Current Points 首页不再使用 Tab。
2. 首页可见：余额主卡、Withdraw 与 Balance Details 双入口、最近提现、最近流水。
3. 点击 Withdraw 进入独立申请页，可成功创建提现。
4. 点击 Balance Details 进入全量流水页。
5. 提现成功后返回首页，关键区块数据自动刷新。
6. API 全部保持在 `/api/personal` 下，且与现有 admin 契约兼容。

---

## 9. 风险与后续演进

1. 首版流水分页可先不做无限滚动，仅保留接口参数与结构兼容。
2. 若后续需要“流水详情页”深挖，可基于 `refType/refId` 增加跳转策略。
3. 状态文案国际化可在下一阶段统一收敛到资源文件。

