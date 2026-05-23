import sys
import os
from datetime import datetime, timedelta, timezone
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QListWidget, QDateTimeEdit, QSpinBox, QPushButton, 
                             QTableWidget, QTableWidgetItem, QLabel, QFileDialog, 
                             QHeaderView, QMessageBox, QTabWidget, QComboBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from core.scheduler import parse_tle_from_dir, parse_stations_from_dir, calculate_passes
from core.exporter import export_to_csv, export_to_yaml
from core.plan_parser import create_default_plan_csv, load_plan_csv, save_plan_to_yaml

class SatelliteSchedulerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LEOP Ground Segment Integrated Operations Planner")
        self.setGeometry(100, 100, 1400, 750)
        
        self.calculated_passes = []
        self.is_populating = False
        self.tle_dir = "tle"
        self.stations_dir = "stations"
        self.plans_dir = "plans"
        self.station_data = []
        
        # 기본 템플릿 환경 구성 자동 실행
        create_default_plan_csv(self.plans_dir)
        
        self.init_ui()
        self.refresh_tle_files()
        self.refresh_stations()
        
    def init_ui(self):
        # 최상위 탭 구조 매핑
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # 탭 등록
        self.tab1_pass_calc = QWidget()
        self.tab2_plan_edit = QWidget()
        
        self.tabs.addTab(self.tab1_pass_calc, "1. Ground Station Pass Prediction")
        self.tabs.addTab(self.tab2_plan_edit, "2. Mission Constraints Planner (Hybrid Editor)")
        
        self.build_tab1_ui()
        self.build_tab2_ui()

    def build_tab1_ui(self):
        """기존 1번 블록 패스 예측 연산 화면 구조"""
        layout = QHBoxLayout(self.tab1_pass_calc)
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
        right_panel.addWidget(QLabel("<b>Pass Prediction Timeline Matrix:</b>"))
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Select", "Satellite", "Pass No. (Orbit)", "Ground Station", "AOS (UTC)", "LOS (UTC)", "Duration (s)", "Max El (deg)", "Status"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemChanged.connect(self.handle_table_lock)
        right_panel.addWidget(self.table)
        
        btn_layout = QHBoxLayout()
        self.btn_csv = QPushButton("Export Predicted Passes (CSV)")
        self.btn_csv.clicked.connect(self.click_export_csv)
        btn_layout.addWidget(self.btn_csv)
        
        self.btn_yaml = QPushButton("Export Predicted Passes (YAML)")
        self.btn_yaml.clicked.connect(self.click_export_yaml)
        btn_layout.addWidget(self.btn_yaml)
        
        right_panel.addLayout(btn_layout)
        layout.addLayout(right_panel, stretch=3)

    def build_tab2_ui(self):
        """🔥 2번 블록: 하이브리드 미션 플랜 제약조건 전용 에디터 인터페이스"""
        layout = QVBoxLayout(self.tab2_plan_edit)
        
        top_ctrl = QHBoxLayout()
        self.btn_import_plan_csv = QPushButton("📂 Load Constraint CSV File")
        self.btn_import_plan_csv.setStyleSheet("font-weight: bold; padding: 6px;")
        self.btn_import_plan_csv.clicked.connect(self.click_import_constraints)
        top_ctrl.addWidget(self.btn_import_plan_csv)
        
        self.btn_add_row = QPushButton("➕ Add New Activity")
        self.btn_add_row.clicked.connect(self.click_add_plan_row)
        top_ctrl.addWidget(self.btn_add_row)
        
        self.btn_delete_row = QPushButton("❌ Delete Selected Activity")
        self.btn_delete_row.clicked.connect(self.click_delete_plan_row)
        top_ctrl.addWidget(self.btn_delete_row)
        
        top_ctrl.addStretch()
        layout.addLayout(top_ctrl)
        
        # 제약 조건 명세 테이블 그리드
        self.plan_table = QTableWidget()
        self.plan_table.setColumnCount(10)
        self.plan_table.setHorizontalHeaderLabels([
            "Satellite ID", "Activity ID", "Activity Name", "Est Duration (s)", 
            "Min Contact Req (s)", "Pre-Requisite ID", "Min Gap (s)", "Target Station", "Target Pass No", "Priority"
        ])
        self.plan_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.plan_table)
        
        bottom_ctrl = QHBoxLayout()
        bottom_ctrl.addStretch()
        self.btn_export_plan_yaml = QPushButton("💾 Compile and Export to Mission Constraints YAML")
        self.btn_export_plan_yaml.setStyleSheet("background-color: #008CBA; color: white; font-weight: bold; padding: 10px;")
        self.btn_export_plan_yaml.clicked.connect(self.click_export_constraints_yaml)
        bottom_ctrl.addWidget(self.btn_export_plan_yaml)
        layout.addLayout(bottom_ctrl)

    # --- 1번 탭 연동 비즈니스 로직 함수군 ---
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
        self.station_data = parse_stations_from_dir(self.stations_dir)
        for cfg in self.station_data:
            # UI 레이블 표출 시 다운로드/커맨딩 유무 플래그를 함께 가시화하여 가독성 증대
            self.gs_list.addItem(f"{cfg[0]} (Lat: {cfg[1]}, Lon: {cfg[2]}) [Down:{cfg[3]} / Cmd:{cfg[4]}]")
        for i in range(self.gs_list.count()):
            self.gs_list.item(i).setSelected(True)

    def run_scheduling(self):
        selected_files = [item.text() for item in self.tle_file_list.selectedItems()]
        tle_data = parse_tle_from_dir(self.tle_dir, selected_files)
        selected_stations = [self.station_data[self.gs_list.row(item)] for item in self.gs_list.selectedItems()]
        
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
            
        self.calculated_passes = calculate_passes(tle_data, selected_stations, start_dt, end_dt, min_el, min_dur)
        self.populate_table()

    def populate_table(self):
        self.is_populating = True
        self.table.setRowCount(0)
        for row_idx, p in enumerate(self.calculated_passes):
            self.table.insertRow(row_idx)
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk_item.setCheckState(Qt.CheckState.Checked if p['selected'] else Qt.CheckState.Unchecked)
            chk_item.setData(Qt.ItemDataRole.UserRole, (row_idx, p['conflict_group'], p['station']))
            self.table.setItem(row_idx, 0, chk_item)
            
            self.table.setItem(row_idx, 1, QTableWidgetItem(p['satellite']))
            self.table.setItem(row_idx, 2, QTableWidgetItem(f"Pass {p['pass_no']}"))
            self.table.setItem(row_idx, 3, QTableWidgetItem(p['station']))
            self.table.setItem(row_idx, 4, QTableWidgetItem(p['aos'].strftime('%Y-%m-%d %H:%M:%S')))
            self.table.setItem(row_idx, 5, QTableWidgetItem(p['los'].strftime('%Y-%m-%d %H:%M:%S')))
            self.table.setItem(row_idx, 6, QTableWidgetItem(str(p['duration'])))
            self.table.setItem(row_idx, 7, QTableWidgetItem(str(p['max_el'])))
            
            status_item = QTableWidgetItem(p['status'])
            self.table.setItem(row_idx, 8, status_item)
            bg_color = QColor(255, 235, 235) if "Conflict" in p['status'] else QColor(240, 248, 240)
            for col in range(self.table.columnCount()):
                self.table.item(row_idx, col).setBackground(bg_color)
        self.is_populating = False

    def handle_table_lock(self, item):
        if self.is_populating or item.column() != 0:
            return
        user_data = item.data(Qt.ItemDataRole.UserRole)
        if not user_data: return
        current_row, group_id, station_name = user_data
        if group_id is None:
            self.calculated_passes[current_row]['selected'] = (item.checkState() == Qt.CheckState.Checked)
            return
        if item.checkState() == Qt.CheckState.Checked:
            self.is_populating = True
            for r in range(self.table.rowCount()):
                if r == current_row:
                    self.calculated_passes[r]['selected'] = True
                    continue
                other_item = self.table.item(r, 0)
                o_row, o_group, o_station = other_item.data(Qt.ItemDataRole.UserRole)
                if o_station == station_name and o_group == group_id:
                    other_item.setCheckState(Qt.CheckState.Unchecked)
                    self.calculated_passes[r]['selected'] = False
            self.is_populating = False
            self.populate_table()
        else:
            self.calculated_passes[current_row]['selected'] = False
            self.populate_table()

    def click_export_csv(self):
        if not self.calculated_passes: return
        path, _ = QFileDialog.getSaveFileName(self, "Save CSV Schedule", "", "CSV Files (*.csv)")
        if path: export_to_csv(path, self.calculated_passes)

    def click_export_yaml(self):
        if not self.calculated_passes: return
        path, _ = QFileDialog.getSaveFileName(self, "Save YAML Schedule", "", "YAML Files (*.yaml)")
        if path: export_to_yaml(path, self.calculated_passes)

    # --- 🔥 2번 탭 하이브리드 계획 편집기 비즈니스 로직 함수군 ---
    def click_import_constraints(self):
        """제약조건 엑셀(CSV) 파일을 읽어 GUI 그리드에 데이터 연동"""
        path, _ = QFileDialog.getOpenFileName(self, "Open Constraints CSV", self.plans_dir, "CSV Files (*.csv)")
        if not path:
            return
            
        try:
            plan_rows = load_plan_csv(path)
            self.plan_table.setRowCount(0)
            
            for row_idx, item in enumerate(plan_rows):
                self.insert_plan_row_into_ui(row_idx, item)
            QMessageBox.information(self, "Loaded", f"Successfully loaded {len(plan_rows)} constraint records.")
        except Exception as e:
            QMessageBox.critical(self, "Parser Error", f"Failed to parse target CSV:\n{str(e)}")

    def insert_plan_row_into_ui(self, row_idx, data_dict):
        """특정 도메인 딕셔너리 데이터를 기반으로 GUI 표 내부에 셀 아이템화 및 콤보박스 임베딩 처리"""
        self.plan_table.insertRow(row_idx)
        self.plan_table.setItem(row_idx, 0, QTableWidgetItem(data_dict["satellite"]))
        self.plan_table.setItem(row_idx, 1, QTableWidgetItem(data_dict["act_id"]))
        self.plan_table.setItem(row_idx, 2, QTableWidgetItem(data_dict["act_name"]))
        self.plan_table.setItem(row_idx, 3, QTableWidgetItem(data_dict["est_dur"]))
        self.plan_table.setItem(row_idx, 4, QTableWidgetItem(data_dict["min_contact"]))
        self.plan_table.setItem(row_idx, 5, QTableWidgetItem(data_dict["pre_id"]))
        self.plan_table.setItem(row_idx, 6, QTableWidgetItem(data_dict["min_gap"]))
        self.plan_table.setItem(row_idx, 7, QTableWidgetItem(data_dict["target_station"]))
        self.plan_table.setItem(row_idx, 8, QTableWidgetItem(data_dict["target_pass"]))
        
        # 우선순위는 선택 범주 오류 차단을 위한 QComboBox 마운트 처리 (None 공백 선택 허용)
        combo = QComboBox()
        combo.addItems(["", "High", "Medium", "Low"])
        combo.setCurrentText(data_dict["priority"])
        self.plan_table.setCellWidget(row_idx, 9, combo)

    def click_add_plan_row(self):
        """GUI 내 즉시 생성용 빈 아이템 더미 행 추가 기능"""
        curr_row = self.plan_table.rowCount()
        dummy = {
            "satellite": "SAT_67614", "act_id": "999", "act_name": "NEW_ACT",
            "est_dur": "60", "min_contact": "60", "pre_id": "None", "min_gap": "0",
            "target_station": "Any", "target_pass": "Any", "priority": ""
        }
        self.insert_plan_row_into_ui(curr_row, dummy)

    def click_delete_plan_row(self):
        """사용자가 선택한 포커스 행 삭제"""
        curr_row = self.plan_table.currentRow()
        if curr_row >= 0:
            self.plan_table.removeRow(curr_row)
        else:
            QMessageBox.warning(self, "Warning", "Please select an activity row to delete first.")

    def click_export_constraints_yaml(self):
        """GUI 상의 변동 사항 수집, 유효성 검증 후 최종 미션 가이드 규칙 파일 생성"""
        row_count = self.plan_table.rowCount()
        if row_count == 0:
            QMessageBox.warning(self, "No Data", "There are no constraints to export.")
            return
            
        extracted_data = []
        for r in range(row_count):
            try:
                sat = self.plan_table.item(r, 0).text().strip() if self.plan_table.item(r, 0) else ""
                aid = self.plan_table.item(r, 1).text().strip() if self.plan_table.item(r, 1) else ""
                aname = self.plan_table.item(r, 2).text().strip() if self.plan_table.item(r, 2) else ""
                
                if not sat or not aid or not aname:
                    QMessageBox.critical(self, "Validation Error", f"Row {r+1} contains empty core fields (Satellite/ID/Name).")
                    return
                    
                combo_widget = self.plan_table.cellWidget(r, 9)
                prio = combo_widget.currentText() if combo_widget else ""
                
                extracted_data.append({
                    "satellite": sat,
                    "act_id": aid,
                    "act_name": aname,
                    "est_dur": self.plan_table.item(r, 3).text().strip() if self.plan_table.item(r, 3) else "0",
                    "min_contact": self.plan_table.item(r, 4).text().strip() if self.plan_table.item(r, 4) else "0",
                    "pre_id": self.plan_table.item(r, 5).text().strip() if self.plan_table.item(r, 5) else "None",
                    "min_gap": self.plan_table.item(r, 6).text().strip() if self.plan_table.item(r, 6) else "0",
                    "target_station": self.plan_table.item(r, 7).text().strip() if self.plan_table.item(r, 7) else "Any",
                    "target_pass": self.plan_table.item(r, 8).text().strip() if self.plan_table.item(r, 8) else "Any",
                    "priority": prio
                })
            except AttributeError:
                QMessageBox.critical(self, "Data Error", f"Critical cell formatting failure on Row {r+1}.")
                return
                
        path, _ = QFileDialog.getSaveFileName(self, "Save Rules YAML", self.plans_dir, "YAML Files (*.yaml)")
        if path:
            save_plan_to_yaml(path, extracted_data)
            QMessageBox.information(self, "Compiled", "Mission constraints compiled and exported successfully.")