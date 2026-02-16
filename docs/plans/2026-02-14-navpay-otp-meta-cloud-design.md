# navpay-otp Meta WhatsApp Cloud + API Key Design

**Date:** 2026-02-14

## Goal

Make `navpay-otp` production-ready for sending OTP via Meta WhatsApp Cloud API, with basic abuse controls:
- Request authentication (`X-Navpay-Otp-Key`)
- Per-IP rate limiting
- Per-phone resend cooldown + daily cap

## Constraints / Reality Check

- WhatsApp Cloud API **requires approved templates** for business-initiated messages.
- You currently **do not have an approved OTP template**, so the implementation must be:
  - template-based (to be compliant),
  - configurable, and
  - testable without real network calls.

## Auth

- Header: `X-Navpay-Otp-Key: <key>`
- Server env: `OTP_API_KEY`
- Behavior:
  - If `OTP_API_KEY` is set: missing/wrong key => `401 { ok:false, error:"unauthorized" }`
  - If `OTP_API_KEY` is empty/unset: auth is disabled (local dev only).

## Rate Limiting

1. Per-IP (Fastify rate limit plugin)
2. Per-phone:
   - cooldown: deny resend within `OTP_RESEND_COOLDOWN_SEC` of last send
   - daily cap: deny if more than `OTP_DAILY_CAP_PER_PHONE` sends in the last 24h

## WhatsApp Provider

Provider interface: `sendText({to,text})`.

Implementations:
- `fake`: logs OTP to stdout
- `meta_cloud`: calls Meta Graph API `/{phoneNumberId}/messages` with a template payload

Config required for `meta_cloud`:
- `WA_ACCESS_TOKEN`
- `WA_PHONE_NUMBER_ID`
- `WA_TEMPLATE_NAME`
- `WA_TEMPLATE_LANG` (default `en_US`)

Template payload assumption (until you create/approve one):
- 1 body parameter: the OTP code

## API Surface

Keep existing endpoints:
- `POST /v1/otp/send`
- `POST /v1/otp/verify`

No change to response shape; only add failure modes:
- `401 unauthorized` (missing/wrong API key)
- `429 rate_limited` (IP or phone caps)
- `409 resend_too_soon`

