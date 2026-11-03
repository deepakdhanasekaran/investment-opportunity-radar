# Deployment (Ubuntu + Docker Compose)
1. Install Docker Engine + compose plugin. `git clone`, `cp .env.example .env`, fill: `POSTGRES_PASSWORD`, `RADAR_API_TOKEN`, Telegram (`@BotFather` → token; message the bot; chat id from `https://api.telegram.org/bot<TOKEN>/getUpdates`).
2. `docker compose up -d --build`. The API applies Alembic migrations on start; the scheduler waits for the API health check.
3. Verify: `docker compose ps` (all healthy), `curl localhost:8000/health`, `docker compose logs -f scheduler`. Scans run only while exchanges are open.
4. Dashboard: either `docker compose --profile dashboard up -d --build` (127.0.0.1:3000) or deploy `frontend/dashboard` to Vercel with env `RADAR_API_URL`, `RADAR_API_TOKEN`, `DASHBOARD_PASSWORD`, `DASHBOARD_SESSION_SECRET` (`openssl rand -hex 32`). For Vercel to reach the API without opening a port, run `--profile tunnel` with `CLOUDFLARE_TUNNEL_TOKEN` and point `RADAR_API_URL` at the tunnel hostname (protect it with Cloudflare Access).
5. FinBERT (optional, ~2 GB image): `docker compose build --build-arg INSTALL_SENTIMENT=1` and set `RADAR_SENTIMENT_BACKEND=finbert`.
6. Backtest: `docker compose run --rm scheduler backtest SE --limit 60` (and `US`); results appear under Performance. Paper-trading evaluation (`backtesting/paper.py`) runs daily at 22:30 UTC and tracks every GREEN opportunity vs the index (needs weeks of live data to mean anything).

## Operations
* Restart/recovery: `restart: unless-stopped`; state lives in the `pgdata` volume; scheduler coalesces missed runs; `docker compose stop` drains within 60 s.
* Backups: `scripts/backup.sh` (cron `0 3 * * *`, keeps 14 days, writes gzip SQL). Restore: `scripts/restore.sh backups/<file>`. Copy backups off-host. Test a restore before you need it.
* Upgrade: `git pull && docker compose up -d --build` (migrations run automatically).
* Refresh universes quarterly: `python scripts/refresh_universe.py`, review Swedish CSVs by hand.
* Alerts you may receive: provider failing 3× in a row; scan degraded (>50% symbols failed/stale).
