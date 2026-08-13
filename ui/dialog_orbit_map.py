import os
import numpy as np
import matplotlib.pyplot as plt
from datetime import timedelta, timezone
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QComboBox, QSlider, QPushButton, QGroupBox)
from PyQt6.QtCore import Qt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar

import cartopy
import cartopy.crs as ccrs
import cartopy.feature as cfeature

from skyfield.api import Loader, EarthSatellite
from core.color_manager import color_manager

# 💡 [핵심] 프로젝트 내 offline_data 폴더 경로 지정
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OFFLINE_DATA_DIR = os.path.join(BASE_DIR, "assets", "offline_data")
CARTOPY_OFFLINE_DIR = os.path.join(OFFLINE_DATA_DIR, "cartopy")
SKYFIELD_OFFLINE_DIR = os.path.join(OFFLINE_DATA_DIR, "skyfield")

# Cartopy 데이터 로딩 경로를 프로젝트 내부 폴더로 지정
cartopy.config['data_dir'] = CARTOPY_OFFLINE_DIR


class OrbitMapDialog(QDialog):
    def __init__(self, calculated_passes, station_data, color_mode="STATION", parent=None):
        super().__init__(parent)
        self.setWindowTitle("🌐 STK 2D Interactive Orbit Tracker (Cartopy Offline Engine)")
        self.resize(1280, 820)
        
        self.passes = [p for p in calculated_passes if p.get('selected', True)]
        if not self.passes:
            self.passes = calculated_passes
            
        self.station_data = station_data
        self.color_mode = color_mode       
        

        # 💡 [수정 후] Loader 객체를 먼저 생성하고 timescale() 호출
        if os.path.exists(SKYFIELD_OFFLINE_DIR):
            offline_loader = Loader(SKYFIELD_OFFLINE_DIR)
            self.ts = offline_loader.timescale()
        else:
            offline_loader = Loader('.')
            self.ts = offline_loader.timescale()
        
        self.current_pass_idx = 0
        self.time_offset_sec = 0  # -600s ~ +600s (±10분)
        
        # 🖐️ 마우스 Drag-Pan 제어 변수
        self.is_panning = False
        self.pan_start = None

        self.init_ui()
        self.update_map()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        ctrl_group = QGroupBox("🛰️ STK Interactive Orbit Control Bar")
        ctrl_layout = QHBoxLayout(ctrl_group)
        
        ctrl_layout.addWidget(QLabel("<b>Select Pass:</b>"))
        self.combo_pass = QComboBox()
        self.combo_pass.setMinimumWidth(380)
        
        for idx, p in enumerate(self.passes):
            aos_str = p['aos'].strftime('%m-%d %H:%M:%S') if hasattr(p['aos'], 'strftime') else str(p['aos'])
            display_text = f"[{idx+1}] {p['satellite']} @ {p['station']} (Pass {p['pass_no']} | AOS: {aos_str})"
            self.combo_pass.addItem(display_text)
            
        self.combo_pass.currentIndexChanged.connect(self.on_pass_changed)
        ctrl_layout.addWidget(self.combo_pass)
        
        ctrl_layout.addSpacing(15)
        
        ctrl_layout.addWidget(QLabel("<b>Time Offset:</b>"))
        self.lbl_time_offset = QLabel("AOS + 00:00 (Live)")
        self.lbl_time_offset.setStyleSheet("font-weight: bold; color: #0D47A1; min-width: 130px;")
        
        self.slider_time = QSlider(Qt.Orientation.Horizontal)
        self.slider_time.setRange(-600, 600)
        self.slider_time.setValue(0)
        self.slider_time.setTickInterval(60)
        self.slider_time.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider_time.valueChanged.connect(self.on_slider_changed)
        
        ctrl_layout.addWidget(self.slider_time)
        ctrl_layout.addWidget(self.lbl_time_offset)
        
        btn_reset_slider = QPushButton("↺ Reset Time")
        btn_reset_slider.clicked.connect(lambda: self.slider_time.setValue(0))
        ctrl_layout.addWidget(btn_reset_slider)
        
        layout.addWidget(ctrl_group)
        
        plt.style.use('default')
        self.fig = plt.figure(figsize=(12, 7), facecolor='#FFFFFF')
        self.ax = self.fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
        
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)
        
        self.canvas.mpl_connect('scroll_event', self.on_mouse_wheel_zoom)
        self.canvas.mpl_connect('button_press_event', self.on_mouse_press)
        self.canvas.mpl_connect('button_release_event', self.on_mouse_release)
        self.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)
        
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)
        
        btn_close = QPushButton("Close 2D Map")
        btn_close.setStyleSheet("background-color: #1976D2; color: white; font-weight: bold; padding: 6px;")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def on_mouse_press(self, event):
        if event.inaxes != self.ax: return
        if event.button == 1:
            self.is_panning = True
            self.pan_start = (event.xdata, event.ydata)

    def on_mouse_release(self, event):
        self.is_panning = False
        self.pan_start = None

    def on_mouse_move(self, event):
        if not self.is_panning or event.inaxes != self.ax or self.pan_start is None: return
        if event.xdata is None or event.ydata is None: return

        dx = event.xdata - self.pan_start[0]
        dy = event.ydata - self.pan_start[1]

        cur_xlim = self.ax.get_xlim()
        cur_ylim = self.ax.get_ylim()

        self.ax.set_xlim([cur_xlim[0] - dx, cur_xlim[1] - dx])
        self.ax.set_ylim([cur_ylim[0] - dy, cur_ylim[1] - dy])
        self.canvas.draw_idle()

    def on_mouse_wheel_zoom(self, event):
        if event.inaxes != self.ax: return
        
        cur_xlim = self.ax.get_xlim()
        cur_ylim = self.ax.get_ylim()
        
        xdata = event.xdata
        ydata = event.ydata
        
        scale_factor = 0.8 if event.button == 'up' else 1.25
        
        new_width = (cur_xlim[1] - cur_xlim[0]) * scale_factor
        new_height = (cur_ylim[1] - cur_ylim[0]) * scale_factor
        
        rel_x = (cur_xlim[1] - xdata) / (cur_xlim[1] - cur_xlim[0])
        rel_y = (cur_ylim[1] - ydata) / (cur_ylim[1] - cur_ylim[0])
        
        self.ax.set_xlim([xdata - new_width * (1 - rel_x), xdata + new_width * rel_x])
        self.ax.set_ylim([ydata - new_height * (1 - rel_y), ydata + new_height * rel_y])
        self.canvas.draw_idle()

    def on_pass_changed(self, idx):
        self.current_pass_idx = idx
        self.slider_time.setValue(0)
        self.update_map()

    def on_slider_changed(self, val):
        self.time_offset_sec = val
        mins = abs(val) // 60
        secs = abs(val) % 60
        sign = "+" if val >= 0 else "-"
        self.lbl_time_offset.setText(f"AOS {sign}{mins:02d}:{secs:02d}")
        self.update_map()

    def update_map(self):
        cur_xlim = self.ax.get_xlim()
        cur_ylim = self.ax.get_ylim()

        self.ax.clear()
        self.ax.set_facecolor('#0B132B')
        
        # Cartopy 지형 및 해안선/국경선 레이어 추가
        self.ax.add_feature(cfeature.LAND, facecolor='#1E293B', edgecolor='none')
        self.ax.add_feature(cfeature.OCEAN, facecolor='#0F172A', edgecolor='none')
        self.ax.add_feature(cfeature.COASTLINE, edgecolor='#38BDF8', linewidth=0.8, alpha=0.9)
        self.ax.add_feature(cfeature.BORDERS, edgecolor='#475569', linestyle=':', linewidth=0.6)

        if cur_xlim != (0, 1) and cur_ylim != (0, 1):
            self.ax.set_xlim(cur_xlim)
            self.ax.set_ylim(cur_ylim)
        else:
            self.ax.set_extent([-180, 180, -90, 90], crs=ccrs.PlateCarree())

        self.ax.set_xlabel("Longitude (deg)", fontsize=10, fontweight='bold', color='#CCCCCC')
        self.ax.set_ylabel("Latitude (deg)", fontsize=10, fontweight='bold', color='#CCCCCC')
        self.ax.set_title("STK 2D Orbit Tracker: Cartopy High-Res Map (Drag to Pan | Scroll to Zoom)", 
                          fontsize=11, fontweight='bold', color='#FFFFFF', pad=10)
        
        gl = self.ax.gridlines(draw_labels=True, crs=ccrs.PlateCarree(), color='#334155', linestyle=':', alpha=0.5)
        gl.top_labels = False
        gl.right_labels = False

        st_dict = {s[0]: (float(s[1]), float(s[2])) for s in self.station_data}
        for st_name, (st_lat, st_lon) in st_dict.items():
            self.ax.plot(st_lon, st_lat, marker='^', color='#EF4444', markersize=9, 
                         transform=ccrs.PlateCarree(), zorder=6)
            self.ax.text(st_lon + 2, st_lat + 2, st_name, fontsize=9, fontweight='bold', 
                         color='#FCA5A5', transform=ccrs.PlateCarree(), zorder=7)
            
            circle_lons = st_lon + 15 * np.cos(np.linspace(0, 2*np.pi, 100))
            circle_lats = st_lat + 15 * np.sin(np.linspace(0, 2*np.pi, 100))
            self.ax.plot(circle_lons, circle_lats, color='#F87171', linestyle=':', linewidth=1.2, alpha=0.6,
                         transform=ccrs.PlateCarree(), zorder=5)

        if not self.passes:
            self.canvas.draw()
            return

        for idx, p in enumerate(self.passes):
            is_active = (idx == self.current_pass_idx)
            sat_raw = p['satellite']
            st_name = p['station']
            tle_lines = p.get('tle_lines', None)

            if self.color_mode == "SATELLITE":
                hex_col, _ = color_manager.get_colors(sat_raw)
            else:
                hex_col, _ = color_manager.get_station_colors(st_name)
            
            line_color = f"#{hex_col}"
            aos_dt = p['aos']
            los_dt = p['los']
            
            if not tle_lines or len(tle_lines) < 2:
                tle_lines = self.find_tle_lines_for_sat(sat_raw)

            if tle_lines and len(tle_lines) >= 2:
                try:
                    sat_obj = EarthSatellite(tle_lines[0], tle_lines[1], sat_raw, self.ts)
                    
                    mid_pass_dt = aos_dt + (los_dt - aos_dt) / 2
                    orbit_start_dt = mid_pass_dt - timedelta(minutes=45)
                    orbit_end_dt = mid_pass_dt + timedelta(minutes=45)
                    
                    total_sec = int((orbit_end_dt - orbit_start_dt).total_seconds())
                    sample_count = 120
                    
                    t_samples = [orbit_start_dt + timedelta(seconds=s) for s in np.linspace(0, total_sec, sample_count)]
                    t_sf = self.ts.from_datetimes([t.replace(tzinfo=timezone.utc) for t in t_samples])
                    
                    subpoint = sat_obj.at(t_sf).subpoint()
                    lats = subpoint.latitude.degrees
                    lons = subpoint.longitude.degrees

                    self.plot_split_ground_track(
                        lons, lats, color=line_color, 
                        linewidth=1.8 if is_active else 1.0, 
                        linestyle='--' if is_active else ':', 
                        alpha=0.55 if is_active else 0.2, 
                        zorder=4 if is_active else 3
                    )

                    pass_sec = max(10, int((los_dt - aos_dt).total_seconds()))
                    t_pass_samples = [aos_dt + timedelta(seconds=s) for s in np.linspace(0, pass_sec, 30)]
                    t_pass_sf = self.ts.from_datetimes([t.replace(tzinfo=timezone.utc) for t in t_pass_samples])
                    
                    p_subpoint = sat_obj.at(t_pass_sf).subpoint()
                    p_lats = p_subpoint.latitude.degrees
                    p_lons = p_subpoint.longitude.degrees

                    self.plot_split_ground_track(
                        p_lons, p_lats, color=line_color, 
                        linewidth=3.8 if is_active else 1.5, 
                        linestyle='-', 
                        alpha=1.0 if is_active else 0.35, 
                        zorder=6 if is_active else 3
                    )

                    if is_active:
                        target_dt = aos_dt + timedelta(seconds=self.time_offset_sec)
                        t_target_sf = self.ts.from_datetime(target_dt.replace(tzinfo=timezone.utc))
                        sat_subpoint = sat_obj.at(t_target_sf).subpoint()
                        
                        sat_lat = sat_subpoint.latitude.degrees
                        sat_lon = sat_subpoint.longitude.degrees
                        
                        self.ax.plot(sat_lon, sat_lat, marker='*', color='#F59E0B', markersize=18, 
                                     markeredgecolor='#FFFFFF', markeredgewidth=1.5, 
                                     transform=ccrs.PlateCarree(), zorder=10)
                        
                        sat_clean = sat_raw.split("(")[0].strip()
                        self.ax.text(sat_lon + 3, sat_lat + 2, f"🛰️ {sat_clean}", 
                                     fontsize=10, fontweight='bold', color='#FBBF24', 
                                     bbox=dict(boxstyle='round,pad=0.3', facecolor='#1E293B', alpha=0.85, edgecolor='#F59E0B'),
                                     transform=ccrs.PlateCarree(), zorder=11)
                except Exception:
                    pass

        self.canvas.draw()

    def plot_split_ground_track(self, lons, lats, color, linewidth, linestyle='-', alpha=1.0, zorder=3):
        lons_clean, lats_clean = [], []
        for i in range(len(lons)):
            if i > 0 and abs(lons[i] - lons[i-1]) > 180:
                self.ax.plot(lons_clean, lats_clean, color=color, linewidth=linewidth, 
                             linestyle=linestyle, alpha=alpha, transform=ccrs.PlateCarree(), zorder=zorder)
                lons_clean, lats_clean = [], []
            lons_clean.append(lons[i])
            lats_clean.append(lats[i])
        if lons_clean:
            self.ax.plot(lons_clean, lats_clean, color=color, linewidth=linewidth, 
                         linestyle=linestyle, alpha=alpha, transform=ccrs.PlateCarree(), zorder=zorder)

    def find_tle_lines_for_sat(self, sat_name):
        tle_dir = "tle"
        sat_clean = sat_name.split("(")[0].strip().lower()
        if not os.path.exists(tle_dir):
            return None
            
        for fn in os.listdir(tle_dir):
            if fn.endswith(".tle") or fn.endswith(".txt"):
                fp = os.path.join(tle_dir, fn)
                try:
                    with open(fp, "r", encoding="utf-8") as f:
                        lines = [l.strip() for l in f.readlines() if l.strip()]
                    for i in range(len(lines) - 2):
                        if sat_clean in lines[i].lower() and lines[i+1].startswith("1 ") and lines[i+2].startswith("2 "):
                            return [lines[i+1], lines[i+2]]
                        if lines[i].startswith("1 ") and lines[i+1].startswith("2 "):
                            return [lines[i], lines[i+1]]
                except Exception:
                    continue
        return None

    def closeEvent(self, event):
        if self.fig:
            plt.close(self.fig)
        super().closeEvent(event)

    def accept(self):
        if self.fig:
            plt.close(self.fig)
        super().accept()