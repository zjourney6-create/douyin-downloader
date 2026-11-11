import os
import subprocess
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QHeaderView, QTableWidgetItem
)
from qfluentwidgets import (
    TitleLabel, TableWidget, PushButton, PrimaryPushButton,
    TransparentToolButton, InfoBar, InfoBarPosition, FluentIcon as FIF
)

from app.config import config

class HistoryView(QWidget):
    """下载历史管理页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # 头部标题与操作栏
        header_layout = QHBoxLayout()
        title_label = TitleLabel("下载历史记录", self)
        header_layout.addWidget(title_label)
        header_layout.addStretch(1)

        self.btn_refresh = PushButton(FIF.SYNC, "刷新", self)
        self.btn_refresh.clicked.connect(self.load_history)
        header_layout.addWidget(self.btn_refresh)

        self.btn_clear = PushButton(FIF.DELETE, "清空记录", self)
        self.btn_clear.clicked.connect(self._clear_history)
        header_layout.addWidget(self.btn_clear)

        self.btn_open_dir = PrimaryPushButton(FIF.FOLDER, "打开下载目录", self)
        self.btn_open_dir.clicked.connect(self._open_download_dir)
        header_layout.addWidget(self.btn_open_dir)

        main_layout.addLayout(header_layout)

        # 历史记录表格
        self.table = TableWidget(self)
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["视频标题", "大小", "格式", "下载时间", "操作"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        self.table.setColumnWidth(4, 110)
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)

        main_layout.addWidget(self.table)

        self.load_history()

    def load_history(self):
        records = config.history
        self.table.setRowCount(len(records))

        for row, item in enumerate(records):
            title = item.get("title", "未命名视频")
            size_str = item.get("file_size_str", "未知")
            date_str = item.get("date", "")
            file_path = item.get("file_path", "")

            # 标题项
            item_title = QTableWidgetItem(title)
            item_title.setToolTip(f"{title}\n{file_path}")
            self.table.setItem(row, 0, item_title)

            # 大小
            item_size = QTableWidgetItem(size_str)
            item_size.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 1, item_size)

            # 格式
            item_fmt = QTableWidgetItem("H.265 / AAC")
            item_fmt.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, item_fmt)

            # 时间
            item_date = QTableWidgetItem(date_str)
            item_date.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, item_date)

            # 操作按钮栏 (播放 + 定位文件夹)
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(4, 2, 4, 2)
            action_layout.setSpacing(6)

            btn_play = TransparentToolButton(FIF.PLAY, action_widget)
            btn_play.setToolTip("播放")
            btn_play.clicked.connect(lambda checked=False, p=file_path: self._play_file(p))
            action_layout.addWidget(btn_play)

            btn_locate = TransparentToolButton(FIF.FOLDER, action_widget)
            btn_locate.setToolTip("定位文件")
            btn_locate.clicked.connect(lambda checked=False, p=file_path: self._locate_file(p))
            action_layout.addWidget(btn_locate)

            self.table.setCellWidget(row, 4, action_widget)

    def _play_file(self, path: str):
        if path and os.path.exists(path):
            os.startfile(path)
        else:
            InfoBar.warning(
                title="文件不存在",
                content="该文件已被移动或删除。",
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=self
            )

    def _locate_file(self, path: str):
        if path and os.path.exists(path):
            subprocess.Popen(f'explorer /select,"{os.path.normpath(path)}"')
        else:
            self._open_download_dir()

    def _open_download_dir(self):
        d = config.download_dir
        if os.path.exists(d):
            os.startfile(d)
        else:
            os.makedirs(d, exist_ok=True)
            os.startfile(d)

    def _clear_history(self):
        config.data["history"] = []
        config.save()
        self.load_history()
        InfoBar.info(
            title="已清空",
            content="下载历史记录已全部清空（磁盘文件仍保留）。",
            position=InfoBarPosition.TOP_RIGHT,
            duration=3000,
            parent=self
        )
