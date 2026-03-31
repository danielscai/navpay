# Heartbeat Common Layer Cross-Repo Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Solidify a shared heartbeat protocol/core layer used by both `navpay-android` and `navpay-phonepe`, while keeping transport/scheduler driver/runtime integration project-specific.

**Architecture:** Define one canonical protocol contract (`version`, fields, commands, headers, validation rules), then extract reusable core logic (payload builder + schedule policy + command parsing) in both projects behind identical APIs. Keep environment-coupled code (network transport, app lifecycle hooks, injection startup behavior) in each project independently to avoid cross-project drag.

**Tech Stack:** Kotlin (Android app), Java (PhonePe injected modules), Gradle, custom javac/d8 build scripts, pytest/unittest for pipeline contracts.

---

### Task 1: Define protocol source-of-truth and governance docs

**Files:**
- Create: `docs/architecture/heartbeat/heartbeat-protocol-v1.md`
- Create: `docs/architecture/heartbeat/heartbeat-change-process.md`

**Step 1: Write failing doc-link test (if exists) or add minimal validation test**

```python
assert protocol_doc.exists()
assert "x-navpay-hb-version" in protocol_doc_text
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest navpay-phonepe/src/pipeline/orch/tests/test_validation_doc_links.py -q`
Expected: FAIL before docs are created/linked.

**Step 3: Write protocol + governance docs**

```md
- envelope fields
- command/ack schema
- compatibility rules
- change gate: spec -> core -> adapters
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest navpay-phonepe/src/pipeline/orch/tests/test_validation_doc_links.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add docs/architecture/heartbeat/*.md
git commit -m "docs(heartbeat): define protocol v1 and change governance"
```

### Task 2: Extract Android heartbeat common protocol/core

**Files:**
- Create: `navpay-android/app/src/main/java/com/navpay/heartbeat/protocol/HeartbeatProtocol.kt`
- Create: `navpay-android/app/src/main/java/com/navpay/heartbeat/core/HeartbeatPayloadBuilder.kt`
- Create: `navpay-android/app/src/main/java/com/navpay/heartbeat/core/HeartbeatSchedulePolicy.kt`
- Modify: `navpay-android/app/src/main/java/com/navpay/ApiClient.kt`
- Modify: `navpay-android/app/src/main/java/com/navpay/HeartbeatManager.kt`
- Modify/Test: `navpay-android/app/src/test/...` (新增/修改 heartbeat core 单测)

**Step 1: Write failing tests**

```kotlin
@Test fun payload_builder_includes_protocol_fields() { ... }
@Test fun schedule_policy_returns_fixed_interval_on_success() { ... }
@Test fun schedule_policy_applies_backoff_on_failure() { ... }
```

**Step 2: Run tests to verify failure**

Run: `cd navpay-android && ./gradlew test --tests "*Heartbeat*"`
Expected: FAIL before implementation.

**Step 3: Implement minimal core extraction + refactor callsites**

```kotlin
object HeartbeatProtocol { const val VERSION = "1" ... }
object HeartbeatPayloadBuilder { fun build(...) : JSONObject }
class HeartbeatSchedulePolicy { fun nextDelayMs(...) : Long }
```

**Step 4: Run tests to verify pass**

Run: `cd navpay-android && ./gradlew test --tests "*Heartbeat*"`
Expected: PASS.

**Step 5: Commit**

```bash
git -C navpay-android add app/src/main/java/com/navpay/heartbeat app/src/main/java/com/navpay/ApiClient.kt app/src/main/java/com/navpay/HeartbeatManager.kt app/src/test
git -C navpay-android commit -m "refactor(android): extract heartbeat protocol and core policy layer"
```

### Task 3: Extract PhonePe heartbeat common protocol/core

**Files:**
- Create: `navpay-phonepe/src/apk/heartbeat_bridge/src/main/java/com/heartbeatbridge/protocol/HeartbeatProtocol.java`
- Create: `navpay-phonepe/src/apk/heartbeat_bridge/src/main/java/com/heartbeatbridge/core/HeartbeatPayloadBuilder.java`
- Create: `navpay-phonepe/src/apk/heartbeat_bridge/src/main/java/com/heartbeatbridge/core/HeartbeatSchedulePolicy.java`
- Modify: `navpay-phonepe/src/apk/heartbeat_bridge/src/main/java/com/heartbeatbridge/HeartbeatSender.java`
- Modify: `navpay-phonepe/src/apk/heartbeat_bridge/src/main/java/com/heartbeatbridge/HeartbeatScheduler.java`
- Test: `navpay-phonepe/src/pipeline/orch/tests/test_heartbeat_bridge_contract.py`

**Step 1: Write failing tests**

```python
assert "HeartbeatPayloadBuilder" in sender_source
assert "HeartbeatSchedulePolicy" in scheduler_source
assert "x-navpay-hb-version" in protocol_source
```

**Step 2: Run test to verify failure**

Run: `cd navpay-phonepe && python3 -m pytest src/pipeline/orch/tests/test_heartbeat_bridge_contract.py -q`
Expected: FAIL before extraction.

**Step 3: Implement minimal extraction + refactor**

```java
public final class HeartbeatProtocol { ... }
public final class HeartbeatPayloadBuilder { ... }
public final class HeartbeatSchedulePolicy { ... }
```

**Step 4: Run test to verify pass**

Run: `cd navpay-phonepe && python3 -m pytest src/pipeline/orch/tests/test_heartbeat_bridge_contract.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git -C navpay-phonepe add src/apk/heartbeat_bridge/src/main/java/com/heartbeatbridge src/pipeline/orch/tests/test_heartbeat_bridge_contract.py
git -C navpay-phonepe commit -m "refactor(phonepe): extract heartbeat protocol and core policy layer"
```

### Task 4: Cross-repo protocol alignment and integration verification

**Files:**
- Modify: `navpay-phonepe/docs/verification/heartbeat_bridge_validation.md`
- Create/Modify: `navpay-android/docs/testing/heartbeat-protocol-validation.md`

**Step 1: Add alignment checklist tests/docs**

```md
- protocol version field equal
- envelope keys equal
- command field semantics equal
```

**Step 2: Run static checks and project tests**

Run:
- `cd navpay-phonepe && python3 -m pytest src/pipeline/orch/tests/test_profile_resolver.py src/pipeline/orch/tests/test_profile_injection_verification.py src/pipeline/orch/tests/test_heartbeat_bridge_contract.py -q`
- `cd navpay-android && ./gradlew test`
Expected: PASS.

**Step 3: Emulator real verification**

Run:
- `cd navpay-phonepe && python3 src/pipeline/orch/orchestrator.py test --smoke --serial emulator-5554 --install-mode reinstall`
- `cd navpay-phonepe && python3 src/pipeline/orch/orchestrator.py test --serial emulator-5554 --install-mode reinstall`
- `adb -s emulator-5554 logcat -d -s HeartbeatBridge PPHelper`
Expected: PASS and heartbeat logs healthy.

**Step 4: Commit**

```bash
git -C navpay-phonepe add docs/verification/heartbeat_bridge_validation.md
git -C navpay-android add docs/testing/heartbeat-protocol-validation.md
git -C navpay-phonepe commit -m "docs(phonepe): add heartbeat common-layer validation checklist"
git -C navpay-android commit -m "docs(android): add heartbeat protocol validation checklist"
```
