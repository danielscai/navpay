# OpenVPN Domain Router (Go) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a local macOS Go daemon that continuously resolves hardcoded OpenAI domains and updates host routes so only those destination IPs go through the active OpenVPN `utun` interface.

**Architecture:** A single Go binary runs as a daemon (via launchd). It resolves hardcoded domains (`chatgpt.com`, `openai.com` + subdomains), computes route diffs against managed state, detects current OpenVPN `utun` interface, and applies incremental IPv4/IPv6 route changes. It persists managed state to a local file for safe restart/recovery and avoids destructive full-flush behavior on transient DNS failures.

**Tech Stack:** Go 1.22+, macOS `route`/`netstat`/`ifconfig` commands, launchd (`.plist`), Go `testing` package.

---

### Task 1: Scaffold CLI and Project Layout

**Files:**
- Create: `tools/vpn-domain-router/go.mod`
- Create: `tools/vpn-domain-router/cmd/vpn-domain-router/main.go`
- Create: `tools/vpn-domain-router/internal/app/app.go`
- Create: `tools/vpn-domain-router/internal/domains/domains.go`
- Create: `tools/vpn-domain-router/README.md`
- Test: `tools/vpn-domain-router/internal/domains/domains_test.go`

**Step 1: Write the failing test**

```go
package domains

import "testing"

func TestHardcodedDomains_DefaultSet(t *testing.T) {
	ds := Default()
	if len(ds) == 0 {
		t.Fatalf("expected non-empty hardcoded domain list")
	}
}
```

**Step 2: Run test to verify it fails**

Run: `cd tools/vpn-domain-router && go test ./...`
Expected: FAIL with missing `Default()` implementation.

**Step 3: Write minimal implementation**

```go
package domains

func Default() []string {
	return []string{
		"chatgpt.com",
		"openai.com",
	}
}
```

Add CLI flags in `main.go`:
- `--once` (single reconciliation)
- `--interval` (default 30s)
- `--state-file` (default `~/.local/state/vpn-domain-router/state.json`)
- `--dry-run` (log route changes without applying)

**Step 4: Run test to verify it passes**

Run: `cd tools/vpn-domain-router && go test ./...`
Expected: PASS.

**Step 5: Commit**

```bash
git add tools/vpn-domain-router
git commit -m "feat(tools): scaffold go vpn domain router cli"
```

### Task 2: DNS Resolver with Subdomain Expansion and TTL-Aware Scheduling

**Files:**
- Create: `tools/vpn-domain-router/internal/resolve/resolve.go`
- Create: `tools/vpn-domain-router/internal/resolve/types.go`
- Test: `tools/vpn-domain-router/internal/resolve/resolve_test.go`

**Step 1: Write the failing test**

```go
func TestResolve_CollectsIPv4AndIPv6(t *testing.T) {
	r := NewWithLookup(mockLookup)
	res, err := r.Resolve([]string{"chatgpt.com"})
	if err != nil {
		t.Fatal(err)
	}
	if len(res.IPv4) == 0 {
		t.Fatalf("expected ipv4 records")
	}
}
```

**Step 2: Run test to verify it fails**

Run: `cd tools/vpn-domain-router && go test ./internal/resolve -v`
Expected: FAIL with unresolved `NewWithLookup`/`Resolve`.

**Step 3: Write minimal implementation**

Implement:
- Resolver interface using `net.Resolver`.
- Domain candidate expansion:
  - base domains hardcoded: `chatgpt.com`, `openai.com`
  - optional fixed subdomain list hardcoded in `domains.go` (e.g. `chatgpt.com`, `www.chatgpt.com`, `auth.openai.com`, `api.openai.com`).
- Return unique IPv4/IPv6 sets.
- Return next refresh duration clamped between 30s and 300s (no config file).

**Step 4: Run test to verify it passes**

Run: `cd tools/vpn-domain-router && go test ./internal/resolve -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tools/vpn-domain-router/internal/resolve tools/vpn-domain-router/internal/domains
git commit -m "feat(tools): add ttl-aware domain resolver"
```

