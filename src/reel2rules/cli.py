"""reel2rules: video URL -> clean transcript + caption + key frames. Fully local, no AI API, no paid service.

Usage:
  reel2rules <url> [<url> ...]          # YouTube (incl. Shorts), Instagram reels, TikTok, X ... (anything yt-dlp supports)
  reel2rules -f urls.txt                # one URL per line, '#' comments allowed
Options: --frames N (default 8, 0 = none)  --model tiny|base|small|medium|large-v3  --lang en|auto
         --cookies firefox|chrome|edge|brave  --force-whisper  --out DIR (default $REEL2RULES_OUT or ./inbox)

Output: <out>/<YYYY-MM-DD>_<site>_<id>/transcript.txt (+ frames/*.jpg, meta.json).
Order: platform captions (instant) -> local faster-whisper on CPU (fallback).
"""
from __future__ import annotations

import os

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import argparse  # noqa: E402
import datetime as dt  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
from pathlib import Path  # noqa: E402

from reel2rules import __version__  # noqa: E402

Lines = list[tuple[float, str]]


def default_out() -> Path:
    return Path(os.environ.get("REEL2RULES_OUT", "inbox"))


def sub_langs(lang: str) -> list[str]:
    """Exact caption codes only. A wildcard like 'en.*' also requests YouTube auto-translations -> HTTP 429."""
    return [lang, f"{lang}-orig"] + ([f"{lang}-US", f"{lang}-GB"] if lang == "en" else [])


def ydl_opts(tmp: Path, cookies: str | None, **extra) -> dict:
    o = {"quiet": True, "no_warnings": True, "noprogress": True, "outtmpl": str(tmp / "%(id)s.%(ext)s"),
         "noplaylist": True}
    if cookies:
        o["cookiesfrombrowser"] = (cookies,)
    o.update(extra)
    return o


