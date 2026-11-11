import uuid
import os
from typing import Dict, Optional, List
from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool

from app.engine.parser import DouyinParser, ParsedVideoInfo
from app.core.downloader import VideoDownloader
from app.utils.file_helper import sanitize_filename
from app.config import config

class TaskSignals(QObject):
    sig_started = Signal(str, str)        # task_id, initial_title
    sig_progress = Signal(str, int, str)  # task_id, progress (0-100), status_text
    sig_finished = Signal(str, str)       # task_id, output_path
    sig_error = Signal(str, str)          # task_id, error_text

    # 博主批量抓取专用信号
    sig_author_fetch_progress = Signal(str)           # status_message
    sig_author_fetch_done = Signal(str, list, str)    # author_name, video_list, author_dir
    sig_author_fetch_error = Signal(str)              # error_message

class DownloadWorker(QRunnable):
    def __init__(self, task_id: str, raw_input: str, signals: TaskSignals, custom_output_dir: Optional[str] = None):
        super().__init__()
        self.task_id = task_id
        self.raw_input = raw_input
        self.signals = signals
        self.custom_output_dir = custom_output_dir
        self.downloader: Optional[VideoDownloader] = None

    def run(self):
        try:
            self.signals.sig_started.emit(self.task_id, "正在解析链接...")
            self.signals.sig_progress.emit(self.task_id, 3, "正在唤起自愈嗅探引擎...")

            # 1. 嗅探提取音视频流
            info: ParsedVideoInfo = DouyinParser.parse(self.raw_input)
            self.signals.sig_started.emit(self.task_id, info.title)
            self.signals.sig_progress.emit(self.task_id, 10, "流地址解析成功，准备下载...")

            # 2. 下载并合并
            self.downloader = VideoDownloader(info, output_dir=self.custom_output_dir)
            def on_progress(percent: int, msg: str):
                self.signals.sig_progress.emit(self.task_id, percent, msg)

            output_path = self.downloader.download(progress_callback=on_progress)
            self.signals.sig_finished.emit(self.task_id, output_path)

        except Exception as e:
            self.signals.sig_error.emit(self.task_id, str(e))

class AuthorFetchWorker(QRunnable):
    """博主主页作品列表异步抓取器"""
    def __init__(self, user_url: str, max_count: int, signals: TaskSignals):
        super().__init__()
        self.user_url = user_url
        self.max_count = max_count
        self.signals = signals

    def run(self):
        try:
            def on_progress(msg: str):
                self.signals.sig_author_fetch_progress.emit(msg)

            author_name, video_list = DouyinParser.fetch_author_videos(
                self.user_url, max_count=self.max_count, progress_cb=on_progress
            )
            # 在 downloads/ 下创建博主独立专属子目录
            safe_author_dir = os.path.join(config.download_dir, sanitize_filename(author_name))
            os.makedirs(safe_author_dir, exist_ok=True)

            self.signals.sig_author_fetch_done.emit(author_name, video_list, safe_author_dir)
        except Exception as e:
            self.signals.sig_author_fetch_error.emit(str(e))

class DownloadTaskManager(QObject):
    """全局下载任务调度器"""
    _instance = None

    def __init__(self):
        super().__init__()
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(2)  # 同时执行 2 个并发任务
        self.signals = TaskSignals()
        self.active_tasks: Dict[str, DownloadWorker] = {}

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = DownloadTaskManager()
        return cls._instance

    def submit_task(self, raw_input: str, custom_output_dir: Optional[str] = None) -> str:
        task_id = str(uuid.uuid4())[:8]
        worker = DownloadWorker(task_id, raw_input, self.signals, custom_output_dir=custom_output_dir)
        self.active_tasks[task_id] = worker
        self.thread_pool.start(worker)
        return task_id

    def submit_author_fetch(self, user_url: str, max_count: int = 100):
        worker = AuthorFetchWorker(user_url, max_count, self.signals)
        self.thread_pool.start(worker)
