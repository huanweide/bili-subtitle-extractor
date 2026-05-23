# B站字幕提取工具

输入 B站 BV 号，自动下载字幕。有字幕直接提取，无字幕用 AI 语音转文字生成。

**输出 SRT + TXT 双格式**，纯 Python 标准库，零强制依赖。

## 功能

- 自动检测 B站 AI 字幕 / 上传字幕，有就直接下载
- 无字幕时自动下载音频 → 硅基流动 ASR 语音转文字
- 支持多分P视频（`--page all` 一键提取）
- 输出 SRT（带时间戳）+ TXT（纯文本）+ JSON 元信息
- 视频信息本地缓存，避免重复请求
- `--list` 预览模式

## 安装

```bash
# 克隆仓库
git clone https://github.com/huanweide/bili-subtitle-extractor.git
cd bili-subtitle-extractor

# 可选：安装 yt-dlp（音频下载增强）
pip install yt-dlp
```

核心功能仅依赖 Python 3.10+ 标准库，无需安装任何包即可使用。

## 使用

```bash
# 基本用法
python bili_subtitle_extractor.py BV1xxXXxxXx

# 指定输出目录
python bili_subtitle_extractor.py BV1xxXXxxXx -o ./my_subtitles

# 提取指定分P
python bili_subtitle_extractor.py BV1xxXXxxXx -p 2

# 提取所有分P
python bili_subtitle_extractor.py BV1xxXXxxXx -p all

# 预览视频信息（不提取）
python bili_subtitle_extractor.py BV1xxXXxxXx --list

# 用 yt-dlp 下载音频（更稳定）
python bili_subtitle_extractor.py BV1xxXXxxXx --use-yt-dlp

# 挂代理
python bili_subtitle_extractor.py BV1xxXXxxXx --use-yt-dlp --proxy http://127.0.0.1:7890

# 也可以用包含 BV 号的 URL
python bili_subtitle_extractor.py https://www.bilibili.com/video/BV1xxXXxxXx
```

## ASR 配置（无字幕时需要）

1. 注册 [硅基流动](https://siliconflow.cn) 获取 API Key
2. 设置环境变量：

```bash
# Linux / macOS
export SILICONFLOW_API_KEY="sk-xxx"

# Windows PowerShell
$env:SILICONFLOW_API_KEY="sk-xxx"
```

或通过命令行参数传入：

```bash
python bili_subtitle_extractor.py BV1xxXXxxXx --asr-key sk-xxx
```

## 输出结构

```
output/
└── BV1xxXXxxXx_p1_视频标题/
    ├── subtitle.srt      # 标准字幕（带时间戳）
    ├── subtitle.txt      # 纯文本
    └── metadata.json     # 视频元信息
```

## 选项

| 参数 | 说明 | 默认 |
|------|------|------|
| `bvid` | BV 号或包含 BV 号的 URL | 必填 |
| `-o, --output-dir` | 输出目录 | `./output` |
| `-p, --page` | 分P页码，`all` 为全部 | `1` |
| `--asr-key` | 硅基流动 API Key | 环境变量 |
| `--asr-model` | ASR 模型 | `FunAudioLLM/SenseVoiceSmall` |
| `--use-yt-dlp` | 用 yt-dlp 下载音频 | 关闭 |
| `--proxy` | HTTP 代理 | 环境变量 `BILI_PROXY` |
| `--no-ssl-verify` | 跳过 SSL 验证（不推荐） | 关闭 |
| `--list` | 仅预览，不提取 | 关闭 |
| `--cache-dir` | 缓存目录 | `./output/.cache` |

## 工作原理

```
输入BV号
  ├→ B站 API 获取视频信息（标题、UP主、分P列表）
  ├→ B站 API 检测字幕
  │   ├─ 有字幕 → 下载 JSON → 解析时间戳 → SRT + TXT
  │   └─ 无字幕 → DASH API 下载音频 → SiliconFlow ASR → SRT + TXT
  └→ 保存到 output/{BV号}_{标题}/
```

## License

MIT
