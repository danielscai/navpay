# Android Release Pointer Publish Runbook

## Purpose

将 Android 支付 App 发布统一为“不可变静态目录 + 可变 pointer”的两层模型。

- 不可变层：`/payment-apps/<appId>/releases/<versionName>/<baseSha256>/...`
- 可变层：`/payment-apps/<appId>/current.json`

回滚只切 pointer，不覆盖历史文件。

## Standard Release Shape

以 `phonepe` 为例：

- manifest：`/payment-apps/phonepe/releases/26.04.13.3/<baseSha256>/manifest.json`
- base：`/payment-apps/phonepe/releases/26.04.13.3/<baseSha256>/base.apk`
- split：`/payment-apps/phonepe/releases/26.04.13.3/<baseSha256>/split_config.*.apk`
- pointer：`/payment-apps/phonepe/current.json`

## Publish Workflow

1. 本地构建：`orch release phonepe --version <versionName> --test|--prod`
2. 静态上传 + 注册：`orch publish phonepe --bundle <bundle-path> --test|--prod`
3. 生产必须双确认：`--prod --yes-prod`
4. 校验 `from-manifest` 返回 `ok=true`，并确认 release 状态（默认激活）
5. 若需要 pointer 流程，更新 `current.json` 指向目标 release
6. 对 pointer 做定向 purge（不要 purge 不可变路径）

## current.json Contract

建议最小字段：

- `appId`
- `releaseId`
- `versionName`
- `versionCode`
- `manifestUrl`
- `updatedAt`

## Rollback Workflow

1. 找到上一稳定 release
2. 将 `current.json` 改回上一版本
3. 仅 purge pointer（和必要 manifest alias）
4. 复核客户端已解析到旧版本

## Do / Don't

Do:

- 只新增静态目录，不覆盖
- 仅 purge pointer 层
- 保留最近稳定版本以便秒级回滚

Don't:

- 不要覆盖 `releases/.../<baseSha256>/` 下任何文件
- 不要全站 purge
- 不要用“重传旧包”代替 pointer 回滚

## Smoke Commands

```bash
# pointer
curl -fsSI "https://download.navpay.site/payment-apps/phonepe/current.json"
curl -fsS  "https://download.navpay.site/payment-apps/phonepe/current.json"

# immutable manifest
curl -fsSI "https://download.navpay.site/payment-apps/phonepe/releases/<versionName>/<baseSha256>/manifest.json"
```
