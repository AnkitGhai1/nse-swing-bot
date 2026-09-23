"""
Sends one test through every alert channel you've configured and explains,
in plain English, anything that fails.

    python3 test_alerts.py

On GitHub: Actions -> "Test alerts" -> Run workflow, then open the run's log.
"""

from notify import cfg, send_message, ntfy_alarm, pushover_emergency, callmebot_call


def main():
    c = cfg()
    print("=== Alert test ===\n")

    tok, chat = str(c.get("telegram_bot_token", "")).strip(), str(c.get("telegram_chat_id", "")).strip()
    print(f"Telegram token present: {'yes' if tok else 'NO'}"
          f"{f' (looks like {tok[:6]}...{tok[-4:]}, {len(tok)} chars)' if tok else ''}")
    if tok and ":" not in tok:
        print("  -> A bot token always contains a ':' -- this one doesn't. Re-copy it from @BotFather.")
    print(f"Telegram chat ID present: {'yes' if chat else 'NO'}"
          f"{f' ({chat})' if chat else ''}")
    if chat and not chat.lstrip("-").isdigit():
        print("  -> A chat ID is just a number (e.g. 123456789). Use the number from getUpdates, "
              "not your @username or the bot's name.")

    ok_tg = send_message("✅ <b>Test message</b> from your NSE swing bot. If you can read this, "
                         "Telegram alerts work.")
    print(f"\nTelegram: {'✅ sent -- check your phone' if ok_tg else '❌ failed (see the Fix line above)'}")

    if str(c.get("ntfy_topic", "")).strip():
        ok = ntfy_alarm("Test alarm", "Test from your NSE swing bot. Open the ntfy app to stop it ringing.")
        print(f"ntfy:     {'✅ sent' if ok else '❌ failed'}")
    else:
        print("ntfy:     not set up (optional, free -- see README)")

    if c.get("pushover_app_token") and c.get("pushover_user_key"):
        ok = pushover_emergency("Test alarm", "Test from your NSE swing bot. Tap Acknowledge to stop.")
        print(f"Pushover: {'✅ sent' if ok else '❌ failed'}")
    else:
        print("Pushover: not set up (optional)")

    if str(c.get("callmebot_user", "")).strip():
        print("CallMeBot: CALLMEBOT_USER is set. Its bot now charges Telegram Stars, so the call "
              "will usually fail -- delete that secret unless you've paid for it.")
        ok = callmebot_call("This is a test call from your stock bot.")
        print(f"CallMeBot: {'✅ call placed' if ok else '❌ failed'}")

    print("\nDone.")


if __name__ == "__main__":
    main()
