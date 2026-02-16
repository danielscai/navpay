# Personal API v1 (Mobile)

Base: /api/personal

## Auth
- POST /auth/login
- POST /auth/register/start
- POST /auth/register/verify
- POST /auth/register/complete
- POST /auth/logout
- POST /auth/password/reset

## Me & Mine
- GET /me
- GET /mine/balance-logs

## Device
- POST /device/report
- POST /device/heartbeat

## Payout Orders
- GET /payout/orders/available
- POST /payout/orders/{orderId}/claim
- POST /payout/orders/{orderId}/complete
- GET /payout/orders/mine

## Bank Apps
- GET /payment-apps

## Rewards / Activities
- GET /rewards/newbie

## Referral / Rebates
- GET /referral/summary
- GET /referral/downlines

