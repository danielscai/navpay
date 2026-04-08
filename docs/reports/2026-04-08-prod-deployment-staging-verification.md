# 2026-04-08 Production Deployment Staging Verification Report

## Scope
This report records staging-like execution evidence for production deployment plan Task 8.

## Environment Notes
- Execution time (UTC): 2026-04-08
- Validation workspace:
  - `/Users/danielscai/Documents/workspace/navpay/worktrees/navpay-admin/prod-deploy-20260408`
- Internal app image in `.env.example` (`ghcr.io/navpay/navpay-admin:sha-6800838`) was not pullable in local staging simulation (`denied`).
- For topology bring-up only, temporary command-line override was used:
  - `ADMIN_INTERNAL_IMAGE=nginx:1.27.0-alpine`
  - `APP_IMAGE=nginx:1.27.0-alpine`

## 1. Deploy Order Verification
Commands executed:
```bash
cd /Users/danielscai/Documents/workspace/navpay/worktrees/navpay-admin/prod-deploy-20260408

docker compose -f deploy/production/infra/compose.infra.yml up -d
ADMIN_INTERNAL_IMAGE=nginx:1.27.0-alpine docker compose --env-file deploy/production/internal/.env.example -f deploy/production/internal/compose.internal.yml up -d
APP_IMAGE=nginx:1.27.0-alpine docker compose --env-file deploy/production/public/.env.example -f deploy/production/public/compose.public.yml up -d
```

Status evidence:
```bash
docker compose -f deploy/production/infra/compose.infra.yml ps
docker compose --env-file deploy/production/internal/.env.example -f deploy/production/internal/compose.internal.yml ps
docker compose --env-file deploy/production/public/.env.example -f deploy/production/public/compose.public.yml ps
```

Observed:
- `infra` services up, `postgres`/`redis` healthy.
- `internal` service up.
- `public` services up with reverse-proxy on `80/443`.

## 2. Route Exposure Verification
Command executed:
```bash
bash deploy/production/public/scripts/test_route_policy.sh
```

Observed:
- allowlisted personal route: non-403 (`502` in this simulation)
- denied admin route: `403`

Interpretation:
- Proxy deny rule for `/api/admin/*` is effective.
- Upstream app behavior is simulated (non-production image), so allowlisted route returned `502` instead of business payload.

## 3. Merchant Allowlist Behavior Verification
Command executed:
```bash
yarn vitest run tests/unit/merchant-ip-allowlist.test.ts tests/unit/merchant-ip-trusted-source.test.ts
```

Observed:
- 2 test files passed, 7 tests passed.
- Includes `OFF` / `SHADOW` / `ENFORCE`, IPv4/IPv6 CIDR, trusted `CF-Connecting-IP` extraction paths.

## 4. Backup and Restore Verification
Command executed:
```bash
bash deploy/production/infra/scripts/backup_pg.sh
bash deploy/production/infra/scripts/restore_verify_pg.sh
```

Observed:
- Failed at backup step: `ERROR: pg_dump is required`

Result:
- Backup/restore verification is **blocked** in this host environment due to missing PostgreSQL client tooling.

## 5. Staging Task Verdict
- Partial pass:
  - deploy ordering and container topology verified
  - route allowlist/deny behavior verified (proxy-level)
  - merchant IP allowlist logic verified via unit tests
- Blocked:
  - backup/restore end-to-end verification cannot complete until `pg_dump/pg_restore/psql/createdb/dropdb` are available on execution host or scripts are adapted to containerized client execution.
