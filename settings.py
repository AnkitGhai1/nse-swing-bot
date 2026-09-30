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

    # Alarm channel 1 (FREE, recommended): ntfy app urgent push that keeps ringing
    # until you open it. Pick a long random topic name -- it acts as a password.
    "ntfy_topic": "",
    "ntfy_server": "https://ntfy.sh",

    # Legacy alarm (no longer free): CallMeBot Telegram voice call
    "callmebot_user": "",            # your Telegram @username
    "callmebot_voice": "en-IN-Standard-A",

    # Alarm channel 2 (paid app, ~US$5 one-time): Pushover emergency alerts that
    # keep ringing every minute until you tap "Acknowledge", even in silent/DND
    "pushover_app_token": "",
    "pushover_user_key": "",
    "pushover_retry_sec": 60,
    "pushover_expire_sec": 1800,

    # which events should ring an alarm (in addition to the Telegram message)
    "alarm_events": ["BUY", "INTRADAY_BUY", "CROSSOVER_BUY", "STOP_HIT", "TARGET_HIT",
                     "TREND_EXIT", "EXPIRED"],

    # Label every alert "PAPER TRADE" (practice, no real money) until a strategy
    # has proven itself live. Set to false (or PAPER_MODE=false) to remove the label.
    "paper_mode": True,

    # Second, separately tracked strategy: 20/50 moving-average crossover
    # (the only idea that held up in both halves of the strategy lab).
    "crossover_enabled": True,
    "crossover_fast": 20,
    "crossover_slow": 50,
    "crossover_stop_atr": 2.5,        # stop = entry - 2.5 x ATR(14); no fixed target
    "crossover_max_hold_days": 120,   # safety limit (~6 months); normal exit is the cross-down
    "crossover_slots": 3,             # its own slots, separate from the main rules
}


def _bool(v: str) -> bool:
    return str(v).strip().lower() not in ("false", "0", "no", "off")

ENV_MAP = {
    "CAPITAL": ("capital", float),
    "TELEGRAM_BOT_TOKEN": ("telegram_bot_token", str),
    "TELEGRAM_CHAT_ID": ("telegram_chat_id", str),
    "CALLMEBOT_USER": ("callmebot_user", str),
    "NTFY_TOPIC": ("ntfy_topic", str),
    "CALLMEBOT_VOICE": ("callmebot_voice", str),
    "PUSHOVER_APP_TOKEN": ("pushover_app_token", str),
    "PUSHOVER_USER_KEY": ("pushover_user_key", str),
    "MAX_OPEN_POSITIONS": ("max_open_positions", int),
    "PAPER_MODE": ("paper_mode", _bool),
    "CROSSOVER_ENABLED": ("crossover_enabled", _bool),
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
