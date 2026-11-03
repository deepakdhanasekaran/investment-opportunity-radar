# Third-party notes
* **balogun14/radar (MIT)** and **OpenStock (AGPL-3.0)** were inspected for the architecture assessment. **No code was copied from either.**
  The Google-News-RSS + FinBERT headline approach is the only idea taken from Investment Radar (re-implemented from scratch).
  Because OpenStock code is not included, no AGPL obligations attach to this repository.
* Runtime libraries (yfinance, exchange_calendars, FastAPI, SQLAlchemy, APScheduler, Next.js, ...) keep their own licenses.
  yfinance is not affiliated with Yahoo; review Yahoo's terms before relying on it, particularly for anything beyond personal use.
