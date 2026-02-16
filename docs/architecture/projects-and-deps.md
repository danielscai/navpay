# NavPay Projects & Dependencies

## Projects
- navpay-android (Android)
- navpay-admin (API + Admin UI)
- navpay-otp (OTP service)
- navpay-landing (Download landing)
- navpay-tgbot (Telegram bot)

## Runtime Dependencies
- navpay-android -> navpay-admin (HTTP)
- navpay-admin -> navpay-otp (HTTP)
- navpay-tgbot -> navpay-admin (HTTP)
- navpay-landing -> navpay-admin (HTTP, public manifest)

## Local Ports (dev defaults)
- navpay-admin: 3000
- navpay-otp: 19090
- navpay-landing: 3100 (suggested)
- navpay-tgbot: no port (outbound polling/webhook)

## API Prefixes
- Mobile: /api/personal/*
- Admin UI: /admin/*
- Integrations: /api/integrations/*
- Public: /api/public/*

