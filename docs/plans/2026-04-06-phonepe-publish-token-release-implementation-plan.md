# PhonePe Publish Token Release Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a token-based publish pipeline so `navpay-phonepe` can manually publish new PhonePe packages into `navpay-admin` via `--env` (default local), without user-session auth.

**Architecture:** `navpay-admin` owns release token lifecycle (hash-only storage, scope-limited auth guard, publish-only routes). `navpay-phonepe` provides a CLI that resolves environment, reads APK metadata, performs idempotency precheck, then calls create/upload/activate. Audit trail is written into release events with token actor identity.

**Tech Stack:** Next.js route handlers, TypeScript, PostgreSQL (`pg`/Prisma migration flow), React admin panel, Node CLI (`tsx`), SHA-256 hashing, Vitest.

---

### Task 1: Add Release Token Persistence Layer

**Files:**
- Create: `navpay-admin/drizzle/00xx_release_tokens.sql`
- Modify: `navpay-admin/src/db/schema.ts`
- Modify: `navpay-admin/src/lib/system-config.ts`
- Test: `navpay-admin/tests/unit/release-token-repo.test.ts`

**Step 1: Write the failing test**

```ts
it("stores hash only and rejects plaintext lookup", async () => {
  const token = await createReleaseToken({ name: "local", scope: "payment_app_release" });
  expect(token.plain).toMatch(/^nprt_/);
  const row = await findReleaseTokenRowById(token.id);
  expect(row?.token_hash).toBeTruthy();
  expect(row?.token_hash).not.toContain(token.plain);
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/release-token-repo.test.ts`
Expected: FAIL with missing table/repo symbols.

**Step 3: Write minimal implementation**

```ts
export function hashReleaseToken(raw: string): string {
  return crypto.createHash("sha256").update(raw).digest("hex");
}
```

