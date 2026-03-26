# Intercept Checksum Real Log Validation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Verify whether the new `navpay-phonepe/src/services/checksum` service can generate usable anti-replay checksum values for real `navpay-admin` intercept logs, then either lock that behavior down with a real-data test or fix the root cause if validation fails.

**Architecture:** Treat this as a cross-repo validation flow. First, extract one or more real replayable PhonePe log samples from `navpay-admin` and convert them into stable fixture data with exact `path`, `body`, original headers, and replay metadata. Then point `navpay-admin` and any validation scripts at the new checksum service on port `19190`, replay the real sample through the existing admin resend flow, and compare the outcome with the old `19090` helper behavior only when triage is needed. Finally, move the proven sample into `navpay-phonepe` as a repeatable checksum service test so future regressions fail locally before manual UI validation is needed.

**Tech Stack:** Next.js App Router, TypeScript, Prisma/Postgres, Vitest, Maven, Java 11, unidbg, shell scripts, curl, jq/Node JSON parsing.

---

### Task 1: Confirm the checksum target and prepare an isolated validation worktree

**Files:**
- Modify: `navpay-admin/src/lib/intercept-checksum-client.ts`
- Modify: `navpay-admin/src/app/api/admin/intercept/checksum/health/route.ts`
- Reference: `navpay-phonepe/src/services/checksum/README.md`
- Reference: `navpay-admin/docs/runbooks/intercept-apk-manual-e2e.md`

**Step 1: Write the failing test**

```ts
// navpay-admin/tests/unit/intercept/intercept-checksum-client-config.test.ts
import { describe, expect, test } from "vitest";
import { readFileSync } from "node:fs";

describe("intercept checksum client config", () => {
  test("documents the new checksum service as the default upstream", () => {
    const src = readFileSync("src/lib/intercept-checksum-client.ts", "utf8");
    expect(src).toContain("19190");
    expect(src).not.toContain('?? "http://127.0.0.1:19090/checksum"');
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/intercept/intercept-checksum-client-config.test.ts`
Expected: FAIL because the current default upstream still points to `http://127.0.0.1:19090/checksum`.

**Step 3: Write minimal implementation**

```ts
// navpay-admin/src/lib/intercept-checksum-client.ts
const DEFAULT_CHECKSUM_URL =
  process.env.INTERCEPT_CHECKSUM_URL ?? "http://127.0.0.1:19190/checksum";
```

```ts
// navpay-admin/src/app/api/admin/intercept/checksum/health/route.ts
const HEALTH_URL =
  process.env.INTERCEPT_CHECKSUM_HEALTH_URL ?? "http://127.0.0.1:19190/health";
```

Also update the manual runbook so the documented health check and operator commands target the new service first, and only reference `19090` as the legacy fallback for comparison.

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/intercept/intercept-checksum-client-config.test.ts tests/unit/intercept/admin-intercept-checksum-health-route.test.ts`
Expected: PASS, and the health route still reports `online=true/false` correctly against the new default port.

**Step 5: Commit**

```bash
git -C navpay-admin add src/lib/intercept-checksum-client.ts src/app/api/admin/intercept/checksum/health/route.ts tests/unit/intercept/intercept-checksum-client-config.test.ts docs/runbooks/intercept-apk-manual-e2e.md
git -C navpay-admin commit -m "fix(intercept): point checksum bridge to unidbg service"
```

### Task 2: Export one real intercept log into a stable replay fixture

**Files:**
- Create: `navpay-admin/scripts/export-intercept-checksum-fixture.ts`
- Create: `navpay-admin/tests/unit/intercept/export-intercept-checksum-fixture.test.ts`
- Create: `navpay-phonepe/src/services/checksum/src/test/resources/fixtures/phonepe_intercept_replay.json`
- Reference: `navpay-admin/src/lib/intercept-log.ts`
- Reference: `navpay-admin/src/app/api/admin/intercept/logs/[id]/route.ts`

**Step 1: Write the failing test**

```ts
// navpay-admin/tests/unit/intercept/export-intercept-checksum-fixture.test.ts
import { describe, expect, test } from "vitest";
import { readFileSync } from "node:fs";