def safe(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", s)[:60] or "video"


def mmss(t: float) -> str:
    return f"{int(t // 60):02d}:{int(t % 60):02d}"


# ---------- captions ----------
_TS = re.compile(r"(\d+):(\d\d):(\d\d)[.,](\d+)\s*-->")


def parse_vtt(text: str) -> Lines:
    """VTT/SRT -> [(start_s, line)], tags stripped, rolling auto-caption duplicates removed."""
    out: Lines = []
    t = 0.0
    last = ""
    for raw in text.splitlines():
        m = _TS.search(raw)
        if m:
            h, mi, s, _ = m.groups()
            t = int(h) * 3600 + int(mi) * 60 + int(s)
            continue
        line = re.sub(r"<[^>]+>", "", raw)
        line = re.sub(r"&nbsp;|&amp;", " ", line).strip()
        if not line or line.isdigit() or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        if line == last or (out and out[-1][1].endswith(line)):
            continue
        last = line
        out.append((t, line))
    return out


def try_captions(url: str, tmp: Path, cookies: str | None, lang: str) -> tuple[Lines, str] | None:
    import yt_dlp
    opts = ydl_opts(tmp, cookies, skip_download=True, writesubtitles=True, writeautomaticsub=True,
                    subtitleslangs=sub_langs(lang), subtitlesformat="vtt/srt/best")
    with yt_dlp.YoutubeDL(opts) as y:
        y.download([url])
    files = sorted(tmp.glob("*.vtt")) + sorted(tmp.glob("*.srt"))
    if not files:
        return None
    files.sort(key=lambda p: (0 if re.search(rf"\.{re.escape(lang)}(-\w+)?\.", p.name) else 1, len(p.name)))
    lines = parse_vtt(files[0].read_text(encoding="utf-8", errors="ignore"))
    tag = files[0].suffixes[-2].strip(".") if len(files[0].suffixes) > 1 else "sub"
    return (lines, f"captions:{tag}") if lines else None


# ---------- whisper ----------
def whisper(url: str, tmp: Path, cookies: str | None, model: str, lang: str | None) -> tuple[Lines, str]:
    import yt_dlp
    from faster_whisper import WhisperModel
    with yt_dlp.YoutubeDL(ydl_opts(tmp, cookies, format="bestaudio/best")) as y:
        info = y.extract_info(url, download=True)
        path = Path(y.prepare_filename(info))
    m = WhisperModel(model, device="cpu", compute_type="int8")
    segs, inf = m.transcribe(str(path), vad_filter=True, beam_size=1, language=lang)
    lines = [(s.start, s.text.strip()) for s in segs if s.text.strip()]
    path.unlink(missing_ok=True)
    return lines, f"whisper-{model}:{inf.language}({inf.language_probability:.2f})"


# ---------- frames ----------
def probe_duration(ff: str, path: Path) -> float | None:
    """Duration from ffmpeg's header dump (Instagram often reports none)."""
    r = subprocess.run([ff, "-hide_banner", "-i", str(path)], capture_output=True, text=True, errors="ignore")
    m = re.search(r"Duration:\s*(\d+):(\d\d):(\d\d(?:\.\d+)?)", r.stderr)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else None


def frames(url: str, tmp: Path, cookies: str | None, n: int, dest: Path, duration: float | None) -> int:
    if n <= 0:
        return 0
    import imageio_ffmpeg
    import yt_dlp
    opts = ydl_opts(tmp, cookies, format="best[height<=720][vcodec!=none]/bestvideo[height<=720]/best")
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(url, download=True)
        vid = Path(y.prepare_filename(info))
    if not vid.exists():
        return 0
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    dur = duration or info.get("duration") or probe_duration(ff, vid) or 60
    dest.mkdir(exist_ok=True)
    made = 0
    for i in range(n):
        t = dur * (i + 0.5) / n
        out = dest / f"{i + 1:02d}_{mmss(t).replace(':', 'm')}s.jpg"
        r = subprocess.run([ff, "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", str(vid), "-frames:v", "1",
                            "-vf", "scale='min(1280,iw)':-2", "-q:v", "4", str(out)], capture_output=True)
        made += r.returncode == 0 and out.exists()
    vid.unlink(missing_ok=True)
    return made


# ---------- output ----------
def paragraphs(lines: Lines, every: float = 60.0) -> str:
    """Join lines into ~60 s paragraphs, each prefixed with [mm:ss]."""
    out, cur, start = [], [], None
    for t, s in lines:
        if start is None:
            start = t
        if t - start >= every and cur:
            out.append(f"[{mmss(start)}] " + " ".join(cur))
            cur, start = [], t
        cur.append(s)
    if cur:
        out.append(f"[{mmss(start or 0)}] " + " ".join(cur))
    return "\n\n".join(out)


def process(url: str, a: argparse.Namespace) -> Path:
    import yt_dlp
    with yt_dlp.YoutubeDL(ydl_opts(Path("."), a.cookies, skip_download=True)) as y:
        info = y.extract_info(url, download=False)
    site = safe((info.get("extractor_key") or "web").lower())
    folder = a.out / f"{dt.date.today()}_{site}_{safe(info.get('id', 'x'))}"
    folder.mkdir(parents=True, exist_ok=True)
    cap_lang = "en" if a.lang == "auto" else a.lang
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        res = None
        if not a.force_whisper:
            try:
                res = try_captions(url, tmp, a.cookies, cap_lang)
            except Exception as e:  # rate limit / no subs -> fall back to local whisper
                print(f"  captions failed ({str(e)[:120]})", flush=True)
        if res is None:
            print("  no captions -> local whisper (CPU, may take a few minutes)...", flush=True)
            res = whisper(url, tmp, a.cookies, a.model, None if a.lang == "auto" else a.lang)
        lines, source = res
        n_frames = frames(url, tmp, a.cookies, a.frames, folder / "frames", info.get("duration"))
    meta = {"url": url, "site": site, "id": info.get("id"), "title": info.get("title"),
            "uploader": info.get("uploader") or info.get("channel"), "upload_date": info.get("upload_date"),
            "duration_s": info.get("duration"), "views": info.get("view_count"), "transcript_source": source,
            "frames": n_frames, "fetched": dt.datetime.now().isoformat(timespec="seconds"),
            "tool": f"reel2rules {__version__}"}
    (folder / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    desc = (info.get("description") or "").strip()
    head = (f"URL: {url}\nTitle: {meta['title']}\nCreator: {meta['uploader']} | uploaded {meta['upload_date']} | "
            f"{meta['duration_s']} s | views {meta['views']}\nTranscript source: {source} | frames: {n_frames}\n")
    body = head + (f"\n## Caption / description\n{desc}\n" if desc else "") + "\n## Transcript\n" + paragraphs(lines) + "\n"
    (folder / "transcript.txt").write_text(body, encoding="utf-8")
    print(f"  {len(body.split())} words, {n_frames} frames, source {source}")
    return folder


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="reel2rules", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="*")
    ap.add_argument("-f", "--file", type=Path, help="text file with one URL per line")
    ap.add_argument("--frames", type=int, default=8, help="key frames to save (0 = none)")
    ap.add_argument("--model", default="small", help="faster-whisper model (default small; CPU int8)")
    ap.add_argument("--lang", default="en", help="caption/speech language code, or 'auto' (whisper detects)")
    ap.add_argument("--cookies", choices=["firefox", "chrome", "edge", "brave"],
                    help="use your logged-in browser session (login-walled reels)")
    ap.add_argument("--force-whisper", action="store_true", help="ignore platform captions")
    ap.add_argument("--out", type=Path, default=default_out(), help="output root (default $REEL2RULES_OUT or ./inbox)")
    ap.add_argument("--version", action="version", version=f"reel2rules {__version__}")
    a = ap.parse_args(argv)
    urls = list(a.urls)
    if a.file:
        urls += [u.strip() for u in a.file.read_text().splitlines() if u.strip() and not u.startswith("#")]
    if not urls:
        ap.print_help()
        sys.exit(1)
    ok = 0
    for u in urls:
        print(f"> {u}", flush=True)
        try:
            print(f"  saved {process(u, a)}")
            ok += 1
        except Exception as e:  # keep going on batch runs
            print(f"  FAILED: {type(e).__name__}: {str(e)[:300]}")
            if "login" in str(e).lower() or "cookies" in str(e).lower():
                print("  hint: retry with --cookies firefox (log in to the site in that browser first)")
    print(f"done: {ok}/{len(urls)} ok")
    sys.exit(0 if ok == len(urls) else 2)


if __name__ == "__main__":
    main()
