# Cloudflare Origin Cache Policy Runbook

## Purpose
Cloudflare is used only as an acceleration and security layer.

The origin remains the source of truth for:
- release manifests
- immutable APK artifacts
- admin application behavior
- authorization and access control decisions

Cloudflare should improve delivery speed and absorb public traffic, but it must not become the system of record for releases or admin data.

## Scope
This policy applies to the public artifact and manifest paths exposed through Cloudflare.

It does not change:
- origin storage layout
- release creation
- pointer-based publish flow
- admin authorization rules at the application layer

## Cache TTL Matrix

| Resource type | Example path | Cache policy | Notes |
| --- | --- | --- | --- |
| Immutable APK artifact | `/releases/<sha>/app-release.apk` | `public, max-age=2592000, immutable` | Long cache is safe because the content is content-addressed by immutable tag / sha. |
| Release manifest | `/releases/<sha>/manifest.json` | `public, max-age=300` | Short-to-medium cache is acceptable because each release has a unique sha path. |
| Pointer file | `/current.json` | `public, max-age=1` to `60` | Keep this very short so cutovers and rollbacks become visible quickly. |
| Admin HTML / app shell | `/admin/*` | `no-store` or bypass | Do not cache sensitive admin pages at the edge. |
| Authorized API | `/api/*` with `Authorization` header | bypass cache | Never cache authenticated responses. |
| Mutable operational endpoints | `/api/*` without immutable content guarantees | bypass cache | Default to origin for anything not explicitly static. |

## Bypass Rules For Authorized APIs
Bypass cache whenever any of the following is true:

- the request includes an `Authorization` header
- the route is under `/api/`
- the route is an admin or session-bound page
- the response depends on user identity, access policy, or server-side session state
- the response is mutable or can differ per caller

Recommended Cloudflare rule ordering:

1. Match and bypass authenticated API traffic first.
2. Match and bypass admin routes second.
3. Allow short cache only for manifest pointer files.
4. Allow long cache only for immutable content-addressed artifacts.

## Selective Purge Scope
Use selective purge only. Do not purge the full zone for routine release work.

Purge only:
- `/current.json`
- the lightweight manifest path that changes during release cutover
- any stale pointer alias that references the newly repointed release

Do not purge:
- immutable release directories
- sha-addressed APK artifacts
- unrelated admin or API routes

Rationale:
- immutable artifacts already have a stable sha path
- pointer files are the only objects that need fast propagation during publish or rollback
- selective purge reduces cache churn and avoids unnecessary origin load

## Optional Curl Examples

### Manifest fetch
```bash
curl -i https://downloads.example.com/current.json
```

### Immutable artifact download
```bash
curl -I https://downloads.example.com/releases/9f2a8c1b6d4e7a3f5c1d2e9f0a6b7c8d9e0f1a2b/app-release.apk
```

### Denied admin route
```bash
curl -i https://admin.example.com/admin/resources
```

Expected outcome:
- authenticated admin routes are not edge-cached
- access is enforced by the application and its auth layer
- Cloudflare only accelerates and protects the origin, it does not replace authorization

## Operational Checks

Before publishing a cache rule change, confirm:

1. immutable release paths still return cache-friendly headers
2. `current.json` remains short-lived
3. authenticated API responses are bypassed
4. admin routes are not cached at the edge
5. selective purge can invalidate only the pointer and manifest layer

## Troubleshooting

- If a new release does not appear, verify the pointer file changed and the selective purge was limited to pointer paths.
- If an authenticated response is cached, inspect the rule ordering and add a bypass rule above any static asset match.
- If admin pages are served from cache, force `no-store` or explicit bypass on the admin route group.
