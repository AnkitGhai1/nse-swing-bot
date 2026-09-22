"""
Alerts.

Two layers:
  * send_message()  -> detailed Telegram message (always, if configured)
  * alarm()         -> something that's hard to miss at the office:
        - CallMeBot:  a REAL Telegram voice call that rings your phone and
                      reads the alert aloud (free). Telegram bots can't call
                      you themselves; CallMeBot is a separate free service
                      that can.
        - Pushover:   an "emergency" push that re-rings every minute (default)
                      until you tap Acknowledge, and bypasses silent/Do Not
                      Disturb. Most reliable option; the app costs ~US$5 once.
    Configure either or both; alarm() uses whatever is set up.

notify(event, detailed_text, spoken_text) does both in one call.
"""

import requests

from settings import load_config

_cfg = None


def cfg():
    global _cfg
    if _cfg is None:
        _cfg = load_config()
    return _cfg


# --------------------------------------------------------------------------- #
# Channels
# --------------------------------------------------------------------------- #
def send_message(text: str) -> bool:
    c = cfg()
    if not c["telegram_bot_token"] or not c["telegram_chat_id"]:
        print("[notify] Telegram not configured -- printing instead:\n" + text)
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{c['telegram_bot_token']}/sendMessage",
            json={"chat_id": c["telegram_chat_id"], "text": text, "parse_mode": "HTML",
                  "disable_web_page_preview": True},
            timeout=20,
        )
        if r.status_code != 200:
            print(f"[notify] Telegram failed: {r.status_code} {r.text[:200]}")
        return r.status_code == 200
    except Exception as e:
        print(f"[notify] Telegram error: {e}")
        return False


def callmebot_call(spoken: str) -> bool:
    c = cfg()
    user = c.get("callmebot_user", "").strip()
    if not user:
        return False
    if not user.startswith("@") and not user.startswith("+"):
        user = "@" + user
    try:
        r = requests.get(
            "https://api.callmebot.com/start.php",
            params={"user": user, "text": spoken[:250], "lang": c["callmebot_voice"],
                    "rpt": 2, "cc": "missed"},
            timeout=60,
        )
        ok = r.status_code == 200
        if not ok:
            print(f"[notify] CallMeBot failed: {r.status_code} {r.text[:200]}")
        return ok
    except Exception as e:
        print(f"[notify] CallMeBot error: {e}")
        return False


def pushover_emergency(title: str, message: str) -> bool:
    c = cfg()
    if not c.get("pushover_app_token") or not c.get("pushover_user_key"):
        return False
    try:
        r = requests.post(
            "https://api.pushover.net/1/messages.json",
            data={
                "token": c["pushover_app_token"], "user": c["pushover_user_key"],
                "title": title[:250], "message": message[:1024],
                "priority": 2,                                   # emergency
                "retry": max(30, int(c["pushover_retry_sec"])),  # re-ring interval
                "expire": min(10800, int(c["pushover_expire_sec"])),
                "sound": "persistent",
            },
            timeout=20,
        )
        ok = r.status_code == 200
        if not ok:
            print(f"[notify] Pushover failed: {r.status_code} {r.text[:200]}")
        return ok
    except Exception as e:
        print(f"[notify] Pushover error: {e}")
        return False


def alarm(title: str, spoken: str) -> bool:
    """Ring now via every configured alarm channel."""
    a = pushover_emergency(title, spoken)
    b = callmebot_call(spoken)
    return a or b


_pending = []   # alarms queued during a run -> ONE call at the end (flush_alarms)


def notify(event: str, detailed: str, title: str, spoken: str) -> None:
    """Telegram message now; alarm queued so several events in one run ring
    you once instead of several back-to-back calls."""
    send_message(detailed)
    if event in cfg().get("alarm_events", []):
        short = title.split(" @ ")[0].replace(" — ", ", ")
        _pending.append((title, spoken, short))


def flush_alarms() -> None:
    if not _pending:
        return
    if len(_pending) == 1:
        title, spoken, _ = _pending[0]
        alarm(title, spoken)
    else:
        shorts = [p[2] for p in _pending]
        title = f"{len(_pending)} stock alerts: " + "; ".join(shorts)
        spoken = f"You have {len(_pending)} stock alerts. " + ". ".join(shorts) + ". Check Telegram."
        if len(spoken) > 250:
            spoken = f"You have {len(_pending)} stock alerts, including {shorts[0]}. Check Telegram now."
        pushover_emergency(title, "\n".join(p[1] for p in _pending))
        callmebot_call(spoken)
    _pending.clear()


# --------------------------------------------------------------------------- #
# Message formats
# --------------------------------------------------------------------------- #
def _pct(a, b):
    return round((a / b - 1) * 100, 1)


