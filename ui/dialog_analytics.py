import numpy as np
import matplotlib.pyplot as plt
from datetime import timezone
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar

from core.color_manager import color_manager
from core.timezone_manager import tz_manager
from core.scheduler import compute_time_weighted_avg_capacity


class AnalyticsDashboardDialog(QDialog):
    def __init__(self, calculated_passes, start_dt, end_dt, station_capacity=None, antenna_overrides=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📊 Pass Analytics & Ground Station Utilization Dashboard")
        self.resize(1180, 780)
        
        self.passes = [p for p in calculated_passes if p.get('selected', True)]
        if not self.passes:
            self.passes = calculated_passes
            
        self.start_dt = start_dt
        self.end_dt = end_dt
        self.fig = None
        # 💡 [M3] 지상국별 동시 수신 가능 대수(RX Capacity). 안 넘어오면 전부 1대로 간주(기존 동작과 동일).
        #    안테나가 N대인 지상국은 "이론상 최대 가동 시간"이 window_hours × N이므로,
        #    가동률(%) 분모에 이 값을 반영해야 100%를 훌쩍 넘는 이상한 숫자가 안 나옵니다.
        self.station_capacity = station_capacity or {}
        # ⚠️ [버그 수정] 점검 일정(시간대별 용량 변경)을 반영하기 위한 오버라이드 목록.
        #    예전에는 이 정보가 없어서 분석 기간 중 일부가 점검 기간이어도 "평소 용량"만으로
        #    가동률을 계산했습니다 (실제보다 가동률이 낮게 나오는 오차가 생길 수 있었습니다).
        self.antenna_overrides = antenna_overrides or []
        
        self.init_ui()

    def _effective_capacity(self, station_name):
        """이 지상국의 분석 기간(start_dt~end_dt) 동안의 시간 가중 평균 용량을 반환합니다.
        점검 일정이 없으면 평소 용량과 동일합니다 (하위 호환)."""
        base_capacity = max(1, self.station_capacity.get(station_name, 1))
        overrides_for_station = [ov for ov in self.antenna_overrides if ov.get("station") == station_name]
        if not overrides_for_station:
            return float(base_capacity)
        return compute_time_weighted_avg_capacity(
            base_capacity, overrides_for_station, "rx_capacity", self.start_dt, self.end_dt
        )

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 1. 요약 메트릭 카드 패널
        summary_group = QGroupBox("📈 Key Operational Metrics")
        summary_layout = QHBoxLayout(summary_group)
        
        total_selected = len(self.passes)
        total_dur_sec = sum(float(p.get('duration', 0)) for p in self.passes)
        total_dur_min = total_dur_sec / 60.0
        avg_dur_min = (total_dur_min / total_selected) if total_selected > 0 else 0
        
        window_hours = max(0.1, (self.end_dt - self.start_dt).total_seconds() / 3600.0)
        
        summary_layout.addWidget(self._create_metric_card("Total Selected Passes", f"{total_selected} passes", "#1E88E5"))
        summary_layout.addWidget(self._create_metric_card("Total Contact Time", f"{total_dur_min:.1f} mins", "#2E7D32"))
        summary_layout.addWidget(self._create_metric_card("Avg Pass Duration", f"{avg_dur_min:.1f} mins", "#F57C00"))
        summary_layout.addWidget(self._create_metric_card("Analysis Window", f"{window_hours:.1f} hours", "#6A1B9A"))
        
        layout.addWidget(summary_group)
        
        # 2. Matplotlib 차트 영역 (좌: 위성별 교신 시간 파이 차트, 우: 지상국 가동률 바 차트)
        plt.style.use('default')
        self.fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5), facecolor='#FFFFFF')
        self.fig.tight_layout(pad=3.5)
        
        self._plot_satellite_pie(ax1)
        self._plot_station_utilization(ax2, window_hours)
        
        canvas = FigureCanvas(self.fig)
        toolbar = NavigationToolbar(canvas, self)
        
        layout.addWidget(toolbar)
        layout.addWidget(canvas)
        
        # 3. 지상국 점유율 상세 요약표
        layout.addWidget(QLabel("<b>🏢 Ground Station Antenna Utilization Summary Table:</b>"))
        table_st = QTableWidget()
        table_st.setColumnCount(6)
        table_st.setHorizontalHeaderLabels([
            "Ground Station", "Pass Count", "Total Duration (min)", "Total Contact (hr)",
            "RX Capacity", "Antenna Utilization (%)"
        ])
        table_st.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        st_data = {}
        for p in self.passes:
            st = p['station']
            dur = float(p.get('duration', 0))
            if st not in st_data:
                st_data[st] = {'count': 0, 'dur_sec': 0.0}
            st_data[st]['count'] += 1
            st_data[st]['dur_sec'] += dur
            
        table_st.setRowCount(len(st_data))
        for row, (st, data) in enumerate(sorted(st_data.items())):
            cnt = data['count']
            dur_m = data['dur_sec'] / 60.0
            dur_h = data['dur_sec'] / 3600.0
            # 💡 [버그 수정] 점검 일정(시간대별 용량 변경)까지 반영한 "시간 가중 평균" 용량.
            #    점검 기간이 섞여 있어도 정확한 가동률(%)이 나오도록 합니다.
            capacity = self._effective_capacity(st)
            # "이론상 최대 가동 가능 시간" = 전체 분석 기간 × 평균 용량
            util_pct = (dur_h / (window_hours * capacity)) * 100.0
            
            table_st.setItem(row, 0, QTableWidgetItem(st))
            table_st.setItem(row, 1, QTableWidgetItem(str(cnt)))
            table_st.setItem(row, 2, QTableWidgetItem(f"{dur_m:.1f}"))
            table_st.setItem(row, 3, QTableWidgetItem(f"{dur_h:.2f}"))
            table_st.setItem(row, 4, QTableWidgetItem(f"{capacity:.1f}대" if abs(capacity - round(capacity)) > 0.01 else f"{int(round(capacity))}대"))
            table_st.setItem(row, 5, QTableWidgetItem(f"{util_pct:.2f}%"))
            
        layout.addWidget(table_st)
        
        # 4. 하단 닫기 버튼
        btn_close = QPushButton("Close Analytics Dashboard")
        btn_close.setStyleSheet("background-color: #1976D2; color: white; font-weight: bold; padding: 6px;")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def _create_metric_card(self, title, value, color_hex):
        card = QGroupBox()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 8, 8, 8)
        
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("font-size: 11px; color: #555555; font-weight: bold;")
        
        lbl_val = QLabel(value)
        lbl_val.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {color_hex};")
        
        card_layout.addWidget(lbl_title)
        card_layout.addWidget(lbl_val)
        return card

    def _plot_satellite_pie(self, ax):
        sat_data = {}
        for p in self.passes:
            sat = p['satellite'].split('(')[0].strip()
            dur = float(p.get('duration', 0)) / 60.0
            sat_data[sat] = sat_data.get(sat, 0.0) + dur

        if not sat_data:
            ax.text(0.5, 0.5, "No Pass Data Available", ha='center', va='center')
            return

        labels = list(sat_data.keys())
        values = list(sat_data.values())
        colors = [f"#{color_manager.get_colors(s)[0]}" for s in labels]

        ax.pie(values, labels=labels, autopct='%1.1f%%', startangle=140, colors=colors,
               textprops={'fontsize': 9, 'weight': 'bold'})
        ax.set_title("Satellite Contact Share (by Duration)", fontsize=11, fontweight='bold', pad=10)

    def _plot_station_utilization(self, ax, window_hours):
        st_data = {}
        for p in self.passes:
            st = p['station']
            dur = float(p.get('duration', 0)) / 3600.0  # 시간 단위
            st_data[st] = st_data.get(st, 0.0) + dur

        if not st_data:
            ax.text(0.5, 0.5, "No Station Data Available", ha='center', va='center')
            return

        stations = list(st_data.keys())
        used_hours = list(st_data.values())
        # 💡 [버그 수정] 표와 동일하게, 점검 일정까지 반영한 시간 가중 평균 용량으로 계산
        util_pcts = [
            (h / (window_hours * self._effective_capacity(st))) * 100.0
            for st, h in zip(stations, used_hours)
        ]
        colors = [f"#{color_manager.get_station_colors(s)[0]}" for s in stations]

        bars = ax.bar(stations, util_pcts, color=colors, edgecolor='#333333', alpha=0.85)
        
        for bar in bars:
            height = bar.get_height()
            ax.annotate(f"{height:.1f}%",
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=9, fontweight='bold')

        ax.set_ylabel("Antenna Utilization (%)", fontsize=10, fontweight='bold')
        ax.set_title("Ground Station Antenna Utilization Rate", fontsize=11, fontweight='bold', pad=10)
        ax.set_ylim(0, max(max(util_pcts) * 1.25, 10))
        ax.grid(True, linestyle=':', alpha=0.6, axis='y')

    def closeEvent(self, event):
        if self.fig:
            plt.close(self.fig)
        super().closeEvent(event)

    def accept(self):
        if self.fig:
            plt.close(self.fig)
        super().accept()