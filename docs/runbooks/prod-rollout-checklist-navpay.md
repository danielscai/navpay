# NavPay Production Rollout Checklist

## 0. Unified Command Contract

- [ ] 仅通过 `yarn release <product>` / `yarn deploy <product> [--version]` 执行。
- [ ] 仅允许单产品执行，不支持 `all`。
- [ ] 版本符合 `YY.MM.DD.N`，tag 符合 `vYY.MM.DD.N`。
- [ ] 发布/部署前已执行：`git fetch --tags --force origin`、`git pull --ff-only origin main`。
- [ ] deploy 未传 `--version` 时，已从本地最新合法 tag 推导并校验 `origin` 存在该 tag。

## 1. Release Gate

- [ ] admin runtime 使用 direct runtime（pm2 + nginx 多 conf），不走 admin/reverse-proxy/download-site 容器 runtime。
- [ ] checksum/postgres/redis 仍由容器运行（infra profile）。
- [ ] Android/PhonePe 发布链路仅包含本地打包 + copy（+ PhonePe activate API）。
- [ ] download-site 静态目录存在，且 pointer 更新使用临时文件 + 原子 `mv`。

## 2. Operator Controls

- [ ] 双人确认（operator + reviewer）记录完成。
- [ ] 执行前已打印并核对环境（`targetEnv=prod`）。
- [ ] 已核对发布版本与 release note 一致。
- [ ] 生产执行需显式 `--prod --yes-prod`，缺一不可。

## 3. Rollout Sequence

1. `yarn release <product>`
2. `yarn deploy <product> [--version]`
3. 校验 `releases/<product>/<version>/metadata.json|steps.log|result.json` 完整落盘
4. 校验业务可用性（admin 页面/下载链接/API 激活）

## 4. Verification

- [ ] admin: `pm2` 进程健康，`nginx -t && nginx -s reload` 成功。
- [ ] android: 版本 APK 已复制到 `download-site/site/android/<version>/`，`current.json` 已原子更新。
- [ ] phonepe: 版本 APK 已复制到 `download-site/site/phonepe/<version>/`，activate API 已按预期调用。
- [ ] checksum/pg/redis 容器健康。

## 5. Stability Regression

- [ ] 至少完成一次每产品 dry-run + real-run 验证（阻塞须记录）。
- [ ] 失败注入（origin 缺失 tag）可稳定阻断。

## 6. Rollback

- [ ] admin: 回滚到上一 tag 并执行 `pm2 startOrReload` + `nginx reload`。
- [ ] android/phonepe: 回滚仅切 `current.json` pointer，不覆盖历史目录。
- [ ] checksum: 继续按容器镜像 tag 回滚。

## 7. Go / No-Go

- [ ] 发布验证通过
- [ ] 回滚路径可用
- [ ] 审计日志完整

任一项失败则 **NO-GO**。
