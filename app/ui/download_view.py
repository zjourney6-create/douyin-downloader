import os
import subprocess
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame
)
from qfluentwidgets import (
    TitleLabel, SubtitleLabel, BodyLabel, CaptionLabel, StrongBodyLabel,
    PrimaryPushButton, PushButton, TransparentToolButton,
    TextEdit, ProgressBar, SimpleCardWidget, InfoBar, InfoBarPosition,
    FluentIcon as FIF
)

from app.config import config
from app.core.task_manager import DownloadTaskManager

class TaskItemCard(SimpleCardWidget):
    """单个下载任务的卡片项"""
    def __init__(self, task_id: str, initial_text: str, parent=None):
        super().__init__(parent)
        self.task_id = task_id
        self.output_path = ""
        self.init_ui(initial_text)

    def init_ui(self, initial_text: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # 顶部：标题与操作
        top_layout = QHBoxLayout()
        self.title_label = StrongBodyLabel(initial_text, self)
        self.title_label.setWordWrap(True)
        top_layout.addWidget(self.title_label, 1)

        self.btn_open = TransparentToolButton(FIF.FOLDER, self)
        self.btn_open.setToolTip("打开所在文件夹")
        self.btn_open.setVisible(False)
        self.btn_open.clicked.connect(self._open_folder)
        top_layout.addWidget(self.btn_open)

        self.btn_play = TransparentToolButton(FIF.PLAY, self)
        self.btn_play.setToolTip("立即播放视频")
        self.btn_play.setVisible(False)
        self.btn_play.clicked.connect(self._play_video)
        top_layout.addWidget(self.btn_play)

        layout.addLayout(top_layout)

        # 中部：进度条
        self.progress_bar = ProgressBar(self)
        self.progress_bar.setValue(5)
        layout.addWidget(self.progress_bar)

        # 底部：状态描述
        bottom_layout = QHBoxLayout()
        self.status_label = CaptionLabel("正在解析视频信息...", self)
        self.status_label.setTextColor("#8c8c8c", "#8c8c8c")
        bottom_layout.addWidget(self.status_label)
        bottom_layout.addStretch(1)

        layout.addLayout(bottom_layout)

    def update_title(self, title: str):
        self.title_label.setText(title)

    def update_progress(self, percent: int, msg: str):
        self.progress_bar.setValue(percent)
        self.status_label.setText(msg)

    def mark_completed(self, output_path: str):
        self.output_path = output_path
        self.progress_bar.setValue(100)
        self.status_label.setText("✅ 下载合成完毕（H.265/AAC 原流）")
        self.status_label.setTextColor("#52c41a", "#52c41a")
        self.btn_open.setVisible(True)
        self.btn_play.setVisible(True)

    def mark_error(self, err_msg: str):
        self.progress_bar.setValue(0)
        self.status_label.setText(f"❌ 失败: {err_msg}")
        self.status_label.setTextColor("#ff4d4f", "#ff4d4f")

    def _open_folder(self):
        if self.output_path and os.path.exists(self.output_path):
            folder = os.path.dirname(self.output_path)
            subprocess.Popen(f'explorer /select,"{os.path.normpath(self.output_path)}"')
        else:
            folder = config.download_dir
            os.startfile(folder)

    def _play_video(self):
        if self.output_path and os.path.exists(self.output_path):
            os.startfile(self.output_path)

class DownloadView(QWidget):
    """主下载页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.task_cards = {}
        self.init_ui()
        self._bind_signals()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # 页面标题
        header_layout = QHBoxLayout()
        title_label = TitleLabel("抖音无水印下载", self)
        header_layout.addWidget(title_label)
        header_layout.addStretch(1)
        main_layout.addLayout(header_layout)

        # 输入卡片
        input_card = SimpleCardWidget(self)
        input_layout = QVBoxLayout(input_card)
        input_layout.setContentsMargins(18, 16, 18, 16)
        input_layout.setSpacing(12)

        input_title = SubtitleLabel("添加视频链接", input_card)
        input_layout.addWidget(input_title)

        self.text_input = TextEdit(input_card)
        self.text_input.setPlaceholderText("在此粘贴抖音分享口令或网址，支持多行批量输入，例如：\nhttps://v.douyin.com/-VB502OwYzk/\nhttps://www.douyin.com/jingxuan?modal_id=7687632073955314970")
        self.text_input.setFixedHeight(95)
        input_layout.addWidget(self.text_input)

        btn_row = QHBoxLayout()
        self.btn_paste = PushButton(FIF.PASTE, "粘贴剪贴板", input_card)
        self.btn_paste.clicked.connect(self._on_paste_clicked)
        btn_row.addWidget(self.btn_paste)

        self.btn_clear = PushButton(FIF.DELETE, "清空输入", input_card)
        self.btn_clear.clicked.connect(self.text_input.clear)
        btn_row.addWidget(self.btn_clear)

        btn_row.addStretch(1)

        self.btn_download = PrimaryPushButton(FIF.DOWNLOAD, "开始下载原流", input_card)
        self.btn_download.setFixedWidth(140)
        self.btn_download.clicked.connect(self._on_download_clicked)
        btn_row.addWidget(self.btn_download)

        input_layout.addLayout(btn_row)
        main_layout.addWidget(input_card)

        # 任务列表标题
        tasks_header = QHBoxLayout()
        task_label = SubtitleLabel("下载任务队列", self)
        tasks_header.addWidget(task_label)
        tasks_header.addStretch(1)
        main_layout.addLayout(tasks_header)

        # 任务滚动区域
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setStyleSheet("background: transparent;")

        self.tasks_container = QWidget()
        self.tasks_layout = QVBoxLayout(self.tasks_container)
        self.tasks_layout.setContentsMargins(0, 0, 0, 0)
        self.tasks_layout.setSpacing(10)
        self.tasks_layout.addStretch(1)

        self.scroll_area.setWidget(self.tasks_container)
        main_layout.addWidget(self.scroll_area, 1)

    def _bind_signals(self):
        signals = DownloadTaskManager.instance().signals
        signals.sig_started.connect(self._on_task_started)
        signals.sig_progress.connect(self._on_task_progress)
        signals.sig_finished.connect(self._on_task_finished)
        signals.sig_error.connect(self._on_task_error)

    def fill_and_prompt(self, text: str):
        """外部（如剪贴板监听器）注入链接并提示"""
        self.text_input.setPlainText(text)
        InfoBar.info(
            title="已捕捉到抖音链接",
            content="检测到您复制了抖音分享链接，已自动填充，点击「开始下载」即可执行！",
            position=InfoBarPosition.TOP_RIGHT,
            duration=4000,
            parent=self
        )

    def _on_paste_clicked(self):
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            text = clipboard.text()
            if text:
                self.text_input.setPlainText(text.strip())

    def _on_download_clicked(self):
        raw_text = self.text_input.toPlainText().strip()
        if not raw_text:
            InfoBar.warning(
                title="请输入链接",
                content="输入框为空，请先粘贴抖音视频链接后再点击下载。",
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=self
            )
            return

        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        manager = DownloadTaskManager.instance()

        for line in lines:
            task_id = manager.submit_task(line)
            card = TaskItemCard(task_id, f"正在准备解析: {line[:40]}...", self.tasks_container)
            self.task_cards[task_id] = card
            # 插入到顶部
            self.tasks_layout.insertWidget(0, card)

        self.text_input.clear()
        InfoBar.success(
            title="任务已提交",
            content=f"已成功添加 {len(lines)} 个下载任务到后台队列中！",
            position=InfoBarPosition.TOP_RIGHT,
            duration=3000,
            parent=self
        )

    def _on_task_started(self, task_id: str, title: str):
        if task_id in self.task_cards:
            self.task_cards[task_id].update_title(title)

    def _on_task_progress(self, task_id: str, progress: int, msg: str):
        if task_id in self.task_cards:
            self.task_cards[task_id].update_progress(progress, msg)

    def _on_task_finished(self, task_id: str, output_path: str):
        if task_id in self.task_cards:
            self.task_cards[task_id].mark_completed(output_path)
            InfoBar.success(
                title="下载完成",
                content=f"视频已保存至: {os.path.basename(output_path)}",
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=4000,
                parent=self
            )

    def _on_task_error(self, task_id: str, err_msg: str):
        if task_id in self.task_cards:
            self.task_cards[task_id].mark_error(err_msg)
            InfoBar.error(
                title="下载异常",
                content=err_msg,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=5000,
                parent=self
            )
