import uuid
from typing import Dict, Optional
from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool

from app.engine.parser import DouyinParser, ParsedVideoInfo
from app.core.downloader import VideoDownloader

class TaskSignals(QObject):
    sig_started = Signal(str, str)        # task_id, initial_title
    sig_progress = Signal(str, int, str)  # task_id, progress (0-100), status_text
    sig_finished = Signal(str, str)       # task_id, output_path
    sig_error = Signal(str, str)          # task_id, error_text

class DownloadWorker(QRunnable):
    def __init__(self, task_id: str, raw_input: str, signals: TaskSignals):
        super().__init__()
        self.task_id = task_id
        self.raw_input = raw_input
        self.signals = signals
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
            self.downloader = VideoDownloader(info)
            def on_progress(percent: int, msg: str):
                self.signals.sig_progress.emit(self.task_id, percent, msg)

            output_path = self.downloader.download(progress_callback=on_progress)
            self.signals.sig_finished.emit(self.task_id, output_path)

        except Exception as e:
            self.signals.sig_error.emit(self.task_id, str(e))

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

    def submit_task(self, raw_input: str) -> str:
        task_id = str(uuid.uuid4())[:8]
        worker = DownloadWorker(task_id, raw_input, self.signals)
        self.active_tasks[task_id] = worker
        self.thread_pool.start(worker)
        return task_id
