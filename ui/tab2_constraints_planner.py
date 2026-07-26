import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTableWidget, QTableWidgetItem, QLabel, QFileDialog, 
                             QHeaderView, QMessageBox, QDialog, QTextEdit)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QColor, QDesktopServices

from core.exporter import export_constraints_to_csv, export_constraints_to_excel_color
from core.plan_parser import load_plan_csv, load_plan_excel, save_plan_to_yaml, PLAN_HEADERS

class ConstraintsPlannerTab(QWidget):
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        self.plans_dir = "plans"
        
        if not os.path.exists(self.plans_dir):
            os.makedirs(self.plans_dir)
            
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
        
        self.btn_open_plan_folder = QPushButton("📂 Open Plan Folder")
        self.btn_open_plan_folder.clicked.connect(lambda: self.open_local_folder(self.plans_dir))
        top_ctrl.addWidget(self.btn_open_plan_folder)
        
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
        self.plan_table.horizontalHeader().setDefaultSectionSize(140)
        self.plan_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.plan_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.plan_table.setWordWrap(True)
        self.plan_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.plan_table)
        
        self.plan_table.itemChanged.connect(self.handle_cell_changed)
        self.plan_table.itemDoubleClicked.connect(self.handle_cell_double_clicked)
        
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

    def open_local_folder(self, folder_path):
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        abs_path = os.path.abspath(folder_path)
        QDesktopServices.openUrl(QUrl.fromLocalFile(abs_path))

    def handle_cell_double_clicked(self, item):
        if item.column() != 1 and item.column() != 2: return
            
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Activity Detail")
        dialog.setMinimumSize(400, 200)
        
        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.addWidget(QLabel("<b>Enter Details (Multi-line supported):</b>"))
        text_edit = QTextEdit()
        text_edit.setPlainText(item.text())
        dialog_layout.addWidget(text_edit)
        
        btn_save = QPushButton("💾 Apply")
        btn_save.setStyleSheet("background-color: #2E7D32; color: white; font-weight: bold;")
        btn_save.clicked.connect(dialog.accept)
        dialog_layout.addWidget(btn_save)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.plan_table.blockSignals(True)
            item.setText(text_edit.toPlainText().strip())
            self.plan_table.blockSignals(False)
            self.plan_table.resizeRowsToContents()

    def click_import_constraints(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Constraints File", self.plans_dir, "Supported Files (*.xlsx *.csv)")
        if not path: return
        try:
            plan_rows = load_plan_excel(path) if path.endswith(".xlsx") else load_plan_csv(path)
            self.populate_plan_table_ui(plan_rows)
            QMessageBox.information(self, "Loaded", f"Successfully loaded {len(plan_rows)} activity records.")
        except Exception as e:
            QMessageBox.critical(self, "Parser Error", f"Failed to load constraints data:\n{str(e)}")

    def populate_plan_table_ui(self, plan_rows):
        self.plan_table.setRowCount(0)
        self.plan_table.blockSignals(True)
        self.plan_table.setRowCount(len(plan_rows))
        from core.color_manager import color_manager
        
        for row_idx, data in enumerate(plan_rows):
            sat_name = str(data.get("sat_id", data.get("satellite", ""))).strip()
            _, sat_bg_color = color_manager.get_colors(sat_name)
            
            for col_idx, key in enumerate(self.plan_headers_keys):
                cell_text = str(data.get(key, ""))
                item = QTableWidgetItem(cell_text)
                item.setBackground(sat_bg_color)
                self.plan_table.setItem(row_idx, col_idx, item)
                
        self.plan_table.blockSignals(False)

    def handle_cell_changed(self, item):
        if item is None or item.column() != 0: return
        row = item.row()
        sat_name = item.text().strip()
        from core.color_manager import color_manager
        _, new_sat_color = color_manager.get_colors(sat_name)
        
        self.plan_table.blockSignals(True)
        for col_idx in range(self.plan_table.columnCount()):
            cell = self.plan_table.item(row, col_idx)
            if cell: cell.setBackground(new_sat_color)
        self.plan_table.blockSignals(False)

    def click_add_plan_row(self):
        curr_idx = self.plan_table.rowCount()
        self.plan_table.blockSignals(True)
        self.plan_table.insertRow(curr_idx)
        from core.color_manager import color_manager
        _, default_sat_color = color_manager.get_colors("SAT_A")
        
        default_row = ["SAT_A", "NEW_MAIN", "NEW_SUB", "10", "CMD", "180", "NONE", str(curr_idx + 1)]
        for col_idx, text in enumerate(default_row):
            item = QTableWidgetItem(text)
            item.setBackground(default_sat_color)
            self.plan_table.setItem(curr_idx, col_idx, item)
            
        self.plan_table.blockSignals(False)

    def click_delete_plan_row(self):
        selected_ranges = self.plan_table.selectedRanges()
        if not selected_ranges: return
        rows_to_delete = {r for r_range in selected_ranges for r in range(r_range.topRow(), r_range.bottomRow() + 1)}
        self.plan_table.blockSignals(True)
        for r in sorted(list(rows_to_delete), reverse=True):
            self.plan_table.removeRow(r)
        self.plan_table.blockSignals(False)

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
        if not extracted_data: return
        if format_type == "YAML":
            path, _ = QFileDialog.getSaveFileName(self, "Save Constraints YAML", self.plans_dir, "YAML Files (*.yaml)")
            if path:
                save_plan_to_yaml(path, extracted_data)
                QMessageBox.information(self, "Success", "Saved YAML successfully.")
        elif format_type == "CSV":
            path, _ = QFileDialog.getSaveFileName(self, "Save Constraints CSV", self.plans_dir, "CSV Files (*.csv)")
            if path:
                export_constraints_to_csv(path, extracted_data, self.plan_headers_labels)
                QMessageBox.information(self, "Success", "Saved CSV successfully.")
        elif format_type == "EXCEL":
            path, _ = QFileDialog.getSaveFileName(self, "Save Constraints Excel", self.plans_dir, "Excel Files (*.xlsx)")
            if path:
                export_constraints_to_excel_color(path, extracted_data, self.plan_headers_labels)
                QMessageBox.information(self, "Success", "Saved Excel successfully.")