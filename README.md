# NSE Swing-Trade Bot — screener, backtester, self-tuning, alarm alerts

A free, rule-based assistant for **NSE swing trades** (hold up to ~1 month),
sized to your capital (default **₹40,000**). It:

- **Screens ~110 liquid NSE stocks** with transparent technical rules and
  gives exact entry, target, stop-loss and quantity.
- **Watches the market every 15 minutes** during trading hours for breakouts
  and for stop-loss/target hits on your open positions.
- **Backtests itself every weekend** on ~6 years of history and **re-tunes
  its rules**, but only when the new rules hold up on data they were
  never tuned on (walk-forward testing), which guards against overfitting.
- **Alerts that are hard to miss at the office:** a Telegram message with
  full details, plus an **actual Telegram voice call** that reads the alert
  aloud (free, via CallMeBot) and/or a **Pushover emergency alarm** that keeps
  ringing until you tap "Acknowledge", even on silent.
- **Tracks its own live accuracy** in `signals.csv`, split by end-of-day and
  intraday picks.

> **Not SEBI-registered investment advice.** It is a mechanical screener. It
> never places trades; every alert is a prompt for your own decision.

---

## What does it cost? Nothing (one optional ₹450-ish app)

| Item | Cost |
|---|---|
| GitHub Actions (runs everything on schedule) | **Free** on public repos. Private repos: 2,000 free minutes/month; this bot uses ~600. |
| Yahoo Finance data (via yfinance) | **Free**, no account |
| NSE official bhavcopy | **Free**, public exchange file |
| Telegram bot + messages | **Free**, unlimited |
| CallMeBot voice calls | **Free** for personal use |
| Pushover alarm app | **Optional** — 30-day free trial, then about US$5 (~₹450) **once**, not a subscription. Skip it and use CallMeBot instead. |
| This bot | Free, it's just your own code |

The only unavoidable money is your **broker's charges on trades you choose to
place** — brokerage, STT, exchange fees, stamp duty, GST. That's roughly
0.2–0.3% of a round trip on delivery, which is exactly what the backtest
already deducts (0.30%), so its results are after costs.

## Is it safe to make the repository public?

Yes, with one thing to know.

**Nobody can change your bot.** Only you can push to your repository.
Strangers can *read* it or take a copy, and they can *propose* a change
(a "pull request"), but a proposal does nothing until you approve and merge
it. There's no way for someone to edit your rules, your schedule or your
alerts.

**Your tokens stay hidden.** The Telegram token, chat ID and Pushover keys go
into GitHub **Secrets**, which are encrypted, never shown in logs, and
deliberately withheld from any run started by an outside contributor. Keep
`config.json` off GitHub (it's in `.gitignore`) and nothing sensitive is
exposed.

**What *is* public:** the code, your `signals.csv` (which stocks it suggested
and the paper P&L) and the backtest report. Not your money, your broker or
your holdings — the bot never knows those.

**Prefer private anyway?** Then schedules may not fire on a free account (see
*GitHub Actions* below). Either upgrade to GitHub Pro, or keep the repo
private and trigger the runs from a free external scheduler such as
cron-job.org calling GitHub's `workflow_dispatch` API with a personal access
token.

---

## The three automatic jobs

| Job | When (IST) | What it does |
|---|---|---|
| **Intraday watch** (`intraday.py`) | Every 15 min, ~9:37am–3:22pm, Mon–Fri | 1) Checks open positions: alarm the moment a **stop-loss or target** is hit. 2) If a slot is free, looks for stocks **breaking out right now** (already in an uptrend yesterday, now crossing their 20-day high on above-normal volume for the time of day). |
| **End-of-day screener** (`main.py`) | 4:20pm, Mon–Fri | Scores every stock on the **completed** daily candle, sends tomorrow's BUY setups, closes out trades past 1 month, sends the live track record. |
| **Weekly backtest** (`backtest.py`) | Saturday 9:00am | Walk-forward backtest over ~6 years (324 rule combinations, ~5 minutes), decides whether to re-tune the rules, sends you a summary, writes `backtest_report.md`. |
| **Check data sources** (`check_sources.py`) | Manual button | Tells you which price sources work from GitHub's servers. |

### Why both end-of-day and intraday?
The core rules (moving averages, RSI, MACD, volume vs average) are defined on
**daily candles**, and a daily candle only exists once the market closes.
Run mid-day, "today's volume" is only half a day's worth and the RSI keeps
moving until 3:30pm, so the same stock can look like a buy at 11am and not
at the close. That is why the main screen runs after the close and you buy
the next morning.

