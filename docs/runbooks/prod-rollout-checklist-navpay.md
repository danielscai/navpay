# NavPay Production Rollout Checklist

## 1. Release Gate (Must Pass Before Rollout)

- [ ] Private-link availability confirmed between Node B (public/download) and Node A (infra/internal).
- [ ] Backup freshness is valid (latest status within threshold) and backup reports `status=success`.
- [ ] Restore verification passed for latest backup.
- [ ] Image references are immutable (commit SHA or digest), no `latest` tag anywhere.
- [ ] Cloudflare policy checksum/review completed for cache and bypass rules.
- [ ] cloudflare policy snapshot archived with checksum for release ticket.
- [ ] Explicit rollback target selected (previous known-good SHA release pointer).

## 2. Operator Anti-Mistake Controls

- [ ] Two-person confirmation recorded for production action (`operator` + `reviewer`).
- [ ] Command line prints environment echo before execution (must show `--env prod`).
- [ ] Command line prints branch/tag echo before execution (target SHA must match release note).
- [ ] Production execution requires `--confirm` and is blocked without it.
- [ ] Post-deploy hard stop: do not proceed to traffic cutover if health checks are not all green.

## 3. Node Boundary Verification

- [ ] Node A runs only `infra + internal` workloads.
- [ ] Node B runs only `public + download` workloads.
- [ ] Cloudflare is used only as acceleration/security layer; origin remains source of truth.
- [ ] Merchant IP allowlist enforcement scope is restricted to merchant API key routes.

## 4. Rollout Execution Sequence

1. Run preflight checks (`backup`, immutable image, confirmation gate).
2. Deploy internal layer first.
3. Run internal health verification.
4. Deploy public/download layer.
5. Run public route + health verification.
6. Confirm Cloudflare selective purge scope (`current.json` + lightweight manifest only).

## 5. Incident Path: "Publish Stopped, Download Alive"

### Trigger

- Private-link between Node B and Node A is unavailable.

### Required behavior

- Stop all new publish/release activation actions immediately.
- Keep existing old-version downloads online (origin + Cloudflare cache serve existing immutable assets).

### Communication

1. Announce incident in ops channel with timestamp and affected path (`publish` only).
2. Notify merchant support that new release publish is paused, download path remains available.
3. Record current active `current.json` pointer SHA in incident ticket.

### Remediation

1. Recover private-link connectivity.
2. Re-run preflight + health checks.
3. Resume publish only after reviewer sign-off.
4. If uncertainty remains, rollback pointer to last known-good SHA and keep publish paused.

## 6. Final Go/No-Go Gate

- [ ] health checks all pass
- [ ] rollback command tested in dry-run mode
- [ ] backup + restore evidence attached
- [ ] Cloudflare selective purge evidence attached
- [ ] operator + reviewer both mark "GO"

If any item fails, decision is **NO-GO**.
