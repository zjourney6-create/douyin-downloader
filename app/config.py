import json
import os
from typing import Dict, Any, List

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
DEFAULT_DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")

class AppConfig:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AppConfig, cls).__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self):
        self.data: Dict[str, Any] = {
            "download_dir": DEFAULT_DOWNLOAD_DIR,
            "auto_clipboard": True,
            "format": "hevc",  # 默认官方原流 H.265 (HEVC) / AAC
            "history": []
        }
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self.data.update(saved)
            except Exception as e:
                print(f"读取配置文件失败，使用默认配置: {e}")

        # 确保下载目录存在
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir, exist_ok=True)

    def save(self):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"写入配置文件失败: {e}")

    @property
    def download_dir(self) -> str:
        d = self.data.get("download_dir", DEFAULT_DOWNLOAD_DIR)
        return os.path.abspath(d)

    @download_dir.setter
    def download_dir(self, path: str):
        self.data["download_dir"] = os.path.abspath(path)
        self.save()

    @property
    def auto_clipboard(self) -> bool:
        return self.data.get("auto_clipboard", True)

    @auto_clipboard.setter
    def auto_clipboard(self, enabled: bool):
        self.data["auto_clipboard"] = bool(enabled)
        self.save()

    @property
    def history(self) -> List[Dict[str, Any]]:
        return self.data.get("history", [])

    def add_history(self, item: Dict[str, Any]):
        """新增下载历史记录（保留最新 200 条）"""
        history = self.data.get("history", [])
        # 避免同路径重复堆叠
        history = [h for h in history if h.get("file_path") != item.get("file_path")]
        history.insert(0, item)
        self.data["history"] = history[:200]
        self.save()

config = AppConfig()
