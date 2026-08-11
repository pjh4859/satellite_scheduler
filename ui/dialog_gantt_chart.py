import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import timezone
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPushButton
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar

from core.color_manager import color_manager


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
    def __init__(self, calculated_passes, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📊 Multi-Satellite Pass Allocation Gantt Timeline")
        self.resize(1150, 680)
        self.passes = calculated_passes
        self.fig = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        plt.style.use('dark_background')
        self.fig, ax = plt.subplots(figsize=(12, 6), facecolor='#1E1E1E')
        ax.set_facecolor('#262626')
        
        stations = sorted(list({p['station'] for p in self.passes}))
        st_y_map = {st: i for i, st in enumerate(stations)}
        
        for p in self.passes:
            st = p['station']
            sat_raw = p['satellite']
            
            y_pos = st_y_map[st]
            aos_dt = p['aos']
            los_dt = p['los']
            is_selected = p.get('selected', True)
            
            aos_num = mdates.date2num(aos_dt)
            los_num = mdates.date2num(los_dt)
            width = los_num - aos_num
            
            if is_selected:
                hex_color, _ = color_manager.get_colors(sat_raw)
                face_color = f"#{hex_color}"
                edge_color = "#FFFFFF"
                alpha = 0.95
                hatch = None
            else:
                face_color = "#3A3A3A"
                edge_color = "#D32F2F"
                alpha = 0.6
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

        ax.set_yticks(range(len(stations)))
        ax.set_yticklabels(stations, fontsize=11, fontweight='bold', color='#FFFFFF')
        ax.xaxis_date()
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M', tz=timezone.utc))
        self.fig.autofmt_xdate()
        
        ax.set_title("Timeline Matrix: Allocated Passes (Solid Pastel) vs Collided / Blocked (Hatched Gray)", 
                     fontsize=12, fontweight='bold', color='#FFFFFF', pad=15)
        ax.set_xlabel("Time (UTC)", fontsize=10, fontweight='bold', color='#DDDDDD')
        ax.grid(True, linestyle=':', alpha=0.35, color='#999999')
        
        if stations:
            ax.set_ylim(-0.6, len(stations) - 0.4)
            
        self.fig.subplots_adjust(left=0.12, right=0.96, top=0.90, bottom=0.18)
        
        canvas = FigureCanvas(self.fig)
        toolbar = HighVisibilityNavigationToolbar(canvas, self)
        layout.addWidget(toolbar)
        layout.addWidget(canvas)
        
        btn_close = QPushButton("Close Timeline Chart")
        btn_close.setStyleSheet("background-color: #333333; color: white; font-weight: bold; padding: 6px;")
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