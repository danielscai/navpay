# Admin Direct Runtime Verification Report (2026-04-15)

## Scope
- Repo: `navpay-admin`
- Phase: Task 5 (admin 阶段链路验收)
- Date: 2026-04-15

## Commands and Results

1. Dry-run release
```bash
cd navpay-admin && yarn release admin --dry-run
```
- Result: PASS
- Evidence:
  - Preflight executed (`git fetch --tags --force origin`, `git pull --ff-only origin main`)
  - Remote build dispatch shown
  - Release records created at `releases/admin/26.04.15.1/`

2. Dry-run deploy
```bash
cd navpay-admin && yarn deploy admin --dry-run
```
- Result: PASS
- Evidence:
  - Output shows direct runtime steps only:
    - `git fetch --tags --force origin`
    - `git checkout -f tags/v26.04.15.0`
    - `yarn install --immutable`
    - `yarn build`
    - `pm2 startOrReload ecosystem.config.cjs --env production`
    - `nginx -t && nginx -s reload`
  - Release records created at `releases/admin/26.04.15.0/`

3. Real-run release
```bash
cd navpay-admin && yarn release admin
```
- Result: BLOCKED (external/runtime gate)
- Block details:
  - SSH proxy issue resolved first by removing SOCKS5 `ProxyCommand` from `~/.ssh/config` host `139.59.16.24`.
  - After direct SSH succeeded, remote run proceeded to lint and then failed on typecheck.
  - Remote typecheck errors observed:
    - `src/app/api/personal/route.ts(38,25): TS2322`
    - `src/app/api/personal/wallets/[walletId]/receive-off/route.ts(20,54): TS2737`
    - `src/app/api/personal/wallets/route.ts(29,50): TS2737`
    - `src/app/api/personal/wallets/route.ts(30,46): TS2737`
    - `src/app/api/personal/wallets/route.ts(65,26): TS2737`
- Log evidence:
  - `releases/prod/runs/20260415070352-64naup.json` status=`failed`, tag=`v26.04.15.2`

4. Real-run deploy
```bash
cd navpay-admin && yarn deploy admin
```
- Result: BLOCKED (config missing)
- Block details:
  - `scripts/remote-deploy-admin-direct.sh` requires `--host` (or `NAVPAY_ADMIN_HOST`) in non-dry-run.
  - Actual error: `--host is required unless --dry-run is set`
- Log evidence:
  - `releases/admin/unknown/result.json`

5. Failure injection
```bash
cd navpay-admin && yarn deploy admin --version 99.99.99.9 --dry-run
```
- Result: PASS (correctly blocked)
- Evidence:
  - Fails by origin tag check:
    - `git ls-remote --exit-code --tags origin refs/tags/v99.99.99.9`
  - Record: `releases/admin/99.99.99.9/result.json`

## Release Record Integrity
- Verified unified release record files are generated under:
  - `releases/admin/<version>/metadata.json`
  - `releases/admin/<version>/steps.log`
  - `releases/admin/<version>/result.json`

## Blockers and Recovery Suggestions
1. Remote typecheck gate failure (real release)
- Suggestion: align/fix TypeScript target/config and nullable type issues before next real release.

2. Real deploy host config not provided
- Suggestion: provide `NAVPAY_ADMIN_HOST` in deploy runtime or make release-core deploy path pass `--host` explicitly.

3. Proxy dependency
- Suggestion: keep direct SSH config for release host (no local SOCKS dependency) or add explicit non-proxy SSH host alias for CI/release usage.
