# PhonePe Simplified Deployment Verification Report (2026-04-15)

## Scope
- Repo: `navpay-phonepe`
- Phase: Task 9 (phonepe 阶段链路验收)
- Date: 2026-04-15

## Commands and Results

1. Dry-run release
```bash
cd navpay-phonepe && yarn release phonepe --dry-run
```
- Result: PASS
- Key evidence:
  - Preflight executed (`git fetch --tags --force origin`, `git pull --ff-only origin main`)
  - Local package hook invoked: `scripts/remote_release.sh(local-package)`

2. Dry-run deploy
```bash
cd navpay-phonepe && yarn deploy phonepe --dry-run
```
- Result: PASS
- Key evidence:
  - Copy + current.json atomic update + admin activate API (dry-run) are printed.
  - No remote runtime command path involved.

3. Real-run release
```bash
cd navpay-phonepe && yarn release phonepe
```
- Result: BLOCKED
- Block details:
  - Tag push succeeded: `v26.04.15.1`
  - Fails at quality gate script lookup:
    - `python3: can't open file '.../scripts/release_check.py': [Errno 2] No such file or directory`

4. Real-run deploy
```bash
cd navpay-phonepe && yarn deploy phonepe
```
- Result: BLOCKED
- Block details:
  - Release artifact missing:
    - `[deploy:phonepe] artifact not found: cache/profiles/full/build/patched_signed.apk`

5. Failure injection
```bash
cd navpay-phonepe && yarn deploy phonepe --version 99.99.99.9 --dry-run
```
- Result: PASS (correctly blocked)
- Key evidence:
  - Blocked by origin tag validation:
    - `[deploy:phonepe] tag not found on origin: v99.99.99.9`

## Release Record Integrity
- Verified release records continue to be written under:
  - `releases/phonepe/<version>/metadata.json`
  - `releases/phonepe/<version>/steps.log`
  - `releases/phonepe/<version>/result.json`

## Recovery Suggestions
1. Replace/remove missing `scripts/release_check.py` dependency in local release hook.
2. Ensure local `release phonepe` produces artifact at `cache/profiles/full/build/patched_signed.apk` before deploy step.
