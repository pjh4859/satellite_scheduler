import os
import yaml
import re
from datetime import datetime
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
from core.scheduler import build_capacity_lookup


def _parse_iso_dt(value):
    """
    💡 [안테나 점검 일정 지원] Tab3는 YAML에서 불러온 패스 데이터를 다루기 때문에
    aos/los가 실제 datetime 객체가 아니라 ISO 8601 문자열입니다 (예: "2026-01-01T00:00:00Z").
    반면 안테나 점검 오버라이드의 start_dt/end_dt는 실제 datetime 객체로 저장되어 있어서,
    이 둘을 그대로 비교하면 타입이 달라 TypeError가 납니다. 이 함수가 그 문자열을
    datetime으로 변환해줍니다. 이미 datetime이면 그대로 반환합니다(방어적 처리).
    """
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


# ==============================================================================
# [수동 재할당 팝업] 패스 더블클릭 시 수동 위성/액티비티 선택 다이얼로그
# ==============================================================================
class ManualActivityDialog(QDialog):
    def __init__(self, pass_item, all_sat_plans, current_activity, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🛠️ Manual Activity & Satellite Reassignment")
        self.resize(560, 440)
        self.pass_item = pass_item
        self.all_sat_plans = all_sat_plans
        self.selected_sat = pass_item.get("satellite", "")
        self.selected_activity = current_activity
        self.selected_status = pass_item.get("status", "Bypassed")
        self.selected_remark = pass_item.get("remark", "")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        p = self.pass_item
        info_text = (f"<b>🛰️ Current Pass: {p.get('satellite')} @ {p.get('station')}</b><br>"
                     f"AOS: {p.get('aos')} | LOS: {p.get('los')}<br>"
                     f"Duration: {p.get('duration')}s | Max El: {p.get('max_el')}°")
        layout.addWidget(QLabel(info_text))

        sat_lay = QHBoxLayout()
        sat_lay.addWidget(QLabel("<b>Target Satellite:</b>"))
        self.combo_sat = QComboBox()
        norm_curr_sat = normalize_sat_name(self.selected_sat)
        sat_keys = list(self.all_sat_plans.keys())
        self.combo_sat.addItems(sat_keys)
        if norm_curr_sat in sat_keys:
            self.combo_sat.setCurrentText(norm_curr_sat)
        self.combo_sat.currentTextChanged.connect(self.populate_task_list)
        sat_lay.addWidget(self.combo_sat)
        layout.addLayout(sat_lay)

        layout.addWidget(QLabel("<b>Select Activity to assign:</b>"))
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        self.populate_task_list(self.combo_sat.currentText())

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self.on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def populate_task_list(self, sat_name):
        self.list_widget.clear()
        self.list_widget.addItem(QListWidgetItem("🚫 [Bypassed] Skip / No Activity"))
        self.list_widget.addItem(QListWidgetItem("📡 [Standby] Routine TM Downlink / Health Check"))
        
        tasks = self.all_sat_plans.get(sat_name, [])
        for task in tasks:
            sub_str = f" ({task['sub']})" if task.get('sub') else ""
            item_str = f"[{task['sequence_id']}] {task['main']}{sub_str} [Req: {task['req_cap']}, El≥{task['min_el']}°, Dur≥{task['min_dur']}s]"
            item = QListWidgetItem(item_str)
            item.setData(Qt.ItemDataRole.UserRole, task)
            self.list_widget.addItem(item)

    def on_accept(self):
        curr_item = self.list_widget.currentItem()
        if not curr_item:
            self.reject()
            return
        
        self.selected_sat = self.combo_sat.currentText()
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
        return self.selected_sat, self.selected_status, self.selected_activity, self.selected_remark


# ==============================================================================
# [메인 탭] Tab 3: LEOP 시퀀스 및 제약 조건 기반 최종 미션 통합 스케줄러
# ==============================================================================
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
        self.all_candidate_passes = []
        self.raw_constraint_data = None
        self.final_schedule_data = []
        self.sat_plans_cached = {}
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        top_ctrl = QHBoxLayout()
        
        # 1. 상단 컨트롤 패널
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

        # 💡 스케줄링 전략 선택 콤보박스 (상세 설명 툴팁 내장)
        top_ctrl.addWidget(QLabel("<b>Strategy:</b>"))
        self.combo_strategy = QComboBox()
        self.combo_strategy.addItems([
            "Strict Sequential (Default)",
            "Look-Ahead & Fill (Pull Ahead)",
            "Fill with Routine Standby (Keep Order)",
            "🌐 Cross-Satellite Swap (Multi-Sat Fallback)"
        ])
        self.combo_strategy.setToolTip(
            "• Strict Sequential: 순서를 엄격히 준수하며 조건 불만족 시 Pass 스킵 (Bypassed)\n"
            "• Look-Ahead & Fill: Block 시 동일 위성의 선행조건 충족 뒷번호 작업 당겨오기\n"
            "• Fill with Routine Standby: 순서 유지, 유휴 패스에 루틴 TM 점검 채우기\n"
            "• Cross-Satellite Swap:\n"
            "   [1단계] 본래 작업 시도\n"
            "   [2단계] Block 시 겹치는 타 위성 작업으로 패스 스왑\n"
            "   [3단계] 스왑 불가 시 동일 위성 작업 당겨오기 (Look-Ahead)\n"
            "   [4단계] 모두 불가 시 Bypassed 유지"
        )
        self.combo_strategy.currentIndexChanged.connect(self.update_strategy_guide_label)
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

        # 💡 상단 전략 가이드 보조 라벨
        self.lbl_strategy_guide = QLabel()
        self.lbl_strategy_guide.setStyleSheet("color: #555555; font-size: 11px; margin-left: 5px; margin-bottom: 2px;")
        layout.addWidget(self.lbl_strategy_guide)
        self.update_strategy_guide_label(self.combo_strategy.currentIndex())
        
        # 2. 그리드 테이블
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
        
        # 3. 하단 컨트롤 패널
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

    def update_strategy_guide_label(self, idx):
        guides = {
            0: "ℹ️ <b>Strict Sequential</b>: 순서를 엄격히 준수하며 조건 미달 시 패스를 스킵(Bypassed)합니다.",
            1: "ℹ️ <b>Look-Ahead & Fill</b>: 차례 작업이 Block되면 선행조건이 완료된 뒷순번 유효 작업을 먼저 당겨와 일정을 단축합니다.",
            2: "ℹ️ <b>Routine Standby Fill</b>: 원래 시퀀스 순번은 그대로 대기시키고, 유휴 패스에 루틴 상태점검(TM)을 채워 낭비를 방지합니다.",
            3: "ℹ️ <b>Cross-Satellite Swap Flow</b>: ①본래 작업 시도 ➔ ②Block 시 <b>타 위성 스왑</b> ➔ ③불가 시 <b>동일 위성 당겨오기</b> ➔ ④최후 Bypassed"
        }
        self.lbl_strategy_guide.setText(guides.get(idx, ""))

    def open_local_folder(self, folder_path):
        if not os.path.exists(folder_path): os.makedirs(folder_path)
        abs_path = os.path.abspath(folder_path)
        QDesktopServices.openUrl(QUrl.fromLocalFile(abs_path))

    def click_load_pass_yaml(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Tab1 Predicted Passes YAML", self.pass_output_dir, "YAML Files (*.yaml)")
        if not path: return
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f) or {}
            self.raw_pass_data = content.get("predicted_passes", [])
            self.all_candidate_passes = content.get("all_candidate_passes", self.raw_pass_data)
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

    def _evaluate_task_constraints(self, task, p_el, p_dur, st_info, st_name, completed_mains, curr_step, min_other_prog, max_lead_steps,
                                    tx_occupied_count=0, tx_capacity=1):
        """
        :param tx_occupied_count: 이 패스의 시간대(aos~los)와 겹치는 다른 패스들 중,
                                   이미 이 지상국에서 CMD/BOTH(커맨딩)로 확정 배정된 개수.
                                   (M2: TX 단일/다중 자원 추적 - 안테나 대수와 무관하게
                                    "커맨딩 체인"은 별도의 용량으로 관리됩니다)
        :param tx_capacity: 이 지상국이 동시에 커맨딩(TX) 가능한 채널 수 (기본 1).
        """
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

        # 💡 [M2] TX(커맨딩) 단일/다중 자원 제약 검사
        #    이 작업이 CMD 또는 BOTH(커맨딩 포함)를 요구하는데, 같은 시간대에 이미
        #    이 지상국의 TX 용량만큼 다른 패스가 커맨딩을 쓰고 있다면 배정할 수 없습니다.
        #    (RX는 M1에서 안테나 대수만큼 동시 패스 자체가 허용되지만, 업링크 체인은
        #     보통 1개뿐이라 "몇 대의 안테나로 동시에 보고 있는가"와는 별개의 제약입니다)
        if req in ('CMD', 'BOTH') and tx_occupied_count >= tx_capacity:
            reject_reasons.append(f"GS {st_name} TX Busy ({tx_occupied_count}/{tx_capacity})")

        pre_req = task["pre_req_main"].strip().upper()
        completed_upper = {m.upper() for m in completed_mains}
        if pre_req not in ["NONE", "NULL", ""] and pre_req not in completed_upper:
            reject_reasons.append(f"Pre-req '{task['pre_req_main']}' Not Met")

        if ((curr_step + 1) - min_other_prog) > max_lead_steps:
            reject_reasons.append(f"Step Lock (Lead > {max_lead_steps})")

        return reject_reasons

    # --------------------------------------------------------------------------
    # 💡 [M2 신규] TX(커맨딩) 자원 점유 추적 헬퍼
    # ------------------------------------------------------------------------------
    # tx_occupied_intervals: {station_name: [(aos_str, los_str), ...]} 형태로,
    # "이 지상국에서 이미 CMD/BOTH로 확정 배정된 시간 구간"들을 계속 누적해서 기록합니다.
    # aos/los는 YAML에서 그대로 불러온 ISO 8601 형식 문자열이며, 이 포맷은 문자열끼리
    # 그대로 비교(<=, >=)해도 시간 순서와 동일하게 비교되므로 datetime 파싱 없이 처리합니다.
    # --------------------------------------------------------------------------
    def _count_tx_overlaps(self, tx_occupied_intervals, st_name, aos_str, los_str):
        """이 지상국에서, 주어진 [aos_str, los_str] 구간과 시간이 겹치는
        '이미 확정된 CMD/BOTH 점유 구간'이 몇 개인지 셉니다."""
        intervals = tx_occupied_intervals.get(st_name, [])
        count = 0
        for occ_aos, occ_los in intervals:
            # 두 구간이 겹치지 않는 경우: 하나가 끝난 뒤에 다른 하나가 시작하는 경우뿐
            if not (occ_los <= aos_str or occ_aos >= los_str):
                count += 1
        return count

    def _register_tx_usage(self, tx_occupied_intervals, st_name, aos_str, los_str):
        """이 지상국의 [aos_str, los_str] 구간을 'CMD/BOTH로 확정 사용됨'으로 기록합니다."""
        tx_occupied_intervals.setdefault(st_name, []).append((aos_str, los_str))

    # --------------------------------------------------------------------------
    # [핵심 엔진] LEOP 미션 스케줄러 (Swarm Cross-Satellite Swap 지원)
    # --------------------------------------------------------------------------
    def click_generate_schedule(self):
        if not self.raw_pass_data or self.raw_constraint_data is None: return
            
        try:
            self.final_schedule_data = []
            max_lead_steps = self.spin_max_lead.value()
            strategy_idx = self.combo_strategy.currentIndex()  # 0: Strict, 1: Look-Ahead, 2: Standby Fill, 3: Cross-Sat Swap
            
            # 1. 지상국 기능 파싱 (3: Downlink, 4: Command, 6: TX_Capacity)
            station_configs = getattr(self.main_app, 'station_data', [])
            # 💡 [안테나 점검 일정 지원] Tab1에서 등록한 점검 일정을 그대로 가져와서 TX 용량에도 반영
            antenna_overrides = getattr(self.main_app, 'antenna_overrides', [])
            st_caps = {}
            for st in station_configs:
                st_name = str(st[0]).strip()
                # ⚠️ [버그 수정] 기존 코드는 `else True[cite: 7]`처럼 잘못된 문자열이 섞여 있어
                #    len(st) <= 3인 경우(사실상 발생하지 않지만) 실행되면 NameError로 죽는 죽은 코드였습니다.
                is_down = (str(st[3]).strip().upper() == 'Y') if len(st) > 3 else True
                is_cmd = (str(st[4]).strip().upper() == 'Y') if len(st) > 4 else True
                # 💡 [M2] TX_Capacity(인덱스 6). 구버전 station_data(길이 5)면 기본값 1.
                base_tx_capacity = int(st[6]) if len(st) > 6 else 1
                # 💡 [안테나 점검 일정 지원] 이 지상국에 해당하는 점검 오버라이드만 추려서
                #    "그 시각의 유효 TX 용량"을 돌려주는 함수로 구성 (오버라이드 없으면 기존과 동일)
                overrides_for_station = [ov for ov in antenna_overrides if ov.get("station") == st_name]
                tx_capacity_fn = build_capacity_lookup(base_tx_capacity, overrides_for_station, "tx_capacity")
                st_caps[st_name] = {'cmd': is_cmd, 'down': is_down, 'tx_capacity_fn': tx_capacity_fn}

            # 💡 [M2] 지상국별 "이미 CMD/BOTH로 확정 배정된 시간 구간" 누적 트래커.
            #    패스를 시간순으로 훑으면서, 커맨딩이 배정될 때마다 여기에 구간을 추가합니다.
            #    나중 패스를 평가할 때 이 트래커를 참조해서 TX 자원이 이미 꽉 찼는지 확인합니다.
            tx_occupied_intervals = {}

            # 2. 미션 제약조건 파싱
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
                p_aos_str = p.get("aos", "")
                p_los_str = p.get("los", "")
                st_info = st_caps.get(st_name, {'cmd': True, 'down': True, 'tx_capacity_fn': (lambda dt: 1)})

                # 💡 [M2] 이 패스(p)의 시간대 기준으로, 이 지상국의 TX가 이미 몇 개 점유 중인지 계산
                p_tx_occupied = self._count_tx_overlaps(tx_occupied_intervals, st_name, p_aos_str, p_los_str)
                # 💡 [안테나 점검 일정 지원] 이 패스 자신의 AOS 시각 기준으로 그때의 유효 TX 용량을 조회
                #    (aos는 문자열이므로 오버라이드의 datetime과 비교 가능하게 먼저 변환)
                p_aos_dt = _parse_iso_dt(p['aos'])
                p_tx_capacity = st_info.get('tx_capacity_fn', lambda dt: 1)(p_aos_dt) if p_aos_dt else 1

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
                        "pass_no": f"Pass {p.get('pass_no', '')}", "aos": p_aos_str,
                        "los": p_los_str, "duration": p_dur, "max_el": p_el,
                        "status": p.get("status", "Normal"), "activity": "N/A (No Plan)", "remark": "",
                        "raw_pass": p
                    })
                    continue

                plan_list = sat_plans[matched_plan_key]
                uncompleted_tasks = [t for t in plan_list if not t["completed"]]

                if not uncompleted_tasks:
                    self.final_schedule_data.append({
                        "station": p.get("station", ""), "satellite": p_sat_full,
                        "pass_no": f"Pass {p.get('pass_no', '')}", "aos": p_aos_str,
                        "los": p_los_str, "duration": p_dur, "max_el": p_el,
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
                assigned_sat = p_sat_full
                assigned_pass_no = f"Pass {p.get('pass_no', '')}"
                # 💡 [버그 수정] 최종 표에 표시될 시간/기간/고도각. 기본값은 "현재 처리 중인 패스(p)"의 값이지만,
                #    Cross-Satellite Swap으로 다른 위성의 다른 패스(other_p)에 작업이 배정되면
                #    아래에서 other_p 자신의 값으로 덮어씁니다. (수정 전에는 스왑이 성공해도
                #    항상 원래 패스 p의 시각을 그대로 보여줘서, 실제 커맨딩/수신이 일어나는
                #    시각과 화면 표시가 어긋나는 문제가 있었습니다)
                assigned_aos_str = p_aos_str
                assigned_los_str = p_los_str
                assigned_dur = p_dur
                assigned_el = p_el

                # --- 1. Mode 0: Strict Sequential ---
                if strategy_idx == 0:
                    primary_task = uncompleted_tasks[0]
                    reject_reasons = self._evaluate_task_constraints(
                        primary_task, p_el, p_dur, st_info, st_name, 
                        sat_completed_mains[matched_plan_key], curr_step, min_other_prog, max_lead_steps,
                        tx_occupied_count=p_tx_occupied, tx_capacity=p_tx_capacity
                    )
                    if not reject_reasons:
                        assigned_task = primary_task
                        primary_task["completed"] = True
                        sat_completed_mains[matched_plan_key].add(primary_task["main"])
                        sub_str = f" ({primary_task['sub']})" if primary_task['sub'] else ""
                        assigned_activity = f"[{primary_task['sequence_id']}] {primary_task['main']}{sub_str}"
                        assigned_status = "Allocated"
                        assigned_remark = primary_task.get("remark", "")
                        # 💡 [M2] 이 작업이 커맨딩(CMD/BOTH)을 썼다면 TX 점유 구간으로 기록
                        if primary_task["req_cap"] in ('CMD', 'BOTH'):
                            self._register_tx_usage(tx_occupied_intervals, st_name, p_aos_str, p_los_str)
                    else:
                        assigned_activity = f"[{primary_task['main']}] Blocked ({', '.join(reject_reasons)})"
                        assigned_status = "Bypassed"
                        assigned_remark = primary_task.get("remark", "")

                # --- 2. Mode 1: Look-Ahead & Fill (Same Sat) ---
                elif strategy_idx == 1:
                    primary_task = uncompleted_tasks[0]
                    first_reasons = []
                    
                    for candidate_task in uncompleted_tasks:
                        reasons = self._evaluate_task_constraints(
                            candidate_task, p_el, p_dur, st_info, st_name, 
                            sat_completed_mains[matched_plan_key], curr_step, min_other_prog, max_lead_steps,
                            tx_occupied_count=p_tx_occupied, tx_capacity=p_tx_capacity
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
                            if candidate_task["req_cap"] in ('CMD', 'BOTH'):
                                self._register_tx_usage(tx_occupied_intervals, st_name, p_aos_str, p_los_str)
                            break
                        elif candidate_task == primary_task:
                            first_reasons = reasons

                    if not assigned_task:
                        assigned_activity = f"[{primary_task['main']}] Blocked ({', '.join(first_reasons)})"
                        assigned_status = "Bypassed"
                        assigned_remark = primary_task.get("remark", "")

                # --- 3. Mode 2: Fill with Routine Standby ---
                elif strategy_idx == 2:
                    primary_task = uncompleted_tasks[0]
                    reject_reasons = self._evaluate_task_constraints(
                        primary_task, p_el, p_dur, st_info, st_name, 
                        sat_completed_mains[matched_plan_key], curr_step, min_other_prog, max_lead_steps,
                        tx_occupied_count=p_tx_occupied, tx_capacity=p_tx_capacity
                    )
                    if not reject_reasons:
                        assigned_task = primary_task
                        primary_task["completed"] = True
                        sat_completed_mains[matched_plan_key].add(primary_task["main"])
                        sub_str = f" ({primary_task['sub']})" if primary_task['sub'] else ""
                        assigned_activity = f"[{primary_task['sequence_id']}] {primary_task['main']}{sub_str}"
                        assigned_status = "Allocated"
                        assigned_remark = primary_task.get("remark", "")
                        if primary_task["req_cap"] in ('CMD', 'BOTH'):
                            self._register_tx_usage(tx_occupied_intervals, st_name, p_aos_str, p_los_str)
                    else:
                        assigned_status = "Standby"
                        assigned_activity = f"📡 [Standby] Routine TM Downlink / Health Check (Waits for [{primary_task['main']}])"
                        assigned_remark = f"Primary Task Blocked: {', '.join(reject_reasons)}"

                # --- 4. Mode 3: 🌐 Cross-Satellite Swap (Swarm Fallback) ---
                elif strategy_idx == 3:
                    # [1단계] 본래 작업 시도
                    primary_task = uncompleted_tasks[0]
                    reject_reasons = self._evaluate_task_constraints(
                        primary_task, p_el, p_dur, st_info, st_name, 
                        sat_completed_mains[matched_plan_key], curr_step, min_other_prog, max_lead_steps,
                        tx_occupied_count=p_tx_occupied, tx_capacity=p_tx_capacity
                    )
                    if not reject_reasons:
                        assigned_task = primary_task
                        primary_task["completed"] = True
                        sat_completed_mains[matched_plan_key].add(primary_task["main"])
                        sub_str = f" ({primary_task['sub']})" if primary_task['sub'] else ""
                        assigned_activity = f"[{primary_task['sequence_id']}] {primary_task['main']}{sub_str}"
                        assigned_status = "Allocated"
                        assigned_remark = primary_task.get("remark", "")
                        if primary_task["req_cap"] in ('CMD', 'BOTH'):
                            self._register_tx_usage(tx_occupied_intervals, st_name, p_aos_str, p_los_str)
                    else:
                        # [2단계] 동시간대 타 위성 후보 탐색 및 스왑
                        found_swap = False
                        other_candidates = []
                        
                        for cand_p in self.all_candidate_passes:
                            c_st = cand_p.get("station", "").split("(")[0].strip()
                            c_sat_norm = normalize_sat_name(cand_p.get("satellite", ""))
                            if c_st == st_name and c_sat_norm != matched_plan_key:
                                if not (cand_p.get("los", "") <= p_aos_str or cand_p.get("aos", "") >= p_los_str):
                                    other_candidates.append((c_sat_norm, cand_p))

                        for other_sat_key, other_p in other_candidates:
                            other_plan = sat_plans.get(other_sat_key, [])
                            other_uncompleted = [t for t in other_plan if not t["completed"]]
                            if not other_uncompleted: continue
                            
                            other_step = len(other_plan) - len(other_uncompleted)
                            o_dur = float(other_p.get("duration_sec", other_p.get("duration", p_dur)))
                            o_el = float(other_p.get("max_elevation_deg", other_p.get("max_el", p_el)))
                            # 💡 [M2] 스왑 대상은 "이 지상국의 다른 시간대(other_p)"이므로,
                            #    TX 점유 여부도 반드시 other_p 자신의 aos~los 구간 기준으로 다시 계산해야 합니다.
                            #    (p_aos_str/p_los_str을 그대로 쓰면 엉뚱한 시간대를 검사하는 버그가 됩니다)
                            o_aos_str = other_p.get("aos", "")
                            o_los_str = other_p.get("los", "")
                            o_tx_occupied = self._count_tx_overlaps(tx_occupied_intervals, st_name, o_aos_str, o_los_str)
                            # 💡 [안테나 점검 일정 지원] 같은 지상국이라도 시각이 다르면 유효 용량이 다를 수 있으므로,
                            #    반드시 other_p 자신의 AOS 시각 기준으로 다시 조회합니다.
                            o_aos_dt = _parse_iso_dt(other_p['aos'])
                            o_tx_capacity = st_info.get('tx_capacity_fn', lambda dt: 1)(o_aos_dt) if o_aos_dt else 1
                            
                            for o_task in other_uncompleted:
                                o_reasons = self._evaluate_task_constraints(
                                    o_task, o_el, o_dur, st_info, st_name,
                                    sat_completed_mains[other_sat_key], other_step, min_other_prog, max_lead_steps,
                                    tx_occupied_count=o_tx_occupied, tx_capacity=o_tx_capacity
                                )
                                if not o_reasons:
                                    o_task["completed"] = True
                                    sat_completed_mains[other_sat_key].add(o_task["main"])
                                    assigned_sat = other_p.get("satellite", other_sat_key)
                                    assigned_pass_no = f"Pass {other_p.get('pass_no', '')}"
                                    # 💡 [버그 수정] 스왑이 성공했으므로, 화면에 표시될 시간/기간/고도각도
                                    #    반드시 "실제로 커맨딩이 일어나는 other_p 자신의 값"으로 갱신합니다.
                                    assigned_aos_str = o_aos_str
                                    assigned_los_str = o_los_str
                                    assigned_dur = o_dur
                                    assigned_el = o_el
                                    sub_str = f" ({o_task['sub']})" if o_task['sub'] else ""
                                    assigned_activity = f"[{o_task['sequence_id']}] {o_task['main']}{sub_str} 🔄[Swapped from {matched_plan_key}]"
                                    assigned_status = "Allocated"
                                    assigned_remark = o_task.get("remark", "")
                                    assigned_task = o_task
                                    found_swap = True
                                    if o_task["req_cap"] in ('CMD', 'BOTH'):
                                        self._register_tx_usage(tx_occupied_intervals, st_name, o_aos_str, o_los_str)
                                    break
                            if found_swap: break

                        # [3단계] 동일 위성 Look-Ahead 당겨오기 Fallback
                        if not found_swap:
                            for candidate_task in uncompleted_tasks[1:]:
                                reasons = self._evaluate_task_constraints(
                                    candidate_task, p_el, p_dur, st_info, st_name, 
                                    sat_completed_mains[matched_plan_key], curr_step, min_other_prog, max_lead_steps,
                                    tx_occupied_count=p_tx_occupied, tx_capacity=p_tx_capacity
                                )
                                if not reasons:
                                    assigned_task = candidate_task
                                    candidate_task["completed"] = True
                                    sat_completed_mains[matched_plan_key].add(candidate_task["main"])
                                    sub_str = f" ({candidate_task['sub']})" if candidate_task['sub'] else ""
                                    assigned_activity = f"[{candidate_task['sequence_id']}] {candidate_task['main']}{sub_str} ⚡[Pulled Ahead]"
                                    assigned_status = "Allocated"
                                    assigned_remark = candidate_task.get("remark", "")
                                    if candidate_task["req_cap"] in ('CMD', 'BOTH'):
                                        self._register_tx_usage(tx_occupied_intervals, st_name, p_aos_str, p_los_str)
                                    break

                        # [4단계] 최후 Bypassed 유지
                        if not assigned_task:
                            assigned_activity = f"[{primary_task['main']}] Blocked ({', '.join(reject_reasons)})"
                            assigned_status = "Bypassed"
                            assigned_remark = primary_task.get("remark", "")

                self.final_schedule_data.append({
                    "station": p.get("station", ""), "satellite": assigned_sat,
                    "pass_no": assigned_pass_no, "aos": assigned_aos_str,
                    "los": assigned_los_str, "duration": assigned_dur, "max_el": assigned_el,
                    "status": assigned_status, "activity": assigned_activity,
                    "remark": assigned_remark, "raw_pass": p
                })

            self.populate_final_table_ui()
            strat_name = self.combo_strategy.currentText()
            
            detail_msg = {
                0: "• Mode: Strict Sequential (All blocked passes preserved as bypassed)",
                1: "• Mode: Look-Ahead & Fill (Pulled available tasks of the same satellite)",
                2: "• Mode: Fill with Routine Standby (Filled unused passes with TM acquisition)",
                3: "• Mode: Cross-Satellite Swap Fallback Chain:\n  [1st] Primary Task ➔ [2nd] Swarm Swap ➔ [3rd] Same-Sat Look-Ahead ➔ [4th] Bypassed"
            }.get(strategy_idx, "")
            
            QMessageBox.information(self, "Allocation Success", f"Successfully compiled schedule using:\n'{strat_name}'\n\n{detail_msg}")
            
        except Exception as e:
            QMessageBox.critical(self, "Engine Error", f"Failed to execute LEOP schedule:\n{str(e)}")

    # --------------------------------------------------------------------------
    # 테이블 행 더블클릭 수동 오버라이드 핸들러
    # --------------------------------------------------------------------------
    def handle_cell_double_clicked(self, row, col):
        if row < 0 or row >= len(self.final_schedule_data): return
        
        pass_item = self.final_schedule_data[row]

        dialog = ManualActivityDialog(
            pass_item=pass_item,
            all_sat_plans=self.sat_plans_cached,
            current_activity=pass_item.get("activity", ""),
            parent=self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_sat, new_status, new_act, new_rem = dialog.get_result()
            pass_item["satellite"] = new_sat
            pass_item["status"] = new_status
            pass_item["activity"] = new_act
            if new_rem: pass_item["remark"] = new_rem

            self.final_table.setItem(row, 1, QTableWidgetItem(new_sat))
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
            export_final_schedule_to_excel(
                path, self.final_schedule_data, color_mode,
                station_data=getattr(self.main_app, 'station_data', None),
                antenna_overrides=getattr(self.main_app, 'antenna_overrides', None)
            )
            QMessageBox.information(self, "Export Success", "Integrated Excel sheet saved successfully to final_output.")