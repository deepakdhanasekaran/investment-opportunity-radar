"""Refresh US index universes from Wikipedia (static CSV seeds; re-run quarterly).
Swedish lists are maintained by hand in app/universe/se_*.csv (no free machine-readable source)."""
import csv
import io
import sys
from pathlib import Path

import httpx
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "backend" / "app" / "universe"
UA = {"User-Agent": "opportunity-radar/0.1 (universe refresh)"}


def table(url: str, *cols: str) -> pd.DataFrame:
    html = httpx.get(url, headers=UA, timeout=30, follow_redirects=True).text
    for t in pd.read_html(io.StringIO(html)):
        if any(c in t.columns for c in cols):
            return t
    raise SystemExit(f"table with {cols!r} not found at {url}")


def write(name: str, rows: list[tuple[str, str, str]]) -> None:
    with open(OUT / name, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["symbol", "name", "sector"])
        w.writerows(rows)
    print(name, len(rows))


if __name__ == "__main__":
    sp = table("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", "Symbol")
    write("us_sp500.csv", [(s.replace(".", "-"), n, g) for s, n, g in zip(sp["Symbol"], sp["Security"], sp["GICS Sector"])])
    try:  # Wikipedia layout for Nasdaq-100 changes often; optional universe
        nq = table("https://en.wikipedia.org/wiki/Nasdaq-100", "Ticker", "Symbol")
        tk = "Ticker" if "Ticker" in nq.columns else "Symbol"
        sec = "GICS Sector" if "GICS Sector" in nq.columns else nq.columns[-1]
        write("us_nasdaq100.csv", [(s.replace(".", "-"), n, g) for s, n, g in zip(nq[tk], nq["Company"], nq[sec])])
    except SystemExit as e:
        print("nasdaq100 skipped:", e)
    sys.exit(0)
