import os
import yaml
import re
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTableWidget, QTableWidgetItem, QLabel, QFileDialog, 
                             QHeaderView, QMessageBox, QRadioButton, QButtonGroup, QSpinBox)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QColor, QDesktopServices

from core.color_manager import color_manager
from core.exporter import export_final_schedule_to_csv, export_final_schedule_to_excel
from core.plan_parser import normalize_sat_name

class FinalSchedulerTab(QWidget):
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        self.plans_dir = "plans"
        self.pass_output_dir = "pass_output"
        self.final_output_dir = "final_output"
        
        if not os.path.exists(self.plans_dir): os.makedirs(self.plans_dir)
        if not os.path.exists(self.pass_output_dir): os.makedirs(self.pass_output_dir)
        if not os.path.exists(self.final_output_dir): os.makedirs(self.final_output_dir)
        
        self.raw_pass_data = None
        self.raw_constraint_data = None
        self.final_schedule_data = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        top_ctrl = QHBoxLayout()
        
        self.btn_load_pass = QPushButton("📂 Load Tab1 Passes (.yaml)")
        self.btn_load_pass.setStyleSheet("font-weight: bold; padding: 5px;")
        self.btn_load_pass.clicked.connect(self.click_load_pass_yaml)
        top_ctrl.addWidget(self.btn_load_pass)
        
        self.btn_open_pass_folder = QPushButton("📂 Pass Folder")
        self.btn_open_pass_folder.clicked.connect(lambda: self.open_local_folder(self.pass_output_dir))
        top_ctrl.addWidget(self.btn_open_pass_folder)
        
        top_ctrl.addSpacing(10)
        
        self.btn_load_constraints = QPushButton("📂 Load Tab2 Constraints (.yaml)")
        self.btn_load_constraints.setStyleSheet("font-weight: bold; padding: 5px;")
        self.btn_load_constraints.clicked.connect(self.click_load_constraints_yaml)
        top_ctrl.addWidget(self.btn_load_constraints)
        
        self.btn_open_plan_folder = QPushButton("📂 Plan Folder")
        self.btn_open_plan_folder.clicked.connect(lambda: self.open_local_folder(self.plans_dir))
        top_ctrl.addWidget(self.btn_open_plan_folder)
        
        top_ctrl.addSpacing(15)
        top_ctrl.addWidget(QLabel("<b>Max Step Lead:</b>"))
        self.spin_max_lead = QSpinBox()
        self.spin_max_lead.setRange(1, 20)
        self.spin_max_lead.setValue(6)
        self.spin_max_lead.setToolTip("Maximum allowed step difference between satellites")
        top_ctrl.addWidget(self.spin_max_lead)
        
        self.lbl_status = QLabel("❌ Files Missing")
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
        self.radio_station = QRadioButton("Station Standard")
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
        
        bottom_ctrl = QHBoxLayout()
        bottom_ctrl.addWidget(QLabel("<b>Export Options:</b>"))
        self.btn_export_csv = QPushButton("Export Final Schedule to CSV")
        self.btn_export_csv.clicked.connect(self.click_export_csv)
        bottom_ctrl.addWidget(self.btn_export_csv)
        
        self.btn_export_excel = QPushButton("🎨 Export Final Schedule to Excel")
        self.btn_export_excel.setStyleSheet("color: #1E7145; font-weight: bold;")
        self.btn_export_excel.clicked.connect(self.click_export_excel)
        bottom_ctrl.addWidget(self.btn_export_excel)
        
        self.btn_open_final_folder = QPushButton("📂 Open Final Output Folder")
        self.btn_open_final_folder.clicked.connect(lambda: self.open_local_folder(self.final_output_dir))
        bottom_ctrl.addWidget(self.btn_open_final_folder)
        
        bottom_ctrl.addStretch()
        layout.addLayout(bottom_ctrl)

    def open_local_folder(self, folder_path):
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        abs_path = os.path.abspath(folder_path)
        QDesktopServices.openUrl(QUrl.fromLocalFile(abs_path))

    def click_load_pass_yaml(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Tab1 Predicted Passes YAML", self.pass_output_dir, "YAML Files (*.yaml)")
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
            self.lbl_status.setText("❌ Files Missing")
            self.lbl_status.setStyleSheet("color: #D32F2F; font-weight: bold; margin-left: 10px; margin-right: 10px;")
            self.btn_generate_final.setEnabled(False)

    def click_generate_schedule(self):
        if not self.raw_pass_data or self.raw_constraint_data is None: return
            
        try:
            self.final_schedule_data = []
            max_lead_steps = self.spin_max_lead.value()
            
            station_configs = getattr(self.main_app, 'station_data', [])
            st_caps = {}
            for st in station_configs:
                st_name = st[0]
                is_down = (st[3].upper() == 'Y') if len(st) > 3 else True
                is_cmd = (st[4].upper() == 'Y') if len(st) > 4 else True
                st_caps[st_name] = {'cmd': is_cmd, 'down': is_down}

            sat_plans = {}
            for act in self.raw_constraint_data:
                raw_sat = act.get("sat_id", act.get("satellite", ""))
                norm_sat = normalize_sat_name(raw_sat)
                if not norm_sat: continue
                
                if norm_sat not in sat_plans: sat_plans[norm_sat] = []
                    
                main_title = str(act.get("main", act.get("activity", ""))).strip()
                sub_title = str(act.get("sub", "")).strip()
                
                raw_seq = act.get("sequence_id", act.get("activity_sequence_id", len(sat_plans[norm_sat]) + 1))
                try: seq_id = int(raw_seq)
                except: seq_id = len(sat_plans[norm_sat]) + 1
                
                try: min_el = float(act.get("min_el", 0.0))
                except: min_el = 0.0
                
                raw_dur = act.get("min_dur", act.get("min_duration", act.get("min_pass_contact", 0.0)))
                try: min_dur = float(raw_dur)
                except: min_dur = 0.0
                
                req_cap = str(act.get("req_cap", act.get("required_cap", act.get("x_band_req", "NONE")))).strip().upper()
                if req_cap == 'Y': req_cap = 'DOWN'
                elif req_cap == 'N': req_cap = 'NONE'

                pre_req = str(act.get("pre_req_main", act.get("pre_activity_sequence_id", "NONE"))).strip()

                sat_plans[norm_sat].append({
                    "main": main_title, "sub": sub_title, "sequence_id": seq_id,
                    "min_el": min_el, "min_dur": min_dur, "req_cap": req_cap, "pre_req_main": pre_req
                })

            for norm_sat in sat_plans:
                sat_plans[norm_sat].sort(key=lambda x: x["sequence_id"])

            sat_progress = {norm_sat: 0 for norm_sat in sat_plans.keys()}
            sat_completed_mains = {norm_sat: set() for norm_sat in sat_plans.keys()}

            sorted_passes = sorted(self.raw_pass_data, key=lambda x: x.get('aos', ''))

            for p in sorted_passes:
                p_sat_full = p.get("satellite", "")
                p_sat_norm = normalize_sat_name(p_sat_full)
                st_name = p.get("station", "").split("(")[0].strip()
                
                p_dur = float(p.get("duration_sec", p.get("duration", 0)))
                p_el = float(p.get("max_elevation_deg", p.get("max_el", 0)))
                st_info = st_caps.get(st_name, {'cmd': True, 'down': True})

                matched_plan_key = None
                if p_sat_norm in sat_plans:
                    matched_plan_key = p_sat_norm
                else:
                    for plan_key in sat_plans.keys():
                        if plan_key in p_sat_norm or p_sat_norm in plan_key:
                            matched_plan_key = plan_key
                            break

                if not matched_plan_key:
                    self.final_schedule_data.append({
                        "station": p.get("station", ""), "satellite": p_sat_full,
                        "pass_no": f"Pass {p.get('pass_no', '')}", "aos": p.get("aos", ""),
                        "los": p.get("los", ""), "duration": p_dur, "max_el": p_el,
                        "status": p.get("status", "Normal"), "activity": "N/A (No Plan)"
                    })
                    continue

                curr_step = sat_progress[matched_plan_key]
                plan_list = sat_plans[matched_plan_key]

                if curr_step >= len(plan_list):
                    self.final_schedule_data.append({
                        "station": p.get("station", ""), "satellite": p_sat_full,
                        "pass_no": f"Pass {p.get('pass_no', '')}", "aos": p.get("aos", ""),
                        "los": p.get("los", ""), "duration": p_dur, "max_el": p_el,
                        "status": "Idle", "activity": "Standby / Idle Operations"
                    })
                    continue

                next_task = plan_list[curr_step]
                reject_reasons = []

                if p_el < next_task["min_el"]:
                    reject_reasons.append(f"El Low ({p_el}° < {next_task['min_el']}°)")

                if p_dur < next_task["min_dur"]:
                    reject_reasons.append(f"Dur Short ({p_dur}s < {next_task['min_dur']}s)")

                req = next_task["req_cap"]
                if req == 'CMD' and not st_info['cmd']:
                    reject_reasons.append(f"GS {st_name} No CMD")
                elif req == 'DOWN' and not st_info['down']:
                    reject_reasons.append(f"GS {st_name} No DOWN")
                elif req == 'BOTH' and not (st_info['cmd'] and st_info['down']):
                    reject_reasons.append(f"GS {st_name} No BOTH")

                pre_req = next_task["pre_req_main"].strip().upper()
                completed_upper = {m.upper() for m in sat_completed_mains[matched_plan_key]}
                if pre_req not in ["NONE", "NULL", ""] and pre_req not in completed_upper:
                    reject_reasons.append(f"Pre-req '{next_task['pre_req_main']}' Not Met")

                min_other_prog = min(sat_progress.values()) if sat_progress else 0
                if ((curr_step + 1) - min_other_prog) > max_lead_steps:
                    reject_reasons.append(f"Step Lock (Lead > {max_lead_steps})")

                if not reject_reasons:
                    sub_str = f" ({next_task['sub']})" if next_task['sub'] else ""
                    assigned_text = f"[{next_task['sequence_id']}] {next_task['main']}{sub_str}"
                    status_text = "Allocated"
                    sat_progress[matched_plan_key] += 1
                    sat_completed_mains[matched_plan_key].add(next_task["main"])
                else:
                    assigned_text = f"[{next_task['main']}] Blocked ({', '.join(reject_reasons)})"
                    status_text = "Bypassed"

                self.final_schedule_data.append({
                    "station": p.get("station", ""), "satellite": p_sat_full,
                    "pass_no": f"Pass {p.get('pass_no', '')}", "aos": p.get("aos", ""),
                    "los": p.get("los", ""), "duration": p_dur, "max_el": p_el,
                    "status": status_text, "activity": assigned_text
                })

            self.populate_final_table_ui()
            QMessageBox.information(self, "Allocation Success", "Successfully compiled LEOP schedule.")
            
        except Exception as e:
            QMessageBox.critical(self, "Engine Error", f"Failed to execute LEOP schedule:\n{str(e)}")

    def populate_final_table_ui(self):
        self.final_table.setRowCount(0)
        self.final_table.setRowCount(len(self.final_schedule_data))
        for row_idx, item in enumerate(self.final_schedule_data):
            self.final_table.setItem(row_idx, 0, QTableWidgetItem(item["station"]))
            self.final_table.setItem(row_idx, 1, QTableWidgetItem(item["satellite"]))
            self.final_table.setItem(row_idx, 2, QTableWidgetItem(item["pass_no"]))
            self.final_table.setItem(row_idx, 3, QTableWidgetItem(item["aos"]))
            self.final_table.setItem(row_idx, 4, QTableWidgetItem(item["los"]))
            self.final_table.setItem(row_idx, 5, QTableWidgetItem(str(item["duration"])))
            self.final_table.setItem(row_idx, 6, QTableWidgetItem(str(item["max_el"])))
            self.final_table.setItem(row_idx, 7, QTableWidgetItem(item["status"]))
            self.final_table.setItem(row_idx, 8, QTableWidgetItem(item["activity"]))
        self.refresh_table_colors()

    def refresh_table_colors(self):
        """🔥 [완벽 보완]: 정규화된 키를 사용하여 지상국별 / 위성별 고유 파스텔톤 일괄 배정"""
        row_count = self.final_table.rowCount()
        if row_count == 0: return
        
        is_station_mode = self.radio_station.isChecked()
        
        for r in range(row_count):
            if is_station_mode:
                st_item = self.final_table.item(r, 0)
                st_name = st_item.text().split("(")[0].strip() if st_item else ""
                _, chosen_color = color_manager.get_station_colors(st_name)
            else:
                sat_item = self.final_table.item(r, 1)
                sat_raw = sat_item.text() if sat_item else ""
                sat_clean = normalize_sat_name(sat_raw)
                _, chosen_color = color_manager.get_colors(sat_clean)
                
            for c in range(self.final_table.columnCount()):
                cell = self.final_table.item(r, c)
                if cell: cell.setBackground(chosen_color)

    def click_export_csv(self):
        if not self.final_schedule_data: return
        path, _ = QFileDialog.getSaveFileName(self, "Save Final Integrated CSV", self.final_output_dir, "CSV Files (*.csv)")
        if path:
            export_final_schedule_to_csv(path, self.final_schedule_data)
            QMessageBox.information(self, "Export Success", "CSV Timeline exported successfully to final_output.")

    def click_export_excel(self):
        if not self.final_schedule_data: return
        path, _ = QFileDialog.getSaveFileName(self, "Save Final Integrated Excel", self.final_output_dir, "Excel Files (*.xlsx)")
        if path:
            color_mode = "STATION" if self.radio_station.isChecked() else "SATELLITE"
            export_final_schedule_to_excel(path, self.final_schedule_data, color_mode)
            QMessageBox.information(self, "Export Success", "Integrated Excel sheet saved successfully to final_output.")