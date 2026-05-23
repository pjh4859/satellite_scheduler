import os
import yaml
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTableWidget, QTableWidgetItem, QLabel, QFileDialog, 
                             QHeaderView, QMessageBox, QRadioButton, QButtonGroup)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from core.color_manager import color_manager
from core.exporter import export_final_schedule_to_csv, export_final_schedule_to_excel

class FinalSchedulerTab(QWidget):
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        self.plans_dir = "plans"
        
        self.raw_pass_data = None
        self.raw_constraint_data = None
        self.final_schedule_data = []
        
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 1. 상단 컨트롤 바
        top_ctrl = QHBoxLayout()
        
        self.btn_load_pass = QPushButton("📂 Load Tab1 Passes (.yaml)")
        self.btn_load_pass.setStyleSheet("font-weight: bold; padding: 5px;")
        self.btn_load_pass.clicked.connect(self.click_load_pass_yaml)
        top_ctrl.addWidget(self.btn_load_pass)
        
        self.btn_load_constraints = QPushButton("📂 Load Tab2 Constraints (.yaml)")
        self.btn_load_constraints.setStyleSheet("font-weight: bold; padding: 5px;")
        self.btn_load_constraints.clicked.connect(self.click_load_constraints_yaml)
        top_ctrl.addWidget(self.btn_load_constraints)
        
        self.lbl_status = QLabel("❌ Files Missing (Please load Pass & Constraints)")
        self.lbl_status.setStyleSheet("color: #D32F2F; font-weight: bold; margin-left: 10px; margin-right: 10px;")
        top_ctrl.addWidget(self.lbl_status)
        
        self.btn_generate_final = QPushButton("⚡ Generate Final Schedule")
        self.btn_generate_final.setStyleSheet("background-color: #2E7D32; color: white; font-weight: bold; padding: 6px;")
        self.btn_generate_final.setEnabled(False)
        self.btn_generate_final.clicked.connect(self.click_generate_schedule)
        top_ctrl.addWidget(self.btn_generate_final)
        
        top_ctrl.addSpacing(20)
        top_ctrl.addWidget(QLabel("<b>🎨 Color Mode:</b>"))
        
        self.color_group = QButtonGroup(self)
        self.radio_station = QRadioButton("Station Standard (Default)")
        self.radio_station.setChecked(True)
        self.radio_station.toggled.connect(self.refresh_table_colors)
        self.color_group.addButton(self.radio_station)
        top_ctrl.addWidget(self.radio_station)
        
        self.radio_satellite = QRadioButton("Satellite Standard")
        self.radio_satellite.toggled.connect(self.refresh_table_colors)
        self.color_group.addButton(self.radio_satellite)
        top_ctrl.addWidget(self.radio_satellite)
        
        top_ctrl.addStretch()
        layout.addLayout(top_ctrl)
        
        # 2. 메인 마스터 타임라인 그리드 배치
        # 🔥 [요구사항 반영]: Select 열을 완벽히 빼고 총 9개 정갈한 컬럼으로 리밸런싱
        self.final_table = QTableWidget()
        self.final_table.setColumnCount(9)
        self.final_table.setHorizontalHeaderLabels([
            "Ground Station", "Satellite", "Pass No. (Orbit)", "AOS (UTC)", 
            "LOS (UTC)", "Duration (s)", "Max El (deg)", "Status", "💡 Mission Activity"
        ])
        self.final_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.final_table.horizontalHeader().setDefaultSectionSize(145)
        self.final_table.setWordWrap(True)
        self.final_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.final_table)
        
        # 3. 하단 덤프 내보내기 제어 바
        bottom_ctrl = QHBoxLayout()
        bottom_ctrl.addWidget(QLabel("<b>Export Options:</b>"))
        
        self.btn_export_csv = QPushButton("Export Final Schedule to CSV")
        self.btn_export_csv.clicked.connect(self.click_export_csv)
        bottom_ctrl.addWidget(self.btn_export_csv)
        
        self.btn_export_excel = QPushButton("🎨 Export Final Schedule to Excel")
        self.btn_export_excel.setStyleSheet("color: #1E7145; font-weight: bold;")
        self.btn_export_excel.clicked.connect(self.click_export_excel)
        bottom_ctrl.addWidget(self.btn_export_excel)
        
        bottom_ctrl.addStretch()
        layout.addLayout(bottom_ctrl)

    def click_load_pass_yaml(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Tab1 Predicted Passes YAML", "", "YAML Files (*.yaml)")
        if not path: return
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f) or {}
            self.raw_pass_data = content.get("predicted_passes", [])
            self.btn_load_pass.setText("✅ Tab1 Passes Loaded")
            self.update_input_readiness()
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to parse Pass YAML:\n{str(e)}")

    def click_load_constraints_yaml(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Tab2 Mission Constraints YAML", self.plans_dir, "YAML Files (*.yaml)")
        if not path: return
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f) or {}
            # YAML의 루트 구조 및 래핑 구조('constraints' 또는 'mission_constraints') 모두 유연하게 대응
            if isinstance(content, list):
                self.raw_constraint_data = content
            else:
                self.raw_constraint_data = content.get("constraints", content.get("mission_constraints", []))
                
            self.btn_load_constraints.setText("✅ Tab2 Constraints Loaded")
            self.update_input_readiness()
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to parse Constraints YAML:\n{str(e)}")

    def update_input_readiness(self):
        if self.raw_pass_data is not None and self.raw_constraint_data is not None:
            self.lbl_status.setText("🟢 Ready to Compile")
            self.lbl_status.setStyleSheet("color: #2E7D32; font-weight: bold; margin-left: 10px; margin-right: 10px;")
            self.btn_generate_final.setEnabled(True)
        else:
            self.lbl_status.setText("❌ Files Missing (Please load Pass & Constraints)")
            self.lbl_status.setStyleSheet("color: #D32F2F; font-weight: bold; margin-left: 10px; margin-right: 10px;")
            self.btn_generate_final.setEnabled(False)

    def click_generate_schedule(self):
        """🔥 [위성 타깃형 순차 슬라이딩 할당 엔진]: 완전 일치(Exact match) 조건으로 위성 파이프라인 분리"""
        if not self.raw_pass_data or self.raw_constraint_data is None:
            return
            
        try:
            self.final_schedule_data = []
            sat_match_pointers = {}
            
            for p in self.raw_pass_data:
                p_sat_full = p.get("satellite", "")
                # 예: "NEONSAT1(67614)" 또는 "NEONSAT1A(67615)" -> 괄호 떼고 순수 대문자 추출
                p_sat_clean = p_sat_full.split("(")[0].strip().upper()
                
                # 2번 탭 데이터에서 현재 패스의 위성 이름과 '정확하게 일치'하는 항목들만 순서대로 추출
                matched_sat_activities = []
                for act in self.raw_constraint_data:
                    act_sat = act.get("satellite", "").strip().upper()
                    
                    # ❌ [기존 버그 코드]: if act_sat in p_sat_clean or p_sat_clean in act_sat:
                    # 💡 [정밀 교정]: 문자열이 완벽하게 글자 수까지 일치할 때만 동종 위성으로 판정!
                    if act_sat == p_sat_clean:
                        matched_sat_activities.append(act)
                        
                if p_sat_clean not in sat_match_pointers:
                    sat_match_pointers[p_sat_clean] = 0
                    
                curr_pointer = sat_match_pointers[p_sat_clean]
                
                if curr_pointer < len(matched_sat_activities):
                    target_act = matched_sat_activities[curr_pointer]
                    assigned_activity_text = target_act.get("activity", target_act.get("act_name", "N/A"))
                    sat_match_pointers[p_sat_clean] += 1
                else:
                    assigned_activity_text = "Standby / Idle Operations"
                
                self.final_schedule_data.append({
                    "station": p.get("station", ""),
                    "satellite": p_sat_full,
                    "pass_no": f"Pass {p.get('pass_no', '')}",
                    "aos": p.get("aos", ""),
                    "los": p.get("los", ""),
                    "duration": p.get("duration_sec", p.get("duration", "0")),
                    "max_el": p.get("max_elevation_deg", p.get("max_el", "0")),
                    "status": p.get("status", "Normal"),
                    "activity": assigned_activity_text
                })
            
            self.populate_final_table_ui()
            QMessageBox.information(self, "Allocation Success", f"Successfully completed schedule synthesis with exact satellite matching.")
            
        except Exception as e:
            QMessageBox.critical(self, "Engine Error", f"Failed to execute satellite sequential merge:\n{str(e)}")

    def populate_final_table_ui(self):
        self.final_table.setRowCount(0)
        self.final_table.setRowCount(len(self.final_schedule_data))
        
        for row_idx, item in enumerate(self.final_schedule_data):
            # Select 체크박스 없이 0번부터 순수 데이터 컬럼 주입 시작
            self.final_table.setItem(row_idx, 0, QTableWidgetItem(item["station"]))
            self.final_table.setItem(row_idx, 1, QTableWidgetItem(item["satellite"]))
            self.final_table.setItem(row_idx, 2, QTableWidgetItem(item["pass_no"]))
            self.final_table.setItem(row_idx, 3, QTableWidgetItem(item["aos"]))
            self.final_table.setItem(row_idx, 4, QTableWidgetItem(item["los"]))
            self.final_table.setItem(row_idx, 5, QTableWidgetItem(str(item["duration"])))
            self.final_table.setItem(row_idx, 6, QTableWidgetItem(str(item["max_el"])))
            self.final_table.setItem(row_idx, 7, QTableWidgetItem(item["status"]))
            self.final_table.setItem(row_idx, 8, QTableWidgetItem(item["activity"])) # 미션 액티비티 항목 상주
            
        self.refresh_table_colors()

    def refresh_table_colors(self):
        row_count = self.final_table.rowCount()
        if row_count == 0: return
        
        is_station_mode = self.radio_station.isChecked()
        
        for r in range(row_count):
            if is_station_mode:
                st_name = self.final_table.item(r, 0).text().strip()
                _, chosen_color = color_manager.get_station_colors(st_name)
            else:
                sat_raw = self.final_table.item(r, 1).text().split("(")[0].strip()
                _, chosen_color = color_manager.get_colors(sat_raw)
                
            for c in range(self.final_table.columnCount()):
                cell = self.final_table.item(r, c)
                if cell:
                    cell.setBackground(chosen_color)

    def click_export_csv(self):
        if not self.final_schedule_data: return
        path, _ = QFileDialog.getSaveFileName(self, "Save Final Integrated CSV", "", "CSV Files (*.csv)")
        if path:
            export_final_schedule_to_csv(path, self.final_schedule_data)
            QMessageBox.information(self, "Export Success", "CSV Timeline exported successfully.")

    def click_export_excel(self):
        if not self.final_schedule_data: return
        path, _ = QFileDialog.getSaveFileName(self, "Save Final Integrated Excel", "", "Excel Files (*.xlsx)")
        if path:
            color_mode = "STATION" if self.radio_station.isChecked() else "SATELLITE"
            export_final_schedule_to_excel(path, self.final_schedule_data, color_mode)
            QMessageBox.information(self, "Export Success", "Integrated Excel sheet saved successfully.")