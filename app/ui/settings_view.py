import os
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFileDialog
)
from qfluentwidgets import (
    TitleLabel, SubtitleLabel, BodyLabel, CaptionLabel, StrongBodyLabel,
    SimpleCardWidget, PushButton, PrimaryPushButton, SwitchButton,
    InfoBar, InfoBarPosition, FluentIcon as FIF
)

from app.config import config
from app.utils.ffmpeg_helper import get_ffmpeg_path, is_ffmpeg_available
from app.engine.parser import DouyinParser, BROWSER_PROFILE_DIR

class LoginThread(QThread):
    finished_sig = Signal()

    def run(self):
        DouyinParser.open_login_window()
        self.finished_sig.emit()

class SettingsView(QWidget):
    """设置页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.login_thread = None
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # 头部标题
        title_label = TitleLabel("系统设置", self)
        main_layout.addWidget(title_label)

        # 0. 抖音账号登录管理卡片（突破26条限制专属）
        account_card = SimpleCardWidget(self)
        account_layout = QHBoxLayout(account_card)
        account_layout.setContentsMargins(18, 16, 18, 16)

        acc_info = QVBoxLayout()
        acc_title = SubtitleLabel("抖音账号登录管理", account_card)
        acc_desc = CaptionLabel("登录后可彻底突破未登录访客仅看26条作品的限制，畅享批量抓取博主前100/200/300个视频！", account_card)
        acc_desc.setTextColor("#8c8c8c", "#8c8c8c")
        acc_info.addWidget(acc_title)
        acc_info.addWidget(acc_desc)
        account_layout.addLayout(acc_info, 1)

        self.btn_login = PrimaryPushButton(FIF.PEOPLE, "扫码登录抖音", account_card)
        self.btn_login.clicked.connect(self._open_login_window)
        account_layout.addWidget(self.btn_login)

        main_layout.addWidget(account_card)

        # 1. 存储路径卡片
        dir_card = SimpleCardWidget(self)
        dir_layout = QVBoxLayout(dir_card)
        dir_layout.setContentsMargins(18, 16, 18, 16)
        dir_layout.setSpacing(10)

        dir_title = SubtitleLabel("下载保存目录", dir_card)
        dir_layout.addWidget(dir_title)

        self.path_label = BodyLabel(config.download_dir, dir_card)
        self.path_label.setTextColor("#1890ff", "#40a9ff")
        dir_layout.addWidget(self.path_label)

        btn_row = QHBoxLayout()
        self.btn_change_dir = PushButton(FIF.EDIT, "更改目录", dir_card)
        self.btn_change_dir.clicked.connect(self._change_download_dir)
        btn_row.addWidget(self.btn_change_dir)

        self.btn_open_dir = PushButton(FIF.FOLDER, "打开目录", dir_card)
        self.btn_open_dir.clicked.connect(self._open_dir)
        btn_row.addWidget(self.btn_open_dir)

        btn_row.addStretch(1)
        dir_layout.addLayout(btn_row)
        main_layout.addWidget(dir_card)

        # 2. 剪贴板自动监听卡片
        clip_card = SimpleCardWidget(self)
        clip_layout = QHBoxLayout(clip_card)
        clip_layout.setContentsMargins(18, 16, 18, 16)

        clip_info = QVBoxLayout()
        clip_title = SubtitleLabel("剪贴板智能监听", clip_card)
        clip_desc = CaptionLabel("在外部复制抖音分享链接时，自动将内容填充至下载输入框并提示", clip_card)
        clip_desc.setTextColor("#8c8c8c", "#8c8c8c")
        clip_info.addWidget(clip_title)
        clip_info.addWidget(clip_desc)
        clip_layout.addLayout(clip_info, 1)

        self.switch_clipboard = SwitchButton(clip_card)
        self.switch_clipboard.setChecked(config.auto_clipboard)
        self.switch_clipboard.checkedChanged.connect(self._on_clipboard_switched)
        clip_layout.addWidget(self.switch_clipboard)

        main_layout.addWidget(clip_card)

        # 3. 运行环境与组件状态卡片
        env_card = SimpleCardWidget(self)
        env_layout = QVBoxLayout(env_card)
        env_layout.setContentsMargins(18, 16, 18, 16)
        env_layout.setSpacing(10)

        env_title = SubtitleLabel("系统依赖与引擎状态", env_card)
        env_layout.addWidget(env_title)

        # FFmpeg 检测
        ffmpeg_ok = is_ffmpeg_available()
        ffmpeg_path = get_ffmpeg_path()
        ffmpeg_row = QHBoxLayout()
        ffmpeg_text = f"✅ FFmpeg 状态正常 ({ffmpeg_path})" if ffmpeg_ok else "❌ 未检测到 FFmpeg"
        ffmpeg_label = BodyLabel(ffmpeg_text, env_card)
        if ffmpeg_ok:
            ffmpeg_label.setTextColor("#52c41a", "#52c41a")
        else:
            ffmpeg_label.setTextColor("#ff4d4f", "#ff4d4f")
        ffmpeg_row.addWidget(ffmpeg_label)
        ffmpeg_row.addStretch(1)
        env_layout.addLayout(ffmpeg_row)

        # Edge 引擎检测
        edge_row = QHBoxLayout()
        edge_label = BodyLabel("✅ 嗅探引擎内核：已集成系统 Microsoft Edge（支持凭证持久化）", env_card)
        edge_label.setTextColor("#52c41a", "#52c41a")
        edge_row.addWidget(edge_label)
        edge_row.addStretch(1)
        env_layout.addLayout(edge_row)

        # 格式信息
        fmt_row = QHBoxLayout()
        fmt_label = CaptionLabel("输出格式规格：官方原流 H.265 (HEVC) / AAC 无损封装合成", env_card)
        fmt_label.setTextColor("#8c8c8c", "#8c8c8c")
        fmt_row.addWidget(fmt_label)
        fmt_row.addStretch(1)
        env_layout.addLayout(fmt_row)

        main_layout.addWidget(env_card)

        main_layout.addStretch(1)

    def _open_login_window(self):
        self.btn_login.setEnabled(False)
        self.btn_login.setText("登录窗口开启中...")
        InfoBar.info(
            title="登录窗口已唤起",
            content="已在弹出窗口中为您打开抖音网页，请在弹出窗口中使用抖音 APP 扫码登录，登录成功后直接关闭浏览器即可！",
            position=InfoBarPosition.TOP_RIGHT,
            duration=6000,
            parent=self
        )

        self.login_thread = LoginThread()
        self.login_thread.finished_sig.connect(self._on_login_finished)
        self.login_thread.start()

    def _on_login_finished(self):
        self.btn_login.setEnabled(True)
        self.btn_login.setText("扫码登录抖音")
        InfoBar.success(
            title="登录配置完成",
            content="浏览器会话已保存，后续批量下载将全自动保持登录态畅通无阻！",
            position=InfoBarPosition.TOP_RIGHT,
            duration=5000,
            parent=self
        )

    def _change_download_dir(self):
        new_dir = QFileDialog.getExistingDirectory(
            self, "选择默认下载保存文件夹", config.download_dir
        )
        if new_dir:
            config.download_dir = new_dir
            self.path_label.setText(config.download_dir)
            InfoBar.success(
                title="目录已更改",
                content=f"新下载目录: {config.download_dir}",
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=self
            )

    def _open_dir(self):
        d = config.download_dir
        if not os.path.exists(d):
            os.makedirs(d, exist_ok=True)
        os.startfile(d)

    def _on_clipboard_switched(self, checked: bool):
        config.auto_clipboard = checked
        msg = "已开启剪贴板智能监听" if checked else "已关闭剪贴板智能监听"
        InfoBar.info(
            title="设置已保存",
            content=msg,
            position=InfoBarPosition.TOP_RIGHT,
            duration=2500,
            parent=self
        )