Opportunities do appear during the day, though, and exits are time-critical.
So the intraday job uses a separate rule designed for live data: the setup
must already be in place at **yesterday's close** (so it doesn't depend on
the incomplete day), and the only live check is "is it breaking out now, on
strong volume for this time of day?" Intraday picks are logged with
`source=intraday` so you can see their own win rate. Note that this breakout
rule is **not backtested**: Yahoo only provides ~60 days of 15-minute
history, which is too little. Judge it by its live record after a couple of
months, and switch it off (`intraday_enabled: false`) if it lags the
end-of-day picks.

---

## Where the prices come from

| Source | Role | Notes |
|---|---|---|
| **Yahoo Finance** (yfinance) | Primary: years of daily history + a live candle during market hours | Free, no key. If it returns nothing for most stocks, the bot falls back to Stooq. |
| **NSE official bhavcopy** | Verification: the exchange's own end-of-day file | Free and authoritative. The bot compares each stock's latest close against NSE's, and **skips any stock that disagrees by more than 1%** rather than trading on suspect data. NSE often blocks non-Indian servers, so this may not work from GitHub — the bot just carries on without it. |
| **Stooq** | Backup daily history if Yahoo breaks | Free, no key; Indian coverage is patchy. |
| **NIFTY 50 index** (Yahoo `^NSEI`) | Market-regime and relative-strength filters | — |

**Why not TradingView?** It has no free public API, and scraping their charts
breaks their terms of service. Everything above is either an official exchange
file or a provider's public data endpoint.

Run **Actions → Check data sources → Run workflow** (or `python3
check_sources.py`) to see which sources work from where you're running. The
answer can differ between your phone and GitHub's US servers.

## What makes it smarter (new)

Four upgrades, each of which must prove itself in the weekly backtest rather
than being taken on faith:

1. **Market-regime filter** — no new buys while the NIFTY 50 itself is below
   its own trend. Swing longs fail much more often in a falling market.
   Intraday, this uses the *live* index, so it stands aside within minutes of
   the market turning down.
2. **Relative strength** — only buys stocks that have beaten the NIFTY over
   the last ~3 months. Buy leaders, not laggards.
3. **Trailing stop** — optional: once a trade moves up, the stop follows it
   and never moves back down, locking in profit if a winner reverses. It is
   **off by default**, because in my testing it cut winners short; the weekly
   backtest turns it on only if it proves better on your real data. When it
   raises a stop, you get a Telegram message so you can update your broker's
   GTT order.
4. **Sector cap** — never two positions from the same sector at once. With
   only 3 slots, three bank stocks is really one bet in disguise.

Every backtest report now includes a **"Do the upgrades help?"** table that
tests each switch one at a time on your real data, so you can see which ones
earn their keep and turn off the rest.

## Backtesting & self-tuning, in plain words

**Backtest:** replay the last ~6 years day by day as if the bot had been
running, without ever peeking at future prices. A signal at Monday's close
is bought at **Tuesday's open**. Stop-loss is assumed to hit first if both
levels are touched the same day. **0.30% costs** are deducted per round
trip (brokerage, STT, charges). Only 3 positions at a time, sized with the
same rules as live.

**The trap it avoids (overfitting):** if you try hundreds of rule variations
on the same history, one will look amazing purely by luck and then fail
live. The protections:

1. **Few knobs, coarse steps:** 5 settings (324 combinations): entry
   strictness, stop width, target width, trailing-stop distance, and whether
   the market-regime and relative-strength filters are on at all. Few knobs =
   little room to curve-fit noise.
2. **Walk-forward:** tune on 2 years, then test on the **next 6 months the
   tuner never saw**. Slide forward and repeat. Only those unseen periods count.
3. **Judged on the trades you'd actually take.** With 3 slots you only get
   into roughly 1 in 12 signals (the top-scored ones), so the tuner scores
   those trades, not the average signal. (Early tests showed these two can
   point in opposite directions.)
4. **Conservative goal:** a *pessimistic* estimate of return per day your
   money is tied up. It favours consistency and quick turnover, and punishes
   small samples. Win rate alone is **not** the goal: 90% win rates are easy
   with tiny targets and huge stops, and they lose money.
5. **Plateau, not peak:** each setting is scored together with its neighbours,
   so a stable region is chosen, not a lucky spike.
6. **Adoption gate:** tuned rules go live only if, on unseen data, they (a)
   were profitable after costs, (b) had profit factor > 1, (c) beat the
   default rules' edge by 10%+, and (d) a 60-run simulation of your actual
   ₹40k also came out ahead. Otherwise the defaults stay.
7. **Stickiness:** live rules only change when a new setting is clearly
   (15%+) better, so they don't flip-flop weekly.
