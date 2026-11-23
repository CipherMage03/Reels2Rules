# reel2rules

**Turn trading videos into testable rules: free, local, no API keys.**

Paste a YouTube video, YouTube Short, Instagram reel or TikTok link and get a clean transcript, the post caption and key screenshots, all on your own machine. Then, if you use [Claude Code](https://docs.claude.com/en/docs/claude-code), two bundled skills turn that transcript into a strict strategy spec and an honest backtest.

```
reel2rules https://www.youtube.com/shorts/XXXXXXXXXXX
> https://www.youtube.com/shorts/XXXXXXXXXXX
  no captions -> local whisper (CPU, may take a few minutes)...
  246 words, 8 frames, source whisper-small:en(1.00)
  saved inbox/2026-11-23_youtube_XXXXXXXXXXX
done: 1/1 ok
```

## Why
Quant and backtesting people keep paying for transcript services just to read what a "10-year strategy in 42 seconds" actually says. That step does not need a subscription or an LLM:

| | reel2rules |
|---|---|
| Cost | Free (MIT). No API keys, no per-minute fees |
| Privacy | Runs locally. Audio never leaves your machine |
| Speed | Platform captions first (instant); local Whisper only when there are none |
| Output | Plain text built for reading by humans *and* LLMs: timestamps every ~60 s, caption-roll duplicates removed (often 30-50% shorter than raw captions) |
| Visual rules | Saves evenly spaced key frames, because indicator settings are often *shown*, never *said* |
| Sites | Anything [yt-dlp](https://github.com/yt-dlp/yt-dlp) supports: YouTube, Shorts, Instagram, TikTok, X, Facebook and more |
| AI tokens | Zero. Transcription is a normal local program; your AI only reads the final text file |

## Install
Needs Python 3.10+. No separate ffmpeg install (a static ffmpeg is fetched by `imageio-ffmpeg`). No GPU needed.

**Recommended (isolated, puts `reel2rules` on your PATH):**
```bash
pipx install git+https://github.com/CipherMage03/reel2rules
```

**Or a plain virtual environment:**
```bash
git clone https://github.com/CipherMage03/reel2rules
cd reel2rules
python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -e .
```

On first use without captions, faster-whisper downloads its model (~460 MB for `small`) to your Hugging Face cache.

## Use
```bash
reel2rules <url>                       # one video
reel2rules <url1> <url2> <url3>        # several
reel2rules -f urls.txt                 # one URL per line, lines starting with # are skipped
reel2rules <url> --frames 0            # transcript only
reel2rules <url> --model medium        # more accurate speech-to-text, slower
reel2rules <url> --lang auto           # non-English: let Whisper detect the language
reel2rules <url> --cookies firefox     # login-walled reels: uses your logged-in browser session
reel2rules <url> --out D:\research\inbox
```
The default output folder is `./inbox`. Set the `REEL2RULES_OUT` environment variable to change it permanently.

### Output
```
inbox/2026-11-23_instagram_<id>/
├── transcript.txt   # header (url, title, creator, date, views, source) + caption/description + transcript
├── meta.json        # same metadata, machine-readable
└── frames/          # 01_00m03s.jpg ... evenly spaced key frames
```
`transcript.txt` looks like this:
```
URL: https://www.instagram.com/p/<id>/
Title: Video by <creator>
Creator: <creator> | uploaded 20261119 | None s | views None
Transcript source: whisper-small:en(1.00) | frames: 8

## Caption / description
<post caption: on Instagram this often contains the actual rules or the sales pitch>

## Transcript
[00:00] You enter on the three minute timeframe ...
[01:00] ...
```
The `Transcript source` line tells you how much to trust the text: `captions:en` came from the platform; `whisper-small:en(0.97)` is local speech-to-text with its language confidence. Speech-to-text gets numbers and tickers wrong ("NAS one hundred", "point five"), so check them against the frames.

## Claude Code integration (optional)
Two skills turn transcripts into research instead of hype:

| Skill | What it does |
|---|---|
| `/strategy-extract <inbox folder>` | Builds a **Strategy Spec Card**: every rule tagged *stated / inferred / missing*, ambiguous readings frozen as at most 4 variants **before** any data is touched, red flags (one-day P&L claims, repainting indicators, no stop, lead-magnet funnels...) and a verdict: *testable / testable with proxy / not testable*. Opens frames only when a rule refers to something on screen. |
| `/strategy-test <card>` | Backtests the frozen variants on **your** data: causal indicators, next-bar fills, costs at 1x and 2x, a look-ahead unit test, random-entry and buy-and-hold baselines, every trial logged, deflated Sharpe, and a pre-registered pass / watch / reject verdict. The holdout stays locked. |

### Install the skills
```powershell
# Windows: user-wide (~/.claude/skills)
.\scripts\install-skills.ps1
# or only for one project
.\scripts\install-skills.ps1 -Project "C:\path\to\your\research-repo"
```
```bash
# macOS / Linux
sh scripts/install-skills.sh                    # user-wide
sh scripts/install-skills.sh /path/to/your/repo # one project
```
Restart Claude Code; the skills appear as `/strategy-extract` and `/strategy-test`.

### Configure once
The skills are framework-agnostic. Tell them about your setup in your research repo's `CLAUDE.md`, for example:
```markdown
## Research data (for /strategy-extract and /strategy-test)
- Data: data/processed/<symbol>_1m.parquet, bid/ask OHLC, UTC; NAS100, US500, XAUUSD, EURUSD; 2015-2026. Volume NOT real (CFD tick count).
- Backtest engine: src/backtest/ (use it; fills at next bar open). Costs: src/backtest/costs.py.
- In-sample 2015-2024; holdout >= 2025-01-01 (locked).
- reel2rules inbox: research/social/inbox ; cards: research/social
```
Then edit the *Settings* block at the top of each `SKILL.md` if your folders differ from `./inbox` and `./strategies/social`.

### Workflow
```bash
reel2rules -f todays_links.txt           # local, zero tokens
```
```text
/strategy-extract inbox/2026-11-23_youtube_<id>
/strategy-test strategies/social/S001-<slug>.md
```
Token tip: transcribe in batches outside Claude Code, then point Claude at the folders. Claude reads a short text file instead of you pasting transcripts.

## Troubleshooting
| Symptom | Fix |
|---|---|
| `HTTP Error 429` on captions | YouTube rate-limits caption requests. The tool automatically falls back to local Whisper. If downloads also fail, wait a while or use `--cookies firefox`. |
| Instagram: login required / empty result | Log in to Instagram in Firefox, then `--cookies firefox`. On Windows, Chrome locks its cookie database while it is running, so Firefox is more reliable. |
| Site changed and downloads break | `pip install -U yt-dlp` (or `pipx upgrade reel2rules`). yt-dlp updates often. |
| `open() got an unexpected keyword argument 'metadata_errors'` | PyAV 16+ with faster-whisper 1.2.x. The package pins `av<16`. Reinstall: `pip install "av<16"`. |
| Slow transcription | It is CPU-only (int8). Use `--model base` for speed or `--model medium` for accuracy. Captions, when present, are instant. |
| Symlink warning from Hugging Face on Windows | Harmless (already silenced). The cache just uses more disk. |

## Responsible use
- Respect each platform's Terms of Service and copyright. This tool is for personal research and education, so don't republish other people's content.
- Only use `--cookies` with your own account.
- Nothing here is financial advice. Most social-media strategies fail honest testing; the skills are built to find that out cheaply, not to sell you an edge.

## How it works
1. yt-dlp reads metadata and tries the platform's own captions (exact language codes only; wildcards trigger auto-translation requests and HTTP 429).
2. If there are none, it downloads audio only and transcribes it locally with [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (CPU, int8, voice-activity filter).
3. It downloads a ≤720p copy, grabs N evenly spaced frames with ffmpeg and deletes the video.
4. It writes `transcript.txt`, `meta.json` and `frames/`.

## Development
```bash
pip install -e ".[dev]"
pytest -q
```

## License
MIT. Built on [yt-dlp](https://github.com/yt-dlp/yt-dlp) (Unlicense), [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (MIT) and [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg) (BSD-2; downloads an ffmpeg binary under its own license).
