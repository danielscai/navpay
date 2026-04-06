# NavPay PhonePe Multi-Device Compatibility Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver emulator-first multi-device compatibility support for single-base `navpay-phonepe` installs with admin-managed release source of truth, policy-driven ROM adaptation, and fast publish rollback.

**Architecture:** Keep one active release artifact line in `navpay-admin` and add a device-segmented install-policy endpoint. `navpay-android` fetches policy per device and applies it during install orchestration while uploading structured install events with standardized error codes. Add a multi-device test orchestrator to run the same install flow in parallel across emulator serials and aggregate ROM-segmented results.

**Tech Stack:** Next.js App Router + TypeScript + Zod + Prisma/Postgres (`navpay-admin`), Kotlin + Coroutines + Android Package Installer (`navpay-android`), Python/Bash orchestration scripts, Vitest, JUnit, Android instrumentation.

---

Execution discipline for this plan: `@test-driven-development`, `@verification-before-completion`, `@requesting-code-review`.

### Task 1: Add install-policy data contract in `navpay-admin`

**Files:**
- Modify: `navpay-admin/src/lib/payment-app-release-service.ts`
- Create: `navpay-admin/src/lib/payment-app-install-policy.ts`
- Create: `navpay-admin/tests/unit/payment-app-install-policy.test.ts`

**Step 1: Write the failing test**

```ts
import { describe, expect, test } from "vitest";
import { resolveInstallPolicyForDevice } from "@/lib/payment-app-install-policy";

describe("payment app install policy", () => {
  test("returns high-risk ROM policy for known risky segment", async () => {
    const out = await resolveInstallPolicyForDevice({
      appId: "pa_phonepe",
      device: { brand: "Xiaomi", model: "23127PN0CC", osVersion: "14", sdkInt: 34 },
    });

    expect(out.segment).toBe("miui_high_risk");
    expect(out.retry.maxAttempts).toBeGreaterThan(0);
    expect(out.postInstall.verifyLaunch).toBe(true);
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn vitest tests/unit/payment-app-install-policy.test.ts`
Expected: FAIL with module not found for `payment-app-install-policy`.

**Step 3: Write minimal implementation**

```ts
// navpay-admin/src/lib/payment-app-install-policy.ts
export type InstallPolicy = {
  segment: string;
  permission: { requireUnknownSourcesGate: boolean };
  confirm: { timeoutMs: number };
  retry: { maxAttempts: number; intervalMs: number; retriableErrorCodes: string[] };
  postInstall: { verifyPackageExists: boolean; verifyLaunch: boolean };
};

export async function resolveInstallPolicyForDevice(input: {
  appId: string;
  device: { brand?: string | null; model?: string | null; osVersion?: string | null; sdkInt?: number | null };
}): Promise<InstallPolicy> {
  const brand = String(input.device.brand ?? "").toLowerCase();
  if (brand.includes("xiaomi") || brand.includes("redmi")) {
    return {
      segment: "miui_high_risk",
      permission: { requireUnknownSourcesGate: true },
      confirm: { timeoutMs: 120000 },
      retry: { maxAttempts: 1, intervalMs: 8000, retriableErrorCodes: ["INSTALLER_UI_NOT_SHOWN", "USER_CONFIRM_TIMEOUT"] },
      postInstall: { verifyPackageExists: true, verifyLaunch: true },
    };
  }
  return {
    segment: "default",
    permission: { requireUnknownSourcesGate: true },
    confirm: { timeoutMs: 90000 },
    retry: { maxAttempts: 0, intervalMs: 0, retriableErrorCodes: [] },
    postInstall: { verifyPackageExists: true, verifyLaunch: false },
  };
}
```

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn vitest tests/unit/payment-app-install-policy.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git -C navpay-admin add src/lib/payment-app-install-policy.ts src/lib/payment-app-release-service.ts tests/unit/payment-app-install-policy.test.ts
git -C navpay-admin commit -m "feat(payment-apps): add device-segmented install policy resolver"
```

### Task 2: Expose install-policy API route in `navpay-admin`

**Files:**
- Create: `navpay-admin/src/app/api/personal/payment-apps/[appId]/install-policy/route.ts`
- Create: `navpay-admin/tests/unit/personal-payment-app-install-policy-route.test.ts`

**Step 1: Write the failing test**

```ts
import { NextRequest } from "next/server";
import { describe, expect, test } from "vitest";
import { GET } from "@/app/api/personal/payment-apps/[appId]/install-policy/route";

