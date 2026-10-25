<!-- badges -->
[![License](https://img.shields.io/github/license/huanweide/bili-subtitle-extractor)](LICENSE)
[![CI](https://github.com/huanweide/bili-subtitle-extractor/actions/workflows/ci.yml/badge.svg)](https://github.com/huanweide/bili-subtitle-extractor/actions/workflows/ci.yml)
[![Stars](https://img.shields.io/github/stars/huanweide/bili-subtitle-extractor)](https://github.com/huanweide/bili-subtitle-extractor/stargazers)
<!-- /badges -->

# B站字幕提取工具

> 姊妹项目：本工具是「命令行批量下载 / AI 语音转文字」形态。如果你想要**在浏览器里点一下就提取字幕**（零配置、无需 Key），请用 [bili-subtitle](https://github.com/huanweide/bili-subtitle)（篡改猴插件版）。

输入 B站 BV 号，自动下载字幕。有字幕直接提取，无字幕用 AI 语音转文字生成。

**输出 SRT + TXT 双格式**，纯 Python 标准库，零强制依赖。

> **📦 便携性速览**
>
> - **纯 Python 标准库，零强制依赖**：核心功能 Python 3.10+ 即跑，无需 `pip install`。
> - 可选 `yt-dlp` 增强音频下载；无字幕时 AI 转写需自备硅基流动 Key。
> - 输入 BV 号，输出 SRT + TXT + JSON 三件套。


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

## 🧰 同一作者的其他工具

> 作者在做一系列开源效率工具，欢迎顺手点 Star 支持：

- 📚 长篇创作 — AI 小说工坊，本地规则引擎零依赖：[点此访问](https://github.com/huanweide/novel-smith)
- 🎓 网课助手 — 智慧树自动播放/续播/AI 答题：[点此访问](https://github.com/huanweide/zhihuishu-helper)
- 🎬 字幕/视频 — B站字幕一键提取（零 Key 取官方字幕）：[点此访问](https://github.com/huanweide/bili-subtitle-universal)
- 📺 实时字幕 — 直播/会议实时字幕：[点此访问](https://github.com/huanweide/live-subtitle)
- ✂️ 视频摘要 — 长视频一键总结：[点此访问](https://github.com/huanweide/video-brief)
- 🖥️ 总览 — 作者全部开源项目集散：[点此访问](https://github.com/huanweide/family-showcase)
- 🩺 代码健康 — 零依赖多轴静态体检：[点此访问](https://github.com/huanweide/doctors)
## License

MIT

---

## 作者

由 **ReTr · 樊斯瑞** 维护 · [GitHub 主页](https://github.com/huanweide)

## CI 门禁用法

开箱即可接入 CI：在流水线中运行本工具，它会输出健康分与严重度；若存在不达标项会以非 0 退出码结束，从而拦下问题提交（具体参数见上方「快速开始」）。

## 赞助支持

如果这个项目帮到了你，欢迎 [点 Star](https://github.com/huanweide/bili-subtitle-extractor) 支持；也可微信扫码自愿赞助（收款码见 `sponsor/wechat-qr.png`，作者本人带 Tri 水印的码，纯静态图片、不含任何密钥）。

## 许可证

详见 [LICENSE](LICENSE)。
---

## 🧰 更多开源工具（by ReTri · 樊斯瑞）

- 🎬 字幕 / 视频：[bili-subtitle-universal](https://github.com/huanweide/bili-subtitle-universal) · [live-subtitle](https://github.com/huanweide/live-subtitle) · [zhihuishu-helper](https://github.com/huanweide/zhihuishu-helper) · [video-brief](https://github.com/huanweide/video-brief)
- 🩺 代码健康全家桶（18 轴零依赖 CLI）：[family-showcase](https://github.com/huanweide/family-showcase)
- 🔧 命令行利器：[idiot-index](https://github.com/huanweide/idiot-index) · [recall-cli](https://github.com/huanweide/recall-cli) · [forge-safeguard](https://github.com/huanweide/forge-safeguard-20260812)
- 🖥️ 桌面 / 资讯：[floatsnip](https://github.com/huanweide/floatsnip) · [tech-news-hub](https://github.com/huanweide/tech-news-hub)
- 📦 全部仓库：<https://github.com/huanweide?tab=repositories>
