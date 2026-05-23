import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTableWidget, QTableWidgetItem, QLabel, QFileDialog, 
                             QHeaderView, QMessageBox, QComboBox)
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
        
        self.plan_table = QTableWidget()
        self.plan_table.setColumnCount(len(self.plan_headers_labels))
        self.plan_table.setHorizontalHeaderLabels(self.plan_headers_labels)
        
        self.plan_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.plan_table.horizontalHeader().setDefaultSectionSize(165)
        layout.addWidget(self.plan_table)
        
        # 🔥 [연결 고리 복원] 사용자가 GUI 셀의 텍스트를 바꾸면 색상 스캐너가 실시간으로 가로줄을 채색하도록 시그널 바인딩!
        self.plan_table.itemChanged.connect(self.handle_cell_changed)
        
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
        """🔥 [2번 탭 완전 유동형 리모델링] 위성별 동적 파스텔톤 실시간 매핑"""
        self.plan_table.setRowCount(0)
        
        # 데이터 일괄 주입 시 불필요한 cellChanged 중복 시그널 전파 차단
        self.plan_table.blockSignals(True)
        
        self.plan_table.setRowCount(len(plan_rows))
        from core.color_manager import color_manager
        
        for row_idx, data in enumerate(plan_rows):
            sat_name = data.get("satellite", "").strip()
            _, sat_bg_color = color_manager.get_colors(sat_name)
            
            for col_idx, key in enumerate(self.plan_headers_keys):
                cell_text = str(data.get(key, ""))
                item = QTableWidgetItem(cell_text)
                item.setBackground(sat_bg_color)  # 위성별 고유 파스텔톤 도색
                self.plan_table.setItem(row_idx, col_idx, item)
                
        self.plan_table.blockSignals(False)

    def handle_cell_changed(self, item):
        """유저가 0번 컬럼(Satellite)의 이름을 바꾸면 즉시 탐지하여 행 전체 색상을 유동적으로 변경"""
        # 아이템이 없거나 위성 이름 컬럼(0번)이 아니면 스킵
        if item is None or item.column() != 0:
            return
            
        row = item.row()
        sat_name = item.text().strip()
        
        from core.color_manager import color_manager
        _, new_sat_color = color_manager.get_colors(sat_name)
        
        # 연쇄적인 변경 플래그 오작동을 차단하기 위해 시그널 잠금
        self.plan_table.blockSignals(True)
        
        # 유저가 새로 기입한 위성 명칭에 맞춰 해당 가로줄 전체 레이어를 동적 컬러로 전면 갱신
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
        # 기본값인 NEONSAT1의 고유 파스텔톤을 추출하여 초기화 시 바로 발라줍니다.
        _, default_sat_color = color_manager.get_colors("NEONSAT1")
        
        default_row = ["NEONSAT1", "NEW_ACTIVITY", f"30{curr_idx}", "None", "120", "N", "Medium"]
        for col_idx, text in enumerate(default_row):
            item = QTableWidgetItem(text)
            item.setBackground(default_color if 'default_color' in locals() else default_sat_color)
            self.plan_table.setItem(curr_idx, col_idx, item)
            
        self.plan_table.blockSignals(False)
        self.refresh_plan_colors_from_ui()

    def click_delete_plan_row(self):
        curr_row = self.plan_table.currentRow()
        if curr_row >= 0:
            self.plan_table.removeRow(curr_row)
            self.refresh_plan_colors_from_ui()
        else:
            QMessageBox.warning(self, "Warning", "Please select an activity row to delete first.")

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