describe("personal install-policy route", () => {
  test("returns policy payload for authenticated personal device", async () => {
    const req = new NextRequest("http://localhost/api/personal/payment-apps/pa_phonepe/install-policy?brand=Xiaomi&model=13T&sdkInt=34", {
      headers: { authorization: "Bearer test_personal_token" },
    });
    const res = await GET(req, { params: { appId: "pa_phonepe" } } as any);
    expect(res.status).toBe(200);
    const json: any = await res.json();
    expect(json.ok).toBe(true);
    expect(json.policy.segment).toBe("miui_high_risk");
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn vitest tests/unit/personal-payment-app-install-policy-route.test.ts`
Expected: FAIL with missing route file.

**Step 3: Write minimal implementation**

```ts
// parse query -> build device profile -> resolveInstallPolicyForDevice -> return { ok, appId, policy }
// keep auth with requirePersonalToken(req)
```

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn vitest tests/unit/personal-payment-app-install-policy-route.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git -C navpay-admin add src/app/api/personal/payment-apps/[appId]/install-policy/route.ts tests/unit/personal-payment-app-install-policy-route.test.ts
git -C navpay-admin commit -m "feat(personal-api): add payment app install-policy endpoint"
```

### Task 3: Standardize install-event error taxonomy in `navpay-admin`

**Files:**
- Modify: `navpay-admin/src/app/api/personal/payment-apps/install-events/route.ts`
- Create: `navpay-admin/src/lib/payment-app-install-errors.ts`
- Create: `navpay-admin/tests/unit/personal-payment-app-install-events-errors.test.ts`

**Step 1: Write the failing test**

```ts
import { describe, expect, test } from "vitest";
import { normalizeInstallErrorCode } from "@/lib/payment-app-install-errors";

describe("install error code normalization", () => {
  test("maps unknown values to SESSION_COMMIT_FAILED fallback", () => {
    expect(normalizeInstallErrorCode("random_x")).toBe("SESSION_COMMIT_FAILED");
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-admin && yarn vitest tests/unit/personal-payment-app-install-events-errors.test.ts`
Expected: FAIL with missing module.

**Step 3: Write minimal implementation**

```ts
export const INSTALL_ERROR_CODES = [
  "PERMISSION_BLOCKED_BY_ROM",
  "INSTALLER_UI_NOT_SHOWN",
  "USER_CONFIRM_TIMEOUT",
  "SESSION_COMMIT_FAILED",
  "APK_PARSE_FAILED",
  "POST_INSTALL_NOT_FOUND",
  "POST_INSTALL_LAUNCH_FAILED",
] as const;

export type InstallErrorCode = (typeof INSTALL_ERROR_CODES)[number];

export function normalizeInstallErrorCode(value: string): InstallErrorCode {
  return (INSTALL_ERROR_CODES as readonly string[]).includes(value) ? (value as InstallErrorCode) : "SESSION_COMMIT_FAILED";
}
```

**Step 4: Run test to verify it passes**

Run: `cd navpay-admin && yarn vitest tests/unit/personal-payment-app-install-events-errors.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git -C navpay-admin add src/lib/payment-app-install-errors.ts src/app/api/personal/payment-apps/install-events/route.ts tests/unit/personal-payment-app-install-events-errors.test.ts
git -C navpay-admin commit -m "feat(payment-apps): enforce standardized install error taxonomy"
```

### Task 4: Add Android install-policy client + models

**Files:**
- Modify: `navpay-android/app/src/main/java/com/navpay/Models.kt`
- Modify: `navpay-android/app/src/main/java/com/navpay/ApiClient.kt`
- Create: `navpay-android/app/src/test/java/com/navpay/ApiClientInstallPolicyTest.kt`

**Step 1: Write the failing test**

```kotlin
@Test
fun getInstallPolicy_parsesSegmentAndRetryConfig() = runBlocking {
    server.enqueue(MockResponse().setResponseCode(200).setBody("""{
      "ok": true,
      "appId": "pa_phonepe",
      "policy": {
        "segment": "miui_high_risk",
        "confirm": { "timeoutMs": 120000 },
        "retry": { "maxAttempts": 1, "intervalMs": 8000, "retriableErrorCodes": ["INSTALLER_UI_NOT_SHOWN"] },
        "postInstall": { "verifyPackageExists": true, "verifyLaunch": true }
      }
    }"""))

    val api = ApiClient(FakeAuthStore("token_1"), server.url("/api/personal").toString().removeSuffix("/"), OkHttpClient())
    val out = api.getPaymentAppInstallPolicy("pa_phonepe", "Xiaomi", "13T", 34)

    assertEquals("miui_high_risk", out.segment)
    assertEquals(1, out.maxAttempts)
}
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-android && ./gradlew testDebugUnitTest --tests "com.navpay.ApiClientInstallPolicyTest"`
Expected: FAIL with unresolved method/model.

**Step 3: Write minimal implementation**

```kotlin
// add InstallPolicyPayload model and ApiClient.getPaymentAppInstallPolicy(appId, brand, model, sdkInt)
// call /api/personal/payment-apps/{appId}/install-policy with query params
```

**Step 4: Run test to verify it passes**

Run: `cd navpay-android && ./gradlew testDebugUnitTest --tests "com.navpay.ApiClientInstallPolicyTest"`
Expected: PASS.

**Step 5: Commit**

```bash
git -C navpay-android add app/src/main/java/com/navpay/Models.kt app/src/main/java/com/navpay/ApiClient.kt app/src/test/java/com/navpay/ApiClientInstallPolicyTest.kt
git -C navpay-android commit -m "feat(android): fetch install policy per device profile"
```

### Task 5: Apply policy in Android install orchestrator

**Files:**
- Modify: `navpay-android/app/src/main/java/com/navpay/ui/paymentapps/InstallOrchestrator.kt`
- Modify: `navpay-android/app/src/main/java/com/navpay/ui/paymentapps/PaymentAppsViewModel.kt`
- Create: `navpay-android/app/src/test/java/com/navpay/ui/paymentapps/InstallOrchestratorPolicyTest.kt`

**Step 1: Write the failing test**

```kotlin
@Test
fun install_usesPolicyConfirmTimeoutAndRetryForInstallerUiMissing() = runBlocking {
    val attempts = mutableListOf<Int>()
    val orchestrator = InstallOrchestrator(
        installRunner = { _, _ ->
            attempts += 1
            if (attempts.size == 1) throw RuntimeException("INSTALLER_UI_NOT_SHOWN")
            InstallExecutionResult.Success
        },
        policyProvider = { InstallPolicyRuntime(confirmTimeoutMs = 120000, maxAttempts = 1, retryIntervalMs = 10) },
    )

    val state = mutableListOf<InstallRuntime>()
    orchestrator.install(canonicalPhonePe()) { state += it }

    assertEquals(2, attempts.size)
    assertTrue(state.any { it.stage == InstallStage.Success })
}
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-android && ./gradlew testDebugUnitTest --tests "com.navpay.ui.paymentapps.InstallOrchestratorPolicyTest"`
Expected: FAIL due to missing policy wiring and retry behavior.

**Step 3: Write minimal implementation**

```kotlin
// extend orchestrator ctor with policyProvider
// apply timeout and retry only for retriable error codes
// preserve existing single-app active install constraints
```

**Step 4: Run test to verify it passes**

Run: `cd navpay-android && ./gradlew testDebugUnitTest --tests "com.navpay.ui.paymentapps.InstallOrchestratorPolicyTest"`
Expected: PASS.

**Step 5: Commit**

```bash
git -C navpay-android add app/src/main/java/com/navpay/ui/paymentapps/InstallOrchestrator.kt app/src/main/java/com/navpay/ui/paymentapps/PaymentAppsViewModel.kt app/src/test/java/com/navpay/ui/paymentapps/InstallOrchestratorPolicyTest.kt
git -C navpay-android commit -m "feat(paymentapps): apply device install policy in orchestrator"
```

### Task 6: Enforce structured install-event upload from Android

**Files:**
- Modify: `navpay-android/app/src/main/java/com/navpay/install/InstallSessionResultStore.kt`
- Modify: `navpay-android/app/src/main/java/com/navpay/install/InstallSessionResultReceiver.kt`
- Modify: `navpay-android/app/src/main/java/com/navpay/ApiClient.kt`
- Create: `navpay-android/app/src/test/java/com/navpay/install/InstallEventErrorMappingTest.kt`

**Step 1: Write the failing test**

```kotlin
@Test
fun mapUnknownInstallFailureToStandardErrorCode() {
    val out = InstallEventErrorMapper.toStandardCode("SOME_PLATFORM_SPECIFIC_FAILURE")
    assertEquals("SESSION_COMMIT_FAILED", out)
}
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-android && ./gradlew testDebugUnitTest --tests "com.navpay.install.InstallEventErrorMappingTest"`
Expected: FAIL (mapper missing).

**Step 3: Write minimal implementation**

```kotlin
// implement mapper constants exactly matching admin taxonomy
// send mapped errorCode plus device profile fields when posting install-events
```

**Step 4: Run test to verify it passes**

Run: `cd navpay-android && ./gradlew testDebugUnitTest --tests "com.navpay.install.InstallEventErrorMappingTest"`
Expected: PASS.

**Step 5: Commit**

```bash
git -C navpay-android add app/src/main/java/com/navpay/install/InstallSessionResultStore.kt app/src/main/java/com/navpay/install/InstallSessionResultReceiver.kt app/src/main/java/com/navpay/ApiClient.kt app/src/test/java/com/navpay/install/InstallEventErrorMappingTest.kt
git -C navpay-android commit -m "feat(android): upload standardized install error events"
```

### Task 7: Add multi-device emulator orchestrator and reports

**Files:**
- Create: `navpay-android/tools/payment_apps_multi_device_orchestrator.py`
- Create: `navpay-android/tools/payment_apps_multi_device_inventory.example.json`
- Create: `navpay-android/docs/testing/payment-apps-multi-device-runbook.md`
- Create: `navpay-android/app/src/test/java/com/navpay/tools/MultiDeviceResultSchemaTest.kt` (if schema constants are in Kotlin) OR
- Create: `navpay-android/tests/tools/test_multi_device_orchestrator.py` (if pure Python)

**Step 1: Write the failing test**

```python
def test_aggregate_outputs_include_by_rom_and_failures_csv(tmp_path):
    from payment_apps_multi_device_orchestrator import aggregate_results

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    aggregate_results([
      {"serial": "emu-1", "brand": "Xiaomi", "status": "failed", "errorCode": "INSTALLER_UI_NOT_SHOWN"},
      {"serial": "emu-2", "brand": "Samsung", "status": "passed", "errorCode": None},
    ], run_dir)

    assert (run_dir / "summary.json").exists()
    assert (run_dir / "by-rom.json").exists()
    assert (run_dir / "failures.csv").exists()
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-android && python3 -m pytest tests/tools/test_multi_device_orchestrator.py -q`
Expected: FAIL because script/module does not exist.

**Step 3: Write minimal implementation**

```python
# read inventory, run per-device flow command in parallel subprocesses,
# capture outputs, write summary.json/by-rom.json/failures.csv under artifacts/multi-device/<run-id>/
```

**Step 4: Run test to verify it passes**

Run: `cd navpay-android && python3 -m pytest tests/tools/test_multi_device_orchestrator.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git -C navpay-android add tools/payment_apps_multi_device_orchestrator.py tools/payment_apps_multi_device_inventory.example.json docs/testing/payment-apps-multi-device-runbook.md tests/tools/test_multi_device_orchestrator.py
git -C navpay-android commit -m "feat(testing): add multi-device payment app orchestrator and reports"
```

### Task 8: End-to-end verification and release gate wiring

**Files:**
- Modify: `navpay-android/tools/test_gate.sh`
- Modify: `navpay-admin/scripts/test-real-all.ts` (or equivalent gate entry)
- Create: `docs/reports/2026-04-06-phonepe-multi-device-compat-verification.md`

**Step 1: Write the failing gate test/assertion**

```bash
# add gate assertion that multi-device artifacts exist and pass threshold
# expected fail when files absent
```

**Step 2: Run gate to verify it fails**

Run: `cd navpay-android && yarn test:gate:paymentapps`
Expected: FAIL with missing `artifacts/multi-device/<run-id>/summary.json` or threshold unmet.

**Step 3: Write minimal implementation**

```bash
# wire orchestrator command into gate
# enforce threshold checks:
# - Tier-1 pass rate required
# - Tier-2 sample optional warning or required by env flag
```

**Step 4: Run full verification**

Run:
- `cd navpay-admin && yarn lint && yarn typecheck && yarn test`
- `cd navpay-android && ./gradlew testDebugUnitTest`
- `cd navpay-android && yarn test:gate:paymentapps`

Expected:
- all required suites PASS,
- multi-device artifacts generated,
- release gate output includes pass-rate summary.

**Step 5: Commit**

```bash
git add navpay-android/tools/test_gate.sh navpay-admin/scripts/test-real-all.ts docs/reports/2026-04-06-phonepe-multi-device-compat-verification.md
git commit -m "chore(release-gate): enforce multi-device payment app compatibility checks"
```

## Final Verification Checklist

- [ ] `navpay-admin` install-policy endpoint returns deterministic segment policy for device profile.
- [ ] Android installer applies policy timeout/retry behavior without breaking existing install flow.
- [ ] Install events use standardized error taxonomy end-to-end.
- [ ] Multi-device orchestrator runs against emulator inventory and emits standard artifacts.
- [ ] Gate blocks activation when minimum compatibility threshold is not met.
- [ ] Verification report records commands, pass/fail, and top ROM failure signatures.

## Rollout Notes

- Start with conservative segment set: `default`, `miui_high_risk`, `oppo_permission_strict`.
- Keep retry policy bounded (max 1) until telemetry confirms stability.
- Keep fallback release ready before first gated publish.
