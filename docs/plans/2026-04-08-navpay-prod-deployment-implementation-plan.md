# NavPay Production Deployment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver a production-ready deployment system with internal/public isolation, Cloudflare-accelerated distribution, shared private DB/Redis, backup/restore guarantees, and merchant API IP allowlist safety controls.

**Architecture:** Deploy three compose layers (`infra`, `internal`, `public`) across two nodes (private Node A, public Node B). Protect internal admin with Cloudflare Tunnel + Access, expose only allowlisted personal distribution routes publicly, and keep release artifacts source-managed at origin with pointer-based atomic publish/rollback. Enforce merchant IP allowlist in application layer using trusted client IP extraction and staged rollout (`SHADOW` -> `ENFORCE`).

**Tech Stack:** Docker Compose, Next.js (`navpay-admin`), PostgreSQL, Redis, Cloudflare CDN/Access/Tunnel, Nginx or Traefik, shell deployment scripts, Prisma migration workflow.

---

Execution skill references: `@superpowers:executing-plans`, `@superpowers:verification-before-completion`

## Execution Delta (Repository Reality Alignment)

To keep this plan executable without changing scope:
1. `Task 1` target files already exist in repository state; execute as "update/verify existing files" (still fail-first/readability verification + commit).
2. `Task 7` spans two independent repositories (`docs/*` in orchestration repo, `navpay-admin/docs/*` in admin repo). Execute one task with two repo-local commits to preserve repository boundaries.
3. All `navpay-admin` changes must run in isolated worktree path under `worktrees/navpay-admin/<ticket>`.

### Task 1: Create deployment design and implementation records in top-level docs

**Files:**
- Create: `docs/plans/2026-04-08-navpay-prod-deployment-design.md`
- Create: `docs/plans/2026-04-08-navpay-prod-deployment-implementation-plan.md`

**Step 1: Add final design content**

Write finalized architecture sections into:
- `docs/plans/2026-04-08-navpay-prod-deployment-design.md`

Include:
1. Node A/Node B topology
2. Cloudflare role boundaries
3. API route exposure allowlist
4. backup/restore policy
5. degradation behavior for private-link outage
6. merchant allowlist scope and rollout mode

**Step 2: Validate markdown file is readable**

Run: `sed -n '1,120p' docs/plans/2026-04-08-navpay-prod-deployment-design.md`  
Expected: title, objectives, constraints, and topology render as complete markdown.

**Step 3: Save implementation plan skeleton**

Write this plan file and keep paths/commands exact.

**Step 4: Verify plan header format**

Run: `sed -n '1,40p' docs/plans/2026-04-08-navpay-prod-deployment-implementation-plan.md`  
Expected: exact required header block with Goal/Architecture/Tech Stack.

**Step 5: Commit**

```bash
git add docs/plans/2026-04-08-navpay-prod-deployment-design.md docs/plans/2026-04-08-navpay-prod-deployment-implementation-plan.md
git commit -m "docs: add navpay production deployment design and implementation plan"
```

### Task 2: Add Node A infra compose and env templates

**Files:**
- Create: `navpay-admin/deploy/production/infra/compose.infra.yml`
- Create: `navpay-admin/deploy/production/infra/.env.example`
- Create: `navpay-admin/deploy/production/infra/scripts/backup_pg.sh`
- Create: `navpay-admin/deploy/production/infra/scripts/restore_verify_pg.sh`

**Step 1: Write failing validation script test (smoke level)**

Create shell check script or test note that expects these compose services:
- `postgres`
- `redis`
- `pg_backup`

**Step 2: Run compose config before files exist**

Run: `docker compose -f navpay-admin/deploy/production/infra/compose.infra.yml config`  
Expected: FAIL (`no such file`), confirming test starts failing.

**Step 3: Implement minimal infra compose and scripts**

Implement:
1. mounted postgres/redis volumes on host paths
2. backup container with cron-like schedule or loop runner
3. status output file for backup progress
4. restore-verify script for temporary DB restore

**Step 4: Re-run config validation**

Run: `docker compose -f navpay-admin/deploy/production/infra/compose.infra.yml config`  
Expected: PASS with resolved services and volume mounts.

**Step 5: Commit**

```bash
git add navpay-admin/deploy/production/infra
git commit -m "feat(deploy): add production infra compose with backup and restore verify"
```

### Task 3: Add Node A internal compose and Cloudflare Tunnel/Access integration scaffold

**Files:**
- Create: `navpay-admin/deploy/production/internal/compose.internal.yml`
- Create: `navpay-admin/deploy/production/internal/.env.example`
- Create: `navpay-admin/deploy/production/internal/README.md`

**Step 1: Write failing config check command**

Run: `docker compose -f navpay-admin/deploy/production/internal/compose.internal.yml config`  
Expected: FAIL before file creation.

**Step 2: Implement internal compose**

Include services:
1. `admin-internal`
2. optional `cloudflared` connector service (or documented external daemon)

Require:
1. private DB/Redis connection strings
2. no public port publishing for sensitive services

**Step 3: Document Access/Tunnel policy requirements**

