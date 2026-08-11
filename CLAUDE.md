# CLAUDE.md — Scrybe 项目工作指引

## 项目简介

Scrybe 是一个 Windows 桌面应用（Python 3.12 + PySide6），批量把 MP4/MP3 等媒体文件转成同名 `.srt` 字幕。识别由云端 API 完成（阿里云百炼 / OpenAI 兼容），本机用 PyAV 内置 FFmpeg 提取音频。发布形态为单文件 exe（PyInstaller，无控制台）。

## 常用命令

| 命令 | 说明 |
| --- | --- |
| `.venv\Scripts\python.exe -m pytest -q` | 跑全部测试（18 项） |
| `.\build.ps1` | 一键打包：装依赖 → 跑测试 → PyInstaller 生成 `dist\Scrybe.exe` |
| `.venv\Scripts\python.exe -m app.main` | 源码运行程序 |
| `.venv\Scripts\python.exe tools\live_dashscope.py <文件> --api-key sk-xxx` | 真实百炼 API 冒烟 |
| `.venv\Scripts\python.exe tools\live_openai.py <文件> --base-url ... --api-key ...` | 真实 OpenAI 兼容 API 冒烟 |

## 目录结构与标准文件路径

| 路径 | 说明 |
| --- | --- |
| [app/main.py](app/main.py) | 程序入口 |
| [app/config.py](app/config.py) | 配置定义与读写（`%APPDATA%\Scrybe\config.json`，原子写入） |
| [app/models.py](app/models.py) | 数据模型：`FileJob` / `FileStatus` / `Segment` / `ProviderResult` |
| [app/core/](app/core/) | 核心处理管线 |
| [app/core/pipeline.py](app/core/pipeline.py) | 管线编排：`extract()`（并行+缓存）→ `recognize()`（串行）→ 写 SRT |
| [app/core/audio_util.py](app/core/audio_util.py) | PyAV 转码为 16kHz 单声道 PCM WAV |
| [app/core/audio_chunker.py](app/core/audio_chunker.py) | 按时长切 WAV，帧级精确偏移 |
| [app/core/srt_builder.py](app/core/srt_builder.py) | `Segment` → SRT 文本（合并阈值、排序去空） |
| [app/core/wav_util.py](app/core/wav_util.py) | 纯头解析读 WAV 时长（不依赖 ffprobe） |
| [app/providers/](app/providers/) | 识别服务抽象层 |
| [app/providers/base.py](app/providers/base.py) | `ASRProvider` 抽象基类 + `ProviderCapability` + `create_provider` 工厂 |
| [app/providers/dashscope.py](app/providers/dashscope.py) | 阿里云百炼（WebSocket 流式，paraformer-realtime-v2） |
| [app/providers/openai_compat.py](app/providers/openai_compat.py) | OpenAI 兼容接口（verbose_json，429/5xx 自动重试） |
| [app/ui/](app/ui/) | Qt 界面层 |
| [app/ui/main_window.py](app/ui/main_window.py) | 主窗口、队列控制、拖拽、重试失败 |
| [app/ui/worker.py](app/ui/worker.py) | 队列工作线程（两阶段编排，Signal 通知 UI） |
| [app/ui/file_list_model.py](app/ui/file_list_model.py) | 文件列表 `QAbstractTableModel` |
| [app/ui/settings_dialog.py](app/ui/settings_dialog.py) | 设置对话框（服务商/语言/切块/并行提取数） |
| [tests/](tests/) | pytest 离线测试（FakeProvider + monkeypatch，不打真实 API） |
| [tools/](tools/) | 开发工具脚本（真实 API 冒烟） |
| [docs/](docs/) | 项目文档：开发需求 / 技术方案 / 设计规范 / 执行步骤 |
| [devlog/](devlog/) | 开发日志：`devlog/YYYY-MM-DD.md` |
| [build.ps1](build.ps1) / [build.spec](build.spec) | PyInstaller 打包配置（单文件、无控制台） |

## 工作说明

1. **改动前先跑测试**，确认基线通过；改动后跑测试并保证新增逻辑有配套测试。
2. **新增识别服务**必须继承 `ASRProvider`，实现 `capability()` 与 `transcribe_wav()`；并在 `create_provider` 工厂注册。
3. **线程模型**：所有耗时操作在 worker 线程，UI 通过 Signal 更新。worker 是两阶段——先并行提取音频（并发数 = 配置 `parallel_extractions`），再**串行**识别（按队列顺序，一个返回才识别下一个）。
4. **音频缓存**：`pipeline.extract()` 把 WAV 缓存到系统临时目录 `Scrybe_cache`（按源文件 hash 命名），识别失败重试直接复用、不重新提取；关闭窗口时清理。改动影响缓存的逻辑时注意其幂等性。
5. **错误处理**：core 层抛 `PipelineError`；provider 抛带中文说明的 `RuntimeError`；worker 捕获后标 `FAILED` 并写日志，继续下一个文件。
6. **测试规范**：离线优先——用 `FakeProvider` + monkeypatch 转码，不打真实 API；真实链路用 `tools/` 下的脚本手动验证。
7. **改完代码**后按顺序：跑测试 → 更新 [docs/](docs/) 相关文档 → 更新今日开发日志（见下）。

## 开发日志维护（每天自动记录）

- 位置：`devlog/YYYY-MM-DD.md`（模板见 [devlog/README.md](devlog/README.md)）。
- 每次开发任务完成后，把**今日完成**（内容、涉及文件、验证方式）和**待办事项**写入当日日志；当天无日志文件则先创建。
- 同一天多次开发**追加**到已有文件，不覆盖。
