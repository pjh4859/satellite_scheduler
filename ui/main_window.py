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
from core.exporter import (export_to_csv, export_to_yaml, export_to_excel_with_color,
                           export_constraints_to_csv, export_constraints_to_excel_color)
from core.plan_parser import (create_default_plan_csv, create_default_plan_excel, 
                               load_plan_csv, load_plan_excel, save_plan_to_yaml, PLAN_HEADERS)

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
        
        # 기본 템플릿 환경 구성 자동 실행 (CSV 및 색상형 엑셀 양식 동시 생성)
        create_default_plan_csv(self.plans_dir)
        create_default_plan_excel(self.plans_dir)
        
        # 동적 항목 추가/삭제에 유연하게 대응하기 위한 헤더 세팅 정보 로드
        self.plan_headers_keys = list(PLAN_HEADERS.keys())
        self.plan_headers_labels = list(PLAN_HEADERS.values())
        
        self.init_ui()
        self.refresh_tle_files()
        self.refresh_stations()
        
    def init_ui(self):
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        self.tab1_pass_calc = QWidget()
        self.tab2_plan_edit = QWidget()
        
        self.tabs.addTab(self.tab1_pass_calc, "1. Ground Station Pass Prediction")
        self.tabs.addTab(self.tab2_plan_edit, "2. Mission Constraints Planner")
        
        self.build_tab1_ui()
        self.build_tab2_ui()

    def build_tab1_ui(self):
        """1번 블록 패스 예측 연산 화면 구조"""
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
        
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
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

    def build_tab2_ui(self):
        """🔥 2번 블록: 신규 동적 제약조건 기준의 유연한 에디터 화면 인터페이스"""
        layout = QVBoxLayout(self.tab2_plan_edit)
        
        top_ctrl = QHBoxLayout()
        self.btn_import_plan_csv = QPushButton("📂 Load Constraint File (Excel / CSV)")
        self.btn_import_plan_csv.setStyleSheet("font-weight: bold; padding: 6px; background-color: #2E7D32; color: white;")
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
        self.plan_table.setColumnCount(len(self.plan_headers_labels))
        self.plan_table.setHorizontalHeaderLabels(self.plan_headers_labels)
        
        # 🔥 [마우스 넓이 조절 적용] Stretch 대신 Interactive 로 설정하여 사용자가 조절 가능하도록 수정!
        self.plan_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.plan_table.horizontalHeader().setDefaultSectionSize(165) # 기본 열 간격 배치 여유 확보
        layout.addWidget(self.plan_table)
        
        # 하단 멀티포맷 익스포트 저장용 컨트롤 바 구축
        bottom_ctrl = QHBoxLayout()
        bottom_ctrl.addWidget(QLabel("<b>Save Options:</b>"))
        
        self.btn_save_plan_csv = QPushButton("Export to CSV")
        self.btn_save_plan_csv.clicked.connect(lambda: self.click_save_plan_file("CSV"))
        bottom_ctrl.addWidget(self.btn_save_plan_csv)
        
        self.btn_save_plan_excel = QPushButton("🎨 Export to Colorized Excel")
        self.btn_save_plan_excel.setStyleSheet("color: #1E7145; font-weight: bold;")
        self.btn_save_plan_excel.clicked.connect(lambda: self.click_save_plan_file("EXCEL"))
        bottom_ctrl.addWidget(self.btn_save_plan_excel)
        
        self.btn_save_plan_yaml = QPushButton("Compile to Constraints YAML")
        self.btn_save_plan_yaml.setStyleSheet("background-color: #008CBA; color: white; font-weight: bold;")
        self.btn_save_plan_yaml.clicked.connect(lambda: self.click_save_plan_file("YAML"))
        bottom_ctrl.addWidget(self.btn_save_plan_yaml)
        
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
        if self.is_populating:
            return
        self.table.setRowCount(0)
        if not self.calculated_passes:
            return
            
        self.is_populating = True
        import os
        tle_dir = "tle"
        for p in self.calculated_passes:
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

        self.table.setRowCount(len(self.calculated_passes))
        for row_idx, p in enumerate(self.calculated_passes):
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
            
            if "Conflict" in status_text:
                conflict_color = QColor(255, 235, 235)
                for col_idx in range(self.table.columnCount()):
                    cell = self.table.item(row_idx, col_idx)
                    if cell:
                        cell.setBackground(conflict_color)
                        
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

    def set_all_checkboxes(self, check_state):
        if not self.calculated_passes:
            return
        self.is_populating = True
        target_state = Qt.CheckState.Checked if check_state else Qt.CheckState.Unchecked
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item:
                item.setCheckState(target_state)
                self.calculated_passes[r]['selected'] = check_state
        self.is_populating = False
        self.populate_table()

    def click_export_excel(self):
        if not self.calculated_passes: return
        if not any(p['selected'] for p in self.calculated_passes):
            QMessageBox.warning(self, "Warning", "No passes are selected.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Colorized Excel Schedule", "", "Excel Files (*.xlsx)")
        if path:
            try:
                export_to_excel_with_color(path, self.calculated_passes)
                QMessageBox.information(self, "Export Success", "Excel file generated successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to save Excel file:\n{str(e)}")

    # --- 🔥 2번 탭 미션 제약조건 및 액티비티 명세 연동 비즈니스 로직 함수군 ---
    def click_import_constraints(self):
        """제약조건 엑셀(.xlsx) 또는 CSV 파일을 동적으로 탐색하여 GUI 그리드에 연동"""
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Constraints File", self.plans_dir, "Supported Files (*.xlsx *.csv)"
        )
        if not path:
            return
            
        try:
            from core.plan_parser import load_plan_csv, load_plan_excel
            if path.endswith(".xlsx"):
                plan_rows = load_plan_excel(path)
            else:
                plan_rows = load_plan_csv(path)
                
            self.populate_plan_table_ui(plan_rows)
            QMessageBox.information(self, "Loaded", f"Successfully loaded {len(plan_rows)} activity records.")
        except Exception as e:
            QMessageBox.critical(self, "Parser Error", f"Failed to load constraints data:\n{str(e)}")

    def populate_plan_table_ui(self, plan_rows):
        """🔥 [신규 완성본] 입력 명세를 2번 탭 그리드에 들이붓고 위성 이름별 가로줄 자동 채색"""
        self.plan_table.setRowCount(0)
        self.plan_table.setRowCount(len(plan_rows))
        
        # 위성별 GUI 가로줄 파스텔톤 컬러 필터 정의 (가독성 증대용)
        gui_sat_colors = {
            "NEONSAT1": QColor(240, 248, 255),    # 은은한 앨리스 블루
            "SPACEEYE-T1": QColor(255, 253, 240), # 부드러운 연아이보리색
            "DEFAULT": QColor(255, 255, 255)      # 기본 흰색
        }
        
        for row_idx, data in enumerate(plan_rows):
            sat_name = data.get("satellite", "").upper().strip()
            bg_color = gui_sat_colors.get(sat_name, gui_sat_colors["DEFAULT"])
            
            # 동적 헤더 키 정의 배열 순서대로 셀 데이터 배치
            for col_idx, key in enumerate(self.plan_headers_keys):
                cell_text = data.get(key, "")
                item = QTableWidgetItem(cell_text)
                item.setBackground(bg_color)  # 위성 이름에 따른 다채로운 가로줄 마킹
                self.plan_table.setItem(row_idx, col_idx, item)

    def click_add_plan_row(self):
        """GUI 내 즉시 실시간 액티비티 행 삽입 및 데이터 자동 동기화"""
        curr_idx = self.plan_table.rowCount()
        self.plan_table.insertRow(curr_idx)
        
        # 유저님의 새로운 컬럼 사양에 맞춘 기본값 더미 생성
        default_row = ["NEONSAT1", "NEW_ACTIVITY", f"30{curr_idx}", "None", "120", "N", "Medium"]
        for col_idx, text in enumerate(default_row):
            item = QTableWidgetItem(text)
            self.plan_table.setItem(curr_idx, col_idx, item)
            
        # 가로줄 색상 자동 업데이트 동기화
        self.refresh_plan_colors_from_ui()

    def click_delete_plan_row(self):
        curr_row = self.plan_table.currentRow()
        if curr_row >= 0:
            self.plan_table.removeRow(curr_row)
            self.refresh_plan_colors_from_ui()
        else:
            QMessageBox.warning(self, "Warning", "Please select an activity row to delete first.")

    def refresh_plan_colors_from_ui(self):
        """현재 그리드 상태를 읽어 위성별 행 컬러를 즉시 재계산"""
        extracted = self.extract_plan_data_from_ui_grid()
        self.populate_plan_table_ui(extracted)

    def extract_plan_data_from_ui_grid(self):
        """그리드 셀 매트릭스로부터 동적 딕셔너리 구조 추출"""
        row_count = self.plan_table.rowCount()
        extracted_data = []
        for r in range(row_count):
            row_dict = {}
            for col_idx, key in enumerate(self.plan_headers_keys):
                cell = self.plan_table.item(r, col_idx)
                row_dict[key] = cell.text().strip() if cell else ""
            extracted_data.append(row_dict)
        return extracted_data

    def click_save_plan_file(self, format_type):
        """🔥 [신규 추가] GUI상에서 직접 추가/수정된 명세를 엑셀/CSV/YAML 로 골라 다운로드하는 연동 스위치"""
        extracted_data = self.extract_plan_data_from_ui_grid()
        if not extracted_data:
            QMessageBox.warning(self, "No Data", "There are no activities to export.")
            return
            
        if format_type == "YAML":
            path, _ = QFileDialog.getSaveFileName(self, "Save Constraints YAML", self.plans_dir, "YAML Files (*.yaml)")
            if path:
                save_plan_to_yaml(path, extracted_data)
                QMessageBox.information(self, "Success", "Mission constraints compiled to YAML successfully.")
        
        elif format_type == "CSV":
            path, _ = QFileDialog.getSaveFileName(self, "Save Constraints CSV", self.plans_dir, "CSV Files (*.csv)")
            if path:
                export_constraints_to_csv(path, extracted_data, self.plan_headers_labels)
                QMessageBox.information(self, "Success", "Constraints CSV backup saved successfully.")
                
        elif format_type == "EXCEL":
            path, _ = QFileDialog.getSaveFileName(self, "Save Constraints Excel", self.plans_dir, "Excel Files (*.xlsx)")
            if path:
                export_constraints_to_excel_color(path, extracted_data, self.plan_headers_labels)
                QMessageBox.information(self, "Success", "Colorized Excel Constraints sheet saved successfully.")

if __name__ == "__main__":
    app = sys.argv
    # PyQt6 앱 실행 가동 구문 생략 방지
    from PyQt6.QtWidgets import QApplication
    q_app = QApplication(app)
    window = SatelliteSchedulerApp()
    window.show()
    sys.exit(q_app.exec())