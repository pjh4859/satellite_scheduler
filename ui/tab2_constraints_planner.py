import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTableWidget, QTableWidgetItem, QLabel, QFileDialog, 
                             QHeaderView, QMessageBox, QDialog, QTextEdit, QComboBox)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QColor, QDesktopServices

from core.exporter import export_constraints_to_csv, export_constraints_to_excel_color
from core.plan_parser import load_plan_file, save_plan_to_yaml, PLAN_HEADERS


class ConstraintsPlannerTab(QWidget):
    """
    Tab 2: 미션 제약 조건 플래너 UI 클래스
    
    [기능 설명]
    - 미션 활동 제약 조건(Sat_ID, Main, Sub, Remark, Min_El, Required_Cap, Min_Duration, Pre_Req_Main, Sequence_ID)을
      그리드 표 형태로 직접 생성, 편집, 조회합니다.
    - YAML, Excel, CSV 형식을 통합 지원하며 Remark (운용 상세 설명) 입력을 지원합니다.
    - 사내 DRM 문서 우회를 위한 Excel Load Engine 선택 기능(Auto / Standard / DRM Bypass)을 제공합니다.
    """
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
        
        # 1. 상단 DRM 엔진 선택 콤보박스
        top_ctrl.addWidget(QLabel("<b>Excel Engine:</b>"))
        self.combo_engine = QComboBox()
        self.combo_engine.addItems([
            "Auto (Standard 시도 ➔ DRM 발생 시 xlwings 자동 전환)",
            "Standard (openpyxl - 고속 / MS Excel 미필요)",
            "DRM Bypass (xlwings - 보안 문서 지원 / MS Excel 필요)"
        ])
        self.combo_engine.setToolTip(
            "사내 DRM(문서 보안)이 적용된 Excel 파일은 'DRM Bypass' 또는 'Auto' 모드를 사용하세요."
        )
        top_ctrl.addWidget(self.combo_engine)

        top_ctrl.addSpacing(10)

        # 2. 파일 로드 및 편집 버튼 구역
        self.btn_import_plan_file = QPushButton("📂 Load Constraint File (YAML / Excel / CSV)")
        self.btn_import_plan_file.setStyleSheet("font-weight: bold; padding: 6px; background-color: #2E7D32; color: white;")
        self.btn_import_plan_file.clicked.connect(self.click_import_constraints)
        top_ctrl.addWidget(self.btn_import_plan_file)
        
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
        
        # 3. 미션 제약 조건 테이블 (9개 컬럼: Sat_ID, Main, Sub, Remark, Min_El, Required_Cap, Min_Duration, Pre_Req_Main, Sequence_ID)
        self.plan_table = QTableWidget()
        self.plan_table.setColumnCount(len(self.plan_headers_labels))
        self.plan_table.setHorizontalHeaderLabels(self.plan_headers_labels)
        self.plan_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.plan_table.horizontalHeader().setDefaultSectionSize(130)
        
        # Main, Sub, Remark 컬럼 유연 가변 확장 (인덱스 1, 2, 3)
        self.plan_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.plan_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.plan_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        
        self.plan_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.plan_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.plan_table.setWordWrap(True)
        self.plan_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.plan_table)
        
        self.plan_table.itemChanged.connect(self.handle_cell_changed)
        self.plan_table.itemDoubleClicked.connect(self.handle_cell_double_clicked)
        
        # 4. 하단 저장 옵션 컨트롤 패널
        bottom_ctrl = QHBoxLayout()
        bottom_ctrl.addWidget(QLabel("<b>Save Options:</b>"))
        
        self.btn_save_plan_yaml = QPushButton("Compile to Constraints YAML")
        self.btn_save_plan_yaml.setStyleSheet("background-color: #008CBA; color: white; font-weight: bold;")
        self.btn_save_plan_yaml.clicked.connect(lambda: self.click_save_plan_file("YAML"))
        bottom_ctrl.addWidget(self.btn_save_plan_yaml)
        
        self.btn_save_plan_csv = QPushButton("Export to CSV")
        self.btn_save_plan_csv.clicked.connect(lambda: self.click_save_plan_file("CSV"))
        bottom_ctrl.addWidget(self.btn_save_plan_csv)
        
        self.btn_save_plan_excel = QPushButton("🎨 Export to Colorized Excel")
        self.btn_save_plan_excel.setStyleSheet("color: #1E7145; font-weight: bold;")
        self.btn_save_plan_excel.clicked.connect(lambda: self.click_save_plan_file("EXCEL"))
        bottom_ctrl.addWidget(self.btn_save_plan_excel)
        
        layout.addLayout(bottom_ctrl)

    def open_local_folder(self, folder_path):
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        abs_path = os.path.abspath(folder_path)
        QDesktopServices.openUrl(QUrl.fromLocalFile(abs_path))

    def handle_cell_double_clicked(self, item):
        """Main, Sub, Remark 셀 더블클릭 시 멀티라인 상세 편집 팝업 띄우기"""
        if item.column() not in [1, 2, 3]: return
            
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Activity Detail")
        dialog.setMinimumSize(420, 220)
        
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
        """Constraint 파일 (YAML, Excel, CSV) 파싱 후 테이블에 로드 (DRM 우회 엔진 옵션 연동)"""
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Constraints File", self.plans_dir, "Supported Files (*.yaml *.yml *.xlsx *.csv)"
        )
        if not path: return

        # 선택된 엔진 매핑
        engine_idx = self.combo_engine.currentIndex()
        engine_map = {0: "auto", 1: "standard", 2: "xlwings"}
        selected_engine = engine_map[engine_idx]

        try:
            plan_rows = load_plan_file(path, engine=selected_engine)
            if not plan_rows:
                QMessageBox.warning(self, "Warning", "Loaded data is empty or invalid format.")
                return

            self.populate_plan_table_ui(plan_rows)
            QMessageBox.information(
                self, "Loaded", 
                f"Successfully loaded {len(plan_rows)} activity records using [{selected_engine.upper()}] engine."
            )
        except Exception as e:
            QMessageBox.critical(self, "Parser Error", f"Failed to load constraints data:\n{str(e)}")

    def populate_plan_table_ui(self, plan_rows):
        """파싱된 미션 활동 데이터를 테이블 UI에 바인딩 및 파스텔 배경색 설정"""
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
        """Sat_ID(첫 번째 열) 셀 수정 시 해당 행 전체 파스텔 배경색 즉시 변경"""
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
        """기본값이 입력된 새로운 태스크 제약 조건 행 추가 (Remark 항목 포함 9개 값)"""
        curr_idx = self.plan_table.rowCount()
        self.plan_table.blockSignals(True)
        self.plan_table.insertRow(curr_idx)
        from core.color_manager import color_manager
        _, default_sat_color = color_manager.get_colors("SAT_A")
        
        # [Sat_ID, Main, Sub, Remark, Min_El, Required_Cap, Min_Duration, Pre_Req_Main, Sequence_ID]
        default_row = ["SAT_A", "NEW_MAIN", "NEW_SUB", "Standard pass operation note", "10", "CMD", "180", "NONE", str(curr_idx + 1)]
        for col_idx, text in enumerate(default_row):
            item = QTableWidgetItem(text)
            item.setBackground(default_sat_color)
            self.plan_table.setItem(curr_idx, col_idx, item)
            
        self.plan_table.blockSignals(False)

    def click_delete_plan_row(self):
        """선택된 행(들) 삭제"""
        selected_ranges = self.plan_table.selectedRanges()
        if not selected_ranges: return
        rows_to_delete = {r for r_range in selected_ranges for r in range(r_range.topRow(), r_range.bottomRow() + 1)}
        self.plan_table.blockSignals(True)
        for r in sorted(list(rows_to_delete), reverse=True):
            self.plan_table.removeRow(r)
        self.plan_table.blockSignals(False)

    def extract_plan_data_from_ui_grid(self):
        """UI 표에 입력된 데이터를 딕셔너리 리스트 형태로 추출"""
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
        """추출된 데이터를 지정된 형식(YAML, CSV, EXCEL)으로 내보내기"""
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