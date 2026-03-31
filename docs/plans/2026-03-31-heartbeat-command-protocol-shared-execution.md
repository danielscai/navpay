# Heartbeat Command Protocol Shared Layer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enforce one shared heartbeat protocol authority across repos, add standardized command-downlink semantics (including common `ping`), and maintain per-app supported-command registries without coupling runtime adapters.

**Architecture:** Keep protocol truth in workspace-level docs (`spec`), mirror protocol constants/codecs in each repo core layer, and gate changes via tests. Implement shared command envelope + ping semantics in core modules; keep execution of business commands adapter-specific per app. Maintain command support registry per app and document it.

**Tech Stack:** Kotlin (navpay-android), Java (navpay-phonepe heartbeat_bridge), Python pytest contracts (phonepe orchestrator tests), Gradle unit tests.

---

### Task 1: Extend protocol spec with command envelope and app command registry governance

**Files:**
- Modify: `docs/architecture/heartbeat/heartbeat-protocol-v1.md`
- Modify: `docs/architecture/heartbeat/heartbeat-change-process.md`
- Create: `docs/architecture/heartbeat/heartbeat-command-registry.md`

**Step 1: Write failing doc assertion test (target existing doc-link tests where possible)**

```python
assert "command envelope" in protocol_doc
assert "ping" in protocol_doc
assert "registry" in process_doc
```

**Step 2: Run test to verify it fails**

Run: `cd navpay-phonepe && python3 -m pytest src/pipeline/orch/tests/test_validation_doc_links.py -q`
Expected: FAIL or missing references before updates.

**Step 3: Implement minimal spec/governance updates**

```md
- command header/body contract
- ack contract
- standardized ping command + pong result
- rule: new command first in shared spec, then app registry
```

**Step 4: Run tests to verify pass**

Run: `cd navpay-phonepe && python3 -m pytest src/pipeline/orch/tests/test_validation_doc_links.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git -C /Users/danielscai/Documents/workspace/navpay add docs/architecture/heartbeat
git -C /Users/danielscai/Documents/workspace/navpay commit -m "docs(heartbeat): add command protocol and registry governance"
```

### Task 2: Add Android shared command core + app registry

**Files:**
- Create: `navpay-android/app/src/main/java/com/navpay/heartbeat/core/HeartbeatCommandCodec.kt`
- Create: `navpay-android/app/src/main/java/com/navpay/heartbeat/core/HeartbeatPingHandler.kt`
- Create: `navpay-android/app/src/main/java/com/navpay/heartbeat/core/HeartbeatCommandRegistry.kt`
- Modify: `navpay-android/app/src/main/java/com/navpay/heartbeat/protocol/HeartbeatProtocol.kt`
- Modify: `navpay-android/app/src/main/java/com/navpay/HeartbeatManager.kt`
- Test: `navpay-android/app/src/test/java/com/navpay/heartbeat/core/HeartbeatCommandCodecTest.kt`
- Test: `navpay-android/app/src/test/java/com/navpay/heartbeat/core/HeartbeatCommandRegistryTest.kt`

**Step 1: Write failing tests**

```kotlin
@Test fun parsePingCommand_fromHeader() { ... }
@Test fun pingHandler_returnsPongResult() { ... }
@Test fun registry_containsDeclaredAndroidCommands() { ... }
```

**Step 2: Run tests to verify failure**

Run: `cd navpay-android && ./gradlew :app:testDebugUnitTest --tests "*HeartbeatCommand*"`
Expected: FAIL before implementation.

**Step 3: Implement minimal command core + wire in manager**

```kotlin
object HeartbeatCommandRegistry { val SUPPORTED = setOf("ping", ...) }
object HeartbeatPingHandler { fun execute(nowMs: Long): RuntimeTaskExecutionResult }
```

**Step 4: Run tests to verify pass**

Run: `cd navpay-android && ./gradlew :app:testDebugUnitTest --tests "*Heartbeat*" --tests "*ApiClient*"`
Expected: PASS.

**Step 5: Commit**

