<p align="center">
  <img src="assets/banner.svg" alt="bili-subtitle-extractor">
</p>

# 🐍 Bilibili Subtitle Extractor · CLI

> **BV id in. SRT + TXT + JSON out.**
> Downloads official subtitles when they exist; when they don't, pulls the audio and transcribes it with ASR — **one command, batchable, scriptable.**

[![CI](https://github.com/huanweide/bili-subtitle-extractor/actions/workflows/ci.yml/badge.svg)](https://github.com/huanweide/bili-subtitle-extractor/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/huanweide/bili-subtitle-extractor)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![tests](https://img.shields.io/badge/tests-33%2F33-3a8ee6)](tests/test_extractor.py)

**中文:** [README.md](README.md)

**Flow:** `BV id / URL → video info + parts → detect subtitles → (found) download & parse → (none) audio → ASR → three files on disk`

[30-Second Demo](#-30-second-demo) · [Features](#features) · [Quick Start](#quick-start) · [CLI Reference](#cli-reference) · [Architecture](#architecture) · [Which repo?](#-python-or-js) · [Star](#-star)

---

## 🎯 30-Second Demo

```text
Before · you want the transcript of a 20-part course playlist
─────────────────────────────────────────────
  browser script   open page → click → copy → next page → repeat 20 times
  hand-rolled      reverse the Bilibili API, signing, per-part cid, subtitle JSON → an afternoon

After · one command
─────────────────────────────────────────────
$ python bili_subtitle_extractor.py BV1xx411c7mD --page all

[1/5] fetching video info...
  title:  ...
  uploader: XXX  |  parts: 20
── part 1: ... (cid=123456) ──
[2/5] detecting subtitles...
  subtitle found (zh-Hans), extracting directly
[5/5] saving subtitles...
  saved to: output/BV1xx411c7mD_p1_...
==================================================
done! 20 parts processed

$ ls output/BV1xx411c7mD_p1_.../
subtitle.srt   subtitle.txt   metadata.json
```

**One-line difference:** browser scripts solve "click once, right here"; this one solves "grab a batch, and put it in cron".

---

## Features

- **Zero-dependency core (stdlib-only)** — the whole pipeline runs on Python 3.10+ standard library, **no `pip install` required**. `yt-dlp` is an optional fallback (`--use-yt-dlp`).
- **Three files per part (SRT + TXT + JSON)** — SRT carries real timestamps for players, TXT is plain text ready for an LLM, JSON holds BV/aid/cid/uploader/source metadata for downstream scripts.
- **Subtitle pick gate (find_best_subtitle)** — AI Chinese > Chinese (auto) > Chinese (manual) > any. It does not just take the first track.
- **Whole-playlist batching (`--page all`)** — one command for the entire collection; an out-of-range part fails loudly ("page N out of range (1-M)") instead of silently downloading the wrong one.
- **Lowest-bitrate audio (bandwidth-min)** — ASR does not need studio quality, so the DASH track with the smallest bandwidth is picked. Faster and lighter.
- **Resumable direct download (Range)** — reuses what is already on disk; if the server ignores Range and answers 200, it restarts cleanly rather than appending a corrupted file.
- **Local cache layer (Cache)** — 24h TTL JSON cache; a corrupt or expired entry is treated as a miss, never served as a result.
- **Proxy and SSL control** — `--proxy` applies to every download and API call (not only yt-dlp); `--no-ssl-verify` exists for hostile networks and is off by default.

---

## Quick Start

```bash
git clone https://github.com/huanweide/bili-subtitle-extractor.git
cd bili-subtitle-extractor
# nothing to install for the core flow; yt-dlp is only for the audio fallback:
pip install yt-dlp          # optional
```

```bash
python bili_subtitle_extractor.py BV1xx411c7mD
# a full URL works too
python bili_subtitle_extractor.py https://www.bilibili.com/video/BV1xx411c7mD
```

Sample output (mirrors the script's real prints):

```text
[1/5] fetching video info...
  title: sample title
  uploader: sample uploader  |  parts: 3
── part 1: part one (cid=111111) ──
[2/5] detecting subtitles...
  subtitle found (zh-Hans), extracting directly
[5/5] saving subtitles...
  saved to: output/BV1xx411c7mD_p1_part one

==================================================
done! 1 part processed
  output/BV1xx411c7mD_p1_part one
```

### ASR key (only needed when there is no subtitle)

```bash
export SILICONFLOW_API_KEY="sk-xxx"        # Linux / macOS
$env:SILICONFLOW_API_KEY="sk-xxx"          # Windows PowerShell
python bili_subtitle_extractor.py BV1xx411c7mD --asr-key sk-xxx   # or pass it directly
```

> ⚠️ The key comes from the environment or the CLI flag only — **never commit it**. With no subtitle and no key, the script fails explicitly instead of silently skipping.

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

| Flag | Meaning | Default |
|---|---|---|
| `bvid` | BV id or a URL containing one (required) | — |
| `-o, --output-dir` | output directory | `./output` |
| `-p, --page` | part number, `all` for every part | `1` |
| `--asr-key` | SiliconFlow API key | env `SILICONFLOW_API_KEY` |
| `--asr-model` | ASR model | `FunAudioLLM/SenseVoiceSmall` |
| `--use-yt-dlp` | download audio via yt-dlp (fallback) | off |
| `--proxy` | HTTP proxy (applies to all requests) | env `BILI_PROXY` |
| `--no-ssl-verify` | skip SSL verification (not recommended) | off |
| `--list` | preview info and available subtitles only | off |
| `--cache-dir` | cache directory | `./output/.cache` |
| `-V, --version` | print version | — |

---

## Architecture

**In one line:** a **five-step straight pipeline** (info → detect → source → transcribe → write) with exactly one branch — whether a subtitle exists. Long videos are not handled by throwing memory at them; they are handled with **lowest-bitrate audio + resumable download**.

### Primitives

| Concept | Meaning |
|---|---|
| BV extraction (extract_bvid) | Regex the BV id out of a raw id or a full URL; fail loudly if absent |
| Part list (pages) | Every part has its own cid; subtitles and audio are addressed by cid |
| Subtitle pick (find_best_subtitle) | AI Chinese > Chinese auto > Chinese manual > any |
| Real timestamps (body_to_srt) | Official subtitles carry true from/to values; no estimation |
| Estimated timestamps (asr_text_to_srt) | ASR returns plain text; sentences are split on CJK punctuation and timestamps are **explicitly estimates** |
| Cache | 24h TTL JSON files; corruption counts as a miss |
| Lowest-bitrate audio | Pick the smallest-bandwidth DASH track that ASR can still use |

### Flow

```text
BV id / URL
   │
   ├─ extract_bvid (missing → exit 1)
   │
   ├─ fetch_video_info ─► title / uploader / parts + cid
   │
   ├─ cache hit? ── yes ─► reuse, skip network
   │
   └─ no ─► per part
          [2/5] fetch_subtitle_list (by cid)
                 ├─ subtitle found ─► find_best_subtitle → download JSON → body_to_srt (real timestamps)
                 └─ none ─► [3/5] audio
                              ├─ --use-yt-dlp → download_audio_ytdlp
                              └─ default → fetch_audio_url (min bandwidth) → download_audio_direct (resumable)
                            [4/5] transcribe_siliconflow (multipart) → asr_text_to_srt (estimated timestamps)
                            temp audio removed
          [5/5] save_output ─► subtitle.srt + subtitle.txt + metadata.json → write cache
```

### Core Modules

| Area | Location | Responsibility |
|---|---|---|
| CLI entry | `bili_subtitle_extractor.py` · `main()` | Flags, BV validation, `--list` preview, errors collapse to exit 1 |
| Pipeline | `bili_subtitle_extractor.py` · `extract_subtitle()` | Five steps and the part loop |
| Bilibili API | `fetch_video_info` / `fetch_subtitle_list` / `fetch_audio_url` | Video info, subtitle tracks, DASH audio |
| Download | `download_audio_direct` / `download_audio_ytdlp` | Resumable direct / yt-dlp fallback |
| ASR | `transcribe_siliconflow` | Multipart upload, returns text |
| Formatting | `body_to_srt` / `asr_text_to_srt` / `fmt_srt_time` | Subtitle body and ASR text → SRT + TXT |
| Cache | `Cache` | 24h JSON cache with corruption tolerance |
| Utils | `extract_bvid` / `safe_filename` / `build_ssl_context` | ID extraction, filename sanitising, SSL context |
| Tests | `tests/test_extractor.py` | 33 assertions, pure functions, no network |

---

## Extension: add your own output format

All three files are written in `save_output()`; adding a format is one more write:

```python
def save_output(output_dir, bvid, title, page_num, srt_content, txt_content, metadata):
    safe = safe_filename(title)
    folder = os.path.join(output_dir, f"{bvid}_p{page_num}_{safe}")
    os.makedirs(folder, exist_ok=True)
    # new: also drop a Markdown copy for note apps
    with open(os.path.join(folder, "subtitle.md"), "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n{txt_content}\n")
    ...
```

Add an assertion to `tests/test_extractor.py` alongside it — every pure-function change is covered.

---

## 🐍 Python or 🎬 JS?

Two subtitle projects by the same author, **non-overlapping**:

| | **this repo** (Python CLI) | [bili-subtitle-universal](https://github.com/huanweide/bili-subtitle-universal) (userscript) |
|---|---|---|
| Shape | one command in a terminal | one click in the browser |
| Coverage | Bilibili focused | **Bilibili + YouTube + any `<video>`** |
| Batch | **`--page all` runs a whole collection** | current page only |
| Dependencies | **Python 3.10+ stdlib** | Tampermonkey + browser |
| Automation | **script / cron / CI friendly** | manual, in-page |
| No subtitle | download audio → SiliconFlow ASR | segmented decode → ASR (with resume) |

> **Want one click in the browser, covering YouTube and arbitrary pages? Use [bili-subtitle-universal](https://github.com/huanweide/bili-subtitle-universal).**
> **Want batch, offline, scriptable? Use this repo.**

---

## Security Boundary

- **No key is bundled.** The ASR key is read from the environment or `--asr-key` only.
- **Only content you can already watch.** No paywall bypass, no paid-content circumvention.
- **Auditable network behaviour.** It calls Bilibili's official endpoints and the ASR endpoint you chose; `--proxy` keeps the egress under your control.
- **It never spends money silently.** ASR runs only when there is no subtitle *and* you supplied a key.
- Use the output for personal study and accessibility, and respect copyright and Bilibili's terms.

---

## Roadmap

- ✅ BV id / URL input, subtitle picking, multi-part `--page all`
- ✅ No subtitle → audio → ASR, resumable direct download, yt-dlp fallback
- ✅ 24h local cache, `--list` preview, proxy and SSL switches
- ✅ 33 zero-dependency unit assertions (`tests/test_extractor.py`)
- ⬜ Multi-language track selection (current picking favours Chinese)
- ⬜ More output formats: VTT / Markdown
- ⬜ Batch BV list input (file / stdin)
- ⬜ Switchable ASR vendors (currently SiliconFlow only)

---

## Contributing

1. Fork → branch → change
2. `python tests/test_extractor.py` must be green (33 assertions, no network)
3. New pure functions come with tests; keep network logic at the CLI layer
4. In your PR, name the real BV id and command you verified with (**never paste a key**)

CI (`ci.yml`) runs on Python 3.12 / 3.13: syntax check + unit tests + CLI smoke; `ruff` is informational only.

---

## License

MIT — see [LICENSE](LICENSE). Bilibili-related names belong to their respective owners.

---

## ⭐ Star

If this tool saved you from scraping subtitles by hand once, **a star is the best thank-you**.

**Author:** ReTri ([@huanweide](https://github.com/huanweide)) · MIT

More tools: [bili-subtitle-universal](https://github.com/huanweide/bili-subtitle-universal) · [live-subtitle](https://github.com/huanweide/live-subtitle) · [zhihuishu-helper](https://github.com/huanweide/zhihuishu-helper) · [all repos](https://github.com/huanweide?tab=repositories)