In README, define:
1. identity provider + MFA policy
2. allowed user groups
3. emergency break-glass account process

**Step 4: Re-run compose validation**

Run: `docker compose -f navpay-admin/deploy/production/internal/compose.internal.yml config`  
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-admin/deploy/production/internal
git commit -m "feat(deploy): add internal compose and cloudflare access scaffold"
```

### Task 4: Add Node B public compose and strict route allowlist proxy

**Files:**
- Create: `navpay-admin/deploy/production/public/compose.public.yml`
- Create: `navpay-admin/deploy/production/public/nginx.conf`
- Create: `navpay-admin/deploy/production/public/.env.example`
- Create: `navpay-admin/deploy/production/public/README.md`

**Step 1: Write failing route policy test**

Create a simple curl test script spec expecting:
1. allowed personal routes return non-403
2. disallowed `/api/admin/*` returns `403`

**Step 2: Run test before proxy exists**

Run: `bash navpay-admin/deploy/production/public/scripts/test_route_policy.sh`  
Expected: FAIL (`file not found` or connection failure).

**Step 3: Implement compose + proxy config**

1. expose only 80/443
2. proxy allowlisted personal distribution routes
3. deny all other `/api/*`
4. include `download-site` route/host mapping

**Step 4: Re-run route policy test**

Run: `bash navpay-admin/deploy/production/public/scripts/test_route_policy.sh`  
Expected: PASS on allowlist/deny checks.

**Step 5: Commit**

```bash
git add navpay-admin/deploy/production/public
git commit -m "feat(deploy): add public compose with api route allowlist proxy"
```

### Task 5: Implement merchant API IP allowlist at application layer (shadow-first)

**Files:**
- Create: `navpay-admin/src/lib/merchant-ip-allowlist.ts`
- Modify: `navpay-admin/src/app/api/merchant/*` auth entry points (exact files discovered during implementation)
- Create: `navpay-admin/tests/unit/merchant-ip-allowlist.test.ts`
- Create: `navpay-admin/tests/unit/merchant-ip-trusted-source.test.ts`

**Step 1: Write failing unit tests for allowlist decisions**

Add tests for:
1. OFF mode allows
2. SHADOW mode logs but allows
3. ENFORCE mode blocks non-allowlisted IP with `403`
4. CIDR matching for IPv4/IPv6
5. trusted proxy extraction via `CF-Connecting-IP`

**Step 2: Run tests to verify fail-first**

Run: `cd navpay-admin && yarn vitest run tests/unit/merchant-ip-allowlist.test.ts tests/unit/merchant-ip-trusted-source.test.ts`  
Expected: FAIL due to missing implementation.

**Step 3: Implement minimal allowlist module and merchant middleware integration**

Requirements:
1. scope only merchant routes
2. structured decision/audit log payload
3. emergency override env switch
4. no behavior change for personal/admin routes

**Step 4: Re-run targeted tests**

Run: `cd navpay-admin && yarn vitest run tests/unit/merchant-ip-allowlist.test.ts tests/unit/merchant-ip-trusted-source.test.ts`  
Expected: PASS.

**Step 5: Commit**

```bash
git -C navpay-admin add src/lib/merchant-ip-allowlist.ts src/app/api/merchant tests/unit/merchant-ip-allowlist.test.ts tests/unit/merchant-ip-trusted-source.test.ts
git -C navpay-admin commit -m "feat(admin): add merchant api ip allowlist with shadow and enforce modes"
```

### Task 6: Add deploy orchestration scripts with guardrails

**Files:**
- Create: `navpay-admin/deploy/production/scripts/deploy_internal.sh`
- Create: `navpay-admin/deploy/production/scripts/deploy_public.sh`
- Create: `navpay-admin/deploy/production/scripts/preflight.sh`
- Create: `navpay-admin/deploy/production/scripts/rollback.sh`
- Create: `navpay-admin/deploy/production/scripts/check_health.sh`

**Step 1: Write failing preflight test script**

Define checks:
1. immutable image tag required (no `latest`)
2. backup freshness check before migration
3. `--confirm` required for production execution

**Step 2: Run preflight before script implementation**

Run: `bash navpay-admin/deploy/production/scripts/preflight.sh --env prod`  
Expected: FAIL (`missing script` or missing requirements).

**Step 3: Implement deployment scripts**

Sequence:
1. preflight
2. deploy internal
3. run health checks
4. deploy public
5. run health checks
6. rollback on failure

**Step 4: Dry-run validation**

Run: `bash navpay-admin/deploy/production/scripts/deploy_internal.sh --env prod --dry-run`  
Expected: PASS in simulation mode with no state mutation.

Run: `bash navpay-admin/deploy/production/scripts/deploy_public.sh --env prod --dry-run`  
Expected: PASS in simulation mode.

**Step 5: Commit**

```bash
git add navpay-admin/deploy/production/scripts
git commit -m "feat(deploy): add guarded deploy and rollback scripts"
```

### Task 7: Add Cloudflare cache/purge runbook and pointer-based release SOP

**Files:**
- Create: `docs/runbooks/cloudflare-origin-cache-policy.md`
- Create: `docs/runbooks/android-release-pointer-publish.md`
- Modify: `navpay-admin/docs/ops/payment-app-release-runbook.md`

**Step 1: Write failing doc check (manual acceptance checklist)**

Checklist must include:
1. cache TTL matrix
2. bypass rules for authorized APIs
3. pointer-switch rollback steps
4. selective purge scope

**Step 2: Implement docs and SOPs**

Document:
1. Cloudflare rule ordering
2. emergency purge procedure
3. release cutover and rollback using `current.json`

**Step 3: Validate consistency with existing release flow**

Run: `rg -n "Cloudflare|current.json|rollback|cache" docs/runbooks navpay-admin/docs/ops/payment-app-release-runbook.md`  
Expected: all key terms present in new/updated docs.

**Step 4: Optional route smoke examples**

Add exact curl examples for:
1. manifest fetch
2. artifact download
3. denied admin route

**Step 5: Commit**

```bash
git add docs/runbooks/cloudflare-origin-cache-policy.md docs/runbooks/android-release-pointer-publish.md navpay-admin/docs/ops/payment-app-release-runbook.md
git commit -m "docs(ops): add cloudflare cache policy and pointer publish runbooks"
```

### Task 8: End-to-end verification in staging-like environment

**Files:**
- Create: `docs/reports/2026-04-08-prod-deployment-staging-verification.md`

**Step 1: Deploy infra/internal/public in staging order**

Run (example):
1. `docker compose -f navpay-admin/deploy/production/infra/compose.infra.yml up -d`
2. `docker compose -f navpay-admin/deploy/production/internal/compose.internal.yml up -d`
3. `docker compose -f navpay-admin/deploy/production/public/compose.public.yml up -d`

Expected: all services healthy.

**Step 2: Run route exposure verification**

Run scripted curls against public endpoint allowlist and denylist.

Expected:
1. allowlisted personal routes work
2. `/api/admin/*` and other blocked routes return `403`

**Step 3: Validate merchant allowlist behavior**

Run tests in `SHADOW` mode and `ENFORCE` mode.

Expected:
1. SHADOW logs decision but allows request
2. ENFORCE blocks non-allowlisted IP

**Step 4: Validate backup and restore verification**

Run backup script then restore verify script.

Expected: restore verify succeeds and report includes timing/size/status.

**Step 5: Commit verification report**

```bash
git add docs/reports/2026-04-08-prod-deployment-staging-verification.md
git commit -m "docs(report): add staging verification for production deployment plan"
```

### Task 9: Production readiness gate and rollout checklist

**Files:**
- Create: `docs/runbooks/prod-rollout-checklist-navpay.md`

**Step 1: Build release gate checklist**

Checklist includes:
1. private-link availability
2. backup freshness + restore verify pass
3. image digest/tag locked
4. Cloudflare policy checksum reviewed
5. rollback target preselected

**Step 2: Add operator anti-mistake controls**

1. mandatory two-person confirmation for prod
2. environment echo and branch/tag echo before deploy
3. post-deploy hard stop unless health checks pass

**Step 3: Add incident path for “publish stopped, download alive”**

Define exact communication and remediation steps.

**Step 4: Verify checklist completeness**

Run: `rg -n "rollback|backup|private-link|cloudflare|health" docs/runbooks/prod-rollout-checklist-navpay.md`  
Expected: all gate terms present.

**Step 5: Commit**

```bash
git add docs/runbooks/prod-rollout-checklist-navpay.md
git commit -m "docs(runbook): add production rollout checklist with guardrails"
```

### Task 10: Final regression commands before production handoff

**Files:**
- Modify: `docs/plans/2026-04-08-navpay-prod-deployment-implementation-plan.md` (append execution evidence checklist)

**Step 1: Run admin static quality gates**

Run:
1. `cd navpay-admin && yarn lint`
2. `cd navpay-admin && yarn typecheck`
3. `cd navpay-admin && yarn test --run`

Expected: all PASS.

**Step 2: Run targeted distribution tests**

Run (example):
1. `cd navpay-admin && yarn vitest run tests/unit/api-public-downloads-manifest.test.ts`
2. `cd navpay-admin && yarn vitest run tests/unit/publisher-payment-app-release-routes.test.ts`

Expected: PASS.

**Step 3: Run deployment script dry-run checks**

Run:
1. `bash navpay-admin/deploy/production/scripts/deploy_internal.sh --env prod --dry-run`
2. `bash navpay-admin/deploy/production/scripts/deploy_public.sh --env prod --dry-run`

Expected: PASS with explicit dry-run summary.

**Step 4: Append final evidence checklist to plan/report**

Record exact command outputs summary and timestamps.

**Step 5: Commit**

```bash
git add docs/plans/2026-04-08-navpay-prod-deployment-implementation-plan.md
git commit -m "docs: append final regression and handoff checklist"
```

---

## Execution order and ownership recommendation

1. Infra compose + backup first.
2. Internal/public compose and route allowlist second.
3. Application-layer merchant allowlist third.
4. Deploy scripts and runbooks fourth.
5. Staging verification and production checklist last.
