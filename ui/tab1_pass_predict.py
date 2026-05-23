import os
from datetime import datetime, timedelta, timezone
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, 
                             QDateTimeEdit, QSpinBox, QPushButton, QTableWidget, 
                             QTableWidgetItem, QLabel, QFileDialog, QHeaderView, QMessageBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from core.scheduler import parse_tle_from_dir, parse_stations_from_dir, calculate_passes
from core.exporter import export_to_csv, export_to_yaml, export_to_excel_with_color

class PassPredictTab(QWidget):
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app  # 메인 데이터 동기화를 위해 참조 유지
        self.tle_dir = "tle"
        self.stations_dir = "stations"
        self.init_ui()
        self.refresh_tle_files()
        self.refresh_stations()

    def init_ui(self):
        layout = QHBoxLayout(self)
        left_panel = QVBoxLayout()
        
        left_panel.addWidget(QLabel("<b>1. Detected TLE Files:</b>"))
        self.tle_file_list = QListWidget()
        self.tle_file_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        left_panel.addWidget(self.tle_file_list)
        
        self.btn_refresh_tle = QPushButton("Refresh TLE Folder")
        self.btn_refresh_tle.clicked.connect(self.refresh_tle_files)
        left_panel.addWidget(self.btn_refresh_tle)
        
        left_panel.addWidget(QLabel("<b>2. Detected Ground Stations:</b>"))
        self.gs_list = QListWidget()
        self.gs_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        left_panel.addWidget(self.gs_list)
        
        self.btn_refresh_gs = QPushButton("Refresh Stations Folder")
        self.btn_refresh_gs.clicked.connect(self.refresh_stations)
        left_panel.addWidget(self.btn_refresh_gs)
        
        left_panel.addWidget(QLabel("<b>3. Time Window (UTC):</b>"))
        now_utc_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        
        left_panel.addWidget(QLabel("Start Time:"))
        self.start_time_edit = QDateTimeEdit(now_utc_naive)
        self.start_time_edit.setCalendarPopup(True)
        left_panel.addWidget(self.start_time_edit)
        
        left_panel.addWidget(QLabel("End Time:"))
        self.end_time_edit = QDateTimeEdit(now_utc_naive + timedelta(days=1))
        self.end_time_edit.setCalendarPopup(True)
        left_panel.addWidget(self.end_time_edit)
        
        left_panel.addWidget(QLabel("<b>4. Filters:</b>"))
        el_layout = QHBoxLayout()
        el_layout.addWidget(QLabel("Min El (deg):"))
        self.min_el_spin = QSpinBox()
        self.min_el_spin.setRange(0, 90)
        self.min_el_spin.setValue(10)
        el_layout.addWidget(self.min_el_spin)
        left_panel.addLayout(el_layout)
        
        dur_layout = QHBoxLayout()
        dur_layout.addWidget(QLabel("Min Dur (sec):"))
        self.min_dur_spin = QSpinBox()
        self.min_dur_spin.setRange(0, 3600)
        self.min_dur_spin.setValue(300)
        dur_layout.addWidget(self.min_dur_spin)
        left_panel.addLayout(dur_layout)
        
        self.btn_calculate = QPushButton("Calculate Pass Schedule")
        self.btn_calculate.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        self.btn_calculate.clicked.connect(self.run_scheduling)
        left_panel.addWidget(self.btn_calculate)
        
        layout.addLayout(left_panel, stretch=1)
        
        right_panel = QVBoxLayout()
        select_all_layout = QHBoxLayout()
        select_all_layout.addWidget(QLabel("<b>Pass Prediction Timeline Matrix:</b>"))
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
        
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Select", "Ground Station", "Satellite", "Pass No. (Orbit)", "AOS (UTC)", "LOS (UTC)", "Duration (s)", "Max El (deg)", "Status"
        ])
        # 🔥 [마우스 폭 조절 연동] Stretch 대신 Interactive 모드로 변경하여 마우스 드래그를 활성화합니다.
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setDefaultSectionSize(140)  # 초기 로드 시 각 열의 기본 너비 설정
        
        self.table.itemChanged.connect(self.handle_table_lock)
        right_panel.addWidget(self.table)
        
        btn_layout = QHBoxLayout()
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

    def refresh_tle_files(self):
        self.tle_file_list.clear()
        parse_tle_from_dir(self.tle_dir)
        for filename in os.listdir(self.tle_dir):
            if filename.endswith(".tle") or filename.endswith(".txt"):
                self.tle_file_list.addItem(filename)
        for i in range(self.tle_file_list.count()):
            self.tle_file_list.item(i).setSelected(True)

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
        if not tle_data or not selected_stations:
            QMessageBox.warning(self, "Warning", "No TLE files or Ground Stations selected.")
            return
            
        self.main_app.calculated_passes = calculate_passes(tle_data, selected_stations, start_dt, end_dt, min_el, min_dur)
        self.populate_table()

    def populate_table(self):
        """계산된 패스 데이터를 UI 테이블 상에 렌더링 (지상국별 실시간 동적 채색 반영)"""
        if self.main_app.is_populating:
            return
        self.table.setRowCount(0)
        if not self.main_app.calculated_passes:
            return
            
        self.main_app.is_populating = True
        
        try:
            import os
            tle_dir = "tle"
            for p in self.main_app.calculated_passes:
                sat_key = p['satellite']
                if "(" not in sat_key:
                    clean_id = sat_key.replace("SAT_", "").strip()
                    pure_file_name = sat_key
                    if os.path.exists(tle_dir):
                        for filename in os.listdir(tle_dir):
                            if filename.endswith(".tle") or filename.endswith(".txt"):
                                try:
                                    with open(os.path.join(tle_dir, filename), "r", encoding="utf-8") as f:
                                        content = f.read()
                                    if clean_id in content:
                                        pure_file_name = os.path.splitext(filename)[0]
                                        break
                                except:
                                    continue
                    p['satellite'] = f"{pure_file_name}({clean_id})"

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
                
                # 🔥 [하드코딩 완전 제거]: 새로운 지상국 명칭이 들어와도 실시간으로 고유 파스텔톤 추출
                st_raw = p['station'].split("(")[0].strip()
                _, station_bg_color = color_manager.get_station_colors(st_raw)
                
                # 경합 행은 식별을 위해 연핑크 고정, 정상 행은 지상국별 유동 컬러 자동 주입
                if "Conflict" in status_text:
                    row_color = QColor(255, 235, 235)
                else:
                    row_color = station_bg_color
                    
                for col_idx in range(self.table.columnCount()):
                    cell = self.table.item(row_idx, col_idx)
                    if cell:
                        cell.setBackground(row_color)
        finally:
            self.main_app.is_populating = False

    def handle_table_lock(self, item):
        """체크박스 상호 배제 잠금 메커니즘 (안전한 신호 차단 스위치 장착형)"""
        if self.main_app.is_populating or item.column() != 0:
            return
            
        user_data = item.data(Qt.ItemDataRole.UserRole)
        if not user_data: 
            return
            
        current_row, group_id, station_name = user_data
        if group_id is None:
            self.main_app.calculated_passes[current_row]['selected'] = (item.checkState() == Qt.CheckState.Checked)
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
            try:
                self.populate_table()
            finally:
                self.main_app.is_populating = False

    def click_export_csv(self):
        """🔥 [더미 데이터 완전 차단] 오직 GUI 화면에서 '선택된(selected=True)' 패스만 격리하여 CSV로 백업"""
        if not self.main_app.calculated_passes: 
            QMessageBox.warning(self, "Warning", "No calculated passes available to export.")
            return
            
        # 백엔드 버퍼 전체를 던지지 않고, 오직 체크박스가 살아있는 정제 데이터만 필터링
        selected_only = [p for p in self.main_app.calculated_passes if p.get('selected', True)]
        if not selected_only:
            QMessageBox.warning(self, "Warning", "No passes are currently selected in the timeline.")
            return
            
        path, _ = QFileDialog.getSaveFileName(self, "Save CSV Schedule", "", "CSV Files (*.csv)")
        if path: 
            export_to_csv(path, selected_only)
            QMessageBox.information(self, "Export Success", f"Successfully exported {len(selected_only)} active passes to CSV.")

    def click_export_yaml(self):
        """🔥 [버그 영구 박멸] 고스트 킹세종 더미 데이터 유입을 차단하고, 체크된 유효 타임라인만 YAML 빌드"""
        if not self.main_app.calculated_passes: 
            QMessageBox.warning(self, "Warning", "No calculated passes available to export.")
            return
            
        # 오직 체크가 유효한 행들만 추출하여 누적 고스트 버퍼 원천 봉쇄
        selected_only = [p for p in self.main_app.calculated_passes if p.get('selected', True)]
        if not selected_only:
            QMessageBox.warning(self, "Warning", "No passes are currently selected in the timeline.")
            return
            
        path, _ = QFileDialog.getSaveFileName(self, "Save YAML Schedule", "", "YAML Files (*.yaml)")
        if path: 
            export_to_yaml(path, selected_only)
            QMessageBox.information(self, "Export Success", f"Successfully compiled {len(selected_only)} active passes to YAML.")

    def click_export_excel(self):
        """🎨 [색상 동기화 통합형] 오직 선택된 행들만 필터링하여 이쁜 파스텔톤 엑셀 레이어 덤프"""
        if not self.main_app.calculated_passes: 
            QMessageBox.warning(self, "Warning", "No calculated passes available to export.")
            return
            
        selected_only = [p for p in self.main_app.calculated_passes if p.get('selected', True)]
        if not selected_only:
            QMessageBox.warning(self, "Warning", "No passes are currently selected in the timeline.")
            return
            
        path, _ = QFileDialog.getSaveFileName(self, "Save Colorized Excel Schedule", "", "Excel Files (*.xlsx)")
        if path:
            try:
                export_to_excel_with_color(path, selected_only)
                QMessageBox.information(self, "Export Success", f"Successfully generated colorized spreadsheet for {len(selected_only)} passes!")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to save Excel file:\n{str(e)}")

    def set_all_checkboxes(self, check_state):
        if not self.main_app.calculated_passes:
            return
        self.main_app.is_populating = True
        target_state = Qt.CheckState.Checked if check_state else Qt.CheckState.Unchecked
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item:
                item.setCheckState(target_state)
                self.main_app.calculated_passes[r]['selected'] = check_state
        self.main_app.is_populating = False
        self.populate_table()    