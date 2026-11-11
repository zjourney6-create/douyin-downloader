import os
import sys
import shutil
import subprocess
from typing import Optional, Callable

_CACHED_CHANNEL: Optional[str] = None
_CHECKED: bool = False

EDGE_CANDIDATE_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\Edge\Application\msedge.exe")
]

CHROME_CANDIDATE_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Google\Chrome\Application\chrome.exe")
]

def has_edge() -> bool:
    """检查电脑是否存在系统 Edge 浏览器"""
    if any(os.path.isfile(p) for p in EDGE_CANDIDATE_PATHS):
        return True
    return bool(shutil.which("msedge"))

def has_chrome() -> bool:
    """检查电脑是否存在系统 Chrome 浏览器"""
    if any(os.path.isfile(p) for p in CHROME_CANDIDATE_PATHS):
        return True
    return bool(shutil.which("chrome"))

def install_builtin_chromium(progress_cb: Optional[Callable[[str], None]] = None) -> bool:
    """
    静默自动下载安装 Playwright 官方绿色 Chromium 内核
    免管理员权限，不弹 UAC 授权窗，直接在本地沙箱运行
    """
    if progress_cb:
        progress_cb("检测到系统未安装 Edge/Chrome，正在自动下载轻量浏览器引擎（仅首次需要）...")

    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0

    # 注入淘宝/阿里云 npmmirror 国内高速镜像，避免国内网络下载原生 Playwright 超时卡顿
    env = os.environ.copy()
    env["PLAYWRIGHT_DOWNLOAD_HOST"] = "https://npmmirror.com/mirrors/playwright/"

    cmd = [sys.executable, "-m", "playwright", "install", "chromium"]
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=startupinfo,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        _, stderr = proc.communicate(timeout=180)
        if proc.returncode == 0:
            if progress_cb:
                progress_cb("浏览器引擎自动配置完成！")
            return True
        else:
            err = stderr.decode("utf-8", errors="ignore")
            print(f"Playwright chromium 安装失败: {err}")
            return False
    except Exception as e:
        print(f"执行自动下载异常: {e}")
        return False

def get_best_browser_channel(p=None, progress_cb: Optional[Callable[[str], None]] = None) -> Optional[str]:
    """
    方案 A 三级自适应浏览器渠道获取：
    1. 优先使用系统原生 Edge ('msedge') - 零下载、秒开
    2. 其次降级使用系统原生 Chrome ('chrome') - 零下载、兼容好
    3. 终极兜底：自动静默下载绿色 Chromium 内核 (返回 None)
    """
    global _CACHED_CHANNEL, _CHECKED

    if _CHECKED:
        return _CACHED_CHANNEL

    # 1. 优先检测 Edge
    if has_edge():
        _CACHED_CHANNEL = "msedge"
        _CHECKED = True
        return "msedge"

    # 2. 备用检测 Chrome
    if has_chrome():
        _CACHED_CHANNEL = "chrome"
        _CHECKED = True
        return "chrome"

    # 3. 如果系统既无 Edge 也无 Chrome，检查或自动下载绿色 Chromium
    try:
        if p and hasattr(p, "chromium") and p.chromium.executable_path and os.path.exists(p.chromium.executable_path):
            _CACHED_CHANNEL = None
            _CHECKED = True
            return None
    except Exception:
        pass

    # 自动静默下载
    success = install_builtin_chromium(progress_cb=progress_cb)
    _CACHED_CHANNEL = None  # None 代表使用 playwright 默认内置的 chromium
    _CHECKED = True
    return None
