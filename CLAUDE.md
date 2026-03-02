# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Workspace Overview

This top-level folder is an orchestration-only repository. The actual app source repos live as independent git repos inside it:

- `navpay-admin/` — Next.js 16 + TypeScript admin web app and API backend (PostgreSQL + Redis)
- `navpay-android/` — Kotlin Android client app
- `navpay-landing/` — Next.js 16 marketing site (port 3010)
- `navpay-otp/` — Fastify standalone OTP/WhatsApp verification service (port 19090)
- `navpay-tgbot/` — Grammy Telegram bot for account binding

**Never add nested repos into the top-level git index.**

## Commands

### navpay-admin
```bash
yarn dev            # Dev server at http://localhost:3000
yarn build          # Production build
yarn lint           # ESLint
yarn typecheck      # tsc --noEmit
yarn db:migrate     # Apply DB migrations
yarn db:seed        # Seed demo users and sample data
yarn test           # Vitest unit tests
yarn test:e2e       # Playwright E2E tests (requires local Postgres + Redis)
yarn test:e2e:clean # Clear .next then run E2E (use for regression)
yarn test:all       # Unit + E2E
```

### navpay-android
```bash
yarn apk            # Build debug APK (./gradlew assembleDebug)
yarn emu1           # Start AVD "phonepe1"
yarn i1             # Build + install APK to running phonepe1 emulator
yarn avds           # List installed AVD names
```
The app calls the local API via emulator host mapping: `http://10.0.2.2:3000/api/personal`.

### navpay-otp / navpay-tgbot / navpay-landing
```bash
yarn dev / yarn start   # Dev/production server
yarn build              # TypeScript compilation
yarn test               # Vitest unit tests
```

## Architecture: navpay-admin

**Stack**: Next.js App Router, React 19, TypeScript strict, Prisma 6 (PostgreSQL), Redis, NextAuth 4, WebAuthn (Passkeys), TOTP 2FA.

**Layer structure**:
- `src/app/api/` — Route handlers split by role: `admin/`, `personal/`, `v1/collect/`, `v1/payout/`
- `src/lib/` — All domain logic: payment processing, auth helpers, OTP client, RBAC, webhook callbacks, recharge (crypto), scenario factory for testing
- `src/components/` — Shared React components
- `src/auth/` — NextAuth + 2FA logic
- `prisma/schema.prisma` — Source of truth for the 23-table schema
- `migrations/` — SQL migrations run by `scripts/db-migrate.ts` via `yarn db:migrate`
- `tests/unit/` — Vitest (`**/*.test.ts`, deterministic, no live network)
- `tests/e2e/` — Playwright (`**/*.spec.ts`, DB-aware, isolated fixtures)
- `docs/testcases/` — Long-term testcase management; `catalog.json` is the machine-readable index; update it whenever a suite changes. Do not put testcases in `docs/plans/`.

**Key domain files in `src/lib/`**:
- `auth.ts`, `rbac.ts` — Auth and role/permission enforcement
- `payment-person.ts` — Payment person assignment and rotation logic
- `security-stepup-registry.ts` — Registry of all sensitive ops requiring step-up auth
- `otp-client.ts`, `otp-local.ts` — OTP service integration
- `merchant-*.ts`, `personal-*.ts` — Merchant and personal account domain logic
- `admin-lists/` — Performance-optimized list queries

## Architecture: navpay-android

**Stack**: Kotlin, Android SDK 24–36, Gradle 8, OkHttp 4, Fragment-based navigation.

- `app/src/main/java/com/phonepe/checksumclient/` — All Kotlin source
- UI logic lives in Fragments; HTTP in `ApiClient`
- No automated test suite yet; manual smoke test: login + me + order lists

## Coding Conventions

**TypeScript**: strict mode, `@/*` import alias for `src/*`, `PascalCase` components, domain-oriented utility names (`payout-lock.ts`).

**Kotlin**: 4-space indent, `PascalCase` classes, `camelCase` members, `snake_case` Android resources (`fragment_login.xml`).

**Shell scripts** in `tools/`: must be `bash -n` clean, use `set -euo pipefail`.

## Security Step-Up Integration

Any new sensitive operation must be integrated end-to-end in the same change:
1. Add/update `opId` in `src/lib/security-stepup-registry.ts`
2. Enforce backend gate: `requireSecurityStepUpForOp(req, "<opId>")` in the route
3. Attach frontend hint: `<StepUpHint opId="<opId>" />` on the triggering button
4. Add unit tests for opId mapping, route gate, and UI hint

Do not ship partial step-up integration.

## Ops Tab Layout Standard (navpay-admin)

All `admin/ops/settings` tab panels must render inside: `min-w-0 max-w-full overflow-x-hidden`.

Tables/lists in tab content must use a local horizontal scroller on their own container (`w-full min-w-0 max-w-full overflow-x-auto`) with an explicit `min-w-[...]`. New/updated tab panels need a unit test asserting these constraints.

## Worktrees

Use centralized worktrees only:
```bash
# Create
git -C navpay-admin worktree add worktrees/navpay-admin/<ticket> <base-branch> -b <new-branch>
git -C navpay-android worktree add worktrees/navpay-android/<ticket> <base-branch> -b <new-branch>

# Remove
git -C navpay-admin worktree remove worktrees/navpay-admin/<ticket>
git -C navpay-android worktree remove worktrees/navpay-android/<ticket>
```

### navpay-admin Worktree Isolation

Each worktree needs its own `.env.local` (copy from `.env.example`). Set:

| Variable | Value |
|---|---|
| `PORT` | `3101`–`3199` (reserve `3000` for main) |
| `APP_BASE_URL` / `NEXTAUTH_URL` | `http://localhost:<port>` |
| `AUTH_SECRET` | unique random secret |
| `COOKIE_NAMESPACE` | `<ticket_slug>` (lowercase, `-` → `_`) |
| `DATABASE_URL` | `postgres://navpay_admin:navpay_admin_pwd@127.0.0.1:5432/navpay_admin_<ticket_slug>` |
| `REDIS_URL` | `redis://127.0.0.1:6379/<index>` (index 1–n; reserve `0` for main) |

Bootstrap:
```bash
createdb -O navpay_admin navpay_admin_<ticket_slug>
yarn db:migrate && yarn db:seed
PORT=<port> yarn dev
```

Cleanup:
```bash
git -C navpay-admin worktree remove worktrees/navpay-admin/<ticket>
dropdb navpay_admin_<ticket_slug>
redis-cli -n <index> FLUSHDB
```

## DB/Perf Agent Tasks (navpay-admin)

For DB/perf tasks, always use an isolated worktree DB. Auto-prepare `.env.local` with isolated `DATABASE_URL`, `AUTH_SECRET`, encryption keys, `COOKIE_NAMESPACE`. Run setup autonomously: create DB → `yarn db:migrate` → `yarn prisma generate` → `yarn db:seed`. Pressure test data must be tagged and cleanup scripts included in the same change.
