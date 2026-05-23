# core/color_manager.py
import hashlib
from PyQt6.QtGui import QColor

class DynamicColorManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DynamicColorManager, cls).__new__(cls)
            # 위성 및 지상국 배정 컬러 맵 분리
            cls._instance.sat_color_map = {}
            cls._instance.station_color_map = {}
            
            # 1. 위성 전용 부드러운 파스텔톤 풀
            cls._instance.sat_pastel_pool = [
                ("F2F9FF", QColor(242, 249, 255)),  # 소프트 블루
                ("FFFBF0", QColor(255, 251, 240)),  # 크림 아이보리
                ("EBFDEB", QColor(235, 253, 235)),  # 민트 그린
                ("FBF0FF", QColor(251, 240, 255)),  # 라벤더 퍼플
            ]
            
            # 2. 지상국 전용 눈이 편한 파스텔톤 풀 (새로운 지상국 대응용 프리미엄 컬러)
            cls._instance.station_pastel_pool = [
                ("E6F2FF", QColor(230, 242, 255)),  # 소프트 스카이
                ("FFFDE6", QColor(255, 253, 230)),  # 레몬 쉬폰
                ("E6FDE6", QColor(230, 253, 230)),  # 라이트 애플
                ("F2E6FF", QColor(242, 230, 255)),  # 모브 퍼플
                ("FFF0F2", QColor(255, 240, 242)),  # 파스텔 핑크
                ("E6F7FA", QColor(230, 247, 250)),  # 파스텔 아쿠아
            ]
            
            cls._instance.sat_index = 0
            cls._instance.station_index = 0
            
        return cls._instance

    def get_colors(self, sat_name):
        """[2번 블록용] 위성 이름 기반 고유 파스텔 색상 반환"""
        key = str(sat_name).strip().upper()
        if not key or key == "NONE":
            return "FFFFFF", QColor(255, 255, 255)
        if key in self.sat_color_map:
            return self.sat_color_map[key]
        if self.sat_index < len(self.sat_pastel_pool):
            chosen = self.sat_pastel_pool[self.sat_index]
            self.sat_index += 1
            self.sat_color_map[key] = chosen
            return chosen
        return self._generate_dynamic_pastel(key, self.sat_color_map)

    def get_station_colors(self, station_name):
        """🔥 [1번 블록용 신규] 지상국 이름 기반 유동적 파스텔 색상 반환"""
        key = str(station_name).strip().upper()
        if not key:
            return "FFFFFF", QColor(255, 255, 255)
        if key in self.station_color_map:
            return self.station_color_map[key]
        
        # 새로운 지상국이 들어오면 준비된 지상국 풀에서 순차 배정
        if self.station_index < len(self.station_pastel_pool):
            chosen = self.station_pastel_pool[self.station_index]
            self.station_index += 1
            self.station_color_map[key] = chosen
            return chosen
            
        return self._generate_dynamic_pastel(key, self.station_color_map)

    def _generate_dynamic_pastel(self, key, target_map):
        """풀을 초과하는 무제한 지상국/위성 생성 시 중복을 차단하는 해시 컬러 연산기"""
        hash_digest = hashlib.md5(key.encode('utf-8')).hexdigest()
        hue = (int(hash_digest[:4], 16) % 360) / 360.0
        q_color = QColor.fromHsvF(hue, 0.12, 0.98) # 고명도 저채도 가이드 고정
        hex_code = f"{q_color.red():02X}{q_color.green():02X}{q_color.blue():02X}"
        chosen = (hex_code, q_color)
        target_map[key] = chosen
        return chosen

color_manager = DynamicColorManager()