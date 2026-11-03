"""Deterministic GREEN/YELLOW/RED classification. Every decision records the rule ids that fired.
No AI output is an input here."""
from dataclasses import dataclass, field

from app.core.config import Classification
from app.fundamentals.quality import QualityResult
from app.risk.rules import Flag
from app.scoring.opportunity import OpportunityResult


@dataclass
class Verdict:
    classification: str
    rules: list[str] = field(default_factory=list)
    incomplete: bool = False


def classify(q: QualityResult | None, o: OpportunityResult | None, flags: list[Flag], cfg: Classification,
             needs_quality: bool = True, quote_ok: bool = True) -> Verdict:
    rules: list[str] = []
    crit = [x for x in flags if x.severity == "CRITICAL"]
    review = [x for x in flags if x.severity == "REVIEW"]
    incomplete = (not quote_ok) or q is None or q.score is None or o is None or o.score is None
    if not quote_ok:
        rules.append("quote_stale_or_missing")
    if crit:
        return Verdict("RED", [f"critical:{x.code}" for x in crit], incomplete)
    if q is not None and q.score is not None and q.confidence >= 0.5 and q.score < cfg.red_max_quality:
        return Verdict("RED", [f"quality {q.score:.0f} < {cfg.red_max_quality:.0f}"], incomplete)
    if incomplete:
        return Verdict("YELLOW", rules + ["incomplete_data_caps_at_yellow"], True)
    assert q and o and q.score is not None and o.score is not None
    if review:
        rules += [f"review:{x.code}" for x in review]
    if q.confidence < cfg.green_min_confidence:
        rules.append(f"confidence {q.confidence:.2f} < {cfg.green_min_confidence}")
    if q.score < cfg.green_min_quality:
        rules.append(f"quality {q.score:.0f} < {cfg.green_min_quality:.0f}")
    if o.score < cfg.green_min_opportunity:
        rules.append(f"opportunity {o.score:.0f} < {cfg.green_min_opportunity:.0f}")
    if not rules:
        return Verdict("GREEN", ["all_green_conditions_met"], False)
    return Verdict("YELLOW", rules, False)
