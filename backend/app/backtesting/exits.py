"""Exit-rule simulation shared by the historical backtest and the live paper tracker. Exits are evaluated on daily closes."""
from statistics import fmean

RULES = {"hi20": "Close ≥ prior 20-day high", "ma50": "Close ≥ 50-day average", "trail8": "Close ≤ 8% below highest close since entry"}
CAP = 60  # trading days; if no signal fires the position is closed here so no trade is held forever


def simulate(bars, s: int, entry: float, rule: str, cap: int = CAP):
    """bars: full daily series; s: index of the first bar after entry; entry: entry price.
    Returns (exit_index, 'signal'|'cap') or (None, 'open') if the data ends before an exit."""
    peak = entry
    for x in range(s, min(s + cap, len(bars))):
        c = bars[x].close
        peak = max(peak, c)
        if rule == "hi20":
            hit = x >= 20 and c >= max(b.close for b in bars[x - 20:x])
        elif rule == "ma50":
            hit = x >= 49 and c >= fmean(b.close for b in bars[x - 49:x + 1])
        else:  # trail8
            hit = c <= peak * 0.92
        if hit:
            return x, "signal"
    return (s + cap - 1, "cap") if s + cap <= len(bars) else (None, "open")
