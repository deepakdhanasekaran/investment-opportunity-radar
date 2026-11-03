#!/bin/sh
# api: migrate then serve. scheduler: run scan jobs. exec so SIGTERM reaches the process (graceful shutdown).
set -e
case "$1" in
  api) alembic upgrade head
       exec uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --proxy-headers --timeout-graceful-shutdown 20 ;;
  scheduler) exec python -m app.scheduling.scheduler ;;
  backtest) shift; exec python -m app.backtesting.run "$@" ;;
  *) exec "$@" ;;
esac
