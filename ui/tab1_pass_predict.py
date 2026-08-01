import os
from datetime import datetime, timedelta, timezone

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, 
                             QDateTimeEdit, QSpinBox, QPushButton, QTableWidget, 
                             QTableWidgetItem, QLabel, QFileDialog, QHeaderView, QMessageBox, 
                             QInputDialog, QDialog, QListWidgetItem, QDialogButtonBox, QCheckBox)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QColor, QDesktopServices

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar

from core.scheduler import parse_tle_from_dir, parse_stations_from_dir, calculate_passes
from core.exporter import export_to_csv, export_to_yaml, export_to_excel_with_color
from core.tle_fetcher import search_satellites_from_celestrak, download_tle_by_norad_id


# ==============================================================================
# [UI 컴포넌트] 다크 모드 맞춤형 고대비 네비게이션 툴바
# ==============================================================================
class HighVisibilityNavigationToolbar(NavigationToolbar):
    """
    다크 테마 환경에서도 100% 선명하게 표출되는 고대비 Navigation Toolbar
    
    [기능 설명]
    - 차트 상단의 돋보기(Zoom to rectangle), 손(Pan), 집(Reset View) 버튼의 배경 및 테라를 
      밝은 고대비 스타일(#F8F9FA)로 디자인하여 가시성을 극대화합니다.
    """
    def __init__(self, canvas, parent=None):
        super().__init__(canvas, parent)
        self.setStyleSheet("""
            QToolBar {
                background-color: #F8F9FA;
                border: 1px solid #CCCCCC;
                padding: 4px;
                spacing: 6px;
            }
            QToolButton {
                background-color: #FFFFFF;
                color: #111111;
                border: 1px solid #B0BEC5;
                border-radius: 4px;
                padding: 4px 8px;
                font-weight: bold;
            }
            QToolButton:hover {
                background-color: #E3F2FD;
                border: 1px solid #2196F3;
            }
            QToolButton:checked {
                background-color: #BBDEFB;
                border: 1px solid #1976D2;
            }
            QLabel {
                color: #111111;
                font-weight: bold;
            }
        """)


