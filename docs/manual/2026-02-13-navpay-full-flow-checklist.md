# NavPay Full Flow Checklist (2026-02-13)

## Scope

- navpay-admin payout review flow
- Android personal login + payout claim/complete
- Personal self-service data visibility

## Preconditions

- `navpay-admin` running on `http://localhost:3000`
- Android emulator app points to `http://10.0.2.2:3000/api/personal`
- test account `pp_android1` available

## Must-Pass Flow

1. Admin creates payout order, status is `REVIEW_PENDING`.
2. Reviewer/admin approves order to `APPROVED`.
3. Android app sees order in available list.
4. Android claims order, status becomes `LOCKED`.
5. Android completes order (`SUCCESS` or `FAILED`).
6. Admin sees final status and callback/task logs.

## Self-Service Visibility Checklist

- Invite code visible
- Password reset entry available
- Today earnings visible
- Team rebate summary visible
- Upline/downline visible
- Device online status visible
- Bank accounts visible
- Bank transactions visible
- Balance logs visible

## Evidence to Keep

- order ID
- person ID
- status transition screenshots
- API response snippets for personal endpoints
