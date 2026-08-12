#!/usr/bin/env python3
"""
B站字幕提取工具 — 输入 BV 号，自动下载字幕。
有字幕直接提取，无字幕用 ASR 语音转文字生成。
输出 SRT + TXT 双格式。

纯标准库实现，零强制依赖。可选 yt-dlp 用于音频下载增强。
"""

import argparse
import hashlib
import json
import os
import re
import ssl
import subprocess
import sys
import time
import urllib.request
import uuid

__version__ = "1.0.0"

# ═══════════════════════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════════════════════

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

BILI_API_VIDEO_INFO = "https://api.bilibili.com/x/web-interface/view"
BILI_API_PLAYER = "https://api.bilibili.com/x/player/v2"
BILI_API_PLAYURL = "https://api.bilibili.com/x/player/playurl"

# 硅基流动 ASR（默认）
SILICONFLOW_ASR_URL = "https://api.siliconflow.cn/v1/audio/transcriptions"
SILICONFLOW_ASR_MODEL = "FunAudioLLM/SenseVoiceSmall"

# BV 号正则
BV_RE = re.compile(r"^BV[a-zA-Z0-9]{10}$")

# 文件名非法字符
ILLEGAL_CHARS = re.compile(r'[\\/:*?"<>|]')

# 缓存有效期（秒）
CACHE_TTL = 86400  # 24 小时

# yt-dlp 检测缓存
_YTDLP_AVAILABLE = None


# ═══════════════════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════════════════


def build_ssl_context(verify: bool = True) -> ssl.SSLContext:
    """创建 SSL 上下文，默认验证证书。"""
    ctx = ssl.create_default_context()
    if not verify:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def http_get(url: str, headers: dict | None = None, timeout: int = 30,
             ssl_verify: bool = True) -> bytes:
    """HTTP GET，返回响应体字节。"""
    if headers is None:
        headers = {
            "User-Agent": UA,
            "Referer": "https://www.bilibili.com",
            "Origin": "https://www.bilibili.com",
        }
    req = urllib.request.Request(url, headers=headers)
    ctx = build_ssl_context(ssl_verify)
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return resp.read()


def http_post_json(url: str, data: bytes, headers: dict | None = None,
                   timeout: int = 120) -> dict:
    """HTTP POST JSON，返回解析后的 dict。"""
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def safe_filename(s: str, max_len: int = 50) -> str:
    """去除文件名非法字符并截断。"""
    return ILLEGAL_CHARS.sub("_", s)[:max_len]


