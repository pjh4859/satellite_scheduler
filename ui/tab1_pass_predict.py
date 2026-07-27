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


class HighVisibilityNavigationToolbar(NavigationToolbar):
    """다크 배경에서도 돋보기/집/손 아이콘이 100% 선명하게 보이는 고대비 툴바"""
    def __init__(self, canvas, parent=None):
        super().__init__(canvas, parent)
        # 툴바 배경과 텍스트를 고대비 라이트 스타일로 강조
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


class GanttChartDialog(QDialog):
    """고대비 툴바 및 네비게이션이 탑재된 간트 차트 팝업"""
    def __init__(self, calculated_passes, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📊 Multi-Satellite Pass Allocation Gantt Timeline")
        self.resize(1150, 680)
        self.passes = calculated_passes
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(12, 6), facecolor='#1E1E1E')
        ax.set_facecolor('#262626')
        
        stations = sorted(list({p['station'] for p in self.passes}))
        st_y_map = {st: i for i, st in enumerate(stations)}
        
        from core.color_manager import color_manager
        
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

            ax.barh(y_pos, width, left=aos_num, height=0.45, 
                    align='center', color=face_color, edgecolor=edge_color, 
                    alpha=alpha, hatch=hatch, linewidth=0.8)
            
            if is_selected and width > 0.0008:
                mid_num = aos_num + (width / 2.0)
                try:
                    mid_date = mdates.num2date(mid_num)
                    ax.text(mid_date, y_pos, sat_clean, ha='center', va='center', 
                            fontsize=8, fontweight='bold', color='#111111', clip_on=True)
                except Exception:
                    pass

        ax.set_yticks(range(len(stations)))
        ax.set_yticklabels(stations, fontsize=11, fontweight='bold', color='#FFFFFF')
        ax.xaxis_date()
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M', tz=timezone.utc))
        fig.autofmt_xdate()
        
        ax.set_title("Timeline Matrix: Allocated Passes (Solid Pastel) vs Collided / Blocked (Hatched Gray)", 
                     fontsize=12, fontweight='bold', color='#FFFFFF', pad=15)
        ax.set_xlabel("Time (UTC)", fontsize=10, fontweight='bold', color='#DDDDDD')
        
        ax.grid(True, linestyle=':', alpha=0.35, color='#999999')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#777777')
        ax.spines['bottom'].set_color('#777777')
        
        if stations:
            ax.set_ylim(-0.6, len(stations) - 0.4)
            
        fig.subplots_adjust(left=0.12, right=0.96, top=0.90, bottom=0.18)
        
        canvas = FigureCanvas(fig)
        
        # 🔥 [고대비 툴바 연결 - 돋보기/집 아이콘 선명화]
        toolbar = HighVisibilityNavigationToolbar(canvas, self)
        layout.addWidget(toolbar)
        layout.addWidget(canvas)
        
        btn_close = QPushButton("Close Timeline Chart")
        btn_close.setStyleSheet("background-color: #333333; color: white; font-weight: bold; padding: 6px;")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)


class PassPredictTab(QWidget):
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
        
        # 1. Detected TLE Files 구역
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
        
        # 2. Detected Ground Stations 구역
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
        
        # 3. Time Window (UTC) 구역 (24시간 형식 적용)
        left_panel.addWidget(QLabel("<b>3. Time Window (UTC):</b>"))
        now_utc_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        
        left_panel.addWidget(QLabel("Start Time:"))
        self.start_time_edit = QDateTimeEdit(now_utc_naive)
        self.start_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.start_time_edit.setCalendarPopup(True)
        left_panel.addWidget(self.start_time_edit)
        
        left_panel.addWidget(QLabel("End Time:"))
        self.end_time_edit = QDateTimeEdit(now_utc_naive + timedelta(days=1))
        self.end_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.end_time_edit.setCalendarPopup(True)
        left_panel.addWidget(self.end_time_edit)
        
        # 4. Filters 구역
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
        
        # 오른쪽 매트릭스 테이블 구역
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

    def open_local_folder(self, folder_path):
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        abs_path = os.path.abspath(folder_path)
        QDesktopServices.openUrl(QUrl.fromLocalFile(abs_path))

    def refresh_tle_files(self):
        self.tle_file_list.clear()
        parse_tle_from_dir(self.tle_dir)
        if os.path.exists(self.tle_dir):
            for filename in os.listdir(self.tle_dir):
                if filename.endswith(".tle") or filename.endswith(".txt"):
                    self.tle_file_list.addItem(filename)
        for i in range(self.tle_file_list.count()):
            self.tle_file_list.item(i).setSelected(True)

    def click_fetch_online_tle(self):
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
        self.gs_list.clear()
        self.main_app.station_data = parse_stations_from_dir(self.stations_dir)
        for cfg in self.main_app.station_data:
            self.gs_list.addItem(f"{cfg[0]} (Lat: {cfg[1]}, Lon: {cfg[2]}) [Down:{cfg[3]} / Cmd:{cfg[4]}]")
        for i in range(self.gs_list.count()):
            self.gs_list.item(i).setSelected(True)

    def run_scheduling(self):
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
        if self.main_app.is_populating: return
        self.table.setRowCount(0)
        if not self.main_app.calculated_passes: return
            
        self.main_app.is_populating = True
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
            self.main_app.is_populating = False

    def click_view_gantt_chart(self):
        if not self.main_app.calculated_passes:
            QMessageBox.warning(self, "Warning", "Please calculate pass schedule first.")
            return
        dialog = GanttChartDialog(self.main_app.calculated_passes, self)
        dialog.exec()

    def handle_table_lock(self, item):
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
        if not self.main_app.calculated_passes: return
        path, _ = QFileDialog.getSaveFileName(self, "Save CSV Schedule", self.pass_output_dir, "CSV Files (*.csv)")
        if path: export_to_csv(path, self.main_app.calculated_passes)

    def click_export_yaml(self):
        if not self.main_app.calculated_passes: return
        path, _ = QFileDialog.getSaveFileName(self, "Save YAML Schedule", self.pass_output_dir, "YAML Files (*.yaml)")
        if path: export_to_yaml(path, self.main_app.calculated_passes)

    def set_all_checkboxes(self, check_state):
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
        if not self.main_app.calculated_passes: return
        if not any(p['selected'] for p in self.main_app.calculated_passes):
            QMessageBox.warning(self, "Warning", "No passes are selected.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Colorized Excel Schedule", self.pass_output_dir, "Excel Files (*.xlsx)")
        if path:
            try:
                export_to_excel_with_color(path, self.main_app.calculated_passes)
                QMessageBox.information(self, "Export Success", "Excel file generated successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to save Excel file:\n{str(e)}")