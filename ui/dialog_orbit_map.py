import numpy as np
import matplotlib.pyplot as plt
from datetime import timedelta, timezone
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPushButton
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar

from skyfield.api import load, EarthSatellite, wgs84
from core.color_manager import color_manager


class OrbitMapDialog(QDialog):
    def __init__(self, calculated_passes, station_data, color_mode="STATION", parent=None):
        super().__init__(parent)
        self.setWindowTitle("🌐 2D Satellite Ground Track & Ground Station Footprint Map")
        self.resize(1150, 680)
        self.passes = calculated_passes
        self.station_data = station_data  # [[name, lat, lon, ...], ...]
        self.color_mode = color_mode
        self.fig = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        plt.style.use('default')
        
        self.fig, ax = plt.subplots(figsize=(12, 6), facecolor='#FFFFFF')
        ax.set_facecolor('#E8F1F5')  # 바다 느낌의 아주 연한 블루톤
        
        # 1. 위도/경도 그리드선 및 0도 격자
        ax.set_xlim(-180, 180)
        ax.set_ylim(-90, 90)
        ax.set_xlabel("Longitude (deg)", fontsize=10, fontweight='bold', color='#333333')
        ax.set_ylabel("Latitude (deg)", fontsize=10, fontweight='bold', color='#333333')
        ax.set_title("Ground Track & Station Visibility Footprints (Plate Carrée Projection)", 
                     fontsize=12, fontweight='bold', color='#111111', pad=15)
        ax.grid(True, linestyle=':', alpha=0.6, color='#A0A0A0')
        ax.axhline(0, color='#666666', linewidth=0.8, linestyle='--')
        ax.axvline(0, color='#666666', linewidth=0.8, linestyle='--')

        # 2. 지상국 위치 표출 (Red Point & Footprint Circle)
        st_dict = {s[0]: (float(s[1]), float(s[2])) for s in self.station_data}
        for st_name, (st_lat, st_lon) in st_dict.items():
            ax.plot(st_lon, st_lat, marker='^', color='#D32F2F', markersize=9, zorder=5)
            ax.text(st_lon + 2, st_lat + 2, st_name, fontsize=9, fontweight='bold', color='#B71C1C', zorder=6)
            
            # 대략적인 가시권 Footprint (약 15도 내외 거리 원)
            circle_lons = st_lon + 15 * np.cos(np.linspace(0, 2*np.pi, 100))
            circle_lats = st_lat + 15 * np.sin(np.linspace(0, 2*np.pi, 100))
            ax.plot(circle_lons, circle_lats, color='#E53935', linestyle=':', linewidth=1.2, alpha=0.7)

        # 3. 선택된 패스들의 Ground Track 계산 및 그리기
        ts = load.timescale()
        selected_passes = [p for p in self.passes if p.get('selected', True)]
        
        for p in selected_passes:
            aos_dt = p['aos']
            los_dt = p['los']
            sat_raw = p['satellite']
            st_name = p['station']
            tle_lines = p.get('tle_lines', None)

            # 색상 매핑
            if self.color_mode == "SATELLITE":
                hex_col, _ = color_manager.get_colors(sat_raw)
            else:
                hex_col, _ = color_manager.get_station_colors(st_name)
            line_color = f"#{hex_col}"

            if tle_lines and len(tle_lines) >= 2:
                try:
                    sat_obj = EarthSatellite(tle_lines[0], tle_lines[1], sat_raw, ts)
                    duration_sec = max(10, int((los_dt - aos_dt).total_seconds()))
                    sample_count = max(15, duration_sec // 10)
                    
                    t_samples = [aos_dt + timedelta(seconds=s) for s in np.linspace(0, duration_sec, sample_count)]
                    t_sf = ts.from_datetimes([t.replace(tzinfo=timezone.utc) for t in t_samples])
                    
                    subpoint = sat_obj.at(t_sf).subpoint()
                    lats = subpoint.latitude.degrees
                    lons = subpoint.longitude.degrees

                    # 날짜 변경선(-180/180도) 불연속 끊어주기
                    lons_clean, lats_clean = [], []
                    for i in range(len(lons)):
                        if i > 0 and abs(lons[i] - lons[i-1]) > 180:
                            ax.plot(lons_clean, lats_clean, color=line_color, linewidth=2.0, alpha=0.85)
                            lons_clean, lats_clean = [], []
                        lons_clean.append(lons[i])
                        lats_clean.append(lats[i])
                    if lons_clean:
                        ax.plot(lons_clean, lats_clean, color=line_color, linewidth=2.0, alpha=0.85)

                    # AOS 시작점 표출
                    ax.plot(lons[0], lats[0], marker='o', color=line_color, markersize=4)
                except Exception:
                    pass
            else:
                # TLE 소스가 없을 경우 지상국 좌표 주변 직선 대용 표출
                if st_name in st_dict:
                    st_lat, st_lon = st_dict[st_name]
                    ax.plot([st_lon - 3, st_lon + 3], [st_lat - 3, st_lat + 3], 
                            color=line_color, linewidth=2.0, linestyle='--')

        canvas = FigureCanvas(self.fig)
        toolbar = NavigationToolbar(canvas, self)
        layout.addWidget(toolbar)
        layout.addWidget(canvas)
        
        btn_close = QPushButton("Close Orbit Map")
        btn_close.setStyleSheet("background-color: #1976D2; color: white; font-weight: bold; padding: 6px;")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def closeEvent(self, event):
        if self.fig:
            plt.close(self.fig)
        super().closeEvent(event)

    def accept(self):
        if self.fig:
            plt.close(self.fig)
        super().accept()