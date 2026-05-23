import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTableWidget, QTableWidgetItem, QLabel, QFileDialog, 
                             QHeaderView, QMessageBox, QComboBox, QDialog, QTextEdit)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from core.exporter import export_constraints_to_csv, export_constraints_to_excel_color
from core.plan_parser import load_plan_csv, load_plan_excel, save_plan_to_yaml, PLAN_HEADERS

class ConstraintsPlannerTab(QWidget):
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        self.plans_dir = "plans"
        
        self.plan_headers_keys = list(PLAN_HEADERS.keys())
        self.plan_headers_labels = list(PLAN_HEADERS.values())
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 1. 상단 제어 버튼 레이아웃
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
        
        # 2. 메인 데이터 테이블 레이아웃
        self.plan_table = QTableWidget()
        self.plan_table.setColumnCount(len(self.plan_headers_labels))
        self.plan_table.setHorizontalHeaderLabels(self.plan_headers_labels)
        
        self.plan_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.plan_table.horizontalHeader().setDefaultSectionSize(165)
        
        # 다중 선택 및 자동 행 개행 기능 유지
        self.plan_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.plan_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.plan_table.setWordWrap(True)
        self.plan_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        
        layout.addWidget(self.plan_table)
        
        # 시그널 바인딩
        self.plan_table.itemChanged.connect(self.handle_cell_changed)
        # 🔥 [신규 추가] 셀을 더블클릭했을 때 여러 줄 입력 팝업창을 띄워주는 시그널 연결!
        self.plan_table.itemDoubleClicked.connect(self.handle_cell_double_clicked)
        
        # 3. 최하단 저장 옵션 레이아웃
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

    # 🔥 [중요 신규 기능] Activity Name 컬럼 더블클릭 시 멀티라인 입력 팝업 매운맛 엔진
    def handle_cell_double_clicked(self, item):
        """Activity Name(2번 컬럼, 인덱스 2)을 더블클릭하면 여러 줄을 입력할 수 있는 서브 창을 오픈합니다."""
        # PLAN_HEADERS에서 'activity'가 몇 번째 컬럼인지 동적으로 인덱스 추적 (유연성 확보)
        activity_col_idx = self.plan_headers_keys.index("activity") if "activity" in self.plan_headers_keys else 2
        
        if item.column() != activity_col_idx:
            return  # Activity 컬럼이 아니면 일반 PyQt6 기본 에디터(한 줄 입력)를 사용하도록 패스
            
        # 미니 대화 상자 팝업 빌드
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Activity Name (Multi-line Input)")
        dialog.setMinimumSize(450, 250)
        
        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.addWidget(QLabel("<b>Enter Activity Details (Press Enter for new line):</b>"))
        
        # 여러 줄 입력이 가능한 QTextEdit 컴포넌트 배치 및 기존 텍스트 로드
        text_edit = QTextEdit()
        text_edit.setPlainText(item.text())
        dialog_layout.addWidget(text_edit)
        
        # 저장 확인 버튼 배치
        btn_save = QPushButton("💾 Apply and Close")
        btn_save.setStyleSheet("background-color: #2E7D32; color: white; font-weight: bold; padding: 6px;")
        btn_save.clicked.connect(dialog.accept)
        dialog_layout.addWidget(btn_save)
        
        # 팝업창 모달(Modal) 실행 및 확인 버튼을 눌러 닫았을 때만 테이블 세팅
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_text = text_edit.toPlainText().strip()
            
            self.plan_table.blockSignals(True)
            item.setText(new_text)
            self.plan_table.blockSignals(False)
            
            # 텍스트가 여러 줄로 늘어났으므로 가로 세로 높이 레이아웃 재배치 계산 트리거
            self.plan_table.resizeRowsToContents()

    def click_import_constraints(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Constraints File", self.plans_dir, "Supported Files (*.xlsx *.csv)")
        if not path: return
            
        try:
            if path.endswith(".xlsx"):
                plan_rows = load_plan_excel(path)
            else:
                plan_rows = load_plan_csv(path)
                
            self.populate_plan_table_ui(plan_rows)
            QMessageBox.information(self, "Loaded", f"Successfully loaded {len(plan_rows)} activity records.")
        except Exception as e:
            QMessageBox.critical(self, "Parser Error", f"Failed to load constraints data:\n{str(e)}")

    def populate_plan_table_ui(self, plan_rows):
        """위성별 동적 파스텔톤 실시간 매핑"""
        self.plan_table.setRowCount(0)
        self.plan_table.blockSignals(True)
        self.plan_table.setRowCount(len(plan_rows))
        
        from core.color_manager import color_manager
        
        for row_idx, data in enumerate(plan_rows):
            sat_name = data.get("satellite", "").strip()
            _, sat_bg_color = color_manager.get_colors(sat_name)
            
            for col_idx, key in enumerate(self.plan_headers_keys):
                cell_text = str(data.get(key, ""))
                item = QTableWidgetItem(cell_text)
                item.setBackground(sat_bg_color)
                self.plan_table.setItem(row_idx, col_idx, item)
                
        self.plan_table.blockSignals(False)

    def handle_cell_changed(self, item):
        """유저가 0번 컬럼(Satellite)의 이름을 바꾸면 즉시 행 전체 색상을 유동적으로 변경"""
        if item is None or item.column() != 0:
            return
            
        row = item.row()
        sat_name = item.text().strip()
        
        from core.color_manager import color_manager
        _, new_sat_color = color_manager.get_colors(sat_name)
        
        self.plan_table.blockSignals(True)
        for col_idx in range(self.plan_table.columnCount()):
            cell = self.plan_table.item(row, col_idx)
            if cell:
                cell.setBackground(new_sat_color)
        self.plan_table.blockSignals(False)

    def click_add_plan_row(self):
        """GUI 내 즉시 실시간 액티비티 행 삽입 및 기본 배경색 주입"""
        curr_idx = self.plan_table.rowCount()
        
        self.plan_table.blockSignals(True)
        self.plan_table.insertRow(curr_idx)
        
        from core.color_manager import color_manager
        _, default_sat_color = color_manager.get_colors("NEONSAT1")
        
        default_row = ["NEONSAT1", "NEW_ACTIVITY", f"30{curr_idx}", "None", "120", "N", "Medium"]
        for col_idx, text in enumerate(default_row):
            item = QTableWidgetItem(text)
            item.setBackground(default_sat_color)
            self.plan_table.setItem(curr_idx, col_idx, item)
            
        self.plan_table.blockSignals(False)
        self.refresh_plan_colors_from_ui()

    def click_delete_plan_row(self):
        """선택된 여러 개의 액티비티 행을 한 번에 삭제"""
        selected_ranges = self.plan_table.selectedRanges()
        if not selected_ranges:
            QMessageBox.warning(self, "Warning", "Please select at least one activity row to delete.")
            return
            
        rows_to_delete = set()
        for r_range in selected_ranges:
            for r in range(r_range.topRow(), r_range.bottomRow() + 1):
                rows_to_delete.add(r)
                
        sorted_rows = sorted(list(rows_to_delete), reverse=True)
        
        self.plan_table.blockSignals(True)
        for r in sorted_rows:
            self.plan_table.removeRow(r)
        self.plan_table.blockSignals(False)
        
        self.refresh_plan_colors_from_ui()

    def refresh_plan_colors_from_ui(self):
        extracted = self.extract_plan_data_from_ui_grid()
        self.populate_plan_table_ui(extracted)

    def extract_plan_data_from_ui_grid(self):
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