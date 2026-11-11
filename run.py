import sys
import os

# 确保项目根路径进入 sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from qfluentwidgets import setTheme, Theme

from app.ui.main_window import MainWindow

def main():
    # 开启高 DPI 缩放支持
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_DontCreateNativeWidgetSiblings)

    # 设置跟随系统或默认明亮主题
    setTheme(Theme.AUTO)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
