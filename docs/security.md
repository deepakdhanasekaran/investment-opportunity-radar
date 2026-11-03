# Security
* No brokerage code or credentials; no order placement anywhere.
* Secrets only in `.env` (git-ignored) / host env. Bot token is never logged (errors log exception type only).
* API: every route except `/health` needs a bearer token (constant-time compare); API refuses (503) if no token is configured; OpenAPI/docs disabled; rate limit 120/min per IP; CORS off unless `RADAR_CORS_ORIGINS` is set; pydantic validation on all inputs; symbol normalisation rejects malformed tickers; settings endpoint only accepts whitelisted groups (`scan, weights, cls, alerts`) and validates values; writes are recorded in `audit_log`.
* Dashboard: password login → HMAC-signed, httpOnly, SameSite=Strict, expiring cookie; middleware guards every page and proxy route; the API token stays server-side; proxy only forwards `watchlist` and `settings`; CSP / X-Frame-Options / nosniff headers. Login throttling is in-memory per instance (best effort on serverless; put Cloudflare Access in front for stronger protection).
* Network: Postgres is on an `internal: true` network with no published port. API binds `127.0.0.1:8000`. For public HTTPS without inbound ports use the `cloudflared` profile (outbound tunnel) and put Cloudflare Access in front.
* Containers run as non-root (`radar`, `node`); healthchecks and restart policies set.
* Dependency scanning: `pip-audit` and `npm audit` run in CI. Pin and review Dependabot updates.
* Known limits: single shared token/password (no multi-user); audit log covers API writes only; the system emits no alerts if the whole host is down (use an external uptime check such as healthchecks.io on `/health`).