### Task 3: OpenVPN Interface Discovery and State Model

**Files:**
- Create: `tools/vpn-domain-router/internal/netif/netif.go`
- Create: `tools/vpn-domain-router/internal/state/state.go`
- Test: `tools/vpn-domain-router/internal/netif/netif_test.go`
- Test: `tools/vpn-domain-router/internal/state/state_test.go`

**Step 1: Write the failing tests**

```go
func TestDetectOpenVPNUtun_FromIfconfigOutput(t *testing.T) {
	iface, err := DetectFromIfconfig(sampleIfconfig)
	if err != nil {
		t.Fatal(err)
	}
	if iface != "utun3" {
		t.Fatalf("got %s", iface)
	}
}
```

```go
func TestState_RoundTrip(t *testing.T) {
	s := State{Interface: "utun3"}
	// save + load and assert equal
}
```

**Step 2: Run tests to verify failure**

Run: `cd tools/vpn-domain-router && go test ./internal/netif ./internal/state -v`
Expected: FAIL due to missing implementations.

**Step 3: Write minimal implementation**

Implement:
- Parse `ifconfig` output and pick `utun*` that has point-to-point address (OpenVPN pattern).
- JSON state file schema:
  - `interface`
  - `managed_ipv4`
  - `managed_ipv6`
  - `updated_at`
- Robust load/save with atomic write (`.tmp` + rename).

**Step 4: Run tests to verify pass**

Run: `cd tools/vpn-domain-router && go test ./internal/netif ./internal/state -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tools/vpn-domain-router/internal/netif tools/vpn-domain-router/internal/state
git commit -m "feat(tools): detect openvpn utun and persist managed state"
```

### Task 4: Route Diff Engine (No Shell Side Effects)

**Files:**
- Create: `tools/vpn-domain-router/internal/route/diff.go`
- Test: `tools/vpn-domain-router/internal/route/diff_test.go`

**Step 1: Write the failing test**

```go
func TestDiff_AddAndRemove(t *testing.T) {
	current := Set{"1.1.1.1": {}}
	target := Set{"2.2.2.2": {}}
	add, del := Diff(current, target)
	if len(add) != 1 || len(del) != 1 {
		t.Fatalf("unexpected diff")
	}
}
```

**Step 2: Run test to verify failure**

Run: `cd tools/vpn-domain-router && go test ./internal/route -v`
Expected: FAIL due to missing `Diff`.

**Step 3: Write minimal implementation**

Implement deterministic diff:
- Inputs: current managed set, target resolved set.
- Outputs: ordered `add`, ordered `delete` slices.
- Keep IPv4 and IPv6 separate.

**Step 4: Run test to verify pass**

Run: `cd tools/vpn-domain-router && go test ./internal/route -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tools/vpn-domain-router/internal/route
git commit -m "feat(tools): add deterministic route diff engine"
```

### Task 5: Route Executor and Reconcile Loop

**Files:**
- Create: `tools/vpn-domain-router/internal/route/exec.go`
- Modify: `tools/vpn-domain-router/internal/app/app.go`
- Test: `tools/vpn-domain-router/internal/route/exec_test.go`
- Test: `tools/vpn-domain-router/internal/app/app_test.go`

**Step 1: Write the failing tests**

```go
func TestReconcile_UsesDetectedInterface(t *testing.T) {
	// mock resolver + mock executor + mock netif detector
	// expect add route commands use utunX
}
```

```go
func TestReconcile_DNSFailureKeepsExistingRoutes(t *testing.T) {
	// resolver returns error; expect no bulk delete
}
```

**Step 2: Run tests to verify failure**

Run: `cd tools/vpn-domain-router && go test ./internal/app ./internal/route -v`
Expected: FAIL due to missing reconcile behavior.

**Step 3: Write minimal implementation**

