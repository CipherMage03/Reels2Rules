---
name: strategy-test
description: Backtest a frozen Strategy Spec Card (from /strategy-extract, or any precisely written rule set) on the user's local market data with honest methodology - frozen variants, next-bar fills, realistic costs at 1x and 2x, chronological in-sample / holdout split, baselines, every trial logged, deflated Sharpe - then give a pre-registered pass / watch / reject verdict. Use when the user says "test this strategy", "backtest this card", or after /strategy-extract produces a testable card.
argument-hint: <path to S###-slug.md card>
---

# Strategy Test (Spec Card -> verdict)

## Settings (edit once for your project; ask the user if missing)
- Data: path, format, instruments, bar size, timezone, whether bid/ask or mid, whether volume is real.
- Backtest framework: use the project's own engine if it has one (read its README / CLAUDE.md conventions first); otherwise write a small, self-contained pandas/NumPy backtester in `strategies/social/`.
- Costs per instrument: spread, commission, slippage, financing (swap). Report at **1x and 2x**.
- In-sample period and **holdout start date** (e.g. last 2 years). The holdout is never touched by this skill.
- Trial log: `strategies/social/trials.jsonl` (append-only).

## Hard rules
- Card variants are frozen. Never add, tune or drop rules after seeing results. A new idea = a new logged variant that counts in the multiple-testing correction.
- No look-ahead: decide only on completed bars; fill at the next bar's open (buy at ask / sell at bid if available); stops can gap through; if stop and target hit in the same bar, the stop wins.
- Indicators must be causal (EMA/VWAP/ATR computed from past bars only; session VWAP resets at the session open; higher-timeframe values only after that bar closes).
- Holdout stays locked. Testing on it is a separate, one-shot step that needs the user's explicit approval and a written reason.
- Log every variant (params, metrics, data hash or file + date range, period, notes) - including failures.

## Steps
1. Read the card. If a rule is still [?] without a frozen variant, stop and fix the card via /strategy-extract - not in code.
2. Implement one module `strategies/social/s###_<slug>.py`: `signals(df, params)` (causal), `simulate(...)` -> trade list (entry/exit time & price, side, gross and net return at 1x / 2x costs), `main()` that runs all variants on in-sample data and appends to the trial log.
3. Look-ahead test (pytest): signals computed on data truncated at time t must equal the full-data signals up to t, at several cut points. It must pass before results are trusted.
4. Baselines: random entries with the same count, side mix and holding time (≥ 500 replicas -> percentile), plus buy-and-hold over the same window.
5. Run, then write `strategies/social/S###-<slug>_results.md` (≤ 40 lines) and append a Results line to the card.

## Default pass criteria (unless the card pre-registered others)
"candidate" only if ALL: net Sharpe at 2x costs > 0.5; positive in both halves of in-sample; no single year > 50% of profit; beats the random-entry 95th percentile and buy-and-hold; deflated Sharpe ≥ 0.95 over all variants of this card; ≥ 100 trades (fewer -> "insufficient sample", never a pass). Base criteria met but DSR < 0.95 -> "watch". Otherwise "reject".

Deflated Sharpe (Bailey & López de Prado 2014): probability the best observed Sharpe exceeds the expected maximum Sharpe of N independent trials with the observed variance of trial Sharpes, adjusted for skew and kurtosis.

## Report (compact)
One table: variant | trades | net per trade 1x / 2x | Sharpe 2x | max DD | half 1 / half 2 | years positive | vs random pctile | DSR | verdict. Then: creator's claim vs measured (one line), main failure reason, red flags confirmed/refuted, next action, and which tests actually ran. No profit claims: a pass means "worth a forward / paper test", not an edge.

## Escalation
"candidate" or "watch": get an independent audit of the code and results (a fresh subagent given the files, not your conclusion) before any holdout test or paper trading. Reject: stop; don't rescue it by tuning.
