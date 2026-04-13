# NavPay Production Rollout Checklist

## 1. Release Gate

- [ ] 发布链路为 `ssh/static + from-manifest`，不使用 HTTP 大文件上传。
- [ ] `orch publish` 生产命令显式包含 `--prod --yes-prod`。
- [ ] `PAYMENT_APP_RELEASE_MANIFEST_ALLOWED_HOSTS` 已配置且仅包含白名单域名。
- [ ] download-site 挂载目录存在且只读对外（默认 `/data/download-site`）。
- [ ] 目标版本静态目录完整：`manifest.json`、`base.apk`、required splits。
- [ ] 幂等键确认：`appId + targetEnv + versionCode + baseSha256`。
- [ ] 回滚目标已确认（上一稳定 release 或 pointer 目标）。

## 2. Operator Controls

- [ ] 双人确认（operator + reviewer）记录完成。
- [ ] 执行前已打印并核对环境（`targetEnv=prod`）。
- [ ] 已核对发布版本与 release note 一致。
- [ ] 生产执行需显式 `--prod --yes-prod`，缺一不可。

## 3. Rollout Sequence

1. `orch release phonepe --version <versionName> --prod`
2. `orch publish phonepe --bundle <bundle-path> --prod --yes-prod`
3. 验证 admin 发布结果（`ok=true`，release 已激活或按预期状态）
4. 验证下载 URL 与 manifest 可达
5. 若使用 pointer，更新 `current.json` 并定向 purge

## 4. Verification

- [ ] `/payment-apps/<appId>/releases/<versionName>/<baseSha256>/manifest.json` 可访问。
- [ ] manifest 中 artifacts URL 全可访问且 hash/size 校验一致。
- [ ] Android 端安装冒烟通过（base + required splits）。
- [ ] 无 `manifest_invalid` / `artifact_unreachable` / `split_missing` / `signature_mismatch`。

## 5. Stability Regression (10 Runs)

- [ ] 在 `--test` 环境完成连续 10 次发布回归。
- [ ] 10 次发布中无 502 上传失败（HTTP 上传链路已移除）。
- [ ] 幂等回归通过：重复发布同幂等键返回已存在 release。

## 6. Rollback

- [ ] 回滚仅切 active release 或 `current.json` pointer。
- [ ] 不修改历史静态目录，不覆盖已发布文件。
- [ ] 回滚后再次执行 manifest + 安装冒烟验证。

## 7. Go / No-Go

- [ ] 发布验证通过
- [ ] 回滚路径可用
- [ ] 审计日志完整

任一项失败则 **NO-GO**。