# ==============================================================================
# [팝업 창] 다크 모드 타임라인 간트 차트 (Gantt Chart Dialog)
# ==============================================================================
class GanttChartDialog(QDialog):
    """
    위성 교신 패스 할당 타임라인 시각화 팝업 다이얼로그
    
    [기능 설명]
    - 지상국별 통신 패스 영역을 Horizontal Bar(간트 차트) 형태로 표출합니다.
    - 선택된 패스(Solid Pastel Color)와 경합/차단된 패스(Hatched Gray)를 시각적으로 구별합니다.
    - 돋보기(Zoom) 확상 및 원복(Reset)을 자유롭게 지원하며, 창이 닫힐 때 Matplotlib 메모리를 완전히 해제합니다.
    """
    def __init__(self, calculated_passes, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📊 Multi-Satellite Pass Allocation Gantt Timeline")
        self.resize(1150, 680)
        self.passes = calculated_passes
        self.fig = None  # 메모리 해제용 Figure 참조 보관
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 다크 스마트 그래픽 스타일 적용
        plt.style.use('dark_background')
        self.fig, ax = plt.subplots(figsize=(12, 6), facecolor='#1E1E1E')
        ax.set_facecolor('#262626')
        
        # 지상국 Y축 인덱스 매핑
        stations = sorted(list({p['station'] for p in self.passes}))
        st_y_map = {st: i for i, st in enumerate(stations)}
        
        from core.color_manager import color_manager
        
        # 패스 데이터별 렌더링
        for p in self.passes:
            st = p['station']
            sat_raw = p['satellite']
            sat_clean = sat_raw.split("(")[0].strip()
            
            y_pos = st_y_map[st]
            aos_dt = p['aos']
            los_dt = p['los']
            is_selected = p.get('selected', True)
            
            aos_num = mdates.date2num(aos_dt)
            los_num = mdates.date2num(los_dt)
            width = los_num - aos_num
            
            if is_selected:
                hex_color, _ = color_manager.get_colors(sat_clean)
                face_color = f"#{hex_color}"
                edge_color = "#FFFFFF"
                alpha = 0.95
                hatch = None
            else:
                face_color = "#3A3A3A"
                edge_color = "#777777"
                alpha = 0.5
                hatch = "///"

            # 표준 barh 렌더링
            ax.barh(y_pos, width, left=aos_num, height=0.45, 
                    align='center', color=face_color, edgecolor=edge_color, 
                    alpha=alpha, hatch=hatch, linewidth=0.8)
            
            # 텍스트 인라인 라벨 표출 (선택된 패스만)
            if is_selected and width > 0.0008:
                mid_num = aos_num + (width / 2.0)
                try:
                    mid_date = mdates.num2date(mid_num)
                    ax.text(mid_date, y_pos, sat_clean, ha='center', va='center', 
                            fontsize=8, fontweight='bold', color='#111111', clip_on=True)
                except Exception:
                    pass

        # 축 및 타이틀 레이아웃 구성
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
        """팝업 창이 닫힐 때 Matplotlib 피규어 메모리 완전 해제"""
        if self.fig:
            plt.close(self.fig)
        super().closeEvent(event)

    def accept(self):
        if self.fig:
            plt.close(self.fig)
        super().accept()


# ==============================================================================
# [메인 탭] Tab 1: 위성 가시 패스 예측 및 스케줄 매트릭스 탭
# ==============================================================================
class PassPredictTab(QWidget):
    """
    Tab 1 메인 UI 클래스
    
    [기능 설명]
    - TLE 파일 및 지상국 선택, 시간 창(24시간제) 지정, 고도각/교신시간 필터를 설정합니다.
    - SGP4 연산을 실행하여 가시 패스를 생성하고, 동시 발사 위성 간 Round-Robin 공평 배정 결과를 표로 나타냅니다.
    - CSV, YAML, Colorized Excel 저장 및 간트 차트 팝업 시각화를 제공합니다.
    """
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        self.tle_dir = "tle"
        self.stations_dir = "stations"
        self.pass_output_dir = "pass_output"
        
        if not os.path.exists(self.pass_output_dir):
            os.makedirs(self.pass_output_dir)
            
        self.init_ui()
        self.refresh_tle_files()
        self.refresh_stations()

    def init_ui(self):
        layout = QHBoxLayout(self)
        left_panel = QVBoxLayout()
        
        # ----------------------------------------------------------------------
        # 1. Detected TLE Files 구역
        # ----------------------------------------------------------------------
        left_panel.addWidget(QLabel("<b>1. Detected TLE Files:</b>"))
        self.tle_file_list = QListWidget()
        self.tle_file_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        left_panel.addWidget(self.tle_file_list)
        
        tle_btn_layout = QHBoxLayout()
        self.btn_refresh_tle = QPushButton("Refresh")
        self.btn_refresh_tle.clicked.connect(self.refresh_tle_files)
        tle_btn_layout.addWidget(self.btn_refresh_tle)
        
        self.btn_open_tle_folder = QPushButton("📂 Open Folder")
        self.btn_open_tle_folder.clicked.connect(lambda: self.open_local_folder(self.tle_dir))
        tle_btn_layout.addWidget(self.btn_open_tle_folder)
        
        self.btn_fetch_tle = QPushButton("🌐 Fetch Online")
        self.btn_fetch_tle.setStyleSheet("font-weight: bold; color: #0D47A1;")
        self.btn_fetch_tle.clicked.connect(self.click_fetch_online_tle)
        tle_btn_layout.addWidget(self.btn_fetch_tle)
        
        left_panel.addLayout(tle_btn_layout)
        
        # ----------------------------------------------------------------------
        # 2. Detected Ground Stations 구역
        # ----------------------------------------------------------------------
        left_panel.addWidget(QLabel("<b>2. Detected Ground Stations:</b>"))
        self.gs_list = QListWidget()
        self.gs_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        left_panel.addWidget(self.gs_list)
        
        gs_btn_layout = QHBoxLayout()
        self.btn_refresh_gs = QPushButton("Refresh")
        self.btn_refresh_gs.clicked.connect(self.refresh_stations)
        gs_btn_layout.addWidget(self.btn_refresh_gs)
        
        self.btn_open_gs_folder = QPushButton("📂 Open Folder")
        self.btn_open_gs_folder.clicked.connect(lambda: self.open_local_folder(self.stations_dir))
        gs_btn_layout.addWidget(self.btn_open_gs_folder)
        
        left_panel.addLayout(gs_btn_layout)
        
        # ----------------------------------------------------------------------
        # 3. Time Window (UTC) 구역 (24시간제 적용)
        # ----------------------------------------------------------------------
        left_panel.addWidget(QLabel("<b>3. Time Window (UTC):</b>"))
        now_utc_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        
        left_panel.addWidget(QLabel("Start Time:"))
        self.start_time_edit = QDateTimeEdit(now_utc_naive)
        self.start_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")  # 24시간 표기법
        self.start_time_edit.setCalendarPopup(True)
        left_panel.addWidget(self.start_time_edit)
        
        left_panel.addWidget(QLabel("End Time:"))
        self.end_time_edit = QDateTimeEdit(now_utc_naive + timedelta(days=1))
        self.end_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")  # 24시간 표기법
        self.end_time_edit.setCalendarPopup(True)
        left_panel.addWidget(self.end_time_edit)
        
        # ----------------------------------------------------------------------
        # 4. Filters & Scheduling Rules 구역
        # ----------------------------------------------------------------------
        left_panel.addWidget(QLabel("<b>4. Filters & Scheduling Rules:</b>"))
        el_layout = QHBoxLayout()
        el_layout.addWidget(QLabel("Min El (deg):"))
        self.min_el_spin = QSpinBox()
        self.min_el_spin.setRange(0, 90)
        self.min_el_spin.setValue(5)
        el_layout.addWidget(self.min_el_spin)
        left_panel.addLayout(el_layout)
        
        dur_layout = QHBoxLayout()
        dur_layout.addWidget(QLabel("Min Dur (sec):"))
        self.min_dur_spin = QSpinBox()
        self.min_dur_spin.setRange(0, 3600)
        self.min_dur_spin.setValue(300)
        dur_layout.addWidget(self.min_dur_spin)
        left_panel.addLayout(dur_layout)
        
        pass_no_layout = QHBoxLayout()
        pass_no_layout.addWidget(QLabel("Start Pass No.:"))
        self.start_pass_spin = QSpinBox()
        self.start_pass_spin.setRange(1, 99999)
        self.start_pass_spin.setValue(1)
        pass_no_layout.addWidget(self.start_pass_spin)
        left_panel.addLayout(pass_no_layout)
        
        self.chk_equalize_sat = QCheckBox("Equalize Sat Allocation (Fairness)")
        self.chk_equalize_sat.setChecked(True)
        self.chk_equalize_sat.setToolTip("Rotates pass assignments fairly among swarm/multi-satellites during conflicts.")
        self.chk_equalize_sat.setStyleSheet("font-weight: bold; color: #1B5E20;")
        left_panel.addWidget(self.chk_equalize_sat)
        
        self.lbl_logic_desc = QLabel(
            "<i>ℹ️ Swarm/Multi-sat fair distribution algorithm based on pass count & duration.</i>"
        )
        self.lbl_logic_desc.setWordWrap(True)
        self.lbl_logic_desc.setStyleSheet("color: #555555; font-size: 11px; margin-bottom: 5px; margin-left: 15px;")
        left_panel.addWidget(self.lbl_logic_desc)
        
        self.btn_calculate = QPushButton("Calculate Pass Schedule")
        self.btn_calculate.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        self.btn_calculate.clicked.connect(self.run_scheduling)
        left_panel.addWidget(self.btn_calculate)
        
        layout.addLayout(left_panel, stretch=1)
        
        # ----------------------------------------------------------------------
        # 오른쪽 패널: 매트릭스 테이블 및 컨트롤 버튼 구역
        # ----------------------------------------------------------------------
        right_panel = QVBoxLayout()
        select_all_layout = QHBoxLayout()
        select_all_layout.addWidget(QLabel("<b>Pass Prediction Timeline Matrix:</b>"))
        
        self.btn_open_pass_out = QPushButton("📂 Open Pass Output Folder")
        self.btn_open_pass_out.clicked.connect(lambda: self.open_local_folder(self.pass_output_dir))
        select_all_layout.addWidget(self.btn_open_pass_out)
        
        select_all_layout.addStretch()
        
        self.btn_select_all = QPushButton("☑ Check All")
        self.btn_select_all.setFixedWidth(100)
        self.btn_select_all.clicked.connect(lambda: self.set_all_checkboxes(True))
        select_all_layout.addWidget(self.btn_select_all)
        
        self.btn_unselect_all = QPushButton("☒ Uncheck All")
        self.btn_unselect_all.setFixedWidth(100)
        self.btn_unselect_all.clicked.connect(lambda: self.set_all_checkboxes(False))
        select_all_layout.addWidget(self.btn_unselect_all)
        right_panel.addLayout(select_all_layout)
        
        # 실시간 위성별 요약 대시보드 바
        self.lbl_summary_bar = QLabel("📊 Satellite Pass Distribution Summary: Run calculation to view metrics.")
        self.lbl_summary_bar.setStyleSheet("background-color: #F1F8E9; border: 1px solid #C8E6C9; padding: 6px; font-weight: bold; color: #2E7D32;")
        right_panel.addWidget(self.lbl_summary_bar)
        
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Select", "Ground Station", "Satellite", "Pass No. (Orbit)", "AOS (UTC)", "LOS (UTC)", "Duration (s)", "Max El (deg)", "Status"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setDefaultSectionSize(140)
        
        self.table.itemChanged.connect(self.handle_table_lock)
        right_panel.addWidget(self.table)
        
        # 하단 내보내기 및 간트 차트 버튼 구역
        btn_layout = QHBoxLayout()
        
        self.btn_gantt_chart = QPushButton("📊 View Gantt Timeline Chart")
        self.btn_gantt_chart.setStyleSheet("background-color: #6A1B9A; color: white; font-weight: bold;")
        self.btn_gantt_chart.clicked.connect(self.click_view_gantt_chart)
        btn_layout.addWidget(self.btn_gantt_chart)
        
        self.btn_csv = QPushButton("Export Selected to CSV")
        self.btn_csv.clicked.connect(self.click_export_csv)
        btn_layout.addWidget(self.btn_csv)
        
        self.btn_excel = QPushButton("🎨 Export Selected to Excel (.xlsx)")
        self.btn_excel.setStyleSheet("font-weight: bold; color: #1E7145;")
        self.btn_excel.clicked.connect(self.click_export_excel)
        btn_layout.addWidget(self.btn_excel)
        
        self.btn_yaml = QPushButton("Export Selected to YAML")
        self.btn_yaml.clicked.connect(self.click_export_yaml)
        btn_layout.addWidget(self.btn_yaml)
        
        right_panel.addLayout(btn_layout)
        layout.addLayout(right_panel, stretch=3)

    # --------------------------------------------------------------------------
    # 이벤트 핸들러 및 유틸리티 함수들
    # --------------------------------------------------------------------------
    def open_local_folder(self, folder_path):
        """지정된 로컬 폴더를 탐색기로 엽니다."""
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        abs_path = os.path.abspath(folder_path)
        QDesktopServices.openUrl(QUrl.fromLocalFile(abs_path))

    def refresh_tle_files(self):
        """tle 디렉토리의 TLE 파일 목록을 새로고침하여 리스트에 출력합니다."""
        self.tle_file_list.clear()
        parse_tle_from_dir(self.tle_dir)
        if os.path.exists(self.tle_dir):
            for filename in os.listdir(self.tle_dir):
                if filename.endswith(".tle") or filename.endswith(".txt"):
                    self.tle_file_list.addItem(filename)
        for i in range(self.tle_file_list.count()):
            self.tle_file_list.item(i).setSelected(True)

    def click_fetch_online_tle(self):
        """CelesTrak 온라인 위성 검색 및 TLE 다운로드 다이얼로그 처리"""
        query, ok = QInputDialog.getText(
            self, "CelesTrak Satellite Search", "Enter Satellite Keyword or NORAD CatNR (e.g. NEONSAT, ISS, 39634):"
        )
        if not ok or not query.strip(): return

        success, sat_list, msg = search_satellites_from_celestrak(query)
        if not success or not sat_list:
            QMessageBox.warning(self, "Search Failed", f"Search results for '{query}':\n{msg}\n\n(No changes were made.)")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Select Satellites to Fetch ({len(sat_list)} found)")
        dialog.resize(500, 360)
        
        dlg_layout = QVBoxLayout(dialog)
        dlg_layout.addWidget(QLabel(f"<b>Search Results for '{query}':</b><br>(Use Ctrl / Shift or 'Select All' to download multiple satellites)"))
        
        list_widget = QListWidget()
        list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        
        for sat in sat_list:
            display_text = f"🛰️  {sat['sat_name']}  |  NORAD ID: {sat['norad_id']}  ({sat['int_designator']})"
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, sat)
            list_widget.addItem(item)
            
        dlg_layout.addWidget(list_widget)
        
        select_ctrl_layout = QHBoxLayout()
        btn_sel_all = QPushButton("☑ Select All")
        btn_sel_all.clicked.connect(list_widget.selectAll)
        select_ctrl_layout.addWidget(btn_sel_all)
        
        btn_desel_all = QPushButton("☒ Unselect All")
        btn_desel_all.clicked.connect(list_widget.clearSelection)
        select_ctrl_layout.addWidget(btn_desel_all)
        
        dlg_layout.addLayout(select_ctrl_layout)
        
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        dlg_layout.addWidget(button_box)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_items = list_widget.selectedItems()
            if not selected_items: return
            
            success_count = 0
            failed_sats = []
            
            for item in selected_items:
                sat_data = item.data(Qt.ItemDataRole.UserRole)
                target_norad_id = sat_data['norad_id']
                target_sat_name = sat_data['sat_name']
                
                dl_success, save_path = download_tle_by_norad_id(target_norad_id, target_sat_name, self.tle_dir)
                if dl_success:
                    success_count += 1
                else:
                    failed_sats.append(target_sat_name)
            
            if success_count > 0:
                msg = f"Successfully fetched TLE files for {success_count} satellite(s)."
                if failed_sats:
                    msg += f"\n\nFailed satellites: {', '.join(failed_sats)}"
                QMessageBox.information(self, "Download Complete", msg)
                self.refresh_tle_files()
            else:
                QMessageBox.critical(self, "Download Error", f"Failed to download selected satellites.")

    def refresh_stations(self):
        """지상국 설정 파일 목록을 읽어 리스트를 새로고침합니다."""
        self.gs_list.clear()
        self.main_app.station_data = parse_stations_from_dir(self.stations_dir)
        for cfg in self.main_app.station_data:
            self.gs_list.addItem(f"{cfg[0]} (Lat: {cfg[1]}, Lon: {cfg[2]}) [Down:{cfg[3]} / Cmd:{cfg[4]}]")
        for i in range(self.gs_list.count()):
            self.gs_list.item(i).setSelected(True)

    def run_scheduling(self):
        """선택된 조건으로 SGP4 궤도 연산을 실행하여 통신 패스를 계산합니다."""
        selected_files = [item.text() for item in self.tle_file_list.selectedItems()]
        tle_data = parse_tle_from_dir(self.tle_dir, selected_files)
        selected_stations = [self.main_app.station_data[self.gs_list.row(item)] for item in self.gs_list.selectedItems()]
        
        start_dt = self.start_time_edit.dateTime().toPyDateTime()
        end_dt = self.end_time_edit.dateTime().toPyDateTime()
        if start_dt >= end_dt:
            QMessageBox.critical(self, "Time Window Error", "Start Time must be earlier than End Time!")
            return
            
        min_el = self.min_el_spin.value()
        min_dur = self.min_dur_spin.value()
        start_pass_no = self.start_pass_spin.value()
        equalize = self.chk_equalize_sat.isChecked()
        
        if not tle_data or not selected_stations:
            QMessageBox.warning(self, "Warning", "No TLE files or Ground Stations selected.")
            return
            
        self.main_app.calculated_passes = calculate_passes(
            tle_data, selected_stations, start_dt, end_dt, min_el, min_dur, start_pass_no,
            equalize_allocation=equalize
        )
        self.populate_table()

    def update_summary_dashboard(self):
        """상단 대시보드 바에 위성별 할당 수량 및 누적 통신 시간을 실시간 업데이트합니다."""
        if not self.main_app.calculated_passes:
            self.lbl_summary_bar.setText("📊 Satellite Pass Distribution Summary: No data calculated.")
            return
            
        sat_stats = {}
        for p in self.main_app.calculated_passes:
            sat_clean = p['satellite'].split("(")[0].strip()
            if sat_clean not in sat_stats:
                sat_stats[sat_clean] = {'selected_count': 0, 'total_count': 0, 'total_duration_sec': 0.0}
                
            sat_stats[sat_clean]['total_count'] += 1
            if p.get('selected', False):
                sat_stats[sat_clean]['selected_count'] += 1
                sat_stats[sat_clean]['total_duration_sec'] += float(p.get('duration', 0))
                
        summary_tokens = []
        for sat_name, stats in sorted(sat_stats.items()):
            dur_min = stats['total_duration_sec'] / 60.0
            summary_tokens.append(f"🛰️ <b>{sat_name}</b>: {stats['selected_count']}/{stats['total_count']} passes ({dur_min:.1f} min)")
            
        summary_text = "📊 <b>Pass Allocation Summary:</b> &nbsp;&nbsp;|&nbsp;&nbsp; " + " &nbsp;&nbsp;|&nbsp;&nbsp; ".join(summary_tokens)
        self.lbl_summary_bar.setText(summary_text)

    def populate_table(self):
        """계산된 패스 리스트를 우측 그리드 테이블에 출력합니다."""
        if self.main_app.is_populating: return
        self.table.setRowCount(0)
        if not self.main_app.calculated_passes: return
            
        self.main_app.is_populating = True
        self.table.blockSignals(True)  # 시그널 무한 재귀 호출 방어막
        try:
            self.table.setRowCount(len(self.main_app.calculated_passes))
            from core.color_manager import color_manager
            
            for row_idx, p in enumerate(self.main_app.calculated_passes):
                chk_item = QTableWidgetItem()
                chk_item.setCheckState(Qt.CheckState.Checked if p.get('selected', True) else Qt.CheckState.Unchecked)
                chk_item.setData(Qt.ItemDataRole.UserRole, (row_idx, p.get('conflict_group', None), p['station']))
                self.table.setItem(row_idx, 0, chk_item)
                
                self.table.setItem(row_idx, 1, QTableWidgetItem(p['station']))
                self.table.setItem(row_idx, 2, QTableWidgetItem(p['satellite']))
                self.table.setItem(row_idx, 3, QTableWidgetItem(f"Pass {p['pass_no']}"))
                self.table.setItem(row_idx, 4, QTableWidgetItem(p['aos'].strftime('%Y-%m-%d %H:%M:%S')))
                self.table.setItem(row_idx, 5, QTableWidgetItem(p['los'].strftime('%Y-%m-%d %H:%M:%S')))
                self.table.setItem(row_idx, 6, QTableWidgetItem(str(p['duration'])))
                self.table.setItem(row_idx, 7, QTableWidgetItem(str(p['max_el'])))
                
                status_text = p.get('status', 'Normal')
                self.table.setItem(row_idx, 8, QTableWidgetItem(status_text))
                
                st_raw = p['station'].split("(")[0].strip()
                _, station_bg_color = color_manager.get_station_colors(st_raw)
                
                row_color = QColor(255, 235, 235) if "Conflict" in status_text else station_bg_color
                    
                for col_idx in range(self.table.columnCount()):
                    cell = self.table.item(row_idx, col_idx)
                    if cell: cell.setBackground(row_color)
                    
            self.update_summary_dashboard()
        finally:
            self.table.blockSignals(False)
            self.main_app.is_populating = False

    def click_view_gantt_chart(self):
        """간트 차트 시각화 팝업 창을 호출합니다."""
        if not self.main_app.calculated_passes:
            QMessageBox.warning(self, "Warning", "Please calculate pass schedule first.")
            return
        dialog = GanttChartDialog(self.main_app.calculated_passes, self)
        dialog.exec()

    def handle_table_lock(self, item):
        """동일 지상국 시간 경합 그룹(Conflict Group) 내 배타적 상호 선택 상호작용 처리"""
        if self.main_app.is_populating or item.column() != 0: return
        user_data = item.data(Qt.ItemDataRole.UserRole)
        if not user_data: return
            
        current_row, group_id, station_name = user_data
        if group_id is None:
            self.main_app.calculated_passes[current_row]['selected'] = (item.checkState() == Qt.CheckState.Checked)
            self.update_summary_dashboard()
            return
            
        if item.checkState() == Qt.CheckState.Checked:
            self.main_app.is_populating = True
            try:
                for r in range(self.table.rowCount()):
                    if r == current_row:
                        self.main_app.calculated_passes[r]['selected'] = True
                        continue
                    other_item = self.table.item(r, 0)
                    if other_item is not None and other_item.data(Qt.ItemDataRole.UserRole) is not None:
                        o_row, o_group, o_station = other_item.data(Qt.ItemDataRole.UserRole)
                        if o_station == station_name and o_group == group_id:
                            other_item.setCheckState(Qt.CheckState.Unchecked)
                            self.main_app.calculated_passes[r]['selected'] = False
            finally:
                self.main_app.is_populating = False
            self.populate_table()
        else:
            self.main_app.calculated_passes[current_row]['selected'] = False
            self.main_app.is_populating = True
            try: self.populate_table()
            finally: self.main_app.is_populating = False

    def click_export_csv(self):
        """선택된 패스 목록을 CSV로 저장합니다."""
        if not self.main_app.calculated_passes: return
        path, _ = QFileDialog.getSaveFileName(self, "Save CSV Schedule", self.pass_output_dir, "CSV Files (*.csv)")
        if path: export_to_csv(path, self.main_app.calculated_passes)

    def click_export_yaml(self):
        """선택된 패스 목록을 YAML로 저장합니다."""
        if not self.main_app.calculated_passes: return
        path, _ = QFileDialog.getSaveFileName(self, "Save YAML Schedule", self.pass_output_dir, "YAML Files (*.yaml)")
        if path: export_to_yaml(path, self.main_app.calculated_passes)

    def set_all_checkboxes(self, check_state):
        """표 내의 모든 선택 체크박스를 일괄 선택/해제합니다."""
        if not self.main_app.calculated_passes: return
        self.main_app.is_populating = True
        target_state = Qt.CheckState.Checked if check_state else Qt.CheckState.Unchecked
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item:
                item.setCheckState(target_state)
                self.main_app.calculated_passes[r]['selected'] = check_state
        self.main_app.is_populating = False
        self.populate_table()

    def click_export_excel(self):
        """선택된 패스 목록을 지상국별 파스텔 색상 디자인이 적용된 Excel 파일로 저장합니다."""
        if not self.main_app.calculated_passes: return
        if not any(p['selected'] for p in self.main_app.calculated_passes):
            QMessageBox.warning(self, "Warning", "No passes are selected.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Colorized Excel Schedule", self.pass_output_dir, "Excel Files (*.xlsx)")
        if path:
            success, msg = export_to_excel_with_color(path, self.main_app.calculated_passes)
            if success:
                QMessageBox.information(self, "Export Success", "Excel file generated successfully!")
            else:
                QMessageBox.critical(self, "Export Error", f"Failed to save Excel file:\n{msg}")