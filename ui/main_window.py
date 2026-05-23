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
from core.exporter import export_to_csv, export_to_yaml, export_to_excel_with_color
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
        """기존 1번 블록 패스 예측 연산 화면 구조 (전체 선택/해제 및 엑셀 버튼 확장)"""
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
        
        # --- 우측 결과 매트릭스 패널 영역 ---
        right_panel = QVBoxLayout()
        
        # 🔥 [신규] 전체 선택 / 전체 해제 미니 컨트롤 바 레이아웃 추가
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
        # 🔥 [순서 변경] Ground Station, Satellite, Pass No. 순으로 헤더 전면 재배치
        self.table.setHorizontalHeaderLabels([
            "Select", "Ground Station", "Satellite", "Pass No. (Orbit)", "AOS (UTC)", "LOS (UTC)", "Duration (s)", "Max El (deg)", "Status"
        ])
        
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemChanged.connect(self.handle_table_lock)
        right_panel.addWidget(self.table)
        
        # 하단 익스포트 버튼 레이아웃
        btn_layout = QHBoxLayout()
        self.btn_csv = QPushButton("Export Selected to CSV")
        self.btn_csv.clicked.connect(self.click_export_csv)
        btn_layout.addWidget(self.btn_csv)
        
        # 🔥 [신규] 알록달록 엑셀 출력 전용 버튼 마운트
        self.btn_excel = QPushButton("🎨 Export Selected to Excel (.xlsx)")
        self.btn_excel.setStyleSheet("font-weight: bold; color: #1E7145;") # 엑셀 시그니처 초록색 폰트
        self.btn_excel.clicked.connect(self.click_export_excel)
        btn_layout.addWidget(self.btn_excel)
        
        self.btn_yaml = QPushButton("Export Selected to YAML")
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
        """계산된 패스 데이터를 UI 테이블 상에 렌더링 (무한 루프 방지 및 위성 명칭 실시간 역추적 완비)"""
        if self.is_populating:
            return
            
        self.table.setRowCount(0)
        if not self.calculated_passes:
            return
            
        # 🔥 1단계: 시그널 연동 무한 루프(RecursionError) 차단용 락킹 활성화
        self.is_populating = True
        
        # -----------------------------------------------------------------
        # 🔥 2단계: 기존 'SAT_67614' 구조를 'NEONSAT1(67614)' 형태로 변환하는 전처리
        # -----------------------------------------------------------------
        import os
        tle_dir = "tle"
        for p in self.calculated_passes:
            sat_key = p['satellite']  # 예: "SAT_67614"
            if "(" not in sat_key:    # 이미 가공된 포맷이 아닐 때만 역추적 수행
                clean_id = sat_key.replace("SAT_", "").strip()
                pure_file_name = sat_key  # 파일 검색 실패 시 기본값 방어
                
                if os.path.exists(tle_dir):
                    for filename in os.listdir(tle_dir):
                        if filename.endswith(".tle") or filename.endswith(".txt"):
                            try:
                                with open(os.path.join(tle_dir, filename), "r", encoding="utf-8") as f:
                                    content = f.read()
                                if clean_id in content:
                                    pure_file_name = os.path.splitext(filename)[0]  # 예: "NEONSAT1"
                                    break
                            except:
                                continue
                
                # 메모리 및 출력 데이터의 위성 명칭 자체를 규격에 맞춰 영구 동기화
                p['satellite'] = f"{pure_file_name}({clean_id})"

        # -----------------------------------------------------------------
        # 🔥 3단계: 가공 완료된 최종 데이터셋을 기반으로 순정 PyQt6 그리드 렌더링
        # -----------------------------------------------------------------
        self.table.setRowCount(len(self.calculated_passes))
        
        for row_idx, p in enumerate(self.calculated_passes):
            # 체크박스 아이템 마운트 및 초기 상태 바인딩 (0번 컬럼)
            chk_item = QTableWidgetItem()
            chk_item.setCheckState(Qt.CheckState.Checked if p.get('selected', True) else Qt.CheckState.Unchecked)
            chk_item.setData(Qt.ItemDataRole.UserRole, (row_idx, p.get('conflict_group', None), p['station']))
            self.table.setItem(row_idx, 0, chk_item)
            
            # 🔥 [순서 변경] 1번: 지상국 / 2번: 위성 / 3번: 패스 번호 순으로 UI 셀 주입
            self.table.setItem(row_idx, 1, QTableWidgetItem(p['station']))                  # 1번 컬럼: Ground Station
            self.table.setItem(row_idx, 2, QTableWidgetItem(p['satellite']))                # 2번 컬럼: Satellite
            self.table.setItem(row_idx, 3, QTableWidgetItem(f"Pass {p['pass_no']}"))        # 3번 컬럼: Pass No.
            
            # 4번 컬럼부터는 기존 타임라인 데이터 그대로 유지
            self.table.setItem(row_idx, 4, QTableWidgetItem(p['aos'].strftime('%Y-%m-%d %H:%M:%S')))
            self.table.setItem(row_idx, 5, QTableWidgetItem(p['los'].strftime('%Y-%m-%d %H:%M:%S')))
            self.table.setItem(row_idx, 6, QTableWidgetItem(str(p['duration'])))
            self.table.setItem(row_idx, 7, QTableWidgetItem(str(p['max_el'])))
            
            # 경합 유무 상태 텍스트 출력 및 배경색 하이라이트
            status_text = p.get('status', 'Normal')
            self.table.setItem(row_idx, 8, QTableWidgetItem(status_text))
            
            # 오리지널 행 색상 테마: Conflict 그룹 소속일 경우 부드러운 파스텔 핑크 오렌지로 자동 마킹
            if "Conflict" in status_text:
                conflict_color = QColor(255, 235, 235)
                for col_idx in range(self.table.columnCount()):
                    cell = self.table.item(row_idx, col_idx)
                    if cell:
                        cell.setBackground(conflict_color)
                        
        # 🔥 4단계: 렌더링 전 과정이 안전하게 종료되었으므로 스위치 해제
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

    def set_all_checkboxes(self, check_state):
        """🔥 버튼 클릭 시 화면의 모든 체크박스를 일괄 켜거나 끕니다."""
        if not self.calculated_passes:
            return
            
        self.is_populating = True  # 상호 락킹 이벤트 핸들러가 오작동하지 않도록 임시 차단
        target_state = Qt.CheckState.Checked if check_state else Qt.CheckState.Unchecked
        
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item:
                item.setCheckState(target_state)
                # 백엔드 메모리 배열도 동기화
                self.calculated_passes[r]['selected'] = check_state
                
        self.is_populating = False
        # 충돌 하이라이트 배경색 유지를 위해 가볍게 리프레시
        self.populate_table()

    def click_export_excel(self):
        """🔥 엑셀 내보내기 버튼 이벤트: 선택된 데이터들만 파스텔톤 색상을 입혀 xlsx로 저장"""
        if not self.calculated_passes: 
            return
        # 선택된 패스가 단 하나도 없는지 방어 검증
        if not any(p['selected'] for p in self.calculated_passes):
            QMessageBox.warning(self, "Warning", "No passes are selected. Please check at least one pass.")
            return
            
        path, _ = QFileDialog.getSaveFileName(self, "Save Colorized Excel Schedule", "", "Excel Files (*.xlsx)")
        if path:
            try:
                export_to_excel_with_color(path, self.calculated_passes)
                QMessageBox.information(self, "Export Success", "Excel file generated with station color codes successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to save Excel file:\n{str(e)}")