def fmt_srt_time(seconds: float) -> str:
    """秒数 → SRT 时间格式 HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def check_ytdlp() -> bool:
    """检测 yt-dlp 是否可用（结果缓存）。"""
    global _YTDLP_AVAILABLE
    if _YTDLP_AVAILABLE is not None:
        return _YTDLP_AVAILABLE
    try:
        r = subprocess.run(["yt-dlp", "--version"], capture_output=True, timeout=10)
        _YTDLP_AVAILABLE = r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        _YTDLP_AVAILABLE = False
    return _YTDLP_AVAILABLE


def extract_bvid(url_or_id: str) -> str:
    """从 URL 或纯文本中提取 BV 号。"""
    m = re.search(r"BV[a-zA-Z0-9]{10}", url_or_id)
    if m:
        return m.group(0)
    raise ValueError(f"无法从输入中提取 BV 号: {url_or_id}")


# ═══════════════════════════════════════════════════════════════════════════════
# 缓存层
# ═══════════════════════════════════════════════════════════════════════════════


class Cache:
    """简单的 JSON 文件缓存。"""

    def __init__(self, cache_dir: str):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def _key(self, bvid: str, cid: int) -> str:
        return f"{bvid}_{cid}"

    def _path(self, key: str) -> str:
        return os.path.join(self.cache_dir, f"{key}.json")

    def get(self, bvid: str, cid: int) -> dict | None:
        path = self._path(self._key(bvid, cid))
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if time.time() - data.get("_cached_at", 0) > CACHE_TTL:
                return None
            return data
        except (json.JSONDecodeError, OSError):
            return None

    def set(self, bvid: str, cid: int, data: dict):
        data["_cached_at"] = time.time()
        with open(self._path(self._key(bvid, cid)), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════════════════════════
# B站 API
# ═══════════════════════════════════════════════════════════════════════════════


def fetch_video_info(bvid: str, ssl_verify: bool = True) -> dict:
    """获取视频元信息（含分P列表）。"""
    url = f"{BILI_API_VIDEO_INFO}?bvid={bvid}"
    resp = json.loads(http_get(url, ssl_verify=ssl_verify))
    if resp.get("code") != 0:
        raise RuntimeError(f"B站 API 返回错误: code={resp.get('code')} msg={resp.get('message')}")
    data = resp["data"]
    pages = data.get("pages", [{"cid": data["cid"], "part": data["title"], "duration": data["duration"]}])
    return {
        "bvid": bvid,
        "aid": data["aid"],
        "title": data["title"],
        "author": data["owner"]["name"],
        "duration": data["duration"],  # 总时长（第一P）
        "pages": [
            {
                "page": p.get("page", i + 1),
                "cid": p["cid"],
                "part": p.get("part", ""),
                "duration": p.get("duration", 0),
            }
            for i, p in enumerate(pages)
        ],
    }


def fetch_subtitle_list(bvid: str, cid: int, ssl_verify: bool = True) -> list[dict]:
    """获取字幕列表。"""
    url = f"{BILI_API_PLAYER}?bvid={bvid}&cid={cid}"
    resp = json.loads(http_get(url, ssl_verify=ssl_verify))
    data = resp.get("data", {})
    return data.get("subtitle", {}).get("subtitles", [])


def download_subtitle_json(subtitle_url: str, ssl_verify: bool = True) -> tuple[str, list[dict]]:
    """下载字幕 JSON，返回 (纯文本, 原始body列表)。"""
    if subtitle_url.startswith("//"):
        subtitle_url = "https:" + subtitle_url
    body = json.loads(http_get(subtitle_url, ssl_verify=ssl_verify)).get("body", [])
    lines = [item.get("content", "") for item in body if item.get("content")]
    return "\n".join(lines), body


def find_best_subtitle(subtitles: list[dict]) -> dict | None:
    """从字幕列表中找到最佳中文字幕。"""
    # 优先级：AI中文 > 中文（自动生成）> 中文（手动）> 任意字幕
    for s in subtitles:
        if s.get("lan") == "ai-zh":
            return s
    for s in subtitles:
        doc = s.get("lan_doc", "")
        if "中文" in doc:
            return s
    return subtitles[0] if subtitles else None


# ═══════════════════════════════════════════════════════════════════════════════
# 音频下载
# ═══════════════════════════════════════════════════════════════════════════════


def fetch_audio_url(bvid: str, cid: int, ssl_verify: bool = True) -> dict | None:
    """从 DASH API 获取最高音质音频流 URL。"""
    url = f"{BILI_API_PLAYURL}?bvid={bvid}&cid={cid}&fnval=4048&fnver=0&fourk=1"
    resp = json.loads(http_get(url, ssl_verify=ssl_verify))
    data = resp.get("data", {})
    dash = data.get("dash", {})
    audios = dash.get("audio", [])
    if not audios:
        return None
    best = max(audios, key=lambda a: a.get("bandwidth", 0))
    return {
        "url": best["baseUrl"],
        "bandwidth": best.get("bandwidth", 0),
        "codecs": best.get("codecs", ""),
        "mime_type": best.get("mimeType", "audio/mp4"),
    }


def download_audio_direct(audio_url: str, output_path: str, ssl_verify: bool = True):
    """直接通过 HTTP 下载音频，支持断点续传。"""
    existing = os.path.getsize(output_path) if os.path.exists(output_path) else 0
    headers = {
        "User-Agent": UA,
        "Referer": "https://www.bilibili.com",
        "Origin": "https://www.bilibili.com",
    }
    if existing > 0:
        headers["Range"] = f"bytes={existing}-"
    req = urllib.request.Request(audio_url, headers=headers)
    ctx = build_ssl_context(ssl_verify)
    with urllib.request.urlopen(req, timeout=600, context=ctx) as resp:
        # 若服务端不支持 Range（返回 200），从头覆盖原文件
        if existing > 0 and resp.status == 200:
            existing = 0
        mode = "ab" if existing > 0 else "wb"
        remaining = int(resp.headers.get("Content-Length", 0) or 0)
        total = existing + remaining if remaining else 0
        downloaded = existing
        with open(output_path, mode) as f:
            while True:
                chunk = resp.read(8192 * 1024)  # 8MB 块
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded * 100 // total
                    print(f"\r  下载进度: {pct}% ({downloaded / 1024 / 1024:.1f}MB)", end="", flush=True)
        if total:
            print()  # 换行


def download_audio_ytdlp(bvid: str, output_path: str, proxy: str | None = None):
    """用 yt-dlp 下载音频（兜底方案）。"""
    base = output_path.rsplit(".", 1)[0]
    cmd = [
        "yt-dlp",
        "-f", "bestaudio",
        "-o", base + ".%(ext)s",
        "--no-playlist",
        "--socket-timeout", "30",
        f"https://www.bilibili.com/video/{bvid}",
    ]
    if proxy:
        cmd.insert(1, "--proxy")
        cmd.insert(2, proxy)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"yt-dlp 下载失败: {r.stderr[:300]}")
    # yt-dlp 会自动加扩展名，找到它
    for ext in [".m4a", ".mp3", ".aac", ".opus", ".webm", ".m4s"]:
        actual = base + ext
        if os.path.exists(actual):
            if actual != output_path:
                os.rename(actual, output_path)
            return
    raise FileNotFoundError(f"找不到 yt-dlp 下载的音频文件: {base}.*")


# ═══════════════════════════════════════════════════════════════════════════════
# ASR 语音识别
# ═══════════════════════════════════════════════════════════════════════════════


def transcribe_siliconflow(audio_path: str, api_key: str,
                           model: str = SILICONFLOW_ASR_MODEL) -> tuple[str, dict]:
    """用硅基流动 SenseVoiceSmall 转写音频（multipart 上传）。"""
    with open(audio_path, "rb") as f:
        file_data = f.read()

    ext = os.path.splitext(audio_path)[1].lower().lstrip(".")
    mime_map = {
        "m4a": "audio/mp4",
        "m4s": "audio/mp4",
        "mp4": "audio/mp4",
        "opus": "audio/ogg",
        "ogg": "audio/ogg",
        "webm": "audio/webm",
        "mp3": "audio/mpeg",
        "aac": "audio/aac",
        "mka": "audio/x-matroska",
    }
    content_type = mime_map.get(ext, "audio/mp4")
    file_name = f"audio.{ext}" if ext else "audio.m4a"

    boundary = "----" + uuid.uuid4().hex
    parts = [
        f"--{boundary}",
        f'Content-Disposition: form-data; name="model"',
        "",
        model,
        f"--{boundary}",
        f'Content-Disposition: form-data; name="file"; filename="{file_name}"',
        f"Content-Type: {content_type}",
        "",
    ]
    body = ("\r\n".join(parts) + "\r\n").encode()
    body += file_data
    body += f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        SILICONFLOW_ASR_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        result = json.loads(resp.read())
    return result.get("text", ""), result


# ═══════════════════════════════════════════════════════════════════════════════
# 字幕格式化
# ═══════════════════════════════════════════════════════════════════════════════


def body_to_srt(body: list[dict]) -> tuple[str, str]:
    """字幕 JSON body → SRT + 纯文本。使用原始时间戳。"""
    srt_lines = []
    txt_lines = []
    for idx, item in enumerate(body, 1):
        content = item.get("content", "")
        if not content:
            continue
        from_time = item.get("from", 0)
        to_time = item.get("to", from_time + 5)
        srt_lines.append(str(idx))
        srt_lines.append(f"{fmt_srt_time(from_time)} --> {fmt_srt_time(to_time)}")
        srt_lines.append(content)
        srt_lines.append("")
        txt_lines.append(content)
    return "\n".join(srt_lines), "\n".join(txt_lines)


def asr_text_to_srt(text: str) -> tuple[str, str]:
    """ASR 纯文本 → SRT（无时间戳，按句分条，时间戳标注为估算）。"""
    # 按中文标点分句
    sentences = re.split(r"(?<=[。！？，、；：\n])", text.strip())
    # 合并过短的句子
    merged = []
    buf = ""
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        buf += s
        if len(buf) >= 15 or s.endswith(("\n", "。", "！", "？")):
            merged.append(buf)
            buf = ""
    if buf:
        merged.append(buf)

    srt_lines = []
    txt_lines = []
    for idx, line in enumerate(merged):
        if not line:
            continue
        # ASR 无真实时间戳，用估算值
        start = idx * 5
        end = start + max(3, len(line) // 4)  # 粗略按语速估算
        srt_lines.append(str(idx + 1))
        srt_lines.append(f"{fmt_srt_time(start)} --> {fmt_srt_time(end)}")
        srt_lines.append(line)
        srt_lines.append("")
        txt_lines.append(line)
    return "\n".join(srt_lines), "\n".join(txt_lines)


# ═══════════════════════════════════════════════════════════════════════════════
# 输出
# ═══════════════════════════════════════════════════════════════════════════════


def save_output(output_dir: str, bvid: str, title: str, page_num: int,
                srt_content: str, txt_content: str, metadata: dict):
    """保存字幕文件到输出目录。"""
    safe = safe_filename(title)
    folder = os.path.join(output_dir, f"{bvid}_p{page_num}_{safe}")
    os.makedirs(folder, exist_ok=True)

    with open(os.path.join(folder, "subtitle.srt"), "w", encoding="utf-8") as f:
        f.write(srt_content)
    with open(os.path.join(folder, "subtitle.txt"), "w", encoding="utf-8") as f:
        f.write(txt_content)
    with open(os.path.join(folder, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    return folder


# ═══════════════════════════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════════════════════════


def extract_subtitle(
    bvid: str,
    output_dir: str = "./output",
    page: int | str = 1,
    asr_key: str = "",
    asr_model: str = SILICONFLOW_ASR_MODEL,
    proxy: str | None = None,
    use_ytdlp: bool = False,
    ssl_verify: bool = True,
    cache: Cache | None = None,
) -> str:
    """
    从 B站视频提取字幕。

    返回输出目录路径。

    参数:
        bvid: BV 号
        output_dir: 输出根目录
        page: 分P页码（1-based），或 "all" 提取所有分P
        asr_key: 硅基流动 API Key（无字幕时 ASR 需要）
        asr_model: ASR 模型名
        proxy: HTTP 代理地址（yt-dlp 模式使用）
        use_ytdlp: 强制使用 yt-dlp 下载音频
        ssl_verify: 是否验证 SSL 证书
        cache: 缓存实例
    """
    # ── 1. 获取视频信息 ──
    print(f"[1/5] 获取视频信息...")
    info = fetch_video_info(bvid, ssl_verify=ssl_verify)
    print(f"  标题: {info['title'][:60]}")
    print(f"  UP主: {info['author']}  |  分P数: {len(info['pages'])}")

    # 确定要处理的页码
    if page == "all":
        pages = info["pages"]
    else:
        page_num = int(page)
        if page_num < 1 or page_num > len(info["pages"]):
            raise ValueError(f"页码 {page_num} 超出范围 (1-{len(info['pages'])})")
        pages = [info["pages"][page_num - 1]]

    results = []
    for p in pages:
        cid = p["cid"]
        page_num = p["page"]
        part_title = p["part"] or info["title"]
        print(f"\n── 第 {page_num}P: {part_title[:40]} (cid={cid}) ──")

        # ── 检查缓存 ──
        if cache:
            cached = cache.get(bvid, cid)
            if cached:
                print(f"  [缓存命中] 直接使用")
                results.append((cached, p))
                continue

        # ── 2. 检测字幕 ──
        print(f"[2/5] 检测字幕...")
        subs = fetch_subtitle_list(bvid, cid, ssl_verify=ssl_verify)
        target = find_best_subtitle(subs)

        if target and target.get("subtitle_url"):
            # 有字幕 → 直接提取
            lang = target.get("lan_doc", target.get("lan", "未知"))
            print(f"  发现字幕 ({lang})，直接提取")
            sub_url = target["subtitle_url"]
            txt, body = download_subtitle_json(sub_url, ssl_verify=ssl_verify)
            srt, _ = body_to_srt(body)
            source = "bilibili_subtitle"
        else:
            # 无字幕 → 下载音频 → ASR
            print(f"  无可用字幕，下载音频...")
            audio_path = os.path.join(output_dir, ".temp", f"{bvid}_p{page_num}.m4a")
            os.makedirs(os.path.dirname(audio_path), exist_ok=True)

            # ── 3. 下载音频 ──
            print(f"[3/5] 下载音频（{'yt-dlp' if use_ytdlp else '直链'}）...")
            if use_ytdlp:
                download_audio_ytdlp(bvid, audio_path, proxy)
            else:
                audio_info = fetch_audio_url(bvid, cid, ssl_verify=ssl_verify)
                if not audio_info:
                    raise RuntimeError("无法获取 DASH 音频流，请尝试 --use-yt-dlp")
                download_audio_direct(audio_info["url"], audio_path, ssl_verify=ssl_verify)
            size_mb = os.path.getsize(audio_path) / 1024 / 1024
            print(f"  完成: {size_mb:.1f}MB")

            # ── 4. ASR 识别 ──
            print(f"[4/5] ASR 语音转文字 ({asr_model})...")
            if not asr_key:
                raise RuntimeError(
                    "无字幕，需要 ASR 转写。请设置环境变量 SILICONFLOW_API_KEY "
                    "或传参 --asr-key"
                )
            txt, raw_result = transcribe_siliconflow(audio_path, asr_key, asr_model)
            srt, _ = asr_text_to_srt(txt)
            print(f"  识别文本: {txt[:100]}...")
            source = "asr_siliconflow"

            # 清理临时音频
            try:
                os.remove(audio_path)
            except OSError:
                pass

        # ── 5. 保存 ──
        print(f"[5/5] 保存字幕...")
        metadata = {
            "bvid": bvid,
            "aid": info["aid"],
            "title": info["title"],
            "author": info["author"],
            "page": page_num,
            "part": part_title,
            "cid": cid,
            "duration": p.get("duration", 0),
            "source": source,
            "extractor_version": __version__,
        }
        out = save_output(output_dir, bvid, part_title, page_num, srt, txt, metadata)
        if cache:
            cache.set(bvid, cid, {**metadata, "output_dir": out})
        results.append((metadata, p))
        print(f"  ✓ 保存到: {out}")

    print(f"\n{'='*50}")
    print(f"完成! 共处理 {len(results)} 个分P")
    for meta, _ in results:
        print(f"  {meta['output_dir']}")
    return output_dir


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(
        prog="bili-subtitle-extractor",
        description=f"B站字幕提取工具 v{__version__} — 输入 BV 号，自动下载字幕",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s BV1xxXXxxXx
  %(prog)s BV1xxXXxxXx --page 2
  %(prog)s BV1xxXXxxXx --page all
  %(prog)s BV1xxXXxxXx --output-dir ./我的字幕
  %(prog)s BV1xxXXxxXx --use-yt-dlp --proxy http://127.0.0.1:7890

环境变量:
  SILICONFLOW_API_KEY    硅基流动 API 密钥（ASR 需要）
  BILI_PROXY             HTTP 代理地址（yt-dlp 模式）
        """,
    )
    parser.add_argument("bvid", help="B站视频 BV 号或包含 BV 号的 URL")
    parser.add_argument("-o", "--output-dir", default="./output",
                        help="输出目录 (默认: ./output)")
    parser.add_argument("-p", "--page", default="1",
                        help="分P页码 (默认: 1, 可用 'all' 提取全部分P)")
    parser.add_argument("--asr-key", default=os.environ.get("SILICONFLOW_API_KEY", ""),
                        help="硅基流动 API 密钥 (默认取环境变量 SILICONFLOW_API_KEY)")
    parser.add_argument("--asr-model", default=SILICONFLOW_ASR_MODEL,
                        help=f"ASR 模型 (默认: {SILICONFLOW_ASR_MODEL})")
    parser.add_argument("--use-yt-dlp", action="store_true",
                        help="强制用 yt-dlp 下载音频（需单独安装 yt-dlp）")
    parser.add_argument("--proxy", default=os.environ.get("BILI_PROXY", ""),
                        help="HTTP 代理地址 (默认取环境变量 BILI_PROXY)")
    parser.add_argument("--no-ssl-verify", action="store_true",
                        help="跳过 SSL 证书验证（不推荐）")
    parser.add_argument("--list", action="store_true",
                        help="仅列出视频信息和可用字幕，不提取")
    parser.add_argument("-V", "--version", action="version",
                        version=f"%(prog)s {__version__}")
    parser.add_argument("--cache-dir", default="./output/.cache",
                        help="缓存目录 (默认: ./output/.cache)")

    args = parser.parse_args()

    # 提取 BV 号
    try:
        bvid = extract_bvid(args.bvid)
    except ValueError as e:
        print(f"错误: {e}")
        sys.exit(1)

    ssl_verify = not args.no_ssl_verify
    proxy = args.proxy or None
    cache = Cache(args.cache_dir)

    try:
        # --list 模式
        if args.list:
            info = fetch_video_info(bvid, ssl_verify=ssl_verify)
            print(f"标题: {info['title']}")
            print(f"UP主: {info['author']}")
            print(f"分P数: {len(info['pages'])}")
            for p in info["pages"]:
                print(f"  P{p['page']}: {p['part'][:50]} (cid={p['cid']}, {p['duration']}s)")
                subs = fetch_subtitle_list(bvid, p["cid"], ssl_verify=ssl_verify)
                if subs:
                    for s in subs:
                        print(f"    字幕: {s.get('lan_doc', s.get('lan', '?'))}")
                else:
                    print(f"    字幕: 无 → 需要 ASR")
            return

        # 提取字幕
        extract_subtitle(
            bvid=bvid,
            output_dir=args.output_dir,
            page=args.page if args.page == "all" else int(args.page),
            asr_key=args.asr_key,
            asr_model=args.asr_model,
            proxy=proxy,
            use_ytdlp=args.use_yt_dlp,
            ssl_verify=ssl_verify,
            cache=cache,
        )
    except Exception as e:
        print(f"\n✗ 失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
