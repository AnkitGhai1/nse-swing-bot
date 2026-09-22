"""One place to load settings.

Order of precedence (later wins):
  1. DEFAULTS below
  2. config.json in this folder        (for Pydroid3 / running on your own device)
  3. environment variables             (for GitHub Actions: repo Secrets/Variables)
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")

DEFAULTS = {
    # money
    "capital": 40000,
    "risk_pct_per_trade": 0.02,
    "max_open_positions": 3,
    "max_new_signals_per_run": 2,
    "max_per_sector": 1,             # never hold 2 stocks from the same sector
    "pause_when_no_edge": True,      # stop BUY alerts if the weekly backtest finds no edge
    "intraday_enabled": True,        # market-hours breakout scanner on/off

    # Telegram (normal detailed messages)
    "telegram_bot_token": "",
    "telegram_chat_id": "",

    # Alarm channel 1 (free): CallMeBot rings you with a real Telegram voice call
    "callmebot_user": "",            # your Telegram @username
    "callmebot_voice": "en-IN-Standard-A",

    # Alarm channel 2 (paid app, ~US$5 one-time): Pushover emergency alerts that
    # keep ringing every minute until you tap "Acknowledge", even in silent/DND
    "pushover_app_token": "",
    "pushover_user_key": "",
    "pushover_retry_sec": 60,
    "pushover_expire_sec": 1800,

    # which events should ring an alarm (in addition to the Telegram message)
    "alarm_events": ["BUY", "INTRADAY_BUY", "STOP_HIT", "TARGET_HIT", "EXPIRED"],
}

ENV_MAP = {
    "CAPITAL": ("capital", float),
    "TELEGRAM_BOT_TOKEN": ("telegram_bot_token", str),
    "TELEGRAM_CHAT_ID": ("telegram_chat_id", str),
    "CALLMEBOT_USER": ("callmebot_user", str),
    "CALLMEBOT_VOICE": ("callmebot_voice", str),
    "PUSHOVER_APP_TOKEN": ("pushover_app_token", str),
    "PUSHOVER_USER_KEY": ("pushover_user_key", str),
    "MAX_OPEN_POSITIONS": ("max_open_positions", int),
}


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH) as f:
                cfg.update(json.load(f))
        except Exception as e:
            print(f"[warn] config.json unreadable, using defaults: {e}")
    for env, (key, cast) in ENV_MAP.items():
        val = os.environ.get(env, "").strip()
        if val:
            try:
                cfg[key] = cast(val)
            except ValueError:
                print(f"[warn] bad value for {env}: {val!r}")
    return cfg
