# Local Emulator Device Observability E2E Runbook (2026-03-02)

## Goal
在本地模拟器环境验证：
- Android 设备上线后能在 `http://localhost:3000/admin/resources?tab=devices` 可见
- 设备展示归属、在线状态、device id、硬件/时区/品牌信息
- Intercept 上报带 `clientDeviceId` 后，日志能归属到对应设备，并标记来源 `phonepe`

## Prerequisites
- `navpay-admin` 已安装依赖并可启动
- PostgreSQL 与 Redis 本地可用
- Android Emulator `phonepe1` 可启动
- Android 客户端可登录并触发 `report/heartbeat`

## Step 1: Start services
```bash
cd /Users/danielscai/Documents/workspace/navpay/navpay-admin
yarn db:migrate
yarn db:seed
PORT=3000 yarn dev
```

## Step 2: Start emulator + Android app
```bash
cd /Users/danielscai/Documents/workspace/navpay/navpay-android
yarn emu1
# 新终端
./gradlew assembleDebug
# 安装 APK（按你的现有方式）
```

## Step 3: Trigger device registration
- 在 Android 端登录支付账号。
- 等待心跳上报 5-15 秒。
- 访问 `http://localhost:3000/admin/resources?tab=devices`。

Expected:
- 设备列表出现一条新设备（含 `deviceId/clientDeviceId`）
- 在线状态显示“在线”
- 右侧详情可见“归属历史/同账号其他设备/PhonePe 信息/上报日志”区块

## Step 4: Trigger intercept log assignment
向上报入口发送一条带 `clientDeviceId` 的日志：
```bash
curl -X POST 'http://localhost:3000/api/intercept/log' \
  -H 'content-type: application/json' \
  -d '{
    "timestamp":"'"$(date -u +%Y-%m-%dT%H:%M:%SZ)'"',
    "method":"POST",
    "url":"https://example.test/e2e/manual",
    "protocol":"HTTP/1.1",
    "status_code":200,
    "clientDeviceId":"<替换为该设备clientDeviceId>",
    "sourceApp":"phonepe"
  }'
```

Expected:
- 设备详情“上报日志”出现该记录
- 记录带 `sourceApp=phonepe`

## Step 5: Ownership history check
- 使用另一个支付账号在同一设备登录并触发心跳。

Expected:
- 设备仍为同一个 `clientDeviceId`
- 当前归属切换为新账号
- “归属历史”新增一条 from -> to 记录（reason=heartbeat/report）

## Troubleshooting
- 如果设备不在线：检查 Android 心跳接口 `/api/personal/device/heartbeat` 返回码。
- 如果日志未归属：确认上报 payload 带 `clientDeviceId`，且值与设备列表一致。
- 如果页面不显示详情：先点左侧设备列表项确保选中。
