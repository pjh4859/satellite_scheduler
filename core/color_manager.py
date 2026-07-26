# core/color_manager.py
from PyQt6.QtGui import QColor

class DynamicColorManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DynamicColorManager, cls).__new__(cls)
            cls._instance.sat_color_map = {}
            cls._instance.station_color_map = {}
            
            # 🎨 1. 위성 전용: 가시성 및 채도가 뚜렷하게 명시된 프리미엄 파스텔 풀
            cls._instance.sat_pastel_pool = [
                ("EBFDEB", QColor(235, 253, 235)),  # 민트 그린
                ("F2E6FF", QColor(242, 230, 255)),  # 소프트 퍼플/라벤더
                ("FFFBF0", QColor(255, 251, 240)),  # 베이지 크림
                ("E6F7FA", QColor(230, 247, 250)),  # 파스텔 아쿠아
                ("FFFDE6", QColor(255, 253, 230)),  # 레몬 옐로우
                ("FFF0F2", QColor(255, 240, 242)),  # 피치 핑크
            ]
            
            # 🎨 2. 지상국 전용: 텍스트 가시성이 우수하고 상호 구분이 뚜렷한 파스텔 풀
            cls._instance.station_pastel_pool = [
                ("E6F2FF", QColor(230, 242, 255)),  # 소프트 스카이 블루
                ("FFEBE6", QColor(255, 235, 230)),  # 소프트 피치/세이지
                ("E6FDE6", QColor(230, 253, 230)),  # 라이트 애플 그린
                ("FBF0FF", QColor(251, 240, 255)),  # 라벤더 로즈
                ("FEFCE8", QColor(254, 252, 232)),  # 크림 옐로우
                ("CCFBF1", QColor(204, 251, 241)),  # 아쿠아 민트
            ]
            
            cls._instance.sat_index = 0
            cls._instance.station_index = 0
            
        return cls._instance

    def get_colors(self, sat_name):
        """위성 이름 기반 명확한 고대비 파스텔 색상 반환"""
        key = str(sat_name).strip().upper()
        if not key or key in ["NONE", "NULL", "N/A"]:
            return "FFFFFF", QColor(255, 255, 255)
            
        if key in self.sat_color_map:
            return self.sat_color_map[key]
            
        # 순차 연산 순환 배정 (랜덤 미사용)
        chosen = self.sat_pastel_pool[self.sat_index % len(self.sat_pastel_pool)]
        self.sat_index += 1
        self.sat_color_map[key] = chosen
        return chosen

    def get_station_colors(self, station_name):
        """지상국 이름 기반 명확한 고대비 파스텔 색상 반환"""
        key = str(station_name).strip().upper()
        if not key or key in ["NONE", "NULL", "N/A"]:
            return "FFFFFF", QColor(255, 255, 255)
            
        if key in self.station_color_map:
            return self.station_color_map[key]
            
        # 순차 연산 순환 배정 (랜덤 미사용)
        chosen = self.station_pastel_pool[self.station_index % len(self.station_pastel_pool)]
        self.station_index += 1
        self.station_color_map[key] = chosen
        return chosen

color_manager = DynamicColorManager()