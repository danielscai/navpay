# Android Release Pointer Publish Runbook

## Purpose
Publish Android releases by uploading immutable artifacts first, then atomically switching the release pointer.

This keeps Cloudflare and the origin aligned with a simple rule:
- artifacts are immutable and can be cached for a long time
- `current.json` is the only mutable release pointer
- rollback is a pointer switch, not a re-upload

## Release Shape

Use immutable tag examples based on sha values:

- release directory: `/releases/9f2a8c1b6d4e7a3f5c1d2e9f0a6b7c8d9e0f1a2b/`
- artifact file: `/releases/9f2a8c1b6d4e7a3f5c1d2e9f0a6b7c8d9e0f1a2b/app-release.apk`
- release manifest: `/releases/9f2a8c1b6d4e7a3f5c1d2e9f0a6b7c8d9e0f1a2b/manifest.json`
- active pointer: `/current.json`

The sha tag must remain immutable. Never overwrite a release directory once published.

## Publish Workflow

### 1. Build the release
Produce the APK and manifest for a single sha-tagged release directory.

Required outputs:
- APK artifact
- manifest with sha, version, checksum, and download URL
- `current.json` candidate payload pointing to the new release

### 2. Upload immutable artifacts first
Upload the sha-tagged directory before touching `current.json`.

Checks:
- artifact bytes match the expected checksum
- manifest references the same sha tag
- nothing in the sha-tagged path is mutable after upload

### 3. Validate the new release
Confirm the release is reachable from origin and, if applicable, through Cloudflare.

Suggested validation:
- manifest fetch succeeds
- artifact download succeeds
- checksum matches the manifest

### 4. Switch the pointer
Replace `current.json` so it points at the new sha release.

Only this file should change for cutover.

### 5. Selective purge
Purge only:
- `/current.json`
- any manifest pointer alias used by clients

Do not purge:
- the immutable APK path
- the release directory for the new sha
- unrelated routes

## Rollback Using current.json

Rollback is a pointer reversion.

### Rollback steps

1. Identify the previous known-good sha release.
2. Update `current.json` to reference the previous sha.
3. Purge only `current.json` and any lightweight manifest alias.
4. Verify clients now resolve the prior release.

### Rollback rules

- do not delete the new immutable release immediately
- do not re-upload the old artifact unless it is missing or corrupted
- do not purge the entire zone
- preserve the new release for later investigation if needed

## Optional Curl Examples

### Manifest fetch
```bash
curl -i https://downloads.example.com/current.json
```

### Artifact download
```bash
curl -L -o app-release.apk \
  https://downloads.example.com/releases/9f2a8c1b6d4e7a3f5c1d2e9f0a6b7c8d9e0f1a2b/app-release.apk
```

### Denied admin route
```bash
curl -i https://admin.example.com/admin/resources
```

Expected outcome:
- manifest and artifact routes are public distribution paths
- admin routes remain protected and should not be treated as release assets
- Cloudflare continues to act only as acceleration and security infrastructure

## Operational Checklist

Before declaring a release complete:

1. the sha-tagged artifact exists
2. the manifest checksum matches the artifact
3. `current.json` points to the new sha
4. selective purge has been run
5. the old release is still available for rollback

## Troubleshooting

- If the wrong release appears, inspect `current.json` first.
- If the artifact does not download, check the immutable sha path and origin upload.
- If rollback fails, verify the previous sha still exists and that only pointer files were purged.