def buy_texts(c):
    intraday = getattr(c, "source", "daily") == "intraday"
    label = "⚡ INTRADAY BREAKOUT — BUY" if intraday else "🟢 BUY"
    when = ("Now, while the breakout holds (use a limit order at or below entry)" if intraday
            else "Tomorrow morning — limit order near entry; skip it if it opens >2% above")
    detailed = (
        f"{label} <b>{c.ticker}</b>\n"
        f"Entry: ₹{c.entry_price}\n"
        f"Target: ₹{c.target}  (+{_pct(c.target, c.entry_price)}%)\n"
        f"Stop-loss: ₹{c.stop_loss}  ({_pct(c.stop_loss, c.entry_price)}%)\n"
        f"Qty: {c.qty}  (≈₹{c.capital_used:,.0f})\n"
        f"Reward:Risk ≈ {c.reward_risk}:1 | Hold up to 1 month\n"
        f"When: {when}\n"
        f"Score: {c.score}/100 | RSI: {c.rsi}\n"
        f"Why: {c.reasons}\n\n"
        f"<i>Not investment advice. This bot never places trades; you decide.</i>"
    )
    title = f"{'INTRADAY ' if intraday else ''}BUY {c.ticker} @ ₹{c.entry_price}"
    spoken = (f"Stock alert. {'Intraday breakout. ' if intraday else ''}Buy {c.ticker}, "
              f"{c.qty} shares, near {c.entry_price:.0f} rupees. Target {c.target:.0f}. "
              f"Stop loss {c.stop_loss:.0f}. Check Telegram for details.")
    return detailed, title, spoken


def exit_texts(event_type: str, row: dict):
    labels = {"TARGET_HIT": "🎯 TARGET HIT", "STOP_HIT": "🔴 STOP-LOSS HIT",
              "TRAIL_STOP": "🟠 TRAILING STOP HIT (profit locked)",
              "EXPIRED": "⌛ 1-MONTH HOLD OVER"}
    action = {"TARGET_HIT": "SELL / book profit", "STOP_HIT": "SELL now to cap the loss",
              "TRAIL_STOP": "SELL — it pulled back from its high",
              "EXPIRED": "SELL (holding period over)"}[event_type]
    detailed = (
        f"{labels[event_type]}: <b>{row['ticker']}</b>\n"
        f"Bought: ₹{row['entry_price']}  →  Exit: ₹{row['exit_price']}\n"
        f"P&L: ₹{row['pnl']} ({row['pnl_pct']}%)\n"
        f"Action: {action}\n"
        f"<i>If you had a stop-loss / GTT order in place it may already have executed.</i>"
    )
    words = {"TARGET_HIT": "target hit", "STOP_HIT": "stop loss hit",
             "TRAIL_STOP": "trailing stop hit", "EXPIRED": "holding period over"}
    title = f"SELL {row['ticker']} — {words[event_type]}"
    spoken = (f"Stock alert. Sell {row['ticker']}. {words[event_type].capitalize()}. "
              f"Exit price about {float(row['exit_price']):.0f} rupees. Check Telegram.")
    return detailed, title, spoken


def stop_raised_texts(row: dict):
    """Trailing stop moved up -- good news, no alarm needed."""
    detailed = (
        f"🔼 <b>STOP RAISED — {row['ticker']}</b>\n"
        f"New stop-loss: ₹{row['stop_loss']} (was ₹{round(float(row['prev_stop']), 2)})\n"
        f"Entry was ₹{row['entry_price']} — this now protects "
        f"₹{round((float(row['stop_loss']) - float(row['entry_price'])) * int(float(row['qty'])), 0):,.0f} "
        f"of the move.\n"
        f"<i>Update your stop-loss / GTT order with your broker to match.</i>"
    )
    title = f"Stop raised on {row['ticker']}"
    spoken = f"Stop loss raised on {row['ticker']} to {float(row['stop_loss']):.0f} rupees."
    return detailed, title, spoken


def format_summary(stats: dict, num_new: int, extra: str = "") -> str:
    if stats.get("total_closed", 0) == 0:
        base = f"📊 No closed trades yet to measure accuracy. {num_new} new signal(s) today."
    else:
        base = (
            f"📊 <b>Live track record</b>: {stats['wins']}/{stats['total_closed']} wins "
            f"({stats['win_rate_pct']}%) | P&L ₹{stats['total_pnl']} | "
            f"avg win {stats['avg_win_pct']}% / avg loss {stats['avg_loss_pct']}% | "
            f"profit factor {stats.get('profit_factor')}\n{num_new} new signal(s) today."
        )
    return base + (f"\n{extra}" if extra else "")
