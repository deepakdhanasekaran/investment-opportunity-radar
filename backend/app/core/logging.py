import json
import logging
import sys
import warnings


class JsonFormatter(logging.Formatter):
    def format(self, r: logging.LogRecord) -> str:
        d = {"ts": self.formatTime(r, "%Y-%m-%dT%H:%M:%S%z"), "level": r.levelname, "logger": r.name, "msg": r.getMessage()}
        d.update(getattr(r, "extra_fields", {}))
        if r.exc_info:
            d["exc"] = self.formatException(r.exc_info)
        return json.dumps(d, default=str)


def setup_logging(level: str = "INFO") -> None:
    warnings.filterwarnings("ignore", module="yfinance")  # pandas deprecation noise from yfinance internals
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter())
    logging.basicConfig(level=level, handlers=[h], force=True)
