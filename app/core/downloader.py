import os
import requests
from typing import Callable, Optional
from datetime import datetime

from app.config import config
from app.engine.parser import ParsedVideoInfo
from app.utils.file_helper import sanitize_filename, format_bytes
from app.utils.ffmpeg_helper import merge_video_audio

class VideoDownloader:
    """抖音视频原流下载与无损合成执行器（支持实时取消与临时碎片文件清理）"""

    def __init__(self, info: ParsedVideoInfo, output_dir: Optional[str] = None):
        self.info = info
        self.output_dir = output_dir or config.download_dir
        self.is_cancelled = False
        self.active_resp: Optional[requests.Response] = None

    def cancel(self):
        """外部触发取消指令"""
        self.is_cancelled = True
        if self.active_resp:
            try:
                self.active_resp.close()
            except Exception:
                pass

    def download(self, progress_callback: Optional[Callable[[int, str], None]] = None) -> str:
        """
        执行下载主流程
        :param progress_callback: 回调函数 (progress: 0-100, status_text: str)
        :return: 最终生成的文件路径
        """
        def update_progress(val: int, text: str):
            if progress_callback:
                progress_callback(val, text)

        os.makedirs(self.output_dir, exist_ok=True)
        safe_title = sanitize_filename(self.info.title) or "抖音视频"

        # 1. 严格检查是否为同一个视频 ID（真正的历史防重）
        is_already_downloaded = False
        final_path = ""
        for h in config.history:
            if self.info.video_id and h.get("video_id") == self.info.video_id:
                recorded_path = h.get("file_path", "")
                if recorded_path and os.path.exists(recorded_path) and os.path.getsize(recorded_path) > 100 * 1024:
                    final_path = recorded_path
                    is_already_downloaded = True
                    break

        if is_already_downloaded:
            size_str = format_bytes(os.path.getsize(final_path))
            update_progress(100, f"✅ 本地已存在该视频，智能跳过 ({size_str})")
            return final_path

        # 2. 如果是不同视频但标题重名（电商博主高频出现），自动追加 ID 或序号，绝不漏下任何作品
        final_filename = f"{safe_title}.mp4"
        final_path = os.path.join(self.output_dir, final_filename)

        if os.path.exists(final_path):
            short_suffix = f"_{self.info.video_id[-6:]}" if self.info.video_id else "_1"
            final_filename = f"{safe_title}{short_suffix}.mp4"
            final_path = os.path.join(self.output_dir, final_filename)

            counter = 1
            while os.path.exists(final_path):
                final_filename = f"{safe_title}_{counter}.mp4"
                final_path = os.path.join(self.output_dir, final_filename)
                counter += 1

        s = requests.Session()
        s.trust_env = False
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.douyin.com/"
        }

        # ----------------------------------------------------
        # 分支 1：单流一体视频（如带货视频、普通 MP4 推流）
        # ----------------------------------------------------
        if self.info.is_single_stream or not self.info.audio_url:
            update_progress(10, "检测为原生完整单流，正在直接高速下载...")
            temp_path = os.path.join(self.output_dir, f".tmp_{self.info.video_id}_full.mp4")

            try:
                self.active_resp = s.get(self.info.video_url, headers=headers, stream=True, timeout=25)
                self.active_resp.raise_for_status()
                total_bytes = int(self.active_resp.headers.get("content-length", 0))
                downloaded = 0

                with open(temp_path, "wb") as f:
                    for chunk in self.active_resp.iter_content(chunk_size=512 * 1024):
                        if self.is_cancelled:
                            raise InterruptedError("下载已被用户取消")
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_bytes > 0:
                                p = 10 + int((downloaded / total_bytes) * 88)
                                update_progress(p, f"正在下载原流: {format_bytes(downloaded)} / {format_bytes(total_bytes)}")

                if self.is_cancelled:
                    raise InterruptedError("下载已被用户取消")

                if os.path.exists(final_path):
                    os.remove(final_path)
                os.rename(temp_path, final_path)

                file_size = os.path.getsize(final_path)
                update_progress(100, f"下载完成！文件大小: {format_bytes(file_size)}")

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
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass

        # ----------------------------------------------------
        # 分支 2：DASH 分流视频（音画独立）
        # ----------------------------------------------------
        temp_video_path = os.path.join(self.output_dir, f".tmp_{self.info.video_id}_video.mp4")
        temp_audio_path = os.path.join(self.output_dir, f".tmp_{self.info.video_id}_audio.mp4")

        try:
            update_progress(10, "检测为分流视频，正在下载官方画轨...")
            self.active_resp = s.get(self.info.video_url, headers=headers, stream=True, timeout=20)
            self.active_resp.raise_for_status()
            total_v = int(self.active_resp.headers.get("content-length", 0))
            downloaded_v = 0

            with open(temp_video_path, "wb") as f_v:
                for chunk in self.active_resp.iter_content(chunk_size=512 * 1024):
                    if self.is_cancelled:
                        raise InterruptedError("下载已被用户取消")
                    if chunk:
                        f_v.write(chunk)
                        downloaded_v += len(chunk)
                        if total_v > 0:
                            p = 10 + int((downloaded_v / total_v) * 60)
                            update_progress(p, f"正在下载画轨: {format_bytes(downloaded_v)} / {format_bytes(total_v)}")

            if self.is_cancelled:
                raise InterruptedError("下载已被用户取消")

            update_progress(70, "正在下载原始 AAC 高清音轨...")
            self.active_resp = s.get(self.info.audio_url, headers=headers, stream=True, timeout=20)
            self.active_resp.raise_for_status()
            total_a = int(self.active_resp.headers.get("content-length", 0))
            downloaded_a = 0

            with open(temp_audio_path, "wb") as f_a:
                for chunk in self.active_resp.iter_content(chunk_size=256 * 1024):
                    if self.is_cancelled:
                        raise InterruptedError("下载已被用户取消")
                    if chunk:
                        f_a.write(chunk)
                        downloaded_a += len(chunk)
                        if total_a > 0:
                            p = 70 + int((downloaded_a / total_a) * 20)
                            update_progress(p, f"正在下载音轨: {format_bytes(downloaded_a)} / {format_bytes(total_a)}")

            if self.is_cancelled:
                raise InterruptedError("下载已被用户取消")

            update_progress(92, "正在执行 FFmpeg 原流无损封装合成...")
            merge_video_audio(temp_video_path, temp_audio_path, final_path)

            file_size = os.path.getsize(final_path)
            update_progress(100, f"下载完成！文件大小: {format_bytes(file_size)}")

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
            for temp_f in [temp_video_path, temp_audio_path]:
                if os.path.exists(temp_f):
                    try:
                        os.remove(temp_f)
                    except Exception:
                        pass
