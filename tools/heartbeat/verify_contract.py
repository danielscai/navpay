#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]

CONTRACT_PATH = ROOT / "docs/architecture/heartbeat/heartbeat-contract-v1.json"
ANDROID_PROTOCOL = ROOT / "navpay-android/app/src/main/java/com/navpay/heartbeat/protocol/HeartbeatProtocol.kt"
ANDROID_REGISTRY = ROOT / "navpay-android/app/src/main/java/com/navpay/heartbeat/core/HeartbeatCommandRegistry.kt"
PHONEPE_PROTOCOL = ROOT / "navpay-phonepe/src/apk/heartbeat_bridge/src/main/java/com/heartbeatbridge/protocol/HeartbeatProtocol.java"
PHONEPE_REGISTRY = ROOT / "navpay-phonepe/src/apk/heartbeat_bridge/src/main/java/com/heartbeatbridge/core/HeartbeatCommandRegistry.java"

KOTLIN_CONST = re.compile(r'const\s+val\s+([A-Z0-9_]+)\s*=\s*"([^"]*)"')
JAVA_CONST = re.compile(r'public\s+static\s+final\s+String\s+([A-Z0-9_]+)\s*=\s*"([^"]*)"\s*;')


def parse_consts(path: Path, pattern: re.Pattern) -> Dict[str, str]:
    text = path.read_text(encoding="utf-8")
    return {name: value for name, value in pattern.findall(text)}


def assert_equal(actual: Optional[str], expected: str, label: str, errors: List[str]) -> None:
    if actual != expected:
        errors.append(f"{label}: expected '{expected}' but got '{actual}'")


def assert_contains(path: Path, needle: str, label: str, errors: List[str]) -> None:
    text = path.read_text(encoding="utf-8")
    if needle not in text:
        errors.append(f"{label}: missing '{needle}' in {path}")


def main() -> int:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    android_consts = parse_consts(ANDROID_PROTOCOL, KOTLIN_CONST)
    phonepe_consts = parse_consts(PHONEPE_PROTOCOL, JAVA_CONST)

    errors: List[str] = []

    expected_version = contract["protocolVersion"]
    expected_header = contract["versionHeader"]
    shared = contract["sharedFields"]
    cmd = contract["commandFields"]
    shared_commands = contract["sharedCommands"]

    # Android protocol constants
    assert_equal(android_consts.get("VERSION"), expected_version, "android.VERSION", errors)
    assert_equal(android_consts.get("VERSION_HEADER"), expected_header, "android.VERSION_HEADER", errors)
    assert_equal(android_consts.get("FIELD_TIMESTAMP"), shared["timestamp"], "android.FIELD_TIMESTAMP", errors)
    assert_equal(android_consts.get("FIELD_APP_NAME"), shared["appName"], "android.FIELD_APP_NAME", errors)
    assert_equal(android_consts.get("FIELD_ANDROID_ID"), shared["androidId"], "android.FIELD_ANDROID_ID", errors)
    assert_equal(android_consts.get("COMMAND_FIELD_ID"), cmd["commandId"], "android.COMMAND_FIELD_ID", errors)
    assert_equal(android_consts.get("COMMAND_FIELD_TYPE"), cmd["commandType"], "android.COMMAND_FIELD_TYPE", errors)
    assert_equal(android_consts.get("COMMAND_FIELD_PAYLOAD"), cmd["commandPayload"], "android.COMMAND_FIELD_PAYLOAD", errors)

    # PhonePe protocol constants
    assert_equal(phonepe_consts.get("PROTOCOL_VERSION"), expected_version, "phonepe.PROTOCOL_VERSION", errors)
    assert_equal(phonepe_consts.get("HEADER_PROTOCOL_VERSION"), expected_header, "phonepe.HEADER_PROTOCOL_VERSION", errors)
    assert_equal(phonepe_consts.get("FIELD_TIMESTAMP"), shared["timestamp"], "phonepe.FIELD_TIMESTAMP", errors)
    assert_equal(phonepe_consts.get("FIELD_APP_NAME"), shared["appName"], "phonepe.FIELD_APP_NAME", errors)
    assert_equal(phonepe_consts.get("FIELD_ANDROID_ID"), shared["androidId"], "phonepe.FIELD_ANDROID_ID", errors)
    assert_equal(phonepe_consts.get("FIELD_COMMAND_ID"), cmd["commandId"], "phonepe.FIELD_COMMAND_ID", errors)
    assert_equal(phonepe_consts.get("FIELD_COMMAND_TYPE"), cmd["commandType"], "phonepe.FIELD_COMMAND_TYPE", errors)
    assert_equal(phonepe_consts.get("FIELD_COMMAND_PAYLOAD"), cmd["commandPayload"], "phonepe.FIELD_COMMAND_PAYLOAD", errors)

    # Shared command checks (ping must exist in both protocol and registries)
    for command in shared_commands:
        assert_equal(android_consts.get("COMMAND_TYPE_PING"), command, "android.COMMAND_TYPE_PING", errors)
        assert_equal(phonepe_consts.get("COMMAND_TYPE_PING"), command, "phonepe.COMMAND_TYPE_PING", errors)
        assert_contains(ANDROID_REGISTRY, "COMMAND_TYPE_PING", "android registry", errors)
        assert_contains(PHONEPE_REGISTRY, "COMMAND_TYPE_PING", "phonepe registry", errors)

    if errors:
        print("[heartbeat-contract-gate] FAIL")
        for item in errors:
            print(f"- {item}")
        return 1

    print("[heartbeat-contract-gate] PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
