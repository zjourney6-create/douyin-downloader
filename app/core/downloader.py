import os
import time
import requests
from typing import Callable, Optional
from datetime import datetime

from app.config import config
from app.engine.parser import ParsedVideoInfo
from app.utils.file_helper import sanitize_filename, format_bytes
from app.utils.ffmpeg_helper import merge_video_audio

class VideoDownloader:
    """抖音视频原流下载与无损合成执行器"""

    def __init__(self, info: ParsedVideoInfo, output_dir: Optional[str] = None):
        self.info = info
        self.output_dir = output_dir or config.download_dir
        self.is_cancelled = False

    def download(self, progress_callback: Optional[Callable[[int, str], None]] = None) -> str:
        """
        执行下载与合并主流程
        :param progress_callback: 回调函数 (progress: 0-100, status_text: str)
        :return: 最终合并生成的文件路径
        """
        def update_progress(val: int, text: str):
            if progress_callback:
                progress_callback(val, text)

        os.makedirs(self.output_dir, exist_ok=True)
        safe_title = sanitize_filename(self.info.title)
        final_filename = f"{safe_title}.mp4"
        final_path = os.path.join(self.output_dir, final_filename)

        # 避免重名覆盖：如果文件已存在，增加后缀编号
        counter = 1
        base_name = safe_title
        while os.path.exists(final_path):
            final_filename = f"{base_name}_{counter}.mp4"
            final_path = os.path.join(self.output_dir, final_filename)
            counter += 1

        temp_video_path = os.path.join(self.output_dir, f".tmp_{self.info.video_id}_video.mp4")
        temp_audio_path = os.path.join(self.output_dir, f".tmp_{self.info.video_id}_audio.mp4")

        s = requests.Session()
        s.trust_env = False
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.douyin.com/"
        }

        try:
            # 1. 下载视频轨 (10% -> 70%)
            update_progress(10, "正在下载官方 H.265 原始画轨...")
            resp_v = s.get(self.info.video_url, headers=headers, stream=True, timeout=20)
            resp_v.raise_for_status()
            total_v = int(resp_v.headers.get("content-length", 0))
            downloaded_v = 0

            with open(temp_video_path, "wb") as f_v:
                for chunk in resp_v.iter_content(chunk_size=512 * 1024):
                    if self.is_cancelled:
                        raise InterruptedError("下载已被用户取消")
                    if chunk:
                        f_v.write(chunk)
                        downloaded_v += len(chunk)
                        if total_v > 0:
                            p = 10 + int((downloaded_v / total_v) * 60)
                            update_progress(p, f"正在下载画轨: {format_bytes(downloaded_v)} / {format_bytes(total_v)}")

            # 2. 下载音频轨 (70% -> 90%)
            update_progress(70, "正在下载原始 AAC 高清音轨...")
            resp_a = s.get(self.info.audio_url, headers=headers, stream=True, timeout=20)
            resp_a.raise_for_status()
            total_a = int(resp_a.headers.get("content-length", 0))
            downloaded_a = 0

            with open(temp_audio_path, "wb") as f_a:
                for chunk in resp_a.iter_content(chunk_size=256 * 1024):
                    if self.is_cancelled:
                        raise InterruptedError("下载已被用户取消")
                    if chunk:
                        f_a.write(chunk)
                        downloaded_a += len(chunk)
                        if total_a > 0:
                            p = 70 + int((downloaded_a / total_a) * 20)
                            update_progress(p, f"正在下载音轨: {format_bytes(downloaded_a)} / {format_bytes(total_a)}")

            # 3. FFmpeg 无损合并 (90% -> 99%)
            update_progress(92, "正在执行 FFmpeg 原流无损封装合成...")
            merge_video_audio(temp_video_path, temp_audio_path, final_path)

            file_size = os.path.getsize(final_path)
            update_progress(100, f"下载完成！文件大小: {format_bytes(file_size)}")

            # 4. 记录历史
            config.add_history({
                "title": self.info.title,
                "file_path": final_path,
                "file_size": file_size,
                "file_size_str": format_bytes(file_size),
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "share_url": self.info.share_url,
                "video_id": self.info.video_id
            })

            return final_path

        finally:
            # 清理临时文件
            for temp_f in [temp_video_path, temp_audio_path]:
                if os.path.exists(temp_f):
                    try:
                        os.remove(temp_f)
                    except Exception:
                        pass

    def cancel(self):
        self.is_cancelled = True
