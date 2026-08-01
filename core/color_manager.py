import re
from PyQt6.QtGui import QColor

class ColorManager:
    """
    위성 및 지상국 고유 파스텔 색상 관리자 (20종 고대비 팔레트 & 정규화 키 고정 매핑)
    """
    def __init__(self):
        # 20가지 고대비 위성 전용 파스텔 팔레트 (HEX)
        self.pastel_palette = [
            "E3F2FD",  # Soft Light Blue
            "F3E5F5",  # Soft Purple
            "E8F5E9",  # Soft Mint Green
            "FFF3E0",  # Soft Orange
            "FCE4EC",  # Soft Pink
            "E0F7FA",  # Soft Cyan
            "FFFDE7",  # Soft Yellow
            "E8EAF6",  # Soft Indigo
            "E0F2F1",  # Soft Teal
            "FFF8E1",  # Soft Amber
            "FFEBEE",  # Soft Red/Rose
            "F1F8E9",  # Soft Lime Green
            "EDE7F6",  # Soft Deep Purple
            "EFEBE9",  # Soft Brown/Taupe
            "F5F5F5",  # Soft Light Gray
            "E1F5FE",  # Soft Sky Blue
            "F48FB1",  # Soft Flamingo
            "C8E6C9",  # Soft Pastel Green
            "FFE0B2",  # Soft Peach
            "D1C4E9"   # Soft Lavender
        ]
        
        # 20가지 고대비 지상국 전용 파스텔 팔레트 (HEX)
        self.station_palette = [
            "E8EAF6", "E0F2F1", "FFF3E0", "F3E5F5", "E8F5E9", "FCE4EC", "E0F7FA",
            "FFFDE7", "E3F2FD", "FFF8E1", "FFEBEE", "F1F8E9", "EDE7F6", "E1F5FE",
            "FFE0B2", "C8E6C9", "D1C4E9", "F48FB1", "EFEBE9", "DCEDC8"
        ]

        self.sat_color_map = {}
        self.station_color_map = {}

    def _normalize_key(self, text):
        """특수문자 및 괄호 제거를 통한 고유 키 정규화"""
        if not text: return ""
        clean = str(text).split("(")[0].strip()
        clean = re.sub(r'[^A-Za-z0-9]', '', clean).upper()
        return clean

    def get_colors(self, sat_name):
        """정규화된 위성 키 기준 20가지 고유 파스텔 색상 1:1 고정 반환"""
        sat_key = self._normalize_key(sat_name)
        if not sat_key:
            return "F5F5F5", QColor(245, 245, 245)

        if sat_key not in self.sat_color_map:
            color_index = len(self.sat_color_map) % len(self.pastel_palette)
            self.sat_color_map[sat_key] = self.pastel_palette[color_index]

        hex_code = self.sat_color_map[sat_key]
        r, g, b = int(hex_code[0:2], 16), int(hex_code[2:4], 16), int(hex_code[4:6], 16)
        return hex_code, QColor(r, g, b)

    def get_station_colors(self, station_name):
        """정규화된 지상국 키 기준 20가지 고유 파스텔 색상 1:1 고정 반환"""
        st_key = self._normalize_key(station_name)
        if not st_key:
            return "F5F5F5", QColor(245, 245, 245)

        if st_key not in self.station_color_map:
            color_index = len(self.station_color_map) % len(self.station_palette)
            self.station_color_map[st_key] = self.station_palette[color_index]

        hex_code = self.station_color_map[st_key]
        r, g, b = int(hex_code[0:2], 16), int(hex_code[2:4], 16), int(hex_code[4:6], 16)
        return hex_code, QColor(r, g, b)

# 싱글톤 인스턴스
color_manager = ColorManager()