**中文** · [README.md](./README.md)

<p align="center">
  <img src="assets/banner.svg" alt="bili-subtitle-extractor — Bilibili subtitle CLI">
</p>

# 🐍 Bilibili subtitle extractor · command-line

> **BV number in, SRT + TXT + JSON out.**
> Downloads official subtitles when present; when not, downloads audio and runs ASR speech-to-text — **one command, batch-capable, scriptable into cron jobs.**

[![CI](https://github.com/huanweide/bili-subtitle-extractor/actions/workflows/ci.yml/badge.svg)](https://github.com/huanweide/bili-subtitle-extractor/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/huanweide/bili-subtitle-extractor)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![tests](https://img.shields.io/badge/tests-33%2F33-3a8ee6)](tests/test_extractor.py)
[![Deps](https://img.shields.io/badge/deps-zero--stdlib--core-4ecca3)](https://github.com/huanweide/bili-subtitle-extractor)

**Flow**: `BV number / URL → fetch video info + parts → detect subtitles → (yes) download & parse → (no) download audio → ASR transcribe → save trio`

[30-second tour](#30-second-tour) · [What it does](#what-it-does) · [Features](#features) · [Quick start](#quick-start) · [CLI reference](#cli-reference) · [Architecture](#architecture) · [Which one](#python-or-js) · [Roadmap](#roadmap)

---

## 🎯 30-second tour

```text
Before · you want the transcript of a 20-part course collection
─────────────────────────────────────────────
  Browser script   open a page → click → copy → next → repeat 20 times
  Hand-rolled      wrestle with Bilibili API, signing, part cid, subtitle JSON → an afternoon

After · one command
─────────────────────────────────────────────
$ python bili_subtitle_extractor.py BV1xx411c7mD --page all

[1/5] Fetching video info...
  Title: 【Open Course】...
  UP: XXX  |  Parts: 20
── Part 1: Lecture 1 (cid=123456) ──
[2/5] Detecting subtitles...
  Found subtitles (Chinese Simplified), extracting directly
[5/5] Saving subtitles...
  ✓ Saved: output/BV1xx411c7mD_p1_Lecture 1
==================================================
Done! Processed 20 parts

$ ls output/BV1xx411c7mD_p1_Lecture\ 1/
subtitle.srt   subtitle.txt   metadata.json
```

**The one-line difference**: the browser script solves "click once"; this project solves "grab a batch at once, and make it scriptable."

---

## What it does

**Scenario 1 · A single video, with official subtitles**

```
User: python bili_subtitle_extractor.py BV1xx411c7mD
  → fetch video info (title / UP / part cid)
  → detect subtitle tracks: AI Chinese > Chinese(auto) > Chinese(manual) > any
  → download subtitle JSON → build SRT + plain TXT with original timestamps
  → save output/{BV}_p{part}_{title}/ trio
```

**Scenario 2 · A video with no subtitles, go ASR**

```
User: python bili_subtitle_extractor.py BV1xx411c7mD --asr-key sk-xxx
  → detect subtitles: none
  → get the lowest-bitrate audio stream from DASH (ASR needs no high quality, saves time/traffic)
  → direct download (resumable) / or --use-yt-dlp as fallback
  → transcribe via SiliconFlow SenseVoiceSmall → split by Chinese punctuation → SRT + TXT
  → clean up temp audio
```

**Scenario 3 · Preview what's available before deciding**

```
User: python bili_subtitle_extractor.py BV1xx411c7mD --list
  → title / UP / part count
  → each part lists available subtitle languages, or explicitly "none → ASR needed"
```

---

## Features

- **Stdlib-only core** — the core path uses only the Python 3.10+ standard library, **runs with zero `pip install`**; `yt-dlp` is only an optional enhancement (`--use-yt-dlp`).
- **Trio on disk (SRT + TXT + JSON)** — SRT carries original timestamps to drop straight into a player, TXT is plain text ready for AI, JSON stores BV/aid/cid/UP/source metadata for downstream scripts.
- **Best-subtitle gate (find_best_subtitle)** — AI Chinese → Chinese(auto) → Chinese(manual) → any, chosen by priority, not "first match wins".
- **Full multi-part batch (`--page all`)** — one command runs the whole collection; an out-of-range part reports "page N out of range (1-M)" explicitly, never silently downloads the wrong one.
- **Lowest-bitrate audio (bandwidth-min)** — ASR needs no high fidelity; auto-picks the lowest-bandwidth DASH audio track, saving time and traffic.
- **Resumable direct download (Range)** — reuses already-downloaded bytes; if the server returns 200 instead of 206, it overwrites from the start, never writing a half-concatenated corrupt file.
- **Local cache layer (Cache)** — video info cached 24h (`CACHE_TTL`); repeated runs don't re-request; a corrupt or expired cache is treated as a miss, never returning stale data.
- **Proxy and SSL controllable** — `--proxy` applies to all downloads and API requests (not just yt-dlp); `--no-ssl-verify` is for forced man-in-the-middle environments, verification on by default.

---

## Quick start

### Install

```bash
git clone https://github.com/huanweide/bili-subtitle-extractor.git
cd bili-subtitle-extractor
# core features need no pip install; only the audio fallback download needs yt-dlp:
pip install yt-dlp          # optional
```

### Run it in one command

```bash
python bili_subtitle_extractor.py BV1xx411c7mD
# or just paste the URL
python bili_subtitle_extractor.py https://www.bilibili.com/video/BV1xx411c7mD
```

Example output (from the script's real print):

```text
[1/5] Fetching video info...
  Title: Sample video title
  UP: SampleUP  |  Parts: 3
── Part 1: Part 1 (cid=111111) ──
[2/5] Detecting subtitles...
  Found subtitles (Chinese Simplified), extracting directly
[5/5] Saving subtitles...
  ✓ Saved: output/BV1xx411c7mD_p1_Part 1

==================================================
Done! Processed 1 part
  output/BV1xx411c7mD_p1_Part 1
```

### Configure an ASR key for no-subtitle videos

```bash
export SILICONFLOW_API_KEY="sk-xxx"        # Linux / macOS
$env:SILICONFLOW_API_KEY="sk-xxx"          # Windows PowerShell
python bili_subtitle_extractor.py BV1xx411c7mD --asr-key sk-xxx   # or pass inline
```

> ⚠️ The key goes only via environment variable or command-line argument, **never written into a repo file**. With no subtitles and no key, the script errors explicitly rather than silently skipping.

### Self-test

```bash
python tests/test_extractor.py      # 33 assertions, no network
python bili_subtitle_extractor.py --version
```

```text
Ran 33 tests in 0.16s
OK
bili-subtitle-extractor 1.0.0
```

---

## CLI reference

| Argument | Description | Default |
|---|---|---|
| `bvid` | BV number or a URL containing one (required) | — |
| `-o, --output-dir` | Output directory | `./output` |
| `-p, --page` | Part number, `all` for everything | `1` |
| `--asr-key` | SiliconFlow API key | env `SILICONFLOW_API_KEY` |
| `--asr-model` | ASR model | `FunAudioLLM/SenseVoiceSmall` |
| `--use-yt-dlp` | Download audio via yt-dlp (fallback, install yourself) | off |
| `--proxy` | HTTP proxy (applies to all requests) | env `BILI_PROXY` |
| `--no-ssl-verify` | Skip SSL verification (not recommended) | off |
| `--list` | Preview video info and available subtitles only, no extraction | off |
| `--cache-dir` | Cache directory | `./output/.cache` |
| `-V, --version` | Print version | — |

---

## Architecture

**In one line**: a **five-step linear pipeline** (fetch info → detect → fetch source → transcribe → save), branching only once at "is there a subtitle"; long videos aren't carried by memory but by **lowest-bitrate audio + resumable download** to keep cost down.

### Primitives

| Concept | Meaning |
|---|---|
| BV extraction (extract_bvid) | Regex out the BV number from a bare BV or full URL; error and exit if not found |
| Part list (pages) | Each part has its own cid; subtitles and audio are located by cid; `all` iterates |
| Best-subtitle (find_best_subtitle) | AI Chinese > Chinese auto > Chinese manual > any |
| Original timestamps (body_to_srt) | Official subtitles carry real from/to; straight to SRT, no estimation |
| Estimated timestamps (asr_text_to_srt) | ASR is plain text only; split by Chinese punctuation then estimate time, **explicitly labeled estimated** |
| Cache | 24h-TTL JSON file cache; corrupt = miss |
| Lowest-bitrate audio (fetch_audio_url) | Pick the smallest-bandwidth DASH audio track, enough for ASR |

### Main flow

```text
Input BV number / URL
   │
   ├─ extract_bvid (not found → error exit 1)
   │
   ├─ fetch_video_info ─► title / UP / parts + cid
   │
   ├─ cache hit? ── yes ─► reuse, skip network request
   │
   └─ no ─► process each part
          [2/5] fetch_subtitle_list (by cid)
                 │
                 ├─ has subtitle ─► find_best_subtitle → download JSON → body_to_srt (real timestamps)
                 │
                 └─ none ─► [3/5] download audio
                                 ├─ --use-yt-dlp → download_audio_ytdlp
                                 └─ default → fetch_audio_url (lowest bitrate) → download_audio_direct (resumable)
                              [4/5] transcribe_siliconflow (multipart upload) → asr_text_to_srt (estimated timestamps)
                              clean up temp audio
          [5/5] save_output ─► subtitle.srt + subtitle.txt + metadata.json
                              └─ write back cache
```

### Core modules

| Module | Location | Responsibility |
|---|---|---|
| CLI entry | `bili_subtitle_extractor.py` · `main()` | Arg parsing, BV validation, `--list` preview, exceptions collapsed to exit code 1 |
| Main flow | `bili_subtitle_extractor.py` · `extract_subtitle()` | Five-step pipeline and part loop |
| Bilibili API | `fetch_video_info` / `fetch_subtitle_list` / `fetch_audio_url` | Video info, subtitle tracks, DASH audio |
| Download | `download_audio_direct` / `download_audio_ytdlp` | Direct resumable / yt-dlp fallback |
| ASR | `transcribe_siliconflow` | Multipart audio upload, returns transcript |
| Formatting | `body_to_srt` / `asr_text_to_srt` / `fmt_srt_time` | Subtitle body and ASR text → SRT + TXT |
| Cache | `Cache` | 24h JSON cache, corruption-tolerant |
| Utils | `extract_bvid` / `safe_filename` / `build_ssl_context` | BV extraction, filename sanitization, SSL context |
| Tests | `tests/test_extractor.py` | 33 assertions, pure-function layer, no network |

---

## Add your own export format

The trio is all in `save_output()`; adding a format is just one more write:

```python
def save_output(output_dir, bvid, title, page_num, srt_content, txt_content, metadata):
    safe = safe_filename(title)
    folder = os.path.join(output_dir, f"{bvid}_p{page_num}_{safe}")
    os.makedirs(folder, exist_ok=True)
    # new: also write a Markdown for your note app
    with open(os.path.join(folder, "subtitle.md"), "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n{txt_content}\n")
    ...
```

After editing, add an assertion in `tests/test_extractor.py` — pure-function changes are test-backed.

---

## Python or JS

The same author maintains two Bilibili subtitle projects, **non-overlapping in scope — don't pick wrong**:

| | **This repo · bili-subtitle-extractor** (Python CLI) | [bili-subtitle-universal](https://github.com/huanweide/bili-subtitle-universal) (userscript) |
|---|---|---|
| Form | One command in the terminal | Click in the browser |
| Coverage | Bilibili-focused | **Bilibili + YouTube + any webpage `<video>`** |
| Batch | **`--page all` runs a whole collection at once** | Single current page |
| Dependencies | **Python 3.10+ stdlib** | Tampermonkey + browser |
| Automation | **Scriptable / scheduled / CI** | Manual page interaction |
| No subtitles | Download audio → SiliconFlow ASR | Segmented decode → ASR (with resume) |

> **If you want "click in the browser, plus YouTube / any webpage coverage" — use [bili-subtitle-universal](https://github.com/huanweide/bili-subtitle-universal).**
> **If you want "batch, offline, scriptable" — use this repo.**

---

## Security boundary

- **No bundled key**: the ASR key is read only from the environment variable or `--asr-key`; the repo contains no secrets.
- **Only content you're authorized to watch**: no permission bypass, no cracking of paid content.
- **Auditable network behavior**: only Bilibili official endpoints and your specified ASR endpoint; `--proxy` lets you control egress.
- **Never spends silently**: ASR is called only when "no subtitles AND you provided a key".
- **Output is for personal study and accessibility assistance only**; please comply with copyright law and Bilibili's rules.

---

## Roadmap

- ✅ BV / URL input, best-subtitle, multi-part `--page all`
- ✅ No-subtitle → audio → ASR, resumable direct download, yt-dlp fallback
- ✅ 24h local cache, `--list` preview, proxy & SSL switches
- ✅ Zero-dependency unit tests, 33 assertions (`tests/test_extractor.py`)
- ⬜ Multi-language subtitle track selection (current priority leans Chinese)
- ⬜ Output formats: VTT / Markdown
- ⬜ Batch BV list input (file / stdin)
- ⬜ Swappable ASR provider (currently SiliconFlow only)

Tell us in [Issues](https://github.com/huanweide/bili-subtitle-extractor/issues) which you want.

---

## Contributing

1. Fork → branch → change code
2. `python tests/test_extractor.py` must be fully green (33 assertions, no network)
3. New pure functions need a synced test; keep network logic at the CLI layer, don't pollute the pure-function layer
4. In your PR, state the real BV number and command you verified with (**don't paste keys**)

CI (`ci.yml`) runs on Python 3.12 / 3.13: syntax check + unit tests + CLI smoke; `ruff` is advisory only, non-blocking.

---

## License

MIT — see [LICENSE](LICENSE). Bilibili-related names belong to their respective owners.

---

## Star

If this tool saved you from manually scraping subtitles once, **a Star is the best thanks**.

**Author**: huanweide ([@huanweide](https://github.com/huanweide)) · MIT

**Other tools by the same author**:

- 🎬 [bili-subtitle-universal](https://github.com/huanweide/bili-subtitle-universal) · universal video subtitle extractor (browser click, includes YouTube)
- 🔴 [live-subtitle](https://github.com/huanweide/live-subtitle) · live / meeting real-time Chinese subtitles (local recognition)
- 🎓 [zhihuishu-helper](https://github.com/huanweide/zhihuishu-helper) · Zhihuishu course auto-play / resume
- 🩺 [family-showcase](https://github.com/huanweide/family-showcase) · code-health tools overview
- 📦 [All repos](https://github.com/huanweide?tab=repositories)