Create SQL migration for `release_tokens` with columns:
- `id`, `name`, `scope`, `token_hash`, `status`, `last_used_at_ms`, `created_at_ms`, `updated_at_ms`.

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/release-token-repo.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-admin/drizzle/00xx_release_tokens.sql navpay-admin/src/db/schema.ts navpay-admin/src/lib/system-config.ts navpay-admin/tests/unit/release-token-repo.test.ts
git commit -m "feat(admin): add scoped release token persistence"
```

### Task 2: Build Publish-Only Bearer Auth Guard

**Files:**
- Create: `navpay-admin/src/lib/release-token-auth.ts`
- Modify: `navpay-admin/src/lib/api.ts`
- Test: `navpay-admin/tests/unit/release-token-auth.test.ts`

**Step 1: Write the failing test**

```ts
it("allows active payment_app_release token and denies revoked token", async () => {
  const ok = await requireReleaseToken("Bearer nprt_valid");
  expect(ok.scope).toBe("payment_app_release");
  await revokeReleaseToken(ok.tokenId);
  await expect(requireReleaseToken("Bearer nprt_valid")).rejects.toThrow("token_revoked");
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/release-token-auth.test.ts`
Expected: FAIL with missing auth guard.

**Step 3: Write minimal implementation**

```ts
export async function requireReleaseToken(req: NextRequest): Promise<{ tokenId: string; actor: string }> {
  const raw = readBearer(req.headers.get("authorization"));
  const hash = hashReleaseToken(raw);
  const token = await findActiveReleaseTokenByHash(hash);
  if (!token || token.scope !== "payment_app_release") throw new Error("forbidden");
  await touchReleaseTokenLastUsed(token.id);
  return { tokenId: token.id, actor: `token:${token.id}` };
}
```

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/release-token-auth.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-admin/src/lib/release-token-auth.ts navpay-admin/src/lib/api.ts navpay-admin/tests/unit/release-token-auth.test.ts
git commit -m "feat(admin): add release token bearer auth guard"
```

### Task 3: Expose Token Management in System Settings

**Files:**
- Modify: `navpay-admin/src/app/admin/ops/settings/page.tsx`
- Create: `navpay-admin/src/app/api/admin/system/release-tokens/route.ts`
- Create: `navpay-admin/src/app/api/admin/system/release-tokens/[tokenId]/revoke/route.ts`
- Test: `navpay-admin/tests/unit/system-release-tokens-route.test.ts`
- Test: `navpay-admin/tests/unit/ops-settings-release-token-panel.test.tsx`

**Step 1: Write the failing tests**

```ts
it("returns plaintext token only on create response", async () => {
  const res = await POST_createToken(req("local-default"));
  const json = await res.json();
  expect(json.row.plainToken).toMatch(/^nprt_/);
  const list = await GET_listTokens();
  expect(JSON.stringify(await list.json())).not.toContain("nprt_");
});
```

**Step 2: Run tests to verify they fail**

Run: `cd navpay-admin && yarn test tests/unit/system-release-tokens-route.test.ts tests/unit/ops-settings-release-token-panel.test.tsx`
Expected: FAIL with missing routes/UI.

**Step 3: Write minimal implementation**

```ts
// create route response shape
return NextResponse.json({
  ok: true,
  row: { id, name, scope: "payment_app_release", status: "active", plainToken },
});
```

Add UI section in system settings with actions:
- Create token
- Revoke token
- Show `lastUsedAt` and `status`

**Step 4: Run tests to verify they pass**

Run: `cd navpay-admin && yarn test tests/unit/system-release-tokens-route.test.ts tests/unit/ops-settings-release-token-panel.test.tsx`
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-admin/src/app/admin/ops/settings/page.tsx navpay-admin/src/app/api/admin/system/release-tokens/route.ts navpay-admin/src/app/api/admin/system/release-tokens/[tokenId]/revoke/route.ts navpay-admin/tests/unit/system-release-tokens-route.test.ts navpay-admin/tests/unit/ops-settings-release-token-panel.test.tsx
git commit -m "feat(admin): add release token management in system settings"
```

### Task 4: Add Publish Token Route Path for Create/Upload/Activate

**Files:**
- Create: `navpay-admin/src/app/api/publisher/payment-apps/[appId]/releases/route.ts`
- Create: `navpay-admin/src/app/api/publisher/payment-apps/[appId]/releases/[releaseId]/artifacts/route.ts`
- Create: `navpay-admin/src/app/api/publisher/payment-apps/[appId]/releases/[releaseId]/activate/route.ts`
- Modify: `navpay-admin/src/lib/payment-app-release-service.ts`
- Test: `navpay-admin/tests/unit/publisher-payment-app-release-routes.test.ts`

**Step 1: Write the failing test**

```ts
it("publisher token can create/upload/activate and logs token actor", async () => {
  const release = await publisherCreateRelease(token, payload);
  await publisherUploadArtifact(token, release.id, file);
  const activated = await publisherActivateRelease(token, release.id);
  expect(activated.status).toBe("active");
  const events = await loadReleaseEvents(release.id);
  expect(events.some((e) => e.actorUserId?.startsWith("token:"))).toBe(true);
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/publisher-payment-app-release-routes.test.ts`
Expected: FAIL with missing routes.

**Step 3: Write minimal implementation**

```ts
const tokenActor = await requireReleaseToken(req);
const row = await createPaymentAppRelease(appId, tokenActor.actor, body.data);
```

Mirror same guard in upload/activate publisher routes.

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/publisher-payment-app-release-routes.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-admin/src/app/api/publisher/payment-apps navpay-admin/src/lib/payment-app-release-service.ts navpay-admin/tests/unit/publisher-payment-app-release-routes.test.ts
git commit -m "feat(admin): add publisher release routes with token auth"
```

### Task 5: Seed Local Default Publish Token (Local Only)

**Files:**
- Create: `navpay-admin/scripts/seed-default-release-token.ts`
- Modify: `navpay-admin/scripts/db-seed.ts`
- Modify: `navpay-admin/package.json`
- Test: `navpay-admin/tests/unit/seed-default-release-token.test.ts`

**Step 1: Write the failing test**

```ts
it("creates default token in local mode and skips in non-local", async () => {
  process.env.NODE_ENV = "development";
  const local = await ensureDefaultReleaseToken();
  expect(local.created || local.exists).toBe(true);
  process.env.APP_ENV = "staging";
  const staging = await ensureDefaultReleaseToken();
  expect(staging.skipped).toBe(true);
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/seed-default-release-token.test.ts`
Expected: FAIL with missing seed utility.

**Step 3: Write minimal implementation**

```ts
if (!isLocalEnv()) return { skipped: true };
return await upsertDefaultReleaseToken("local-phonepe-publisher");
```

Expose script:
- `yarn db:seed:release-token`

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/seed-default-release-token.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-admin/scripts/seed-default-release-token.ts navpay-admin/scripts/db-seed.ts navpay-admin/package.json navpay-admin/tests/unit/seed-default-release-token.test.ts
git commit -m "feat(admin): seed local default publish token"
```

### Task 6: Add navpay-phonepe Publisher CLI (`--env` default local)

**Files:**
- Create: `navpay-phonepe/scripts/release_to_admin.ts`
- Modify: `navpay-phonepe/package.json`
- Create: `navpay-phonepe/docs/release-to-admin.md`
- Test: `navpay-phonepe/scripts/__tests__/release_to_admin.test.ts`

**Step 1: Write the failing test**

```ts
it("uses local env by default and skips duplicate active release", async () => {
  const out = await runReleaseCli(["--apk", "cache/profiles/full/build/patched_signed.apk"], fakeApi);
  expect(out.targetEnv).toBe("local");
  expect(out.idempotent).toBe(true);
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-phonepe && yarn test scripts/__tests__/release_to_admin.test.ts`
Expected: FAIL with missing CLI.

**Step 3: Write minimal implementation**

```ts
const envName = argv.env ?? "local";
const baseUrl = resolveBaseUrl(envName, argv.baseUrl);
const token = argv.token ?? process.env.RELEASE_TOKEN;

const checksum = sha256File(apkPath);
const active = await api.getActiveRelease(appId);
if (active?.versionCode === versionCode && active?.baseSha256 === checksum) {
  return { ok: true, idempotent: true };
}
```

Then run create -> upload -> activate with retry wrapper for transient network errors.

**Step 4: Run tests to verify they pass**

Run: `cd navpay-phonepe && yarn test scripts/__tests__/release_to_admin.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add navpay-phonepe/scripts/release_to_admin.ts navpay-phonepe/package.json navpay-phonepe/docs/release-to-admin.md navpay-phonepe/scripts/__tests__/release_to_admin.test.ts
git commit -m "feat(phonepe): add token-based publish CLI to navpay-admin"
```

### Task 7: End-to-End Verification and Documentation Sync

**Files:**
- Modify: `docs/plans/2026-04-06-phonepe-local-publish-to-navpay-admin-design.md`
- Create: `navpay-admin/docs/reports/2026-04-06-publish-token-e2e-report.md`

**Step 1: Run admin quality gates**

Run:
```bash
cd navpay-admin
yarn lint
yarn typecheck
yarn test tests/unit/release-token-repo.test.ts tests/unit/release-token-auth.test.ts tests/unit/system-release-tokens-route.test.ts tests/unit/publisher-payment-app-release-routes.test.ts
```
Expected: PASS.

**Step 2: Run publisher CLI local e2e**

Run:
```bash
cd navpay-admin
yarn db:seed:release-token
cd ../navpay-phonepe
yarn release:to-admin --env local --apk cache/profiles/full/build/patched_signed.apk
```
Expected: release created/uploaded/activated with summary output and releaseId.

**Step 3: Validate DB and release history**

Run:
```bash
cd navpay-admin
node --env-file=.env.local --import tsx -e "import { sqlQuery } from './src/lib/db'; const rows = await sqlQuery(\"select event_type, actor_user_id from payment_app_release_events order by created_at_ms desc limit 5\"); console.log(rows.rows); process.exit(0);"
```
Expected: latest events include `release.created` / `release.activated` with `actor_user_id` prefixed by `token:`.

**Step 4: Commit verification docs**

```bash
git add docs/plans/2026-04-06-phonepe-local-publish-to-navpay-admin-design.md navpay-admin/docs/reports/2026-04-06-publish-token-e2e-report.md
git commit -m "docs: add publish-token local e2e verification report"
```

## Implementation Notes

- Follow `@test-driven-development` for every task before implementation.
- Use `@systematic-debugging` on any failing integration test before patching logic.
- Keep commits focused per task; do not batch multiple tasks into one commit.
- YAGNI guardrails:
  - no generic token RBAC framework in this scope
  - no background publisher daemon
  - no multi-artifact auto-discovery in V1 (manual base artifact input is enough)

