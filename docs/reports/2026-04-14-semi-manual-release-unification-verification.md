# 2026-04-14 Semi-Manual Release Unification Verification

## Scope
- Repos: `navpay-admin`, `navpay-android`, `navpay-phonepe`
- Contract under verification:
  - `yarn release <product>`
  - `yarn deploy <product> [--version]`
- Version policy:
  - Business version: `YY.MM.DD.N`
  - Git tag: `vYY.MM.DD.N`

## Admin (`navpay-admin`)

### Dry-run
1. `cd navpay-admin && yarn release admin --dry-run`
- Result: PASS
- Evidence:
  - `remote-build ... --tag v26.04.15.0 --dry-run`
  - release record written: `releases/admin/26.04.15.0`

2. `cd navpay-admin && yarn deploy admin --dry-run`
- Result: PASS
- Evidence:
  - `remote-deploy ... --tag v26.04.14.3 --dry-run`
  - release record written: `releases/admin/26.04.14.3`

### Real-run
3. `cd navpay-admin && yarn release admin`
- Result: FAIL (blocked by remote connectivity)
- Error:
  - `Connection closed by UNKNOWN port 65535`
  - failure surfaced by release-core

4. `cd navpay-admin && yarn deploy admin`
- Result: FAIL (blocked by remote connectivity)
- Error:
  - `Connection closed by UNKNOWN port 65535`
  - failure surfaced by release-core

## Android (`navpay-android`)

### Dry-run
1. `cd navpay-android && yarn release android --dry-run`
- Result: PASS
- Evidence:
  - preflight logs present
  - planned tag: `v26.04.15.0`
  - release record path: `releases/android/26.04.15.0`

2. `cd navpay-android && yarn deploy android --dry-run`
- Result: PASS
- Evidence:
  - default version resolved from latest local tag
  - origin-tag check passed
  - atomic `current.json` update step logged

### Real-run
3. `cd navpay-android && yarn release android`
- Result: PARTIAL FAIL
- Evidence:
  - tag pushed successfully: `v26.04.15.0`
  - failed at release hook local path permission:
    - `mkdir: /opt/navpay: Permission denied`

4. `cd navpay-android && yarn deploy android`
- Result: PASS
- Evidence:
  - copied APK to version dir
  - completed with `version=26.04.15.0 tag=v26.04.15.0`

## PhonePe (`navpay-phonepe`)

### Dry-run
1. `cd navpay-phonepe && yarn release phonepe --dry-run`
- Result: PASS
- Evidence:
  - planned tag: `v26.04.15.0`
  - release record path: `releases/phonepe/26.04.15.0`

2. `cd navpay-phonepe && yarn deploy phonepe --dry-run`
- Result: PASS
- Evidence:
  - default version resolved from latest local tag
  - origin-tag check passed
  - atomic `current.json` update step logged
  - admin activation call logged (dry-run)

### Real-run
3. `cd navpay-phonepe && yarn release phonepe`
- Result: PARTIAL FAIL
- Evidence:
  - tag pushed successfully: `v26.04.15.0`
  - failed at remote step:
    - `Connection closed by UNKNOWN port 65535`

4. `cd navpay-phonepe && yarn deploy phonepe`
- Result: FAIL
- Error:
  - `artifact not found: cache/profiles/full/build/patched_signed.apk`

## Failure Injection: missing origin tag must block deploy

Command:
- `cd navpay-android && yarn deploy android --version 99.99.99.9 --dry-run`

Result:
- PASS (expected block)
- Error:
  - `[deploy:android] tag not found on origin: v99.99.99.9`

Conclusion:
- Contract requirement "deploy default/explicit version must exist on origin" is enforced.

## Release Record Check

Observed record directories/files were generated under unified shape:
- `releases/<product>/<version>/metadata.json`
- `releases/<product>/<version>/steps.log`
- `releases/<product>/<version>/result.json`

This includes both success and failure paths (failure reasons persisted in `result.json`/`steps.log`).