describe("export intercept checksum fixture script", () => {
  test("strips query string and preserves original request body", () => {
    const src = readFileSync("scripts/export-intercept-checksum-fixture.ts", "utf8");
    expect(src).toContain("new URL");
    expect(src).toContain(".pathname");
    expect(src).toContain("X-REQUEST-CHECKSUM-V4");
    expect(src).toContain("X-REQUEST-ALIAS");
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/intercept/export-intercept-checksum-fixture.test.ts`
Expected: FAIL because the fixture export script does not exist yet.

**Step 3: Write minimal implementation**

```ts
// navpay-admin/scripts/export-intercept-checksum-fixture.ts
import { writeFileSync } from "node:fs";
import { prisma } from "@/lib/prisma";
import { parseHeaders } from "@/lib/intercept-log";

async function main() {
  const id = Number(process.argv[2] ?? "");
  if (!Number.isFinite(id) || id <= 0) throw new Error("usage: tsx scripts/export-intercept-checksum-fixture.ts <logId>");

  const row = await prisma.http_intercept_logs.findUnique({ where: { id } });
  if (!row) throw new Error(`log ${id} not found`);

  const requestHeaders = parseHeaders(row.request_headers);
  const url = new URL(row.url);
  const fixture = {
    source: {
      adminLogId: row.id,
      exportedAt: new Date().toISOString(),
      note: "Captured from navpay-admin real intercept log",
    },
    request: {
      method: row.method,
      url: row.url,
      path: url.pathname,
      body: row.request_body ?? "",
      headers: requestHeaders,
    },
    replay: {
      existingChecksum: requestHeaders["X-REQUEST-CHECKSUM-V4"] ?? "",
      existingAlias: requestHeaders["X-REQUEST-ALIAS"] ?? "",
    },
  };

  writeFileSync(
    "../navpay-phonepe/src/services/checksum/src/test/resources/fixtures/phonepe_intercept_replay.json",
    JSON.stringify(fixture, null, 2),
  );
}

void main();
```

Pick a real log that meets all of these conditions before exporting:
- `source_app = 'phonepe'`
- `method = 'POST'` or another write request that normally needs anti-replay handling
- URL host is a real PhonePe API host
- `request_body` is non-empty if the endpoint depends on body bytes for checksum
- original request headers already include `X-REQUEST-CHECKSUM-V4` so you can compare shape and replay semantics

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/intercept/export-intercept-checksum-fixture.test.ts`
Expected: PASS.

Then export one real sample:

```bash
cd navpay-admin
node --env-file=.env.local --import tsx scripts/export-intercept-checksum-fixture.ts <real_log_id>
```

Expected: `navpay-phonepe/src/services/checksum/src/test/resources/fixtures/phonepe_intercept_replay.json` exists and contains the exact request `path` and `body` from the real intercept log.

**Step 5: Commit**

```bash
git -C navpay-admin add scripts/export-intercept-checksum-fixture.ts tests/unit/intercept/export-intercept-checksum-fixture.test.ts
git -C navpay-phonepe add src/services/checksum/src/test/resources/fixtures/phonepe_intercept_replay.json
git -C navpay-admin commit -m "feat(intercept): export real checksum replay fixture"
git -C navpay-phonepe commit -m "test(checksum): add real intercept replay fixture"
```

### Task 3: Manually validate the new checksum service against the real fixture before writing the permanent test

**Files:**
- Create: `navpay-phonepe/src/services/checksum/scripts/validate_real_fixture.sh`
- Create: `navpay-phonepe/src/services/checksum/src/test/resources/fixtures/phonepe_intercept_replay.expected.json`
- Reference: `navpay-phonepe/src/services/checksum/scripts/test_http_service.sh`
- Reference: `navpay-admin/src/components/intercept-console.tsx`

**Step 1: Write the failing test**

```bash
# navpay-phonepe/src/services/checksum/scripts/validate_real_fixture.sh
#!/usr/bin/env bash
set -euo pipefail

FIXTURE="src/services/checksum/src/test/resources/fixtures/phonepe_intercept_replay.json"
test -f "${FIXTURE}"
jq -e '.request.path != ""' "${FIXTURE}" >/dev/null
jq -e '.request.body != null' "${FIXTURE}" >/dev/null
```

```bash
cd navpay-phonepe
bash src/services/checksum/scripts/validate_real_fixture.sh
```

Expected: FAIL before the script and expected output file exist.

**Step 2: Run test to verify it fails**

Run: `cd navpay-phonepe && bash src/services/checksum/scripts/validate_real_fixture.sh`
Expected: FAIL because the script and expected file are not implemented yet.

**Step 3: Write minimal implementation**

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
FIXTURE="${ROOT_DIR}/src/services/checksum/src/test/resources/fixtures/phonepe_intercept_replay.json"
BASE_URL="http://127.0.0.1:${CHECKSUM_HTTP_PORT:-19190}"

PATH_ARG="$(jq -r '.request.path' "${FIXTURE}")"
BODY_ARG="$(jq -c '.request.body' "${FIXTURE}")"
UUID_ARG="${CHECKSUM_TEST_UUID:-8e8f7e5c-3f14-4cb3-bf70-8ec3dbf5a001}"

RESP="$(curl -sS -m 20 "${BASE_URL}/checksum" \
  -H 'Content-Type: application/json' \
  -d "$(jq -nc --arg path "${PATH_ARG}" --arg body "${BODY_ARG}" --arg uuid "${UUID_ARG}" '{path:$path,body:$body,uuid:$uuid}')")"

echo "${RESP}" > "${ROOT_DIR}/src/services/checksum/src/test/resources/fixtures/phonepe_intercept_replay.expected.json"

RESP="${RESP}" python3 - <<'PY'
import json, os
payload = json.loads(os.environ["RESP"])
assert payload["ok"] is True
assert payload["data"]["structureOk"] is True
assert payload["data"]["checksum"]
PY
```

After the script is in place, run both validation modes:

```bash
cd navpay-phonepe
yarn checksum:test
bash src/services/checksum/scripts/validate_real_fixture.sh
```

Then validate the admin resend path manually with the same record:

1. `cd navpay-admin && yarn dev`
2. Open `http://localhost:3000/admin/resources?tab=intercept_logs`
3. Locate the same exported log
4. Keep `启用 checksum（防重放）` enabled
5. Click `发送`

Expected:
- `/api/admin/intercept/checksum` returns `success=true`
- proxy send reaches upstream
- the upstream response is not an anti-replay rejection caused by a stale checksum

**Step 4: Run test to verify it passes**

Run: `cd navpay-phonepe && bash src/services/checksum/scripts/validate_real_fixture.sh`
Expected: PASS, plus `phonepe_intercept_replay.expected.json` contains a real checksum response captured from the new `19190` service.

**Step 5: Commit**

```bash
git -C navpay-phonepe add src/services/checksum/scripts/validate_real_fixture.sh src/services/checksum/src/test/resources/fixtures/phonepe_intercept_replay.expected.json
git -C navpay-phonepe commit -m "test(checksum): validate real intercept fixture via http service"
```

### Task 4: Add a permanent Maven test that proves the real fixture works

**Files:**
- Modify: `navpay-phonepe/src/services/checksum/pom.xml`
- Create: `navpay-phonepe/src/services/checksum/src/test/java/com/navpay/phonepe/unidbg/ChecksumHttpServiceRealFixtureTest.java`
- Create: `navpay-phonepe/src/services/checksum/src/test/java/com/navpay/phonepe/unidbg/ChecksumFixtureLoader.java`
- Test: `navpay-phonepe/src/services/checksum/src/test/resources/fixtures/phonepe_intercept_replay.json`

**Step 1: Write the failing test**

```java
// navpay-phonepe/src/services/checksum/src/test/java/com/navpay/phonepe/unidbg/ChecksumHttpServiceRealFixtureTest.java
package com.navpay.phonepe.unidbg;

import static org.junit.jupiter.api.Assertions.*;

import org.junit.jupiter.api.Test;

final class ChecksumHttpServiceRealFixtureTest {

    @Test
    void realInterceptFixtureProducesStructureValidChecksum() throws Exception {
        ChecksumFixtureLoader.Fixture fixture =
                ChecksumFixtureLoader.load("fixtures/phonepe_intercept_replay.json");

        ChecksumHttpService.ProbeResponse probe = ChecksumHttpServiceTestHarness.run(
                fixture.request.path(),
                fixture.request.body(),
                "8e8f7e5c-3f14-4cb3-bf70-8ec3dbf5a001");

        assertNotNull(probe);
        assertFalse(probe.checksum().isBlank());
        assertTrue(probe.shape().isStructureOk());
    }
}
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-phonepe/src/services/checksum && mvn test -Dtest=ChecksumHttpServiceRealFixtureTest`
Expected: FAIL because there is no test dependency setup, no fixture loader, and no reusable test harness around `runProbe`.

**Step 3: Write minimal implementation**

```xml
<!-- navpay-phonepe/src/services/checksum/pom.xml -->
<dependency>
  <groupId>org.junit.jupiter</groupId>
  <artifactId>junit-jupiter</artifactId>
  <version>5.11.4</version>
  <scope>test</scope>
</dependency>
```

```xml
<plugin>
  <groupId>org.apache.maven.plugins</groupId>
  <artifactId>maven-surefire-plugin</artifactId>
  <version>3.5.2</version>
  <configuration>
    <useSystemClassLoader>false</useSystemClassLoader>
  </configuration>
</plugin>
```

```java
// introduce a package-private helper inside production code or a dedicated test harness
static ProbeResponse runProbeForTest(String apkPath, String libPath, String path, String body, String uuid) throws Exception {
    ChecksumHttpService service = new ChecksumHttpService(apkPath, libPath, "e755b7-first", false);
    Map<String, String> request = new LinkedHashMap<>();
    request.put("path", path);
    request.put("body", body);
    request.put("uuid", uuid);
    return service.runProbe(request);
}
```

Keep the test assertions at the real-data level:
- the fixture `path` is sent exactly as captured from admin
- the fixture `body` bytes are preserved exactly
- generated checksum is non-empty and Base64-decodable
- `structureOk=true`
- response length is within the expected current range

Do not assert byte-for-byte equality with the original in-app checksum unless Task 3 proves the new service is deterministic and equivalent for the chosen sample.

**Step 4: Run test to verify it passes**

Run: `cd navpay-phonepe/src/services/checksum && mvn test -Dtest=ChecksumHttpServiceRealFixtureTest`
Expected: PASS.

Then run the shell regression too:

Run: `cd navpay-phonepe && yarn checksum:test && bash src/services/checksum/scripts/validate_real_fixture.sh`
Expected: PASS.

**Step 5: Commit**

```bash
git -C navpay-phonepe add src/services/checksum/pom.xml src/services/checksum/src/test/java/com/navpay/phonepe/unidbg/ChecksumHttpServiceRealFixtureTest.java src/services/checksum/src/test/java/com/navpay/phonepe/unidbg/ChecksumFixtureLoader.java
git -C navpay-phonepe commit -m "test(checksum): cover real intercept replay fixture"
```

### Task 5: Triage and fix root causes if the real fixture does not work

**Files:**
- Modify: `navpay-phonepe/src/services/checksum/src/main/java/com/navpay/phonepe/unidbg/ChecksumHttpService.java`
- Modify: `navpay-phonepe/src/services/checksum/src/main/java/com/navpay/phonepe/unidbg/UnidbgChecksumProbe.java`
- Modify: `navpay-phonepe/src/services/checksum/src/main/java/com/navpay/phonepe/unidbg/ChEmulation.java`
- Modify: `navpay-phonepe/src/services/checksum/scripts/validate_real_fixture.sh`
- Modify: `navpay-phonepe/src/services/checksum/TECHNICAL.md`

**Step 1: Write the failing test**

Use the real fixture test from Task 4 as the failing guard. If replay still fails in the UI, add one focused regression test for the discovered defect before changing production code. Pick exactly one of these failure shapes based on evidence:

```java
@Test
void preservesRequestBodyBytesExactly() { ... }

@Test
void acceptsEncodedPathWithoutQueryString() { ... }

@Test
void usesExplicitUuidWhenProvided() { ... }
```

**Step 2: Run test to verify it fails**

Run the smallest failing reproduction first:

```bash
cd navpay-phonepe/src/services/checksum
mvn test -Dtest=ChecksumHttpServiceRealFixtureTest,<new_regression_test>
```

Expected: FAIL with a concrete reason captured from one of:
- admin resend gets anti-replay rejection
- `structureOk=false`
- checksum service throws `IllegalArgumentException`, `IllegalStateException`, or Base64 decoding error
- new service output differs materially from the legacy `19090` helper for the same `path/body/uuid`

**Step 3: Write minimal implementation**

Triage in this order:

```bash
cd navpay-phonepe
yarn checksum:start
bash src/services/checksum/scripts/validate_real_fixture.sh
curl -sS http://127.0.0.1:19190/validate -H 'Content-Type: application/json' -d @/tmp/real-fixture-request.json
curl -sS http://127.0.0.1:19090/checksum -H 'Content-Type: application/json' -d @/tmp/real-fixture-request.json
```

Fix only the demonstrated root cause:
- If the real fixture fails only on the new `19190` service but passes on `19090`, inspect path/body normalization and `uuid` propagation first.
- If both fail, the captured admin log is probably not replayable as-is; export a different real log that is known to succeed from the UI and document why.
- If `body` escaping is wrong, stop using lossy JSON-string extraction in tests or service glue and preserve raw body bytes.
- If signature/device context is wrong, verify `PROBE_DEVICE_ID`, APK path, and certificate extraction before touching checksum algorithm code.

**Step 4: Run test to verify it passes**

Run:

```bash
cd navpay-phonepe/src/services/checksum
mvn test
cd /Users/danielscai/Documents/workspace/navpay/navpay-phonepe
yarn checksum:test
bash src/services/checksum/scripts/validate_real_fixture.sh
cd /Users/danielscai/Documents/workspace/navpay/navpay-admin
yarn test tests/unit/intercept/admin-intercept-checksum-route.test.ts tests/unit/intercept/admin-intercept-checksum-health-route.test.ts
```

Expected: PASS across Java tests, shell validation, and admin checksum bridge tests.

**Step 5: Commit**

```bash
git -C navpay-phonepe add src/services/checksum/src/main/java/com/navpay/phonepe/unidbg/ChecksumHttpService.java src/services/checksum/src/main/java/com/navpay/phonepe/unidbg/UnidbgChecksumProbe.java src/services/checksum/src/main/java/com/navpay/phonepe/unidbg/ChEmulation.java src/services/checksum/TECHNICAL.md src/services/checksum/scripts/validate_real_fixture.sh
git -C navpay-phonepe commit -m "fix(checksum): support real intercept replay fixture"
```

### Task 6: Document the operator workflow and verification evidence

**Files:**
- Modify: `navpay-admin/docs/runbooks/intercept-apk-manual-e2e.md`
- Modify: `navpay-phonepe/src/services/checksum/README.md`
- Modify: `navpay-phonepe/docs/checksum_service_integration.md`
- Create: `navpay-phonepe/docs/reports/2026-03-25-real-log-checksum-validation.md`

**Step 1: Write the failing test**

```ts
// navpay-admin/tests/unit/intercept/readme-intercept-regression.test.ts
import { readFileSync } from "node:fs";
import { describe, expect, test } from "vitest";

describe("intercept checksum docs regression", () => {
  test("manual docs mention real fixture validation against 19190 service", () => {
    const adminDoc = readFileSync("docs/runbooks/intercept-apk-manual-e2e.md", "utf8");
    expect(adminDoc).toContain("19190");
    expect(adminDoc).toContain("real fixture");
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn test tests/unit/intercept/readme-intercept-regression.test.ts`
Expected: FAIL if the workflow is still described only in terms of helper service or manual clicking.

**Step 3: Write minimal implementation**

Document:
- how to choose the real log
- how to export the fixture
- how to run the new `19190` checksum validation
- what evidence proves success
- which command compares `19190` with legacy `19090` only for debugging

In the report file, record:
- exact admin log id
- exact fixture path
- exact commands run
- whether UI resend succeeded
- whether the permanent test was added or what root cause blocked it

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn test tests/unit/intercept/readme-intercept-regression.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git -C navpay-admin add docs/runbooks/intercept-apk-manual-e2e.md tests/unit/intercept/readme-intercept-regression.test.ts
git -C navpay-phonepe add src/services/checksum/README.md docs/checksum_service_integration.md docs/reports/2026-03-25-real-log-checksum-validation.md
git -C navpay-admin commit -m "docs(intercept): document real checksum validation flow"
git -C navpay-phonepe commit -m "docs(checksum): record real log validation evidence"
```

## Notes for Execution

- Use a dedicated worktree before implementation. For this cross-repo task, create one worktree under `worktrees/navpay-admin/<ticket>` and one under `worktrees/navpay-phonepe/<ticket>` if you need to edit both repos in parallel.
- Follow `@test-driven-development` for each code change and `@verification-before-completion` before claiming the flow works.
- Prefer one real fixture only. Add a second sample only if the first turns out to be non-replayable for reasons unrelated to checksum generation.
- Do not silently keep `19090` as the active admin upstream if the goal is to validate the new `navpay-phonepe/src/services/checksum` service. `19090` is only the comparison baseline.
- If the permanent Java test cannot be made reliable because unidbg is too heavy for CI, fall back to a shell-based fixture regression under `src/services/checksum/scripts/` plus a Maven smoke test that verifies fixture loading and request normalization. Document the reason explicitly in the report.
