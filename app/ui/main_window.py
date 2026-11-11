from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from qfluentwidgets import (
    FluentWindow, NavigationItemPosition, FluentIcon as FIF
)

from app.ui.download_view import DownloadView
from app.ui.history_view import HistoryView
from app.ui.settings_view import SettingsView
from app.core.clipboard_watcher import ClipboardWatcher

class MainWindow(FluentWindow):
    """应用主窗口容器"""

    def __init__(self):
        super().__init__()
        self.init_window()
        self.init_navigation()
        self.init_clipboard()

    def init_window(self):
        self.resize(980, 680)
        self.setMinimumSize(850, 560)
        self.setWindowTitle("抖音无水印视频下载器 - [H.265原流直出]")

        # 居中显示
        desktop = self.screen().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move((w - self.width()) // 2, (h - self.height()) // 2)

    def init_navigation(self):
        # 1. 视频下载主视图
        self.download_view = DownloadView(self)
        self.download_view.setObjectName("download_view")
        self.addSubInterface(
            self.download_view,
            FIF.DOWNLOAD,
            "视频下载"
        )

        # 2. 历史记录视图
        self.history_view = HistoryView(self)
        self.history_view.setObjectName("history_view")
        self.addSubInterface(
            self.history_view,
            FIF.HISTORY,
            "历史记录"
        )

        # 3. 设置视图（底部）
        self.settings_view = SettingsView(self)
        self.settings_view.setObjectName("settings_view")
        self.addSubInterface(
            self.settings_view,
            FIF.SETTING,
            "设置",
            NavigationItemPosition.BOTTOM
        )

    def init_clipboard(self):
        self.clipboard_watcher = ClipboardWatcher(self)
        self.clipboard_watcher.sig_douyin_url_detected.connect(self._on_clipboard_detected)
        self.clipboard_watcher.start()

    def _on_clipboard_detected(self, text: str):
        # 切换到下载视图并填入链接
        self.switchTo(self.download_view)
        self.download_view.fill_and_prompt(text)