8. **Edge check:** if *nothing* made money on unseen data, new BUY alerts
   pause automatically (open positions are still watched) until a later
   weekly run finds an edge. Toggle with `pause_when_no_edge`.

**Underfitting** is the opposite risk: rules too simple to catch real
patterns. The 4 tuned knobs cover what matters most for swing trades, and
the report shows the edge per fold so you can see whether it's real.

Read `backtest_report.md` after each weekly run. The key lines are
**Retention** (how much of the training-period edge survived on unseen data:
70%+ is healthy, under 40% means the tuner is fitting noise) and
**Parameter changes between folds** (frequent flipping = less trustworthy).

---

## GitHub Actions, explained

GitHub is a free website for storing code. **GitHub Actions** is its free
built-in "run this code for me on a schedule" service. On each scheduled
time, GitHub starts a fresh Linux computer in its cloud, downloads this
project, installs Python packages, runs the script, saves the updated
`signals.csv` back into your project, and shuts the computer down. Your
phone doesn't need to be on, and you don't need a server.

**Things worth knowing:**

- **Make the repository PUBLIC.** On free accounts, scheduled runs in
  *private* repositories are unreliable: several reports in 2026 describe
  them never firing, while manual runs work. Public repos also get unlimited
  free Actions minutes. What becomes visible to others: the code,
  `signals.csv` (your picks and paper P&L) and the backtest report. **Your
  tokens and keys stay secret**, because they go into GitHub **Secrets**,
  which are encrypted and never shown, even in public repos. If you must stay
  private, budget ~600 of the 2,000 free minutes per month, and if the
  schedule never fires, see *Troubleshooting*.
- **Timing isn't exact.** GitHub often starts scheduled runs a few minutes
  late (the busiest times are on the hour, so these jobs use odd minutes).
  Fine for swing trading, not for split-second trading.
- **60-day rule:** GitHub pauses schedules in repos with no activity for 60
  days. The bot's own daily commits normally keep the repo active. If you
  ever see "This scheduled workflow is disabled", click **Enable workflow**
  in the Actions tab.
- **Watching it:** the **Actions** tab lists every run with ✅/❌ and full
  logs. Each workflow has a **Run workflow** button to trigger it by hand
  (useful for testing).

---

## Setup (≈20 minutes, once)

### 1. Telegram bot (detailed messages)
1. In Telegram, open **@BotFather** → `/newbot` → pick a name and a username
   ending in `bot`. Copy the **token**.
2. Open your new bot and tap **Start** (send it "hi").
3. In a browser open `https://api.telegram.org/bot<TOKEN>/getUpdates` and
   copy the number after `"chat":{"id":`. That's your **chat ID**.

### 2. Alarms (pick one or both)

**A) Free: a real Telegram voice call (CallMeBot)**
1. Make sure your Telegram account has a **username** (Settings → Username).
2. Authorise CallMeBot: open **@CallMeBot_txtbot** in Telegram and send
   `/start` (or use the login link on callmebot.com's Telegram-call page).
3. Your secret is just your username, e.g. `@ankit_xyz`.
4. Test it: open
   `https://api.callmebot.com/start.php?user=@YOURNAME&text=test+call&lang=en-IN-Standard-A`
   in a browser. Your phone should ring with a Telegram call.

   Notes: it's a free public service, so it can occasionally be slow or
   busy. The bot combines everything from one run into **one** call. On
   iPhone, CallMeBot notes a bug where the voice may not play when you answer
   (the ring still works). If the Indian-English voice fails, set the voice
   to `en-GB-Standard-B`.

**B) Most reliable: Pushover emergency alarm (~US$5 one-time after a 30-day trial)**
1. Install **Pushover** on your phone and create an account. Your **User
   Key** is on the pushover.net dashboard.
2. On pushover.net → *Create an Application/API Token* (name it "NSE bot")
   → copy the **API Token**.
3. Emergency alerts re-ring every 60 seconds for up to 30 minutes until you
   tap **Acknowledge**, and bypass quiet hours. On Android, also allow
   Pushover to override Do Not Disturb in its notification settings.

**Free extra for Telegram messages:** in Telegram, open the bot chat →
⋮ → *Notifications* → choose a loud, distinct **custom sound**. On Android,
also allow the Telegram notification channel to override Do Not Disturb.

### 3. GitHub
1. Create a free account at github.com → **New repository** → name it
   `nse-swing-bot` → **Public** → Create.
2. **Add file → Upload files** → drag in everything from this folder,
   *including* the hidden `.github` folder. If your file browser hides it,
   create the three files under `.github/workflows/` via **Add file →
   Create new file** and paste their contents.
   **Do NOT upload `config.json`** if you created one (it holds your tokens).
