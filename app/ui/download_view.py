import os
import subprocess
from typing import Dict
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame, QDialog
)
from qfluentwidgets import (
    TitleLabel, SubtitleLabel, BodyLabel, CaptionLabel, StrongBodyLabel,
    PrimaryPushButton, PushButton, TransparentToolButton, RadioButton,
    TextEdit, ProgressBar, SimpleCardWidget, InfoBar, InfoBarPosition,
    MessageBoxBase, FluentIcon as FIF
)

from app.config import config
from app.core.task_manager import DownloadTaskManager
from app.engine.parser import DouyinParser

class AuthorBatchDialog(MessageBoxBase):
    """博主批量下载规模选择弹窗"""
    def __init__(self, user_url: str, parent=None):
        super().__init__(parent)
        self.user_url = user_url
        self.selected_count = 100

        self.titleLabel = SubtitleLabel("检测到博主主页链接", self)
        self.descLabel = CaptionLabel("您正在添加博主主页，支持一键批量抓取下载该博主的作品列表：", self)
        self.descLabel.setTextColor("#8c8c8c", "#8c8c8c")

        self.radio_100 = RadioButton("下载前 100 个视频 (推荐)", self)
        self.radio_100.setChecked(True)
        self.radio_200 = RadioButton("下载前 200 个视频", self)
        self.radio_300 = RadioButton("下载前 300 个视频", self)

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.descLabel)
        self.viewLayout.addSpacing(10)
        self.viewLayout.addWidget(self.radio_100)
        self.viewLayout.addWidget(self.radio_200)
        self.viewLayout.addWidget(self.radio_300)

        self.yesButton.setText("开始批量抓取")
        self.cancelButton.setText("取消")

        self.yesButton.clicked.connect(self._on_confirm)

    def _on_confirm(self):
        if self.radio_100.isChecked():
            self.selected_count = 100
        elif self.radio_200.isChecked():
            self.selected_count = 200
        elif self.radio_300.isChecked():
            self.selected_count = 300

class TaskItemCard(SimpleCardWidget):
    """单个下载任务的卡片项（支持动态取消、打开、重试）"""
    def __init__(self, task_id: str, raw_url: str, initial_text: str, custom_output_dir: str = "", parent=None):
        super().__init__(parent)
        self.task_id = task_id
        self.raw_url = raw_url
        self.custom_output_dir = custom_output_dir
        self.output_path = ""
        self.is_completed = False
        self.is_cancelled = False
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

        # 取消按钮（进行中时可见）
        self.btn_cancel = TransparentToolButton(FIF.CLOSE, self)
        self.btn_cancel.setToolTip("取消下载")
        self.btn_cancel.clicked.connect(self._on_cancel_clicked)
        top_layout.addWidget(self.btn_cancel)

        # 重新下载按钮（取消后变为可见）
        self.btn_retry = TransparentToolButton(FIF.SYNC, self)
        self.btn_retry.setToolTip("重新下载该视频")
        self.btn_retry.setVisible(False)
        self.btn_retry.clicked.connect(self._on_retry_clicked)
        top_layout.addWidget(self.btn_retry)

        # 打开文件夹按钮（完成后可见）
        self.btn_open = TransparentToolButton(FIF.FOLDER, self)
        self.btn_open.setToolTip("打开所在文件夹")
        self.btn_open.setVisible(False)
        self.btn_open.clicked.connect(self._open_folder)
        top_layout.addWidget(self.btn_open)

        # 播放视频按钮（完成后可见）
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

    def _on_cancel_clicked(self):
        DownloadTaskManager.instance().cancel_task(self.task_id)
        self.mark_cancelled()

    def _on_retry_clicked(self):
        # 重新提交下载
        self.btn_retry.setVisible(False)
        self.btn_cancel.setVisible(True)
        self.is_cancelled = False
        self.progress_bar.setValue(5)
        self.status_label.setText("正在重新启动下载...")
        self.status_label.setTextColor("#8c8c8c", "#8c8c8c")

        new_task_id = DownloadTaskManager.instance().submit_task(self.raw_url, custom_output_dir=self.custom_output_dir)
        # 通知父级替换绑定
        if self.parent() and hasattr(self.parent(), "remap_card_id"):
            self.parent().remap_card_id(self.task_id, new_task_id)
        self.task_id = new_task_id

    def update_title(self, title: str):
        self.title_label.setText(title)

    def update_progress(self, percent: int, msg: str):
        if not self.is_cancelled and not self.is_completed:
            self.progress_bar.setValue(percent)
            self.status_label.setText(msg)

    def mark_completed(self, output_path: str):
        self.is_completed = True
        self.output_path = output_path
        self.progress_bar.setValue(100)
        self.status_label.setText("✅ 下载完成（原流纯净无水印）")
        self.status_label.setTextColor("#52c41a", "#52c41a")
        self.btn_cancel.setVisible(False)
        self.btn_retry.setVisible(False)
        self.btn_open.setVisible(True)
        self.btn_play.setVisible(True)

    def mark_cancelled(self):
        self.is_cancelled = True
        self.progress_bar.setValue(0)
        self.status_label.setText("⚠️ 已取消下载（已清理临时缓存）")
        self.status_label.setTextColor("#faad14", "#faad14")
        self.btn_cancel.setVisible(False)
        self.btn_retry.setVisible(True)

    def mark_error(self, err_msg: str):
        self.progress_bar.setValue(0)
        self.status_label.setText(f"❌ 失败: {err_msg}")
        self.status_label.setTextColor("#ff4d4f", "#ff4d4f")
        self.btn_cancel.setVisible(False)
        self.btn_retry.setVisible(True)

    def _open_folder(self):
        if self.output_path and os.path.exists(self.output_path):
            folder = os.path.dirname(self.output_path)
            subprocess.Popen(f'explorer /select,"{os.path.normpath(self.output_path)}"')
        else:
            folder = self.custom_output_dir or config.download_dir
            os.startfile(folder)

    def _play_video(self):
        if self.output_path and os.path.exists(self.output_path):
            os.startfile(self.output_path)

