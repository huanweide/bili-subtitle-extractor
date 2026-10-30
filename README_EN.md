**中文** · [README.md](./README.md)

<p align="center">
  <img src="assets/banner.svg" alt="bili-subtitle-extractor — B站字幕提取命令行版">
</p>

**English** · [README_EN.md](./README_EN.md)

# Bilibili Subtitle Extractor · Command-Line Edition

> **BV id in, SRT + TXT + JSON out.**
> Official subtitles are downloaded directly; if there are none, it downloads the audio and runs ASR speech-to-text — **one command, batch-capable, scriptable into scheduled tasks**.

[![CI](https://github.com/huanweide/bili-subtitle-extractor/actions/workflows/ci.yml/badge.svg)](https://github.com/huanweide/bili-subtitle-extractor/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/huanweide/bili-subtitle-extractor)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![tests](https://img.shields.io/badge/tests-33%2F33-3a8ee6)](tests/test_extractor.py)
[![Deps](https://img.shields.io/badge/deps-zero--stdlib--core-4ecca3)](https://github.com/huanweide/bili-subtitle-extractor)

**Pipeline**: `BV id / URL → fetch video info + parts → detect subtitles → (yes) download & parse → (no) download audio → ASR transcribe → trio on disk`

[30-Second Overview](#30-second-overview) · [What It Does](#what-it-does) · [Features](#features) · [Quick Start](#quick-start) · [CLI Reference](#cli-reference) · [Architecture](#architecture) · [Python or JS](#python-or-js) · [Roadmap](#roadmap)

---

## Who Should Use It / Who Should NOT

**Good fit if —**

- You want **batch / offline / scriptable** Bilibili subtitle extraction — one command handles a whole multi-part collection, and it drops into a cron job or CI.
- You want the **SRT + TXT + JSON trio** on disk (SRT with original timestamps for players, TXT for feeding AI, JSON with metadata for downstream scripts).
- You only need Bilibili (not YouTube or arbitrary web pages).

**Not for you if —**

- You want to **click in the browser**, or you need **YouTube / any webpage `<video>`** — use the JS [bili-subtitle-universal](https://github.com/huanweide/bili-subtitle-universal) instead.
- You won't bring your own ASR key for no-subtitle videos. (Official subtitles need no key.)

---

## 30-Second Overview

```text
BEFORE · you want the transcript of a 20-part course bundle
─────────────────────────────────────────────
  Browser script   open a page → click → copy → next page → repeat 20×   →  a night
  Hand script      wrestle Bilibili API, signing, part cid, subtitle JSON   →  an afternoon

AFTER · one command
─────────────────────────────────────────────
$ python bili_subtitle_extractor.py BV1xx411c7mD --page all

[1/5] fetching video info...
  title: 【public lecture】...
  UP: XXX  |  parts: 20
── part 1: lecture 1 (cid=123456) ──
[2/5] detecting subtitles...
  found subtitles (Chinese Simplified), extracting directly
[5/5] saving subtitles...
  ✓ saved to: output/BV1xx411c7mD_p1_lecture 1
==================================================
Done! processed 20 parts total

$ ls output/BV1xx411c7mD_p1_lecture\ 1/
subtitle.srt   subtitle.txt   metadata.json
```

**The one-line difference**: the browser script solves "click on the spot"; this project solves "grab a bunch at once, and make it scriptable".

---

## What It Does

**Scenario 1 · Single video, official subtitles present**

```text
User: python bili_subtitle_extractor.py BV1xx411c7mD
  → fetch video info (title / UP / part cid)
  → detect subtitle tracks: AI Chinese > Chinese (auto) > Chinese (manual) > any subtitle
  → download subtitle JSON → generate SRT + plain TXT with original timestamps
  → write trio to output/{BV}_p{page}_{title}/
```

**Scenario 2 · No-subtitle video, go via ASR**

```text
User: python bili_subtitle_extractor.py BV1xx411c7mD --asr-key sk-xxx
  → detect subtitles: none
  → take the lowest-bitrate audio stream from the DASH interface (ASR doesn't need high quality — saves time and traffic)
  → direct-link download (resumable) / or --use-yt-dlp as fallback
  → send to SiliconFlow SenseVoiceSmall for transcription → split by Chinese punctuation → SRT + TXT
  → clean up temp audio
```

**Scenario 3 · Look first, decide later**

```text
User: python bili_subtitle_extractor.py BV1xx411c7mD --list
  → title / UP / part count
  → each part lists available subtitle languages, or explicitly "none → ASR needed"
```

---

## Features

- **Stdlib-only core** — the core chain uses only the Python 3.10+ standard library; **no `pip install` needed to run**; `yt-dlp` is only an optional enhancement (`--use-yt-dlp`).
- **Trio on disk (SRT + TXT + JSON)** — SRT with original timestamps loads straight into a player, TXT is plain text ready for AI, JSON stores BV/aid/cid/UP/source metadata for downstream scripts.
- **Best-subtitle gate (find_best_subtitle)** — AI Chinese → Chinese (auto) → Chinese (manual) → any subtitle, picked by priority, not "first match wins".
- **Full-part batch (`--page all`)** — one command runs the whole collection; an out-of-range single part clearly reports "page N out of range (1-M)" instead of silently downloading the wrong one.
- **Lowest-bitrate audio (bandwidth-min)** — ASR doesn't need high quality; auto-picks the lowest-bandwidth audio track in DASH, saving time and traffic.
- **Resumable direct download (Range)** — reuses already-downloaded bytes; if the server returns 200 without Range support, it overwrites from the start, never writing a half-joined corrupt file.
- **Local cache layer (Cache)** — video info cached 24h (`CACHE_TTL`); reruns don't re-request; a corrupt or expired cache is treated as a miss, never feeding stale data as a result.
- **Proxy and SSL controllable** — `--proxy` applies to all downloads and API requests (not just yt-dlp); `--no-ssl-verify` is left for forced man-in-the-middle environments; verification stays on by default.

---

## Quick Start

### Install

```bash
git clone https://github.com/huanweide/bili-subtitle-extractor.git
cd bili-subtitle-extractor
# core features need no pip install; only the audio fallback download needs yt-dlp:
pip install yt-dlp          # optional
```

### Run it with one command

```bash
python bili_subtitle_extractor.py BV1xx411c7mD
# or just paste a URL
python bili_subtitle_extractor.py https://www.bilibili.com/video/BV1xx411c7mD
```

Example output (from the script's real print):

```text
[1/5] fetching video info...
  title: sample video title
  UP: sample UP  |  parts: 3
── part 1: part one (cid=111111) ──
[2/5] detecting subtitles...
  found subtitles (Chinese Simplified), extracting directly
[5/5] saving subtitles...
  ✓ saved to: output/BV1xx411c7mD_p1_part one

==================================================
Done! processed 1 part total
  output/BV1xx411c7mD_p1_part one
```

### Configure an ASR key when there are no subtitles

```bash
export SILICONFLOW_API_KEY="sk-xxx"        # Linux / macOS
$env:SILICONFLOW_API_KEY="sk-xxx"          # Windows PowerShell
python bili_subtitle_extractor.py BV1xx411c7mD --asr-key sk-xxx   # or pass directly
```

> ⚠️ The key only comes from an environment variable or a CLI argument; **don't write it into repo files**. When there are no subtitles and no key, the script errors clearly rather than silently skipping.

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

## CLI Reference

| Argument | Description | Default |
|---|---|---|
| `bvid` | BV id, or a URL containing a BV id (required) | — |
| `-o, --output-dir` | output directory | `./output` |
| `-p, --page` | part number; `all` for everything | `1` |
| `--asr-key` | SiliconFlow API key | env `SILICONFLOW_API_KEY` |
| `--asr-model` | ASR model | `FunAudioLLM/SenseVoiceSmall` |
| `--use-yt-dlp` | download audio with yt-dlp (fallback, install yourself) | off |
| `--proxy` | HTTP proxy (applies to all requests) | env `BILI_PROXY` |
| `--no-ssl-verify` | skip SSL verification (not recommended) | off |
| `--list` | preview video info and available subtitles only, don't extract | off |
| `--cache-dir` | cache directory | `./output/.cache` |
| `-V, --version` | print version | — |

---

## Architecture

**One sentence**: a **five-step straight pipeline** (info → detect → fetch source → transcribe → write), branching only once at "are there subtitles?"; long video isn't carried by memory but by **lowest-bitrate audio + resumable download** to keep the cost down.

### Concepts

| Concept | Meaning |
|---|---|
| BV extraction (extract_bvid) | regex-extract the BV id from a bare BV id or full URL; error exit if not found |
| Part list (pages) | each part has its own cid; subtitles and audio are located by cid; `all` iterates |
| Best-subtitle (find_best_subtitle) | AI Chinese > Chinese auto > Chinese manual > any |
| Original timestamps (body_to_srt) | official subtitles carry real from/to; converted straight to SRT, no estimation |
| Estimated timestamps (asr_text_to_srt) | ASR gives plain text only; split by Chinese punctuation then estimate time, **explicitly marked as estimated** |
| Cache | 24h-TTL JSON file cache; corrupt = treated as miss |
| Lowest-bitrate audio (fetch_audio_url) | pick the smallest bandwidth track in DASH; good enough for ASR |

### Main flow

```text
Input BV id / URL
   │
   ├─ extract_bvid (not found → exit 1)
   │
   ├─ fetch_video_info ─► title / UP / parts + cid
   │
   ├─ cache hit? ── yes ─► reuse directly, skip network request
   │
   └─ no ─► process each part
          [2/5] fetch_subtitle_list (by cid)
                 │
                 ├─ subtitles ─► find_best_subtitle → download JSON → body_to_srt (real timestamps)
                 │
                 └─ none ─► [3/5] download audio
                                 ├─ --use-yt-dlp → download_audio_ytdlp
                                 └─ default → fetch_audio_url (lowest bitrate) → download_audio_direct (resumable)
                              [4/5] transcribe_siliconflow (multipart upload) → asr_text_to_srt (estimated timestamps)
                              clean up temp audio
          [5/5] save_output ─► subtitle.srt + subtitle.txt + metadata.json
                              └─ write back to cache
```

### Core modules

| Module | Location | Responsibility |
|---|---|---|
| CLI entry | `bili_subtitle_extractor.py` · `main()` | arg parsing, BV validation, `--list` preview, exceptions collapsed to exit code 1 |
| Main flow | `bili_subtitle_extractor.py` · `extract_subtitle()` | five-step pipeline and part loop |
| Bilibili API | `fetch_video_info` / `fetch_subtitle_list` / `fetch_audio_url` | video info, subtitle tracks, DASH audio |
| Download | `download_audio_direct` / `download_audio_ytdlp` | direct resumable / yt-dlp fallback |
| ASR | `transcribe_siliconflow` | multipart audio upload, returns transcript |
| Formatting | `body_to_srt` / `asr_text_to_srt` / `fmt_srt_time` | subtitle body and ASR text → SRT + TXT |
| Cache | `Cache` | 24h JSON cache, corruption-tolerant |
| Utils | `extract_bvid` / `safe_filename` / `build_ssl_context` | BV extraction, filename sanitization, SSL context |
| Tests | `tests/test_extractor.py` | 33 assertions, pure-function layer, no network |

---

## Add Your Own Export Format

The output trio all lives in `save_output()`; adding a format is just one more file write:

```python
def save_output(output_dir, bvid, title, page_num, srt_content, txt_content, metadata):
    safe = safe_filename(title)
    folder = os.path.join(output_dir, f"{bvid}_p{page_num}_{safe}")
    os.makedirs(folder, exist_ok=True)
    # new: also write a Markdown, handy to drop into note software
    with open(os.path.join(folder, "subtitle.md"), "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n{txt_content}\n")
    ...
```

After changing, add an assertion to `tests/test_extractor.py` — pure-function changes always have test cover.

---

## Python or JS

The same author maintains two Bilibili subtitle projects, **with non-overlapping positioning — don't pick wrong**:

| | **This repo · bili-subtitle-extractor** (Python CLI) | [bili-subtitle-universal](https://github.com/huanweide/bili-subtitle-universal) (userscript) |
|---|---|---|
| Form | one terminal command | click in the browser |
| Coverage | Bilibili focused | **Bilibili + YouTube + any webpage `<video>`** |
| Batch | **`--page all` runs the whole collection at once** | single current page |
| Dependencies | **Python 3.10+ standard library** | Tampermonkey + browser |
| Automation | **scriptable / scheduled / CI** | needs human on the page |
| No subtitles | download audio → SiliconFlow ASR | segmented decode → ASR (with resume) |

> **If you want "click in the browser, also covering YouTube / any webpage" — use [bili-subtitle-universal](https://github.com/huanweide/bili-subtitle-universal).**
> **If you want "batch, offline, scriptable" — use this repo.**

---

## Security Boundary

- **No built-in keys**: the ASR key is read only from an environment variable or `--asr-key`; the repo contains no secret.
- **Only fetches content you're authorized to watch**: this project doesn't bypass permissions or crack paid content.
- **Auditable network behavior**: only requests Bilibili's official interfaces and the ASR endpoint you specify; `--proxy` keeps the egress in your hands.
- **Doesn't secretly spend your money**: ASR is only called when "no subtitles AND you provided a key".
- **Output is for personal study and accessibility assistance only**; comply with copyright law and Bilibili's rules.

---

## Roadmap

- ✅ BV id / URL input, best-subtitle selection, multi-part `--page all`
- ✅ No subtitles → audio → ASR transcription, resumable direct download, yt-dlp fallback
- ✅ 24h local cache, `--list` preview, proxy and SSL toggles
- ✅ Zero-dependency unit tests, 33 cases (`tests/test_extractor.py`)
- ⬜ Multi-language subtitle track selection (current best-subtitle rule leans Chinese)
- ⬜ Output format expansion: VTT / Markdown
- ⬜ Batch BV id list input (file / stdin)
- ⬜ Switchable ASR vendors (currently SiliconFlow only)

Tell us in [Issues](https://github.com/huanweide/bili-subtitle-extractor/issues) which one you want most.

---

## Contributing

1. Fork → branch → change code
2. `python tests/test_extractor.py` must be fully green (33 assertions, no network)
3. New pure functions must add tests; network logic stays at the CLI layer, don't pollute the pure-function layer
4. On PR, state the real BV id and command you verified with (**don't paste keys**)

CI (`ci.yml`) runs on Python 3.12 / 3.13: syntax check + unit tests + CLI smoke; `ruff` is advisory only, non-blocking.

---

## License

MIT — see [LICENSE](LICENSE). Bilibili-related names are trademarks of their respective owners.

---

## Star

If this tool saved you from manually scraping subtitles once, **a Star is the best reward**.

**Author**: huanweide ([github.com/huanweide](https://github.com/huanweide)) · MIT

**Other tools by the same author**:

- 🎬 [bili-subtitle-universal](https://github.com/huanweide/bili-subtitle-universal) · universal video subtitle extraction (click in browser, includes YouTube)
- 🔴 [live-subtitle](https://github.com/huanweide/live-subtitle) · live / meeting real-time Chinese subtitles (local recognition)
- 🎓 [zhihuishu-helper](https://github.com/huanweide/zhihuishu-helper) · Zhihuishu course auto-play / resume
- 🩺 [family-showcase](https://github.com/huanweide/family-showcase) · code-health tools hub
- 📦 [All repositories](https://github.com/huanweide?tab=repositories)
