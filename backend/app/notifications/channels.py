"""Delivery channels. Plain text only (no markup parsing surprises)."""
import logging
import time

import httpx

from app.core.config import Settings

log = logging.getLogger(__name__)


def send_telegram(token: str, chat_id: str, text: str, client: httpx.Client | None = None) -> None:
    r = (client or httpx).post(f"https://api.telegram.org/bot{token}/sendMessage",
                               json={"chat_id": chat_id, "text": text[:4000], "disable_web_page_preview": True}, timeout=15)
    r.raise_for_status()


def send_ntfy(url: str, text: str, severity: str, client: httpx.Client | None = None) -> None:
    prio = {"critical": "5", "warning": "4"}.get(severity, "3")
    r = (client or httpx).post(url, content=text.encode(), headers={"Priority": prio, "Title": "Opportunity Radar"}, timeout=15)
    r.raise_for_status()


def deliver(st: Settings, text: str, severity: str, retries: int, sleep=time.sleep, client: httpx.Client | None = None) -> tuple[list[str], int, str | None]:
    """Returns (channels_ok, attempts, last_error). Retries with exponential backoff per channel."""
    chans = []
    if st.telegram_bot_token and st.telegram_chat_id:
        chans.append(("telegram", lambda: send_telegram(st.telegram_bot_token, st.telegram_chat_id, text, client)))
    if st.ntfy_url:
        chans.append(("ntfy", lambda: send_ntfy(st.ntfy_url, text, severity, client)))
    if not chans:
        return [], 0, "no notification channel configured"
    ok, attempts, err = [], 0, None
    for name, fn in chans:
        for i in range(retries):
            attempts += 1
            try:
                fn()
                ok.append(name)
                break
            except Exception as e:  # httpx errors; never log the URL (contains the bot token)
                err = f"{name}: {type(e).__name__}"
                log.warning("delivery failed", extra={"extra_fields": {"channel": name, "attempt": i + 1, "error": err}})
                if i < retries - 1:
                    sleep(2**i)
    return ok, attempts, None if ok else err
