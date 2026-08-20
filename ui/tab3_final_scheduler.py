import os
import yaml
import re
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTableWidget, QTableWidgetItem, QLabel, QFileDialog, 
                             QHeaderView, QMessageBox, QRadioButton, QButtonGroup, 
                             QSpinBox, QComboBox, QDialog, QListWidget, QListWidgetItem, 
                             QDialogButtonBox)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QColor, QDesktopServices

from core.color_manager import color_manager
from core.exporter import export_final_schedule_to_csv, export_final_schedule_to_excel
from core.plan_parser import normalize_sat_name


# ==============================================================================
# [수동 재할당 팝업] 패스 더블클릭 시 수동 액티비티 선택 다이얼로그
# ==============================================================================
class ManualActivityDialog(QDialog):
    def __init__(self, pass_item, candidate_tasks, current_activity, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🛠️ Manual Activity Reassignment")
        self.resize(520, 400)
        self.pass_item = pass_item
        self.candidate_tasks = candidate_tasks
        self.selected_activity = current_activity
        self.selected_status = pass_item.get("status", "Bypassed")
        self.selected_remark = pass_item.get("remark", "")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        p = self.pass_item
        info_text = (f"<b>🛰️ {p.get('satellite')} @ {p.get('station')}</b><br>"
                     f"AOS: {p.get('aos')} | LOS: {p.get('los')}<br>"
                     f"Duration: {p.get('duration')}s | Max El: {p.get('max_el')}°")
        layout.addWidget(QLabel(info_text))
        layout.addWidget(QLabel("<b>Select Activity to assign to this pass:</b>"))

        self.list_widget = QListWidget()
        
        # 1. 시스템 기본 옵션
        self.list_widget.addItem(QListWidgetItem("🚫 [Bypassed] Skip / No Activity"))
        self.list_widget.addItem(QListWidgetItem("📡 [Standby] Routine TM Downlink / Health Check"))
        
        # 2. 해당 위성의 후보 태스크 목록
        for task in self.candidate_tasks:
            sub_str = f" ({task['sub']})" if task.get('sub') else ""
            item_str = f"[{task['sequence_id']}] {task['main']}{sub_str} [Req: {task['req_cap']}, El≥{task['min_el']}°, Dur≥{task['min_dur']}s]"
            item = QListWidgetItem(item_str)
            item.setData(Qt.ItemDataRole.UserRole, task)
            self.list_widget.addItem(item)
            
        layout.addWidget(self.list_widget)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self.on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def on_accept(self):
        curr_item = self.list_widget.currentItem()
        if not curr_item:
            self.reject()
            return
        
        task_data = curr_item.data(Qt.ItemDataRole.UserRole)
        if task_data:
            sub_str = f" ({task_data['sub']})" if task_data.get('sub') else ""
            self.selected_activity = f"[{task_data['sequence_id']}] {task_data['main']}{sub_str} (Manual)"
            self.selected_status = "Allocated"
            self.selected_remark = task_data.get("remark", "")
        else:
            txt = curr_item.text()
            if "Standby" in txt:
                self.selected_activity = "[Standby] Routine TM Downlink / Health Check (Manual)"
                self.selected_status = "Standby"
                self.selected_remark = ""
            else:
                self.selected_activity = "Manual Bypassed"
                self.selected_status = "Bypassed"
                self.selected_remark = ""
        self.accept()

    def get_result(self):
        return self.selected_status, self.selected_activity, self.selected_remark


# ==============================================================================
# [메인 탭] Tab 3: LEOP 시퀀스 및 제약 조건 기반 최종 미션 통합 스케줄러
# ==============================================================================
class FinalSchedulerTab(QWidget):
    """
    Tab 3 메인 UI 및 스케줄링 컴파일 엔진 클래스
    
    [기능 설명]
    - Tab 1의 패스 예측 결과(.yaml)와 Tab 2의 미션 제약 조건(.yaml)을 로드합니다.
    - 안테나 기능(CMD/DOWN), 최소 고도각, 최소 교신 시간, 선행 작업(Pre-req), 
      위성 간 단계 격차 제한(Max Step Lead)을 검증하여 최종 미션을 할당(Allocated/Bypassed/Idle/Standby)합니다.
    - Strict Sequential, Look-Ahead Pull, Routine Standby Fill의 3가지 스케줄링 전략을 지원합니다.
    - 테이블 셀 더블클릭을 통한 수동 오버라이드 및 10개 컬럼 파스텔톤 그리드를 제공합니다.
    """
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        self.plans_dir = "plans"
        self.pass_output_dir = "pass_output"
        self.final_output_dir = "final_output"
        
        # 기본 디렉토리 자동 생성
        if not os.path.exists(self.plans_dir): os.makedirs(self.plans_dir)
        if not os.path.exists(self.pass_output_dir): os.makedirs(self.pass_output_dir)
        if not os.path.exists(self.final_output_dir): os.makedirs(self.final_output_dir)
        
        self.raw_pass_data = None
        self.raw_constraint_data = None
        self.final_schedule_data = []
        self.sat_plans_cached = {}
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        top_ctrl = QHBoxLayout()
        
        # ----------------------------------------------------------------------
        # 1. 상단 컨트롤 패널 (파일 로드, Max Lead 설정, 전략 선택, 색상 모드)
        # ----------------------------------------------------------------------
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

        top_ctrl.addSpacing(10)

        # 💡 할당 전략 선택 콤보박스
        top_ctrl.addWidget(QLabel("<b>Strategy:</b>"))
        self.combo_strategy = QComboBox()
        self.combo_strategy.addItems([
            "Strict Sequential (Default)",
            "Look-Ahead & Fill (Pull Ahead)",
            "Fill with Routine Standby (Keep Order)"
        ])
        self.combo_strategy.setToolTip(
            "• Strict Sequential: 순서를 엄격히 준수하며 조건 불만족 시 Pass 스킵 (Bypassed)\n"
            "• Look-Ahead & Fill: Block 시 선행조건을 만족하는 뒷순번 유효작업 당겨오기 (진도 단축)\n"
            "• Fill with Routine Standby: 순번은 그대로 대기시키고 유휴 패스에 루틴 TM 점검 채우기"
        )
        top_ctrl.addWidget(self.combo_strategy)
        
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
        
        # ----------------------------------------------------------------------
        # 2. 중앙 최종 스케줄 그리드 테이블 (더블클릭 수동 재할당 지원)
        # ----------------------------------------------------------------------
        self.final_table = QTableWidget()
        self.final_table.setColumnCount(10)
        self.final_table.setHorizontalHeaderLabels([
            "Ground Station", "Satellite", "Pass No. (Orbit)", "AOS (UTC)", 
            "LOS (UTC)", "Duration (s)", "Max El (deg)", "Status", "💡 Mission Activity", "📝 Remark / Notes"
        ])
        self.final_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.final_table.horizontalHeader().setDefaultSectionSize(130)
        self.final_table.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)
        self.final_table.horizontalHeader().setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)
        self.final_table.setWordWrap(True)
        self.final_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.final_table.cellDoubleClicked.connect(self.handle_cell_double_clicked)
        layout.addWidget(self.final_table)
        
        # ----------------------------------------------------------------------
        # 3. 하단 컨트롤 패널 (CSV / Excel 저장)
        # ----------------------------------------------------------------------
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

    # --------------------------------------------------------------------------
    # 파일 탐색기 열기 유틸리티
    # --------------------------------------------------------------------------
    def open_local_folder(self, folder_path):
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        abs_path = os.path.abspath(folder_path)
        QDesktopServices.openUrl(QUrl.fromLocalFile(abs_path))

    # --------------------------------------------------------------------------
    # YAML 데이터 로드 및 준비 상태 업데이트
    # --------------------------------------------------------------------------
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

    # --------------------------------------------------------------------------
    # 개별 태스크 제약 조건 검증 헬퍼
    # --------------------------------------------------------------------------
    def _evaluate_task_constraints(self, task, p_el, p_dur, st_info, st_name, completed_mains, curr_step, min_other_prog, max_lead_steps):
        reject_reasons = []

        if p_el < task["min_el"]:
            reject_reasons.append(f"El Low ({p_el}° < {task['min_el']}°)")

        if p_dur < task["min_dur"]:
            reject_reasons.append(f"Dur Short ({p_dur}s < {task['min_dur']}s)")

        req = task["req_cap"]
        if req == 'CMD' and not st_info['cmd']:
            reject_reasons.append(f"GS {st_name} No CMD")
        elif req == 'DOWN' and not st_info['down']:
            reject_reasons.append(f"GS {st_name} No DOWN")
        elif req == 'BOTH':
            if not st_info['cmd'] and not st_info['down']:
                reject_reasons.append(f"GS {st_name} No CMD/DOWN")
            elif not st_info['cmd']:
                reject_reasons.append(f"GS {st_name} No CMD")
            elif not st_info['down']:
                reject_reasons.append(f"GS {st_name} No DOWN")

        pre_req = task["pre_req_main"].strip().upper()
        completed_upper = {m.upper() for m in completed_mains}
        if pre_req not in ["NONE", "NULL", ""] and pre_req not in completed_upper:
            reject_reasons.append(f"Pre-req '{task['pre_req_main']}' Not Met")

        if ((curr_step + 1) - min_other_prog) > max_lead_steps:
            reject_reasons.append(f"Step Lock (Lead > {max_lead_steps})")

        return reject_reasons

    # --------------------------------------------------------------------------
    # [핵심 엔진] LEOP 미션 시퀀스 및 다중 전략 기반 스케줄러
    # --------------------------------------------------------------------------
    def click_generate_schedule(self):
        if not self.raw_pass_data or self.raw_constraint_data is None: return
            
        try:
            self.final_schedule_data = []
            max_lead_steps = self.spin_max_lead.value()
            strategy_idx = self.combo_strategy.currentIndex()  # 0: Strict, 1: Look-Ahead, 2: Standby Fill
            
            # 1. 지상국 기능(Downlink: 3번, Command: 4번) 파싱
            station_configs = getattr(self.main_app, 'station_data', [])
            st_caps = {}
            for st in station_configs:
                st_name = str(st[0]).strip()
                is_down = (str(st[3]).strip().upper() == 'Y') if len(st) > 3 else True
                is_cmd = (str(st[4]).strip().upper() == 'Y') if len(st) > 4 else True
                st_caps[st_name] = {'cmd': is_cmd, 'down': is_down}

            # 2. 미션 플랜 파싱 및 정규화
            sat_plans = {}
            for act in self.raw_constraint_data:
                raw_sat = act.get("sat_id", act.get("satellite", ""))
                norm_sat = normalize_sat_name(raw_sat)
                if not norm_sat: continue
                
                if norm_sat not in sat_plans: sat_plans[norm_sat] = []
                    
                main_title = str(act.get("main", act.get("activity", ""))).strip()
                sub_title = str(act.get("sub", "")).strip()
                remark_text = str(act.get("remark", act.get("remarks", act.get("note", "")))).strip()
                
                raw_seq = act.get("sequence_id", act.get("activity_sequence_id", len(sat_plans[norm_sat]) + 1))
                try: seq_id = int(raw_seq)
                except Exception: seq_id = len(sat_plans[norm_sat]) + 1
                
                try: min_el = float(act.get("min_el", 0.0))
                except Exception: min_el = 0.0
                
                raw_dur = act.get("min_dur", act.get("min_duration", act.get("min_pass_contact", 0.0)))
                try: min_dur = float(raw_dur)
                except Exception: min_dur = 0.0
                
                raw_req = str(act.get("req_cap", act.get("required_cap", act.get("required_capability", "NONE")))).strip().upper()
                if raw_req in ['CMD', 'COMMAND', 'TC', 'UPLINK', 'CMD_ONLY', 'TX']:
                    req_cap = 'CMD'
                elif raw_req in ['DOWN', 'DOWNLOAD', 'TM', 'DOWNLINK', 'X_BAND', 'RX']:
                    req_cap = 'DOWN'
                elif raw_req in ['BOTH', 'ALL', 'CMD+DOWN', 'DOWN+CMD', 'FULL', 'TX/RX']:
                    req_cap = 'BOTH'
                else:
                    req_cap = 'NONE'

                pre_req = str(act.get("pre_req_main", act.get("pre_activity_sequence_id", "NONE"))).strip()

                sat_plans[norm_sat].append({
                    "main": main_title, "sub": sub_title, "remark": remark_text, "sequence_id": seq_id,
                    "min_el": min_el, "min_dur": min_dur, "req_cap": req_cap, "pre_req_main": pre_req,
                    "completed": False
                })

            for norm_sat in sat_plans:
                sat_plans[norm_sat].sort(key=lambda x: x["sequence_id"])

            self.sat_plans_cached = sat_plans

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
                        "status": p.get("status", "Normal"), "activity": "N/A (No Plan)", "remark": "",
                        "raw_pass": p
                    })
                    continue

                plan_list = sat_plans[matched_plan_key]
                uncompleted_tasks = [t for t in plan_list if not t["completed"]]

                if not uncompleted_tasks:
                    self.final_schedule_data.append({
                        "station": p.get("station", ""), "satellite": p_sat_full,
                        "pass_no": f"Pass {p.get('pass_no', '')}", "aos": p.get("aos", ""),
                        "los": p.get("los", ""), "duration": p_dur, "max_el": p_el,
                        "status": "Idle", "activity": "Standby / Idle Operations", "remark": "",
                        "raw_pass": p
                    })
                    continue

                curr_step = len(plan_list) - len(uncompleted_tasks)
                min_other_prog = min([len(sat_plans[k]) - len([t for t in sat_plans[k] if not t["completed"]]) for k in sat_plans]) if sat_plans else 0

                assigned_task = None
                assigned_status = "Bypassed"
                assigned_activity = ""
                assigned_remark = ""

                # --- Mode 0: Strict Sequential (기본 순차 검사) ---
                if strategy_idx == 0:
                    primary_task = uncompleted_tasks[0]
                    reject_reasons = self._evaluate_task_constraints(
                        primary_task, p_el, p_dur, st_info, st_name, 
                        sat_completed_mains[matched_plan_key], curr_step, min_other_prog, max_lead_steps
                    )
                    if not reject_reasons:
                        assigned_task = primary_task
                        primary_task["completed"] = True
                        sat_completed_mains[matched_plan_key].add(primary_task["main"])
                        sub_str = f" ({primary_task['sub']})" if primary_task['sub'] else ""
                        assigned_activity = f"[{primary_task['sequence_id']}] {primary_task['main']}{sub_str}"
                        assigned_status = "Allocated"
                        assigned_remark = primary_task.get("remark", "")
                    else:
                        assigned_activity = f"[{primary_task['main']}] Blocked ({', '.join(reject_reasons)})"
                        assigned_status = "Bypassed"
                        assigned_remark = primary_task.get("remark", "")

                # --- Mode 1: Look-Ahead & Fill (선행조건 충족 시 유효작업 당겨오기) ---
                elif strategy_idx == 1:
                    primary_task = uncompleted_tasks[0]
                    first_reasons = []
                    
                    for candidate_task in uncompleted_tasks:
                        reasons = self._evaluate_task_constraints(
                            candidate_task, p_el, p_dur, st_info, st_name, 
                            sat_completed_mains[matched_plan_key], curr_step, min_other_prog, max_lead_steps
                        )
                        if not reasons:
                            assigned_task = candidate_task
                            candidate_task["completed"] = True
                            sat_completed_mains[matched_plan_key].add(candidate_task["main"])
                            sub_str = f" ({candidate_task['sub']})" if candidate_task['sub'] else ""
                            is_pulled = (candidate_task != primary_task)
                            pulled_tag = " ⚡[Pulled Ahead]" if is_pulled else ""
                            assigned_activity = f"[{candidate_task['sequence_id']}] {candidate_task['main']}{sub_str}{pulled_tag}"
                            assigned_status = "Allocated"
                            assigned_remark = candidate_task.get("remark", "")
                            break
                        elif candidate_task == primary_task:
                            first_reasons = reasons

                    if not assigned_task:
                        assigned_activity = f"[{primary_task['main']}] Blocked ({', '.join(first_reasons)})"
                        assigned_status = "Bypassed"
                        assigned_remark = primary_task.get("remark", "")

                # --- Mode 2: Fill with Routine Standby (순번 유지 + 유휴 패스 TM 채우기) ---
                elif strategy_idx == 2:
                    primary_task = uncompleted_tasks[0]
                    reject_reasons = self._evaluate_task_constraints(
                        primary_task, p_el, p_dur, st_info, st_name, 
                        sat_completed_mains[matched_plan_key], curr_step, min_other_prog, max_lead_steps
                    )
                    if not reject_reasons:
                        assigned_task = primary_task
                        primary_task["completed"] = True
                        sat_completed_mains[matched_plan_key].add(primary_task["main"])
                        sub_str = f" ({primary_task['sub']})" if primary_task['sub'] else ""
                        assigned_activity = f"[{primary_task['sequence_id']}] {primary_task['main']}{sub_str}"
                        assigned_status = "Allocated"
                        assigned_remark = primary_task.get("remark", "")
                    else:
                        assigned_status = "Standby"
                        assigned_activity = f"📡 [Standby] Routine TM Downlink / Health Check (Waits for [{primary_task['main']}])"
                        assigned_remark = f"Primary Task Blocked: {', '.join(reject_reasons)}"

                self.final_schedule_data.append({
                    "station": p.get("station", ""), "satellite": p_sat_full,
                    "pass_no": f"Pass {p.get('pass_no', '')}", "aos": p.get("aos", ""),
                    "los": p.get("los", ""), "duration": p_dur, "max_el": p_el,
                    "status": assigned_status, "activity": assigned_activity,
                    "remark": assigned_remark, "raw_pass": p
                })

            self.populate_final_table_ui()
            strat_name = self.combo_strategy.currentText()
            QMessageBox.information(self, "Allocation Success", f"Successfully compiled schedule using:\n'{strat_name}'")
            
        except Exception as e:
            QMessageBox.critical(self, "Engine Error", f"Failed to execute LEOP schedule:\n{str(e)}")

    # --------------------------------------------------------------------------
    # 테이블 행 더블클릭 수동 오버라이드 핸들러
    # --------------------------------------------------------------------------
    def handle_cell_double_clicked(self, row, col):
        if row < 0 or row >= len(self.final_schedule_data): return
        
        pass_item = self.final_schedule_data[row]
        sat_norm = normalize_sat_name(pass_item.get("satellite", ""))
        candidate_tasks = self.sat_plans_cached.get(sat_norm, [])

        dialog = ManualActivityDialog(
            pass_item=pass_item,
            candidate_tasks=candidate_tasks,
            current_activity=pass_item.get("activity", ""),
            parent=self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_status, new_act, new_rem = dialog.get_result()
            pass_item["status"] = new_status
            pass_item["activity"] = new_act
            if new_rem: pass_item["remark"] = new_rem

            self.final_table.setItem(row, 7, QTableWidgetItem(new_status))
            self.final_table.setItem(row, 8, QTableWidgetItem(new_act))
            self.final_table.setItem(row, 9, QTableWidgetItem(pass_item.get("remark", "")))
            self.refresh_table_colors()

    # --------------------------------------------------------------------------
    # UI 표 세팅 및 파스텔톤 색상 바인딩 (10개 컬럼)
    # --------------------------------------------------------------------------
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
            self.final_table.setItem(row_idx, 9, QTableWidgetItem(item.get("remark", "")))
        self.refresh_table_colors()

    def refresh_table_colors(self):
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

    # --------------------------------------------------------------------------
    # CSV / Excel 저장 이벤트 핸들러
    # --------------------------------------------------------------------------
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