import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import timezone
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPushButton
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar

from core.color_manager import color_manager
from core.timezone_manager import tz_manager


class HighVisibilityNavigationToolbar(NavigationToolbar):
    def __init__(self, canvas, parent=None):
        super().__init__(canvas, parent)
        self.setStyleSheet("""
            QToolBar { background-color: #F8F9FA; border: 1px solid #CCCCCC; padding: 4px; spacing: 6px; }
            QToolButton { background-color: #FFFFFF; color: #111111; border: 1px solid #B0BEC5; border-radius: 4px; padding: 4px 8px; font-weight: bold; }
            QToolButton:hover { background-color: #E3F2FD; border: 1px solid #2196F3; }
            QToolButton:checked { background-color: #BBDEFB; border: 1px solid #1976D2; }
            QLabel { color: #111111; font-weight: bold; }
        """)


class GanttChartDialog(QDialog):
    def __init__(self, calculated_passes, color_mode="STATION", parent=None):
        super().__init__(parent)
        self.setWindowTitle("📊 Multi-Satellite Pass Allocation Gantt Timeline")
        self.resize(1150, 680)
        self.passes = calculated_passes
        self.color_mode = color_mode
        self.fig = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 라이트 모드 기본 테마
        plt.style.use('default')
        self.fig, ax = plt.subplots(figsize=(12, 6), facecolor='#FFFFFF')
        ax.set_facecolor('#F9F9F9')
        
        stations = sorted(list({p['station'] for p in self.passes}))
        st_y_map = {st: i for i, st in enumerate(stations)}
        
        for p in self.passes:
            st = p['station']
            sat_raw = p['satellite']
            
            y_pos = st_y_map[st]
            
            # 💡 [핵심] tz_manager를 이용해 KST / UTC 타임존 시간으로 변환
            aos_local = tz_manager.convert_dt(p['aos'])
            los_local = tz_manager.convert_dt(p['los'])
            is_selected = p.get('selected', True)
            
            aos_num = mdates.date2num(aos_local)
            los_num = mdates.date2num(los_local)
            width = los_num - aos_num
            
            # 색상 모드(By Satellite / By Station) 반영
            if is_selected:
                if self.color_mode == "SATELLITE":
                    hex_color, _ = color_manager.get_colors(sat_raw)
                else:
                    hex_color, _ = color_manager.get_station_colors(st)
                face_color = f"#{hex_color}"
                edge_color = "#333333"
                alpha = 0.90
                hatch = None
            else:
                face_color = "#E0E0E0"
                edge_color = "#D32F2F"
                alpha = 0.7
                hatch = "///"

            ax.barh(y_pos, width, left=aos_num, height=0.45, 
                    align='center', color=face_color, edgecolor=edge_color, 
                    alpha=alpha, hatch=hatch, linewidth=1.0)
            
            if is_selected and width > 0.0008:
                mid_num = aos_num + (width / 2.0)
                try:
                    sat_clean = sat_raw.split("(")[0].strip()
                    mid_date = mdates.num2date(mid_num)
                    ax.text(mid_date, y_pos, sat_clean, ha='center', va='center', 
                            fontsize=8, fontweight='bold', color='#111111', clip_on=True)
                except Exception:
                    pass

        # Y축 지상국 라벨 설정
        ax.set_yticks(range(len(stations)))
        ax.set_yticklabels(stations, fontsize=11, fontweight='bold', color='#222222')
        ax.xaxis_date()
        
        # 💡 [핵심] 현재 선택된 타임존(UTC / KST) 표기 및 DateFormatter 반영
        tz_label = tz_manager.current_tz
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
        self.fig.autofmt_xdate()
        
        ax.set_title("Timeline Matrix: Allocated Passes (Solid) vs Collided / Blocked (Hatched Gray)", 
                     fontsize=12, fontweight='bold', color='#111111', pad=15)
        ax.set_xlabel(f"Time ({tz_label})", fontsize=10, fontweight='bold', color='#333333')
        ax.grid(True, linestyle=':', alpha=0.6, color='#CCCCCC')
        
        if stations:
            ax.set_ylim(-0.6, len(stations) - 0.4)
            
        self.fig.subplots_adjust(left=0.12, right=0.96, top=0.90, bottom=0.18)
        
        canvas = FigureCanvas(self.fig)
        toolbar = HighVisibilityNavigationToolbar(canvas, self)
        layout.addWidget(toolbar)
        layout.addWidget(canvas)
        
        btn_close = QPushButton("Close Timeline Chart")
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