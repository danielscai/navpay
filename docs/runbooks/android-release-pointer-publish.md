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

1. 统一入口发布：`yarn release <product>`（Android 对应 `yarn release android`）
2. 统一入口部署：`yarn deploy <product> [--version]`（Android 对应 `yarn deploy android [--version]`）
3. 版本规则：业务版本 `YY.MM.DD.N`，Git Tag `vYY.MM.DD.N`
4. 发布/部署前必须执行：`git fetch --tags --force origin` + `git pull --ff-only origin main`
5. 不传 `--version` 时，从本地最新 tag 推导版本并校验 `origin` 存在
6. `current.json` 更新必须使用临时文件 + 原子 `mv`

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
