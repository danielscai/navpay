# Android Simplified Deployment Verification Report (2026-04-15)

## Scope
- Repo: `navpay-android`
- Phase: Task 7 (android 阶段链路验收)
- Date: 2026-04-15

## Commands and Results

1. Dry-run release
```bash
cd navpay-android && yarn release android --dry-run
```
- Result: PASS
- Key evidence:
  - Preflight executed (`git fetch --tags --force origin`, `git pull --ff-only origin main`)
  - Local package hook invoked: `tools/remote_release.sh(local-package)`
  - Record path: `releases/android/26.04.15.1/`

2. Dry-run deploy
```bash
cd navpay-android && yarn deploy android --dry-run
```
- Result: PASS
- Key evidence:
  - Copy plan only: APK copy to `../navpay-admin/download-site/site/android/<version>/navpay-android.apk`
  - Atomic pointer update planned: `current.json`

3. Real-run release
```bash
cd navpay-android && yarn release android
```
- Result: PASS
- Key evidence:
  - Tag pushed: `v26.04.15.1`
  - Local `assembleRelease` completed successfully
  - SHA256 emitted for release artifact
  - Done message: `[release:android] done version=26.04.15.1 tag=v26.04.15.1`

4. Real-run deploy
```bash
cd navpay-android && yarn deploy android
```
- Result: PASS
- Key evidence:
  - Copy executed to `../navpay-admin/download-site/site/android/26.04.15.1/navpay-android.apk`
  - Pointer update completed
  - Done message: `[deploy:android] done version=26.04.15.1 tag=v26.04.15.1`

5. Failure injection
```bash
cd navpay-android && yarn deploy android --version 99.99.99.9 --dry-run
```
- Result: PASS (correctly blocked)
- Key evidence:
  - Blocked by origin tag validation:
    - `[deploy:android] tag not found on origin: v99.99.99.9`

## Release Record Integrity
- Verified unified records are generated under:
  - `releases/android/<version>/metadata.json`
  - `releases/android/<version>/steps.log`
  - `releases/android/<version>/result.json`

## Notes
- Real release showed Kotlin daemon cache warnings and fallback compile path, but final build/deploy succeeded without manual intervention.
