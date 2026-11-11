import os
import shutil
import subprocess
import sys

def get_ffmpeg_path() -> str:
    """探测 FFmpeg 可执行文件路径（优先检查应用目录便携版，其次检查系统 PATH）"""
    # 1. 检查当前目录及同级目录是否存在 portable ffmpeg.exe
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    local_candidates = [
        os.path.join(base_dir, "ffmpeg.exe"),
        os.path.join(base_dir, "bin", "ffmpeg.exe"),
        os.path.join(base_dir, "resources", "ffmpeg.exe"),
    ]
    for candidate in local_candidates:
        if os.path.exists(candidate) and os.path.isfile(candidate):
            return candidate

    # 2. 检查系统全局 PATH
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    return ""

def is_ffmpeg_available() -> bool:
    """检测当前系统或应用是否可用 FFmpeg"""
    return bool(get_ffmpeg_path())

def merge_video_audio(video_track: str, audio_track: str, output_path: str) -> bool:
    """
    使用 FFmpeg 将视频轨与音频轨无损封装合并为 MP4（-c copy）
    零重新编码，极速秒级完成，100% 保留 H.265/HEVC 与 AAC 原生画质与音质
    """
    ffmpeg_bin = get_ffmpeg_path()
    if not ffmpeg_bin:
        raise RuntimeError("未检测到 FFmpeg 组件，无法执行音视频无损合成。")

    # Windows 下隐藏弹出的命令行黑框
    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE

    cmd = [
        ffmpeg_bin,
        "-y",
        "-i", video_track,
        "-i", audio_track,
        "-c", "copy",
        output_path
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        startupinfo=startupinfo,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    )
    stdout, stderr = process.communicate()

    if process.returncode != 0:
        err_msg = stderr.decode("utf-8", errors="ignore")
        raise RuntimeError(f"FFmpeg 合并失败 (code {process.returncode}): {err_msg}")

    return os.path.exists(output_path) and os.path.getsize(output_path) > 0
