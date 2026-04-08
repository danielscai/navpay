# NavPay Production Deployment Design (Internal/Public Split + Cloudflare Acceleration)

**Date:** 2026-04-08  
**Status:** Approved for implementation  
**Scope:** `navpay-admin`, `navpay-android`, `navpay-phonepe`, top-level ops/deployment process

---

## 1. Objectives

1. Build a stable production deployment model with clear separation of internal and public traffic.
2. Keep `infra + internal admin` isolated from public internet access.
3. Provide fast public download and distribution via Cloudflare cache acceleration while keeping source-of-truth on origin.
4. Share one PostgreSQL and one Redis across internal/public services safely.
5. Add operational safeguards: backup, restore validation, rollout gates, rollback, auditability.
6. Enforce merchant API IP allowlist at application layer with safe rollout mode.

---

## 2. Constraints and Decisions

### 2.1 Confirmed decisions

Architecture boundaries (explicit):
1. Node A: infra + internal
2. Node B: public + download
3. Cloudflare only acts as an acceleration/security layer.
4. Merchant IP allowlist applies only to merchant APIs.
5. Private-link outage strategy: stop publishing, keep old-version downloads online.

1. Internal workloads (`infra`, `internal`) must not be colocated with download station.
2. Public/download may be colocated or split; default is colocated for simplicity.
3. Cloudflare is acceleration/security layer only; artifacts and manifests remain managed by origin.
4. Merchant IP allowlist applies only to `merchant` APIs.
5. If private link between public node and internal DB/Redis is down: stop publishing, but keep existing downloads available.
6. Internal API must not be directly reachable by cloud public IP.

### 2.2 Security model choice

Use **Cloudflare Tunnel + Access** for internal admin access. Internal origin has no required public inbound API ports.

---

## 3. Target Topology

## 3.1 Node A (private network)

Services:
1. `postgres`
2. `redis`
3. `pg_backup`
4. `admin-internal` (full admin/API surface)
5. optional metrics exporters

Rules:
1. DB/Redis bind private interface only.
2. No public inbound to application/API ports.
3. Access via Cloudflare Tunnel + Access policy.

## 3.2 Node B (public edge origin)

Services:
1. `reverse-proxy`
2. `admin-public` (same app image, restricted routing)
3. `download-site` (static downloads page + files)

Rules:
1. Expose only 80/443 publicly.
2. Connect to Node A DB/Redis over private tunnel/network only.

## 3.3 Cloudflare layer

1. DNS + CDN cache acceleration for download/public domains.
2. WAF/rate limits at edge.
3. Access policy for internal domain.
4. Tunnel from Node A outbound only.

---

## 4. Service Exposure Policy

## 4.1 Internal domain (`internal-admin.<domain>`)

1. Protected by Cloudflare Access (SSO + MFA + policy).
2. No direct public IP access.

## 4.2 Public API domain (`api.<domain>`)

Allowed route set (reverse-proxy allowlist):
1. `/api/personal/payment-apps`
2. `/api/personal/payment-apps/:appId/releases/:releaseId/manifest`
3. `/api/personal/payment-apps/:appId/releases/:releaseId/artifacts/:artifactId/download`
4. `/api/personal/payment-apps/install-events`
5. required personal auth endpoints only if client requires them

All other `/api/*` routes return `403`.

## 4.3 Download domain (`dl.<domain>`)

1. Public static page and artifact file hosting.
2. Manifest pointer file controls active downloadable version.

---

## 5. Data and State Management

## 5.1 Shared PostgreSQL/Redis

1. Single PostgreSQL + Redis on Node A.
2. Separate DB users:
   - `admin_internal_user` (broader permissions)
   - `admin_public_user` (minimum required permissions)
3. Redis ACL or strict key-prefix conventions.
4. Private network only between Node B and Node A.

## 5.2 Persistence

1. PostgreSQL data dir mounted to host (`/srv/navpay/postgres-data`).
2. Redis persistence enabled with host mount (`/srv/navpay/redis-data`).

## 5.3 Backup and restore

1. `pg_backup` container runs scheduled `pg_dump -Fc`.
2. Backups mounted to host (`/srv/navpay/postgres-backups`).
3. Retention baseline:
   - daily: 7 copies
   - weekly: 4 copies
4. Mandatory restore verification job weekly to temporary DB.
5. Backup status output must include timestamp, result, size, duration.

---

## 6. Cloudflare Caching and Publish Model

## 6.1 Cache policy

1. `*.apk`: long cache (e.g., 30d, immutable).
2. release manifest pointer files (`current.json`, lightweight manifest): short cache (1-60s).
3. Authorized API responses (`Authorization` present): bypass cache.

## 6.2 Atomic release

1. Upload full new release directory first.
2. Validate hashes and completeness.
3. Switch only pointer file (`current.json`) to new release.
4. Purge only pointer/manifest paths.

## 6.3 Rollback

1. Re-point `current.json` to previous release.
2. Purge pointer/manifest.
3. No large artifact re-upload required.

---

## 7. Merchant API IP Allowlist (Application Layer)

## 7.1 Scope

Only `merchant` API routes enforce allowlist.

## 7.2 Trusted IP extraction

1. If request comes from trusted reverse proxy, use `CF-Connecting-IP`.
2. Else fallback to validated forwarded chain.
3. Final fallback to socket remote address.

## 7.3 Rule support

1. IPv4 single IP
2. IPv6 single IP
3. CIDR ranges

## 7.4 Rollout modes

1. `OFF`: disabled
2. `SHADOW`: evaluate and log, do not block
3. `ENFORCE`: block non-allowlisted IP with `403`

Recommended rollout: `SHADOW` for 7 days, then `ENFORCE`.

## 7.5 Audit requirements

Per decision log record fields:
1. merchantId
2. apiKeyId
3. clientIp
4. route
5. decision
6. reason
7. timestamp

---

## 8. Release Pipeline Standard

## 8.1 Admin image deployment

1. CI: lint/typecheck/tests/build.
2. Build immutable image tag by commit SHA.
3. Deploy sequence: internal first, then public.
4. DB migration executed once under controlled step.
5. Post-deploy health checks mandatory.
6. Auto rollback to previous SHA on failure.

## 8.2 Android/split artifact publishing

1. Keep existing `navpay-phonepe` split release pipeline.
2. Publish artifacts to origin download storage with release-versioned path.
3. Switch active pointer atomically.
4. Verify manifest/artifact availability via smoke checks.

---

## 9. Failure Modes and Degradation

1. Private link Node B -> Node A down:
   - publishing disabled
   - existing downloads continue from origin + Cloudflare cache
2. Backup job failed:
   - block schema migration/deployment stage
3. Public API route misconfigured:
   - deny by default in reverse proxy
4. Allowlist misconfiguration:
   - use `SHADOW` mode and emergency override switch

---

## 10. Operational Guardrails

1. All deploy scripts default to `dry-run`.
2. Production actions require explicit `--confirm` and environment re-entry.
3. No `latest` tags in deployment.
4. Mandatory runbook for deploy/rollback/disaster-recovery.
5. All high-risk ops actions are auditable.

---

## 11. Acceptance Criteria

1. Internal admin is inaccessible from direct public cloud IP.
2. Public domain exposes only approved personal distribution routes.
3. Merchant allowlist blocks non-allowlisted IPs in `ENFORCE` mode.
4. Backup and restore verification pass in staging and production rehearsal.
5. Atomic release and rollback via pointer switching validated.
6. Private-link outage behavior matches policy: no publish, downloads continue.