```bash
git -C navpay-android add app/src/main/java/com/navpay/heartbeat app/src/main/java/com/navpay/HeartbeatManager.kt app/src/test/java/com/navpay/heartbeat
git -C navpay-android commit -m "feat(android): add heartbeat command core and command registry"
```

### Task 3: Add PhonePe shared command core + app registry

**Files:**
- Create: `navpay-phonepe/src/apk/heartbeat_bridge/src/main/java/com/heartbeatbridge/core/HeartbeatCommandCodec.java`
- Create: `navpay-phonepe/src/apk/heartbeat_bridge/src/main/java/com/heartbeatbridge/core/HeartbeatPingHandler.java`
- Create: `navpay-phonepe/src/apk/heartbeat_bridge/src/main/java/com/heartbeatbridge/core/HeartbeatCommandRegistry.java`
- Modify: `navpay-phonepe/src/apk/heartbeat_bridge/src/main/java/com/heartbeatbridge/protocol/HeartbeatProtocol.java`
- Modify: `navpay-phonepe/src/apk/heartbeat_bridge/src/main/java/com/heartbeatbridge/HeartbeatSender.java`
- Modify: `navpay-phonepe/src/pipeline/orch/tests/test_heartbeat_bridge_contract.py`

**Step 1: Write failing tests**

```python
assert "HeartbeatCommandRegistry" in sender_or_core
assert "ping" in protocol_or_registry
assert "HeartbeatPingHandler" in core
```

**Step 2: Run tests to verify failure**

Run: `cd navpay-phonepe && python3 -m pytest src/pipeline/orch/tests/test_heartbeat_bridge_contract.py -q`
Expected: FAIL before implementation.

**Step 3: Implement minimal command core + ping shared behavior**

```java
public final class HeartbeatCommandRegistry { ... }
public final class HeartbeatPingHandler { ... }
```

**Step 4: Run tests to verify pass**

Run:
- `cd navpay-phonepe/src/apk/heartbeat_bridge && ./scripts/compile.sh`
- `cd navpay-phonepe && python3 -m pytest src/pipeline/orch/tests/test_heartbeat_bridge_contract.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git -C navpay-phonepe add src/apk/heartbeat_bridge/src/main/java/com/heartbeatbridge src/pipeline/orch/tests/test_heartbeat_bridge_contract.py
git -C navpay-phonepe commit -m "feat(phonepe): add heartbeat command core and command registry"
```

### Task 4: Cross-repo alignment verification and emulator validation

**Files:**
- Modify: `navpay-phonepe/docs/verification/heartbeat_bridge_validation.md`
- Modify: `navpay-android/docs/testing/heartbeat-protocol-validation.md`

**Step 1: Add explicit alignment checklist**

```md
- same protocol version header key
- same command envelope keys
- ping semantics match
- app registries documented and tested
```

**Step 2: Run static/unit tests**

Run:
- `cd navpay-phonepe && python3 -m pytest src/pipeline/orch/tests/test_heartbeat_bridge_contract.py src/pipeline/orch/tests/test_profile_injection_verification.py src/pipeline/orch/tests/test_validation_doc_links.py -q`
- `cd navpay-android && ./gradlew :app:testDebugUnitTest --tests "*Heartbeat*" --tests "*ApiClient*"`
Expected: PASS.

**Step 3: Emulator end-to-end check**

Run:
- `cd navpay-phonepe && python3 src/pipeline/orch/orchestrator.py test --smoke --serial emulator-5554 --install-mode reinstall`
- `cd navpay-phonepe && python3 src/pipeline/orch/orchestrator.py test --serial emulator-5554 --install-mode reinstall`
- `adb -s emulator-5554 logcat -d -s HeartbeatBridge PPHelper`
Expected: PASS and bridge heartbeat healthy.

**Step 4: Commit**

```bash
git -C navpay-phonepe add docs/verification/heartbeat_bridge_validation.md
git -C navpay-android add docs/testing/heartbeat-protocol-validation.md
git -C navpay-phonepe commit -m "docs(phonepe): align heartbeat command protocol validation"
git -C navpay-android commit -m "docs(android): align heartbeat command protocol validation"
```
