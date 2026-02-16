# Repository Guidelines

## Project Structure & Module Organization
This workspace contains two independent projects:
- `navpay-android/`: Android client (Kotlin + Gradle). Main code is in `navpay-android/app/src/main/java/com/phonepe/checksumclient`, resources in `navpay-android/app/src/main/res`, tests in `navpay-android/app/src/test`, helper scripts in `navpay-android/tools`, and docs in `navpay-android/docs`.
- `navpay-admin/`: Admin web app (Next.js + TypeScript). App routes are in `navpay-admin/src/app`, shared UI in `navpay-admin/src/components`, domain logic in `navpay-admin/src/lib`, DB schema in `navpay-admin/src/db`, migrations in `navpay-admin/drizzle`, and tests in `navpay-admin/tests`.

## Build, Test, and Development Commands
- Android (`cd navpay-android`):
  - `yarn apk` or `./gradlew assembleDebug`: build debug APK.
  - `yarn emu1`: start AVD `phonepe1`.
  - `yarn i1`: build and install APK to the running emulator.
- Admin (`cd navpay-admin`):
  - `yarn dev`: start local server on `http://localhost:3000`.
  - `yarn build` and `yarn start`: production build and runtime check.
  - `yarn lint` and `yarn typecheck`: static quality gates.
  - `yarn test` and `yarn test:e2e`: run Vitest and Playwright suites.
  - `yarn db:migrate` and `yarn db:seed`: prepare local SQLite data.

## Coding Style & Naming Conventions
- Kotlin: 4-space indentation, `PascalCase` classes, `camelCase` members, Android resource files in `snake_case` (for example, `fragment_login.xml`).
- TypeScript/React: strict typing, `@/*` import alias for `src/*`, components in `PascalCase`, utility modules in concise domain-oriented names (for example, `payout-lock.ts`).
- Run lint/type checks before opening a PR.

## Testing Guidelines
- Android: add unit tests under `navpay-android/app/src/test/...` with `*Test.kt` naming; run `./gradlew test` when changing app logic.
- Admin unit tests: `navpay-admin/tests/unit/**/*.test.ts` (deterministic, no live network).
- Admin E2E tests: `navpay-admin/tests/e2e/**/*.spec.ts`; keep fixtures isolated and DB-aware.

## Commit & Pull Request Guidelines
- Follow Conventional Commits: `feat(scope): ...`, `fix(scope): ...`, `docs: ...`, `chore: ...`.
- Keep commits focused by project (`navpay-android` vs `navpay-admin`) and include migrations with related code changes.
- PRs should include:
  - purpose and impacted paths,
  - verification commands run,
  - screenshots for UI changes,
  - DB migration/backfill notes when schema changes.

## Security & Configuration Tips
- Never commit secrets; use `.env` files (`navpay-admin/.env.example` as template).
- Keep local DB paths under `navpay-admin/data/` and avoid committing generated DB/test artifacts.
- For Android emulator API access, prefer host mapping (`10.0.2.2`) over `localhost`.

## Workspace Git & Worktree Rules
- This top-level folder is an orchestration repository only. Track shared docs/scripts/metadata here and keep app source repos independent.
- Never add nested repositories (`navpay-android/`, `navpay-admin/`, `navpay-landing/`, `navpay-otp/`, `navpay-tgbot/`) into the top-level Git index.
- Use centralized worktrees under `worktrees/` only.
- Required worktree layout:
  - `worktrees/navpay-android/<ticket-or-branch>`
  - `worktrees/navpay-admin/<ticket-or-branch>`
- Create new worktrees from source repos with explicit target path:
  - `git -C navpay-android worktree add worktrees/navpay-android/<ticket-or-branch> <base-branch> -b <new-branch>`
  - `git -C navpay-admin worktree add worktrees/navpay-admin/<ticket-or-branch> <base-branch> -b <new-branch>`
- Remove finished worktrees with:
  - `git -C navpay-android worktree remove worktrees/navpay-android/<ticket-or-branch>`
  - `git -C navpay-admin worktree remove worktrees/navpay-admin/<ticket-or-branch>`