class DownloadView(QWidget):
    """主下载页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.task_cards: Dict[str, TaskItemCard] = {}
        self.init_ui()
        self._bind_signals()

    def remap_card_id(self, old_id: str, new_id: str):
        if old_id in self.task_cards:
            card = self.task_cards.pop(old_id)
            self.task_cards[new_id] = card

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

        input_title = SubtitleLabel("添加视频或博主主页链接", input_card)
        input_layout.addWidget(input_title)

        self.text_input = TextEdit(input_card)
        self.text_input.setPlaceholderText("在此粘贴抖音分享口令、视频网址或博主主页，例如：\n• 单视频/带货：https://v.douyin.com/2j45DyIqAns/\n• 博主主页批量：https://www.douyin.com/user/MS4wLjABAAAA...")
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

        self.btn_download = PrimaryPushButton(FIF.DOWNLOAD, "开始解析下载", input_card)
        self.btn_download.setFixedWidth(140)
        self.btn_download.clicked.connect(self._on_download_clicked)
        btn_row.addWidget(self.btn_download)

        input_layout.addLayout(btn_row)
        main_layout.addWidget(input_card)

        # 任务列表标题与全局操作
        tasks_header = QHBoxLayout()
        task_label = SubtitleLabel("下载任务队列", self)
        tasks_header.addWidget(task_label)
        tasks_header.addStretch(1)

        self.btn_cancel_all = PushButton(FIF.CLOSE, "全部取消", self)
        self.btn_cancel_all.clicked.connect(self._on_cancel_all_clicked)
        tasks_header.addWidget(self.btn_cancel_all)

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
        signals.sig_cancelled.connect(self._on_task_cancelled)

        signals.sig_author_fetch_progress.connect(self._on_author_fetch_progress)
        signals.sig_author_fetch_done.connect(self._on_author_fetch_done)
        signals.sig_author_fetch_error.connect(self._on_author_fetch_error)

    def fill_and_prompt(self, text: str):
        self.text_input.setPlainText(text)
        InfoBar.info(
            title="已捕捉到抖音链接",
            content="检测到您复制了抖音链接，已自动填充，点击「开始解析下载」即可！",
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

    def _on_cancel_all_clicked(self):
        DownloadTaskManager.instance().cancel_all()
        for card in self.task_cards.values():
            if not card.is_completed:
                card.mark_cancelled()
        InfoBar.warning(
            title="已触发全部取消",
            content="正在终止所有进行中的下载任务并释放网络资源...",
            position=InfoBarPosition.TOP_RIGHT,
            duration=3000,
            parent=self
        )

    def _on_download_clicked(self):
        raw_text = self.text_input.toPlainText().strip()
        if not raw_text:
            InfoBar.warning(
                title="请输入链接",
                content="输入框为空，请先粘贴抖音视频或博主主页链接。",
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=self
            )
            return

        if DouyinParser.is_user_homepage(raw_text):
            extracted_url = DouyinParser.extract_url(raw_text) or raw_text
            dialog = AuthorBatchDialog(extracted_url, self.window())
            if dialog.exec():
                count = dialog.selected_count
                InfoBar.info(
                    title="正在抓取博主作品",
                    content=f"已开始扫描该博主主页（抓取前 {count} 个视频），请稍候...",
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=5000,
                    parent=self
                )
                DownloadTaskManager.instance().submit_author_fetch(extracted_url, max_count=count)
                self.text_input.clear()
            return

        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        manager = DownloadTaskManager.instance()

        for line in lines:
            task_id = manager.submit_task(line)
            card = TaskItemCard(task_id, line, f"正在准备解析: {line[:40]}...", parent=self)
            self.task_cards[task_id] = card
            self.tasks_layout.insertWidget(0, card)

        self.text_input.clear()
        InfoBar.success(
            title="任务已提交",
            content=f"已成功添加 {len(lines)} 个下载任务到后台队列中！",
            position=InfoBarPosition.TOP_RIGHT,
            duration=3000,
            parent=self
        )

    def _on_author_fetch_progress(self, msg: str):
        InfoBar.info(
            title="博主作品抓取进度",
            content=msg,
            position=InfoBarPosition.TOP_RIGHT,
            duration=2500,
            parent=self
        )

    def _on_author_fetch_done(self, author_name: str, video_list: list, author_dir: str):
        manager = DownloadTaskManager.instance()
        count = len(video_list)

        for item in video_list:
            v_url = item.get("url")
            v_title = item.get("title")
            task_id = manager.submit_task(v_url, custom_output_dir=author_dir)
            card = TaskItemCard(task_id, v_url, f"[{author_name}] {v_title}", custom_output_dir=author_dir, parent=self)
            self.task_cards[task_id] = card
            self.tasks_layout.insertWidget(0, card)

        InfoBar.success(
            title="批量抓取完成",
            content=f"已成功为博主【{author_name}】载入 {count} 个视频下载任务！文件将归档至专属文件夹。",
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=6000,
            parent=self
        )

    def _on_author_fetch_error(self, err: str):
        InfoBar.error(
            title="博主主页抓取失败",
            content=err,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=5000,
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

    def _on_task_cancelled(self, task_id: str):
        if task_id in self.task_cards:
            self.task_cards[task_id].mark_cancelled()

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