3. **Settings → Secrets and variables → Actions**:
   - *Secrets* tab → add: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and
     optionally `CALLMEBOT_USER`, `PUSHOVER_APP_TOKEN`, `PUSHOVER_USER_KEY`.
   - *Variables* tab → optionally `CAPITAL` = `40000` (raise it whenever you
     like) and `INTRADAY_ENABLED` = `false` to switch intraday off.
4. **Actions** tab → enable workflows if asked → open **Weekly backtest +
   self-tuning** → **Run workflow**. In ~2 minutes you'll get the backtest
   summary on Telegram, and `backtest_report.md` appears in the repo.
5. Then run **End-of-day screener** once by hand to confirm alerts and your
   alarm arrive. After that everything runs by itself.

### 4. Optional: run by hand on your phone (Pydroid 3)
Not needed for the automation, but handy for testing.
1. Install **Pydroid 3** → its *Pip* menu → install `yfinance pandas numpy requests`.
   (Newer `yfinance` needs `curl_cffi`, which may not install on some
   phones. If it fails, just use GitHub's **Run workflow** button instead.)
2. Copy the `.py` files to a folder on the phone, copy `config.example.json`
   to `config.json` there, and fill in your tokens.
3. Open and run `main.py` (after 3:30pm), `intraday.py --force` (market
   hours), or `backtest.py` (takes a few minutes on a phone).

---

## Settings (`config.json` locally, Variables/Secrets on GitHub)

| Setting | Default | Meaning |
|---|---|---|
| `capital` | 40000 | Money the bot sizes positions for. Raise it as profits grow. |
| `risk_pct_per_trade` | 0.02 | Max loss per trade if the stop hits (2% of capital). |
| `max_open_positions` | 3 | Trades at once (≈ capital ÷ 3 each). |
| `max_new_signals_per_run` | 2 | New picks per run / per day intraday. |
| `max_per_sector` | 1 | Positions allowed from one sector at a time. |
| `pause_when_no_edge` | true | Pause BUY alerts if the weekly backtest finds no edge. |
| `intraday_enabled` | true | Market-hours breakout scanner on/off. |
| `alarm_events` | all actionable | Which events ring an alarm (BUY, INTRADAY_BUY, STOP_HIT, TARGET_HIT, EXPIRED). |

The trading-rule parameters live in `rules.py` (`DEFAULT_PARAMS`). The weekly
job may override them via `params.json`; don't edit that file by hand.

## Files

| File | Purpose |
|---|---|
| `main.py` | End-of-day run |
| `intraday.py` | Market-hours exit watch + breakout scan |
| `backtest.py` | Walk-forward backtest + self-tuning |
| `rules.py` | The trading rules (shared by live + backtest) |
| `screener.py` | Applies rules to the latest candle, sizes positions |
| `tracker.py` | Open positions, exits, live accuracy |
| `notify.py` | Telegram, CallMeBot call, Pushover alarm |
| `settings.py` | Loads config.json / GitHub secrets |
| `sources.py` | Yahoo / NSE bhavcopy / Stooq adapters |
| `data.py` | Picks a working source, caches, cross-checks against NSE |
| `check_sources.py` | Tells you which sources work where you run it |
| `indicators.py`, `universe.py` | Indicator maths; stock list + sector map |
| `signals.csv` | Every live pick and its outcome (your real track record) |
| `backtest_report.md`, `backtest_trades.csv`, `params.json` | Written by the weekly job |

## Troubleshooting
- **Scheduled runs never start (private repo):** make the repo public; or
  push any small change (commits can "wake" the scheduler); or turn Actions
  off and on in Settings → Actions.
- **No alerts:** check the run log in the Actions tab; "Telegram not
  configured" means a secret name is misspelled.
- **A stock never shows up:** it may have been renamed or delisted; edit
  `universe.py`.

## Honest limitations
- The upgrades above (regime, relative strength, trailing stop, sector cap)
  were tested on **simulated** price data, because live market data wasn't
  reachable while building this. Your first weekly backtest on real NSE
  history is the real test — read the "Do the upgrades help?" table before
  trusting any of them.
- Backtests have **survivorship bias** (today's large caps survived by
  definition), so real past results would have been somewhat worse.
- Target/stop hits are judged from daily high/low and 15-minute checks. Fast
  moves between checks, and gaps, can fill worse than the alert price. Place
  real **stop-loss / GTT orders** with your broker rather than relying on
  alerts alone.
- Yahoo Finance data is free but can lag or have gaps; the bot skips a stock
  rather than guess.
- No rule set guarantees profit. Watch the live record in `signals.csv` for
  a month or two before adding capital.
