#!/usr/bin/env bash
set -euo pipefail

# Start navpay-admin, navpay-otp, navpay-landing for local integration.
# Note: Use separate terminals for logs if you prefer; this is a convenience runner.

( cd navpay-otp && yarn dev ) > /tmp/navpay-otp.log 2>&1 &
( cd navpay-admin && yarn dev ) > /tmp/navpay-admin.log 2>&1 &
( cd navpay-landing && PORT=3100 yarn dev ) > /tmp/navpay-landing.log 2>&1 &

echo "otp:     http://127.0.0.1:19090"
echo "admin:   http://127.0.0.1:3000"
echo "landing: http://127.0.0.1:3100"
echo "logs: /tmp/navpay-otp.log /tmp/navpay-admin.log /tmp/navpay-landing.log"