Implement:
- Route command builder:
  - IPv4 add: `route -n add -host <ip> -interface <utun>`
  - IPv4 del: `route -n delete -host <ip>`
  - IPv6 add/del equivalent.
- `--dry-run` bypasses command execution.
- Reconcile order:
  - detect interface
  - resolve targets
  - diff against state
  - apply deletes/adds
  - save state
- If interface changed, rebuild managed routes for new interface.

**Step 4: Run tests to verify pass**

Run: `cd tools/vpn-domain-router && go test ./internal/app ./internal/route -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tools/vpn-domain-router/internal/app tools/vpn-domain-router/internal/route
git commit -m "feat(tools): implement reconcile loop and route executor"
```

### Task 6: Daemon Runtime, Signals, and Logging

**Files:**
- Modify: `tools/vpn-domain-router/cmd/vpn-domain-router/main.go`
- Test: `tools/vpn-domain-router/cmd/vpn-domain-router/main_test.go`

**Step 1: Write the failing test**

```go
func TestRun_OnceModeExitsAfterSingleReconcile(t *testing.T) {
	// run with --once and assert single app call
}
```

**Step 2: Run test to verify failure**

Run: `cd tools/vpn-domain-router && go test ./cmd/vpn-domain-router -v`
Expected: FAIL due to missing run loop behavior.

**Step 3: Write minimal implementation**

Implement:
- `--once` single cycle.
- default daemon loop ticker (30s).
- `SIGINT`/`SIGTERM` graceful shutdown.
- concise structured logs with timestamp.

**Step 4: Run test to verify pass**

Run: `cd tools/vpn-domain-router && go test ./cmd/vpn-domain-router -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tools/vpn-domain-router/cmd/vpn-domain-router
git commit -m "feat(tools): add daemon run loop and graceful shutdown"
```

### Task 7: launchd Integration and Operational Docs

**Files:**
- Create: `tools/vpn-domain-router/deploy/com.navpay.vpn-domain-router.plist`
- Modify: `tools/vpn-domain-router/README.md`

**Step 1: Write the failing verification step**

Run:
`plutil -lint tools/vpn-domain-router/deploy/com.navpay.vpn-domain-router.plist`
Expected: FAIL because file is missing.

**Step 2: Add minimal implementation**

Create `.plist` with:
- `RunAtLoad=true`
- `KeepAlive=true`
- `ProgramArguments` to binary path
- `StandardOutPath` and `StandardErrorPath`

Update README:
- build command
- install binary path
- launchctl load/unload/restart commands
- verify route commands
- required sudoers note

**Step 3: Re-run verification**

Run:
`plutil -lint tools/vpn-domain-router/deploy/com.navpay.vpn-domain-router.plist`
Expected: PASS.

**Step 4: Commit**

```bash
git add tools/vpn-domain-router/deploy tools/vpn-domain-router/README.md
git commit -m "docs(tools): add launchd deployment and runbook"
```

### Task 8: End-to-End Validation on macOS with OpenVPN Connect

**Files:**
- Create: `docs/reports/2026-04-15-openvpn-domain-router-validation.md`

**Step 1: Execute validation commands**

Run:
1. `cd tools/vpn-domain-router && go test ./...`
2. `go build -o bin/vpn-domain-router ./cmd/vpn-domain-router`
3. Connect OpenVPN profile manually.
4. `sudo ./bin/vpn-domain-router --once`
5. `netstat -rn -f inet | rg -n "(chatgpt|openai|utun)"`
6. `netstat -rn -f inet6 | rg -n "utun"`

Expected:
- all tests PASS
- routes for resolved OpenAI IPs point to active `utunX`
- no non-target bulk default-route changes

**Step 2: Write validation report**

Record:
- test output summary
- detected `utun` interface
- sample managed IPv4/IPv6 routes
- reconnect test result (disconnect/reconnect OpenVPN then rerun once)

**Step 3: Commit**

```bash
git add docs/reports/2026-04-15-openvpn-domain-router-validation.md
git commit -m "test(tools): validate openvpn domain router on macos"
```

