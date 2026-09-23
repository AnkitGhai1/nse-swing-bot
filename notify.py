"""
Alerts.

Two layers:
  * send_message()  -> detailed Telegram message (always, if configured)
  * alarm()         -> something that's hard to miss at the office. Uses every
                       channel you've configured:
        - ntfy (FREE, recommended): an "urgent" push to the free ntfy app.
          With the app's "Keep alerting for highest priority" setting on, it
          keeps ringing until you open the app -- even in Do Not Disturb.
        - Pushover (~US$5 once): emergency push that re-rings every minute
          until you tap Acknowledge, bypasses silent/DND.
        - CallMeBot (legacy): a Telegram voice call. Its bot now charges
          Telegram Stars to start a chat, so it's no longer free -- kept only
          for people already set up. Hard 60-second cap so it can never hang
          a run.

Every network call here has a hard time limit, and the scripts save
signals.csv BEFORE ringing alarms, so a slow alarm service can never lose
your trade log.
"""

import threading
import time

import requests

from settings import load_config

_cfg = None


def cfg():
    global _cfg
    if _cfg is None:
        _cfg = load_config()
    return _cfg


def _hard_deadline(fn, seconds: float, label: str):
    """Run fn() but give up after `seconds` of WALL-CLOCK time. (A plain
    requests timeout only limits silence between bytes, so a service that
    trickles output can hold a connection open for many minutes.)"""
    result = {"ok": False}

    def run():
        try:
            result["ok"] = bool(fn())
        except Exception as e:
            print(f"[notify] {label} error: {e}")

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(seconds)
    if t.is_alive():
        print(f"[notify] {label}: no answer within {seconds:.0f}s -- skipped, carrying on.")
        return False
    return result["ok"]


# --------------------------------------------------------------------------- #
# Telegram
# --------------------------------------------------------------------------- #
TELEGRAM_HINTS = {
    401: "Bot token is wrong -- re-copy it from @BotFather into the TELEGRAM_BOT_TOKEN secret.",
    404: "Bot token is wrong or incomplete -- re-copy it from @BotFather (no spaces).",
    403: "The bot is blocked or you never pressed Start -- open your bot in Telegram and tap Start.",
}


def telegram_diagnose(status: int, body: str) -> str:
    b = body.lower()
    if "chat not found" in b:
        return ("Chat ID is wrong, or you never sent your bot a message. Open your bot in "
                "Telegram, tap Start / send 'hi', then re-check the number from getUpdates.")
    if "can't parse entities" in b:
        return "Message formatting error (retried as plain text)."
    return TELEGRAM_HINTS.get(status, "")


def send_message(text: str) -> bool:
    c = cfg()
    token, chat = str(c.get("telegram_bot_token", "")).strip(), str(c.get("telegram_chat_id", "")).strip()
    if not token or not chat:
        print("[notify] Telegram NOT configured (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID secret "
              "missing or misspelled) -- message printed here instead:\n" + text)
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat, "text": text[:4000], "parse_mode": "HTML",
               "disable_web_page_preview": True}
    try:
        r = requests.post(url, json=payload, timeout=(10, 20))
        if r.status_code == 400 and "parse entities" in r.text.lower():
            payload.pop("parse_mode")                        # retry as plain text
            payload["text"] = (text.replace("<b>", "").replace("</b>", "")
                               .replace("<i>", "").replace("</i>", ""))[:4000]
            r = requests.post(url, json=payload, timeout=(10, 20))
        if r.status_code != 200:
            print(f"[notify] Telegram FAILED ({r.status_code}): {r.text[:200]}")
            hint = telegram_diagnose(r.status_code, r.text)
            if hint:
                print(f"[notify] -> Fix: {hint}")
            return False
        print("[notify] Telegram message sent.")
        return True
    except Exception as e:
        print(f"[notify] Telegram error: {e}")
        return False


# --------------------------------------------------------------------------- #
# Alarm channels
# --------------------------------------------------------------------------- #
def ntfy_alarm(title: str, message: str) -> bool:
    c = cfg()
    topic = str(c.get("ntfy_topic", "")).strip()
    if not topic:
        return False
    server = str(c.get("ntfy_server", "https://ntfy.sh")).rstrip("/")

    def go():
        r = requests.post(
            f"{server}/{topic}",
            data=message.encode("utf-8"),
            headers={"Title": title.replace("₹", "Rs ").replace("—", "-")
                                   .encode("ascii", "ignore").decode()[:200] or "Stock alert",
                     "Priority": "5", "Tags": "rotating_light,chart_with_upwards_trend"},
            timeout=(10, 20),
        )
        if r.status_code != 200:
            print(f"[notify] ntfy failed: {r.status_code} {r.text[:200]}")
        return r.status_code == 200

    ok = _hard_deadline(go, 30, "ntfy")
    if ok:
        print("[notify] ntfy alarm sent.")
    return ok


def pushover_emergency(title: str, message: str) -> bool:
    c = cfg()
    if not c.get("pushover_app_token") or not c.get("pushover_user_key"):
        return False

    def go():
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
            timeout=(10, 20),
        )
        if r.status_code != 200:
            print(f"[notify] Pushover failed: {r.status_code} {r.text[:200]}")
        return r.status_code == 200

    ok = _hard_deadline(go, 30, "Pushover")
    if ok:
        print("[notify] Pushover alarm sent.")
    return ok


def callmebot_call(spoken: str) -> bool:
    c = cfg()
    user = str(c.get("callmebot_user", "")).strip()
    if not user:
        return False
    if not user.startswith("@") and not user.startswith("+"):
        user = "@" + user

    def go():
        r = requests.get(
            "https://api.callmebot.com/start.php",
            params={"user": user, "text": spoken[:250], "lang": c["callmebot_voice"],
                    "rpt": 2, "cc": "missed"},
            timeout=(10, 20),
        )
        body = r.text.lower()
        if r.status_code != 200 or "error" in body:
            print(f"[notify] CallMeBot problem: {r.text[-300:]}")
            return False
        return True

    return _hard_deadline(go, 60, "CallMeBot")


def alarm(title: str, spoken: str) -> bool:
    """Ring now via every configured alarm channel."""
    a = ntfy_alarm(title, spoken)
    b = pushover_emergency(title, spoken)
    d = callmebot_call(spoken)
    return a or b or d


_pending = []   # alarms queued during a run -> ONE ring at the end (flush_alarms)


def notify(event: str, detailed: str, title: str, spoken: str) -> None:
    """Telegram message now; alarm queued so several events in one run ring
    you once instead of several times back to back."""
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
        ntfy_alarm(title, "\n".join(p[1] for p in _pending))
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
