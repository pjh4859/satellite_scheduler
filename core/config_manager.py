import os
import json
from datetime import datetime, time, date

CONFIG_FILE_PATH = "config.json"


def serialize_custom(obj):
    """datetime, date, time, set 객체를 JSON 직렬화 가능 포맷으로 변환"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, time):
        return obj.strftime("%H:%M:%S")
    if isinstance(obj, set):
        return list(obj)
    raise TypeError(f"Type {type(obj)} not serializable")


class ConfigManager:
    def __init__(self, config_path=CONFIG_FILE_PATH):
        self.config_path = config_path

    def load_config(self):
        """config.json 읽기"""
        if not os.path.exists(self.config_path):
            return {}
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ConfigManager] Failed to load config: {e}")
            return {}

    def save_config(self, data):
        """config.json 저장"""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False, default=serialize_custom)
            return True
        except Exception as e:
            print(f"[ConfigManager] Failed to save config: {e}")
            return False


config_manager = ConfigManager()