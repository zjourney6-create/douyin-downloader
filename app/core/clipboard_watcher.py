import re
from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtGui import QGuiApplication
from app.config import config

class ClipboardWatcher(QObject):
    sig_douyin_url_detected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.last_url = ""
        self.timer = QTimer(self)
        self.timer.setInterval(1000)  # 每秒轮询检测一次剪贴板
        self.timer.timeout.connect(self._check_clipboard)

    def start(self):
        self.timer.start()

    def stop(self):
        self.timer.stop()

    def _check_clipboard(self):
        if not config.auto_clipboard:
            return

        clipboard = QGuiApplication.clipboard()
        if not clipboard:
            return

        text = clipboard.text()
        if not text or not isinstance(text, str):
            return

        # 匹配抖音分享链接特征
        if ("v.douyin.com" in text or "douyin.com" in text) and ("http://" in text or "https://" in text):
            # 提取匹配到的有效 url
            match = re.search(r'https?://[^\s，,。]+douyin\.com[^\s，,。]*', text)
            if match:
                url = match.group(0)
                if url != self.last_url:
                    self.last_url = url
                    self.sig_douyin_url_detected.emit(text)
