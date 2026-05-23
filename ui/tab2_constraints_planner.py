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
        self.plan_table.setRowCount(0)
        self.plan_table.setRowCount(len(plan_rows))
        
        gui_sat_colors = {
            "NEONSAT1": QColor(240, 248, 255),
            "SPACEEYE-T1": QColor(255, 253, 240),
            "DEFAULT": QColor(255, 255, 255)
        }
        
        for row_idx, data in enumerate(plan_rows):
            sat_name = data.get("satellite", "").upper().strip()
            bg_color = gui_sat_colors.get(sat_name, gui_sat_colors["DEFAULT"])
            
            for col_idx, key in enumerate(self.plan_headers_keys):
                cell_text = data.get(key, "")
                item = QTableWidgetItem(cell_text)
                item.setBackground(bg_color)
                self.plan_table.setItem(row_idx, col_idx, item)

    def click_add_plan_row(self):
        curr_idx = self.plan_table.rowCount()
        self.plan_table.insertRow(curr_idx)
        
        default_row = ["NEONSAT1", "NEW_ACTIVITY", f"30{curr_idx}", "None", "120", "N", "Medium"]
        for col_idx, text in enumerate(default_row):
            item = QTableWidgetItem(text)
            self.plan_table.setItem(curr_idx, col_idx, item)
            
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