"""Headline sentiment in [-1, 1]. FinBERT when installed and selected; otherwise a small finance lexicon (English + a few Swedish terms; other headlines score 0.0 = no signal).
The model name is stored with every score so lexicon and FinBERT results are never confused."""
import logging
import re
from functools import lru_cache

log = logging.getLogger(__name__)

_NEG = r"plunge|slump|miss(?:es|ed)?|warning|cuts?|lowers?|downgrade|probe|lawsuit|fraud|loss|falls?|drops?|recall|weak|decline|layoffs?|bankrupt|default|fine[sd]?|rasar|faller|föll|sänker|varning|förlust|konkurs|utredning|skandal|nedgradera"
_POS = r"beats?|surge|soar|record|upgrade|raises?|strong|growth|profit rises?|wins?|approval|buyback|rises?|jumps?|outperform|stiger|steg|rekord|höjer|ökar|uppgradera|stark|vinst"


def lexicon_score(text: str) -> float:
    n, p = len(re.findall(_NEG, text, re.I)), len(re.findall(_POS, text, re.I))
    return 0.0 if n + p == 0 else (p - n) / (p + n)


@lru_cache
def _finbert():
    from transformers import pipeline  # optional extra: pip install .[sentiment]
    return pipeline("text-classification", model="ProsusAI/finbert", top_k=None)


def score_titles(titles: list[str], backend: str = "lexicon") -> tuple[list[float], str]:
    if backend == "finbert":
        try:
            res = _finbert()(titles)
            return [next(d["score"] for d in r if d["label"] == "positive") - next(d["score"] for d in r if d["label"] == "negative")
                    for r in res], "finbert"
        except Exception as e:  # missing torch, offline model download, etc.
            log.warning("FinBERT unavailable, falling back to lexicon: %s", e)
    return [lexicon_score(t) for t in titles], "lexicon"
