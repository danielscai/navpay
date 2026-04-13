# Cloudflare Origin Cache Policy Runbook

## Purpose

Cloudflare 仅作为加速/防护层，origin 仍是发布真相源。

## Scope

适用于 download-site 暴露的支付 App 静态路径：

- `/payment-apps/<appId>/releases/...`（不可变）
- `/payment-apps/<appId>/current.json`（pointer）

## Cache Matrix

| Resource | Path pattern | Policy |
| --- | --- | --- |
| Immutable artifact/manifest | `/payment-apps/<appId>/releases/<versionName>/<baseSha256>/*` | `Cache-Control: public, max-age=31536000, immutable` |
| Pointer | `/payment-apps/<appId>/current.json` | `Cache-Control: public, max-age=60, s-maxage=300, stale-while-revalidate=60` |
| Admin/API authenticated traffic | `/admin/*`, `/api/*` with auth/session | bypass/no-store |

## Rule Ordering

1. 先匹配并 bypass 鉴权 API / admin 页面
2. 再匹配 pointer 短缓存
3. 最后匹配 immutable 长缓存

## Selective Purge Policy

只 purge 发生变化的可变 URL：

- `current.json`
- 必要的轻量 manifest alias（如果存在）

不要 purge：

- `releases/<versionName>/<baseSha256>/...` 不可变目录
- 无关 API / admin 路径

## Origin Requirements

- `etag on`
- `autoindex off`
- 不可变路径严禁覆盖（只新增）

## Smoke Commands

```bash
# pointer short-cache
curl -fsSI "https://download.navpay.site/payment-apps/phonepe/current.json"

# immutable cache
curl -fsSI "https://download.navpay.site/payment-apps/phonepe/releases/<versionName>/<baseSha256>/manifest.json"

# ensure admin path is not cacheable public artifact
curl -I "https://admin.navpay.site/admin"
```
