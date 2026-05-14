# user_api

## Swagger UI

- Swagger UI: `http://localhost:8082/docs/`
- OpenAPI JSON: `http://localhost:8082/openapi.json`

Enable/disable via env var `ENABLE_SWAGGER` (default: `true`).

## Async email sending (message queue)

Password reset and booking confirmation emails are queued to Redis when `REDIS_URL` is set.
If Redis is not configured, delivery runs in a background thread so HTTP requests still return without waiting for SMTP.

- Queue name: `EMAIL_QUEUE_NAME` (default: `user_api:email_jobs`)
- Docker default command starts the API and an email worker in the same container when `REDIS_URL` is set.
- Manual worker command, if split deployment is needed later: `python -m app.workers.email_worker`

## Circuit breaker demo

The same circuit breaker implementation is used by `OAuthVerifier` to protect outbound Google/Facebook OAuth HTTP calls. Provider timeouts or 5xx responses are converted to `503 OAUTH_PROVIDER_UNAVAILABLE`; after three provider failures, the breaker opens and later calls fail fast until recovery or reset.

- Reset/success: `GET /circuit-breaker/demo?reset=true`
- Force failures: call `GET /circuit-breaker/demo?fail=true` three times.
- Open-circuit behavior: `GET /circuit-breaker/demo` returns `503` until the recovery timeout passes or `reset=true` is used.
