import heapq

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


def _assign_lanes(items):
    """
    💡 [M3 신규] 같은 지상국 안에서, 시간이 겹치는 패스들을 서로 다른 "서브레인(sub-lane)"에
    배치하기 위한 고전적인 구간 스케줄링 그리디 알고리즘 ("최소 플랫폼 수" 문제와 동일).

    - 시간이 안 겹치는 패스들은 같은 레인 번호를 재사용해서, 안테나 대수보다 레인이
      쓸데없이 많아지지 않도록 합니다.
    - 이 함수는 "안테나 용량 배정"이 아니라 순전히 "겹치는 막대를 어느 줄에 그릴지"를
      정하는 시각화 전용 로직입니다 (실제 선택 여부는 core/scheduler.py에서 이미 결정됨).

    :param items: (aos_num, los_num, pass_dict) 튜플의 리스트 (아직 정렬 안 되어 있어도 됨)
    :return: (lane_index_by_id, lane_count) - lane_index_by_id는 id(pass_dict) -> 레인 번호
    """
    sorted_items = sorted(items, key=lambda t: (t[0], t[1]))

    free_lanes = []   # 재사용 가능한 레인 번호들 (min-heap)
    active = []        # (종료시각, 레인번호) - 현재 사용 중인 레인들 (min-heap, 종료시각 기준)
    lane_count = 0
    lane_index_by_id = {}

    for aos_num, los_num, p in sorted_items:
        # 이미 끝난 패스들의 레인을 반납
        while active and active[0][0] <= aos_num:
            _, freed_lane = heapq.heappop(active)
            heapq.heappush(free_lanes, freed_lane)

        if free_lanes:
            lane_idx = heapq.heappop(free_lanes)
        else:
            lane_idx = lane_count
            lane_count += 1

        lane_index_by_id[id(p)] = lane_idx
        heapq.heappush(active, (los_num, lane_idx))

    return lane_index_by_id, max(lane_count, 1)


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

        # 💡 [M3] 지상국별로 먼저 (aos_num, los_num) 을 계산해두고, 겹치는 패스를
        #    서로 다른 서브레인에 배치합니다. 그 다음, 각 지상국이 차지하는 "레인 수"만큼
        #    y축 공간을 순서대로 쌓아올립니다 (안테나 여러 대인 지상국은 자연히 여러 줄을 차지함).
        passes_by_station = {st: [] for st in stations}
        for p in self.passes:
            aos_local = tz_manager.convert_dt(p['aos'])
            los_local = tz_manager.convert_dt(p['los'])
            aos_num = mdates.date2num(aos_local)
            los_num = mdates.date2num(los_local)
            passes_by_station[p['station']].append((aos_num, los_num, p))

        LANE_HEIGHT = 1.0     # 레인(줄) 하나의 세로 폭
        STATION_GAP = 0.4     # 지상국 블록 사이 여백

        station_lane_count = {}
        lane_index_by_pass_id = {}
        station_y_base = {}
        cursor_y = 0.0

        for st in stations:
            items = passes_by_station[st]
            lanes, n_lanes = _assign_lanes(items)
            lane_index_by_pass_id.update(lanes)
            station_lane_count[st] = n_lanes
            station_y_base[st] = cursor_y
            cursor_y += (n_lanes * LANE_HEIGHT) + STATION_GAP

        for p in self.passes:
            st = p['station']
            sat_raw = p['satellite']
            
            lane_idx = lane_index_by_pass_id.get(id(p), 0)
            y_pos = station_y_base[st] + (lane_idx * LANE_HEIGHT)
            
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
        # 💡 [M3] 지상국이 여러 레인(안테나 여러 대)을 차지하면, 그 블록의 세로 중앙에 라벨을 달고
        #    안테나 대수를 함께 표기해서 "이 줄들이 한 지상국"임을 알아보기 쉽게 합니다.
        tick_positions = []
        tick_labels = []
        for st in stations:
            n_lanes = station_lane_count[st]
            center_y = station_y_base[st] + ((n_lanes - 1) * LANE_HEIGHT / 2.0)
            tick_positions.append(center_y)
            label = st if n_lanes <= 1 else f"{st} ({n_lanes}x)"
            tick_labels.append(label)

            # 안테나가 2대 이상인 지상국은 블록을 옅은 구분선으로 살짝 표시
            if n_lanes > 1:
                ax.axhspan(
                    station_y_base[st] - LANE_HEIGHT / 2, 
                    station_y_base[st] + (n_lanes - 1) * LANE_HEIGHT + LANE_HEIGHT / 2,
                    color='#000000', alpha=0.03, zorder=0
                )

        ax.set_yticks(tick_positions)
        ax.set_yticklabels(tick_labels, fontsize=11, fontweight='bold', color='#222222')
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
            ax.set_ylim(-0.6, cursor_y - STATION_GAP + 0.4)
            
        self.fig.subplots_adjust(left=0.14, right=0.96, top=0.90, bottom=0.18)
        
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