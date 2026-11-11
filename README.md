# 抖音无水印原流下载器 (Douyin Video Downloader)

一款专为 Windows 设计的现代化、纯净无水印抖音视频下载桌面客户端。基于 **PySide6 + Fluent UI**（Windows 11 视觉风格）与 **混合自愈嗅探引擎** 开发。

---

## ✨ 核心特性

- 🎯 **官方原流品质**：100% 直出抖音 CDN 原始推流 **H.265 (HEVC) / AAC**，纯损无重编码极速合成。
- 🚫 **彻底纯净无水印**：彻底去除所有画面浮动 ID 标识与片尾水印。
- 🛡️ **自愈防封嗅探**：深度集成系统 Microsoft Edge 内核引擎，无感处理反爬、动态签名（`a_bogus` 等）与风控，永不怕接口失效。
- 📋 **剪贴板智能感知**：在任何地方复制抖音分享口令或网址，回到软件即可自动感知、提示并一键填入。
- ⚡ **批量队列多任务**：支持单行或多行链接批量添加，后台线程池异步下载，界面流畅不卡死。
- 📂 **历史与便捷管理**：内置历史记录卡片，支持一键定位文件、调用本地默认播放器秒开播放。
- 🎨 **Win11 Fluent 质感**：圆角卡片、亚克力微光泽感、自适应亮暗色主题。

---

## 🚀 快速启动

### 方式一：双击启动（最便捷）
直接在项目根目录下双击运行：
👉 **`启动下载器.bat`**

### 方式二：命令行启动
```bash
python run.py
```

---

## 🛠️ 项目架构

```text
g:\My Projects\抖音视频下载器/
├── app/
│   ├── config.py                 # 全局配置与历史记录持久化 (config.json)
│   ├── ui/
│   │   ├── main_window.py        # 主窗口与 Fluent 导航布局
│   │   ├── download_view.py      # 下载主页面（链接输入、任务队列卡片）
│   │   ├── history_view.py       # 下载历史列表（一键播放/定位）
│   │   └── settings_view.py      # 设置（存储目录、剪贴板开关、环境检测）
│   ├── core/
│   │   ├── clipboard_watcher.py  # 剪贴板轮询监听器
│   │   ├── task_manager.py       # 异步多线程任务调度
│   │   └── downloader.py         # 流媒体分段下载与 FFmpeg 无损合成
│   ├── engine/
│   │   └── parser.py             # 混合自愈解析器（Edge 内核无头嗅探）
│   └── utils/
│       ├── ffmpeg_helper.py      # FFmpeg 路径探测与无损混流工具
│       └── file_helper.py        # 跨平台文件名过滤与大小格式化
├── downloads/                    # 默认下载文件存储目录
├── run.py                        # Python 启动主入口
├── 启动下载器.bat                 # Windows 一键启动脚本
└── requirements.txt              # 依赖清单
```

---

## 📦 打包为独立 EXE（可选）

如需将软件打包为便携版或单文件 `.exe` 分发给他人使用：
```bash
pip install pyinstaller
pyinstaller -w -F --name "抖音无水印原流下载器" run.py
```
*(注意：他人电脑若无全局 FFmpeg，将 `ffmpeg.exe` 放置于生成的 `.exe` 相同目录下即可被软件自动识别并免配置使用)*
