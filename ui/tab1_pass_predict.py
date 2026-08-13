import os
from datetime import datetime, timedelta, timezone, time, date

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, 
                             QDateTimeEdit, QSpinBox, QPushButton, QTableWidget, 
                             QTableWidgetItem, QLabel, QFileDialog, QHeaderView, QMessageBox, 
                             QInputDialog, QDialog, QListWidgetItem, QDialogButtonBox, QCheckBox,
                             QRadioButton, QGroupBox, QComboBox)
from PyQt6.QtCore import Qt, QUrl, QDateTime, QTimer
from PyQt6.QtGui import QColor, QFont, QDesktopServices

from core.scheduler import parse_tle_from_dir, parse_stations_from_dir, calculate_passes
from core.exporter import export_to_csv, export_to_yaml, export_to_excel_with_color
from core.tle_fetcher import search_satellites_from_celestrak, download_tle_by_norad_id
from core.config_manager import config_manager
from core.timezone_manager import tz_manager

from ui.dialog_tle_generator import TleFromSepVectorDialog
from ui.dialog_gantt_chart import GanttChartDialog
from ui.dialog_equalize_rules import EqualizeRuleDialog
from ui.dialog_shift_rules import ShiftRuleDialog
from ui.tab1_file_loader import ExternalScheduleLoader
from ui.dialog_orbit_map import OrbitMapDialog


class PassPredictTab(QWidget):
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        self.tle_dir = "tle"
        self.stations_dir = "stations"
        self.plans_dir = "plans"
        self.pass_output_dir = "pass_output"
        self.color_mode = "STATION"
        
        self.equalize_target_sats = None
        self.min_pass_targets = {}
        self.max_pass_targets = {}
        self.shift_hours_rules = []
        
        if not os.path.exists(self.pass_output_dir):
            os.makedirs(self.pass_output_dir)
        if not os.path.exists(self.plans_dir):
            os.makedirs(self.plans_dir)
            
        # 💡 실시간 카운트다운용 QTimer 생성 (1초 주기)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_countdown)
        self.timer.start(1000)
            
        self.init_ui()
        self.refresh_tle_files()
        self.refresh_stations()
        
        # 💡 이전 세팅 자동 복원
        self.restore_settings()

    def init_ui(self):
        layout = QHBoxLayout(self)
        left_panel = QVBoxLayout()
        
        # 1. TLE 파일 목록
        left_panel.addWidget(QLabel("<b>1. Detected TLE Files:</b>"))
        self.tle_file_list = QListWidget()
        self.tle_file_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.tle_file_list.itemSelectionChanged.connect(self.save_settings)
        left_panel.addWidget(self.tle_file_list)
        
        tle_btn_layout = QHBoxLayout()
        self.btn_refresh_tle = QPushButton("Refresh")
        self.btn_refresh_tle.clicked.connect(self.refresh_tle_files)
        tle_btn_layout.addWidget(self.btn_refresh_tle)
        
        self.btn_open_tle_folder = QPushButton("📂 Open Folder")
        self.btn_open_tle_folder.clicked.connect(lambda: self.open_local_folder(self.tle_dir))
        tle_btn_layout.addWidget(self.btn_open_tle_folder)
        
        self.btn_fetch_tle = QPushButton("🌐 Fetch Online")
        self.btn_fetch_tle.setStyleSheet("font-weight: bold; color: #0D47A1;")
        self.btn_fetch_tle.clicked.connect(self.click_fetch_online_tle)
        tle_btn_layout.addWidget(self.btn_fetch_tle)

        self.btn_gen_vector_tle = QPushButton("🚀 TLE from Sep Vector")
        self.btn_gen_vector_tle.setStyleSheet("font-weight: bold; color: #E65100;")
        self.btn_gen_vector_tle.clicked.connect(self.click_generate_tle_from_vector)
        tle_btn_layout.addWidget(self.btn_gen_vector_tle)
        
        left_panel.addLayout(tle_btn_layout)
        
        # 2. 지상국 목록
        left_panel.addWidget(QLabel("<b>2. Detected Ground Stations:</b>"))
        self.gs_list = QListWidget()
        self.gs_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.gs_list.itemSelectionChanged.connect(self.save_settings)
        left_panel.addWidget(self.gs_list)
        
        gs_btn_layout = QHBoxLayout()
        self.btn_refresh_gs = QPushButton("Refresh")
        self.btn_refresh_gs.clicked.connect(self.refresh_stations)
        gs_btn_layout.addWidget(self.btn_refresh_gs)
        
        self.btn_open_gs_folder = QPushButton("📂 Open Folder")
        self.btn_open_gs_folder.clicked.connect(lambda: self.open_local_folder(self.stations_dir))
        gs_btn_layout.addWidget(self.btn_open_gs_folder)
        
        left_panel.addLayout(gs_btn_layout)
        
        # 3. 시간 설정 (UTC 기준)
        left_panel.addWidget(QLabel("<b>3. Time Window (UTC):</b>"))
        now_utc_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        
        left_panel.addWidget(QLabel("Start Time:"))
        self.start_time_edit = QDateTimeEdit(now_utc_naive)
        self.start_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.start_time_edit.setCalendarPopup(True)
        self.start_time_edit.dateTimeChanged.connect(self.save_settings)
        left_panel.addWidget(self.start_time_edit)
        
        left_panel.addWidget(QLabel("End Time:"))
        self.end_time_edit = QDateTimeEdit(now_utc_naive + timedelta(days=1))
        self.end_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.end_time_edit.setCalendarPopup(True)
        self.end_time_edit.dateTimeChanged.connect(self.save_settings)
        left_panel.addWidget(self.end_time_edit)
        
        # 4. 필터 및 스케쥴링 규칙
        left_panel.addWidget(QLabel("<b>4. Filters & Scheduling Rules:</b>"))
        el_layout = QHBoxLayout()
        el_layout.addWidget(QLabel("Min El (deg):"))
        self.min_el_spin = QSpinBox()
        self.min_el_spin.setRange(0, 90)
        self.min_el_spin.setValue(5)
        self.min_el_spin.valueChanged.connect(self.save_settings)
        el_layout.addWidget(self.min_el_spin)
        left_panel.addLayout(el_layout)
        
        dur_layout = QHBoxLayout()
        dur_layout.addWidget(QLabel("Min Dur (sec):"))
        self.min_dur_spin = QSpinBox()
        self.min_dur_spin.setRange(0, 3600)
        self.min_dur_spin.setValue(300)
        self.min_dur_spin.valueChanged.connect(self.save_settings)
        dur_layout.addWidget(self.min_dur_spin)
        left_panel.addLayout(dur_layout)
        
        pass_no_layout = QHBoxLayout()
        pass_no_layout.addWidget(QLabel("Start Pass No.:"))
        self.start_pass_spin = QSpinBox()
        self.start_pass_spin.setRange(1, 99999)
        self.start_pass_spin.setValue(1)
        self.start_pass_spin.valueChanged.connect(self.save_settings)
        pass_no_layout.addWidget(self.start_pass_spin)
        left_panel.addLayout(pass_no_layout)

        self.chk_use_shift_hours = QCheckBox("Apply Shift Hours Filter (UTC)")
        self.chk_use_shift_hours.setChecked(False)
        self.chk_use_shift_hours.setStyleSheet("font-weight: bold; color: #0D47A1;")
        self.chk_use_shift_hours.toggled.connect(self.save_settings)
        left_panel.addWidget(self.chk_use_shift_hours)

        self.btn_open_shift_dialog = QPushButton("⚙️ Set Work Shift Hours (UTC)")
        self.btn_open_shift_dialog.setStyleSheet("background-color: #0288D1; color: white; font-weight: bold; margin-top: 1px; margin-bottom: 2px;")
        self.btn_open_shift_dialog.clicked.connect(self.click_open_shift_dialog)
        left_panel.addWidget(self.btn_open_shift_dialog)
        
        self.chk_equalize_sat = QCheckBox("Equalize Sat Allocation (Fairness)")
        self.chk_equalize_sat.setChecked(True)
        self.chk_equalize_sat.setStyleSheet("font-weight: bold; color: #1B5E20;")
        self.chk_equalize_sat.toggled.connect(self.save_settings)
        left_panel.addWidget(self.chk_equalize_sat)

        self.btn_open_equalize_dialog = QPushButton("⚙️ Set Allocation Target & Rules")
        self.btn_open_equalize_dialog.setStyleSheet("background-color: #388E3C; color: white; font-weight: bold; margin-top: 2px; margin-bottom: 2px;")
        self.btn_open_equalize_dialog.clicked.connect(self.click_open_equalize_dialog)
        left_panel.addWidget(self.btn_open_equalize_dialog)
        
        self.lbl_logic_desc = QLabel(
            "<i>ℹ️ Shift Hours & Swarm fair distribution algorithm per satellite.</i>"
        )
        self.lbl_logic_desc.setWordWrap(True)
        self.lbl_logic_desc.setStyleSheet("color: #555555; font-size: 11px; margin-bottom: 5px; margin-left: 15px;")
        left_panel.addWidget(self.lbl_logic_desc)
        
        self.btn_calculate = QPushButton("Calculate Pass Schedule")
        self.btn_calculate.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        self.btn_calculate.clicked.connect(self.run_scheduling)
        left_panel.addWidget(self.btn_calculate)
        
        layout.addLayout(left_panel, stretch=1)
        
        # ----------------------------------------------------------------------
        # 우측 패널
        # ----------------------------------------------------------------------
        right_panel = QVBoxLayout()
        
        # 💡 [신규] 상단 실시간 카운트다운 & 타임존 셀렉터 컨트롤 바
        top_tz_bar = QHBoxLayout()
        
        self.lbl_countdown = QLabel("⏳ Next Pass: No passes scheduled")
        self.lbl_countdown.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #0D47A1; "
            "background-color: #E3F2FD; padding: 6px 12px; border-radius: 4px;"
        )
        top_tz_bar.addWidget(self.lbl_countdown, stretch=1)
        
        top_tz_bar.addWidget(QLabel("<b>🌐 Timezone Display:</b>"))
        self.combo_tz = QComboBox()
        self.combo_tz.addItems(["UTC", "KST (UTC+9)"])
        self.combo_tz.currentIndexChanged.connect(self.on_timezone_changed)
        top_tz_bar.addWidget(self.combo_tz)
        
        right_panel.addLayout(top_tz_bar)

        select_all_layout = QHBoxLayout()
        select_all_layout.addWidget(QLabel("<b>Pass Prediction Timeline Matrix:</b>"))

        select_all_layout.addSpacing(10)
        self.combo_import_engine = QComboBox()
        self.combo_import_engine.addItems([
            "Auto Engine (Standard ➔ DRM 시 xlwings 자동 전환)",
            "Standard Engine (openpyxl / CSV)",
            "DRM Bypass Engine (xlwings)"
        ])
        self.combo_import_engine.setToolTip("사내 DRM(문서 보안)이 걸린 Excel 파일은 DRM Bypass 또는 Auto 모드로 읽습니다.")
        select_all_layout.addWidget(self.combo_import_engine)

        self.btn_import_schedule = QPushButton("📂 Import Schedule File (.xlsx / .csv / .yaml)")
        self.btn_import_schedule.setStyleSheet("background-color: #0288D1; color: white; font-weight: bold; padding: 4px 8px;")
        self.btn_import_schedule.clicked.connect(self.click_import_external_schedule)
        select_all_layout.addWidget(self.btn_import_schedule)
        
        self.btn_open_pass_out = QPushButton("📂 Open Pass Output")
        self.btn_open_pass_out.clicked.connect(lambda: self.open_local_folder(self.pass_output_dir))
        select_all_layout.addWidget(self.btn_open_pass_out)       
            
        select_all_layout.addStretch()

        self.chk_highlight_conflict = QCheckBox("Highlight Conflicts (⚠️)")
        self.chk_highlight_conflict.setChecked(True)
        self.chk_highlight_conflict.setStyleSheet("font-weight: bold; color: #D32F2F;")
        self.chk_highlight_conflict.toggled.connect(self.populate_table)
        select_all_layout.addWidget(self.chk_highlight_conflict)

        group_color = QGroupBox("Color Mode")
        layout_color = QHBoxLayout(group_color)
        
        self.radio_color_station = QRadioButton("By Station")
        self.radio_color_station.setChecked(True)
        self.radio_color_station.toggled.connect(self.on_color_mode_changed)
        layout_color.addWidget(self.radio_color_station)

        self.radio_color_sat = QRadioButton("By Satellite")
        self.radio_color_sat.toggled.connect(self.on_color_mode_changed)
        layout_color.addWidget(self.radio_color_sat)

        select_all_layout.addWidget(group_color)
        
        self.btn_select_all = QPushButton("☑ Check All")
        self.btn_select_all.setFixedWidth(100)
        self.btn_select_all.clicked.connect(lambda: self.set_all_checkboxes(True))
        select_all_layout.addWidget(self.btn_select_all)
        
        self.btn_unselect_all = QPushButton("☒ Unselect All")
        self.btn_unselect_all.setFixedWidth(100)
        self.btn_unselect_all.clicked.connect(lambda: self.set_all_checkboxes(False))
        select_all_layout.addWidget(self.btn_unselect_all)
        right_panel.addLayout(select_all_layout)
        
        self.lbl_summary_bar = QLabel("📊 Satellite Pass Distribution Summary: Run calculation or import schedule file.")
        self.lbl_summary_bar.setStyleSheet("background-color: #F1F8E9; border: 1px solid #C8E6C9; padding: 6px; font-weight: bold; color: #2E7D32;")
        right_panel.addWidget(self.lbl_summary_bar)
        
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Select", "Ground Station", "Satellite", "Pass No. (Orbit)", "AOS", "LOS", "Duration (s)", "Max El (deg)", "Status"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setDefaultSectionSize(145)
        
        self.table.itemChanged.connect(self.handle_table_lock)
        right_panel.addWidget(self.table)
        
        btn_layout = QHBoxLayout()
        
        self.btn_gantt_chart = QPushButton("📊 View Gantt Timeline Chart")
        self.btn_gantt_chart.setStyleSheet("background-color: #6A1B9A; color: white; font-weight: bold;")
        self.btn_gantt_chart.clicked.connect(self.click_view_gantt_chart)
        btn_layout.addWidget(self.btn_gantt_chart)

        self.btn_orbit_map = QPushButton("🌐 View 2D Orbit Map")
        self.btn_orbit_map.setStyleSheet("background-color: #00796B; color: white; font-weight: bold;")
        self.btn_orbit_map.clicked.connect(self.click_view_orbit_map)
        btn_layout.addWidget(self.btn_orbit_map)
        
        self.btn_csv = QPushButton("Export Selected to CSV")
        self.btn_csv.clicked.connect(self.click_export_csv)
        btn_layout.addWidget(self.btn_csv)
        
        self.btn_excel = QPushButton("🎨 Export Selected to Excel (.xlsx)")
        self.btn_excel.setStyleSheet("font-weight: bold; color: #1E7145;")
        self.btn_excel.clicked.connect(self.click_export_excel)
        btn_layout.addWidget(self.btn_excel)
        
        self.btn_yaml = QPushButton("Export Selected to YAML")
        self.btn_yaml.clicked.connect(self.click_export_yaml)
        btn_layout.addWidget(self.btn_yaml)
        
        right_panel.addLayout(btn_layout)
        layout.addLayout(right_panel, stretch=3)

    # --------------------------------------------------------------------------
    # ⏰ 실시간 카운트다운 & 타임존 이벤트
    # --------------------------------------------------------------------------
    def on_timezone_changed(self, idx):
        """타임존 콤보박스 변경 시 호출"""
        selected_tz = "KST" if idx == 1 else "UTC"
        tz_manager.set_timezone(selected_tz)
        
        # 테이블 컬럼 헤더 갱신
        tz_str = tz_manager.current_tz
        self.table.setHorizontalHeaderItem(4, QTableWidgetItem(f"AOS ({tz_str})"))
        self.table.setHorizontalHeaderItem(5, QTableWidgetItem(f"LOS ({tz_str})"))
        
        self.populate_table()

    def update_countdown(self):
        """1초 주기로 실시간 카운트다운 타이머 갱신"""
        if not getattr(self.main_app, 'calculated_passes', None):
            self.lbl_countdown.setText("⏳ Next Pass: No passes scheduled")
            self.lbl_countdown.setStyleSheet(
                "font-size: 13px; font-weight: bold; color: #555555; "
                "background-color: #F5F5F5; padding: 6px 12px; border-radius: 4px;"
            )
            return

        now_utc = datetime.now(timezone.utc)
        selected_passes = [p for p in self.main_app.calculated_passes if p.get('selected', True)]
        
        if not selected_passes:
            self.lbl_countdown.setText("⏳ Next Pass: No pass selected")
            return

        next_pass = None
        in_progress_pass = None
        
        for p in sorted(selected_passes, key=lambda x: x['aos']):
            aos_utc = p['aos'].replace(tzinfo=timezone.utc) if p['aos'].tzinfo is None else p['aos']
            los_utc = p['los'].replace(tzinfo=timezone.utc) if p['los'].tzinfo is None else p['los']
            
            if aos_utc <= now_utc <= los_utc:
                in_progress_pass = p
                break
            elif aos_utc > now_utc:
                next_pass = p
                break

        if in_progress_pass:
            los_utc = in_progress_pass['los'].replace(tzinfo=timezone.utc) if in_progress_pass['los'].tzinfo is None else in_progress_pass['los']
            rem = los_utc - now_utc
            m, s = divmod(int(rem.total_seconds()), 60)
            h, m = divmod(m, 60)
            
            sat = in_progress_pass['satellite'].split('(')[0].strip()
            st = in_progress_pass['station']
            
            self.lbl_countdown.setText(f"🟢 PASS IN PROGRESS | 🛰️ {sat} @ {st} | LOS in {h:02d}:{m:02d}:{s:02d}")
            self.lbl_countdown.setStyleSheet(
                "font-size: 13px; font-weight: bold; color: #FFFFFF; "
                "background-color: #2E7D32; padding: 6px 12px; border-radius: 4px;"
            )
        elif next_pass:
            aos_utc = next_pass['aos'].replace(tzinfo=timezone.utc) if next_pass['aos'].tzinfo is None else next_pass['aos']
            diff = aos_utc - now_utc
            total_sec = int(diff.total_seconds())
            
            days, remainder = divmod(total_sec, 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            sat = next_pass['satellite'].split('(')[0].strip()
            st = next_pass['station']
            
            if days > 0:
                time_str = f"{days}d {hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                
            self.lbl_countdown.setText(f"⏳ Next AOS in {time_str} | 🛰️ {sat} @ {st}")
            self.lbl_countdown.setStyleSheet(
                "font-size: 13px; font-weight: bold; color: #0D47A1; "
                "background-color: #E3F2FD; padding: 6px 12px; border-radius: 4px;"
            )
        else:
            self.lbl_countdown.setText("✅ All scheduled passes completed")
            self.lbl_countdown.setStyleSheet(
                "font-size: 13px; font-weight: bold; color: #424242; "
                "background-color: #E0E0E0; padding: 6px 12px; border-radius: 4px;"
            )

    # --------------------------------------------------------------------------
    # 💾 설정 저장 및 복원 (Config Persistence)
    # --------------------------------------------------------------------------
    def save_settings(self):
        if getattr(self, 'is_restoring', False):
            return

        selected_tle = [item.text() for item in self.tle_file_list.selectedItems()]
        selected_gs = [item.text() for item in self.gs_list.selectedItems()]

        serialized_shift_rules = []
        for r in self.shift_hours_rules:
            serialized_shift_rules.append({
                "phase_name": r.get("phase_name", ""),
                "start_date": r["start_date"].isoformat() if isinstance(r["start_date"], date) else str(r["start_date"]),
                "end_date": r["end_date"].isoformat() if isinstance(r["end_date"], date) else str(r["end_date"]),
                "start_time": r["start_time"].strftime("%H:%M:%S") if isinstance(r["start_time"], time) else str(r["start_time"]),
                "end_time": r["end_time"].strftime("%H:%M:%S") if isinstance(r["end_time"], time) else str(r["end_time"]),
                "is_24h": r.get("is_24h", False)
            })

        start_dt_str = self.start_time_edit.dateTime().toString("yyyy-MM-dd HH:mm:ss")
        end_dt_str = self.end_time_edit.dateTime().toString("yyyy-MM-dd HH:mm:ss")

        config_data = config_manager.load_config()
        config_data["tab1"] = {
            "start_time_utc": start_dt_str,
            "end_time_utc": end_dt_str,
            "selected_tle_files": selected_tle,
            "selected_gs_items": selected_gs,
            "min_el": self.min_el_spin.value(),
            "min_dur": self.min_dur_spin.value(),
            "start_pass_no": self.start_pass_spin.value(),
            "use_shift_hours": self.chk_use_shift_hours.isChecked(),
            "shift_hours_rules": serialized_shift_rules,
            "use_equalize": self.chk_equalize_sat.isChecked(),
            "equalize_target_sats": list(self.equalize_target_sats) if self.equalize_target_sats else None,
            "min_pass_targets": self.min_pass_targets,
            "max_pass_targets": self.max_pass_targets,
            "color_mode": self.color_mode,
            "display_tz": tz_manager.current_tz
        }
        config_manager.save_config(config_data)

    def restore_settings(self):
        config_data = config_manager.load_config()
        tab1_cfg = config_data.get("tab1", {})
        if not tab1_cfg:
            return

        self.is_restoring = True
        self.blockSignals(True)
        try:
            if "start_time_utc" in tab1_cfg:
                s_qdt = QDateTime.fromString(tab1_cfg["start_time_utc"], "yyyy-MM-dd HH:mm:ss")
                if s_qdt.isValid():
                    self.start_time_edit.setDateTime(s_qdt)

            if "end_time_utc" in tab1_cfg:
                e_qdt = QDateTime.fromString(tab1_cfg["end_time_utc"], "yyyy-MM-dd HH:mm:ss")
                if e_qdt.isValid():
                    self.end_time_edit.setDateTime(e_qdt)

            if "min_el" in tab1_cfg: self.min_el_spin.setValue(tab1_cfg["min_el"])
            if "min_dur" in tab1_cfg: self.min_dur_spin.setValue(tab1_cfg["min_dur"])
            if "start_pass_no" in tab1_cfg: self.start_pass_spin.setValue(tab1_cfg["start_pass_no"])
            if "use_shift_hours" in tab1_cfg: self.chk_use_shift_hours.setChecked(tab1_cfg["use_shift_hours"])
            if "use_equalize" in tab1_cfg: self.chk_equalize_sat.setChecked(tab1_cfg["use_equalize"])

            raw_rules = tab1_cfg.get("shift_hours_rules", [])
            restored_rules = []
            for r in raw_rules:
                try:
                    s_date = datetime.strptime(r["start_date"], "%Y-%m-%d").date()
                    e_date = datetime.strptime(r["end_date"], "%Y-%m-%d").date()
                    s_time = datetime.strptime(r["start_time"], "%H:%M:%S").time()
                    e_time = datetime.strptime(r["end_time"], "%H:%M:%S").time()
                    restored_rules.append({
                        "phase_name": r.get("phase_name", "Phase"),
                        "start_date": s_date,
                        "end_date": e_date,
                        "start_time": s_time,
                        "end_time": e_time,
                        "is_24h": r.get("is_24h", False)
                    })
                except Exception:
                    continue
            if restored_rules:
                self.shift_hours_rules = restored_rules

            if tab1_cfg.get("equalize_target_sats") is not None:
                self.equalize_target_sats = set(tab1_cfg["equalize_target_sats"])
            self.min_pass_targets = tab1_cfg.get("min_pass_targets", {})
            self.max_pass_targets = tab1_cfg.get("max_pass_targets", {})

            saved_tle = set(tab1_cfg.get("selected_tle_files", []))
            for i in range(self.tle_file_list.count()):
                item = self.tle_file_list.item(i)
                if saved_tle:
                    item.setSelected(item.text() in saved_tle)
                else:
                    item.setSelected(True)

            saved_gs = set(tab1_cfg.get("selected_gs_items", []))
            for i in range(self.gs_list.count()):
                item = self.gs_list.item(i)
                if saved_gs:
                    item.setSelected(item.text() in saved_gs)
                else:
                    item.setSelected(True)

            color_mode = tab1_cfg.get("color_mode", "STATION")
            if color_mode == "SATELLITE":
                self.radio_color_sat.setChecked(True)
            else:
                self.radio_color_station.setChecked(True)

            # 타임존 설정 복원
            saved_tz = tab1_cfg.get("display_tz", "UTC")
            if saved_tz == "KST":
                self.combo_tz.setCurrentIndex(1)
            else:
                self.combo_tz.setCurrentIndex(0)
        finally:
            self.blockSignals(False)
            self.is_restoring = False

    # --------------------------------------------------------------------------
    # 외부 파일 로더 연결
    # --------------------------------------------------------------------------
    def click_import_external_schedule(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Schedule File", self.pass_output_dir, 
            "Supported Schedule Files (*.xlsx *.xls *.csv *.yaml *.yml)"
        )
        if not path:
            return

        engine_idx = self.combo_import_engine.currentIndex()
        engine_map = {0: "auto", 1: "standard", 2: "xlwings"}
        selected_engine = engine_map[engine_idx]

        try:
            parsed_passes = ExternalScheduleLoader.parse_external_schedule_file(path, engine=selected_engine)
            if not parsed_passes:
                QMessageBox.warning(self, "Warning", "The selected schedule file contains no valid pass data.")
                return

            self.main_app.calculated_passes = parsed_passes
            self.populate_table()

            filename = os.path.basename(path)
            QMessageBox.information(
                self, "Import Complete", 
                f"Successfully loaded {len(parsed_passes)} pass records from:\n'{filename}'"
            )
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to load schedule file:\n{str(e)}")

    def click_open_shift_dialog(self):
        base_start_dt = self.start_time_edit.dateTime().toPyDateTime()
        dialog = ShiftRuleDialog(current_rules=self.shift_hours_rules, base_start_dt=base_start_dt, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.shift_hours_rules = dialog.get_results()
            self.chk_use_shift_hours.setChecked(True)
            self.save_settings()
            
            info_tokens = []
            for r in self.shift_hours_rules:
                if r["is_24h"]:
                    info_tokens.append(f"• {r['phase_name']}: 24H Full")
                else:
                    info_tokens.append(f"• {r['phase_name']}: {r['start_time'].strftime('%H:%M')}~{r['end_time'].strftime('%H:%M')} UTC")
            
            msg = "Updated Shift Hours Rules (UTC):\n" + "\n".join(info_tokens)
            QMessageBox.information(self, "Shift Rules Updated", msg)

    def is_pass_in_shift_hours(self, aos_dt, los_dt):
        if not self.chk_use_shift_hours.isChecked() or not self.shift_hours_rules:
            return True

        pass_date = aos_dt.date()
        pass_start_time = aos_dt.time()
        pass_end_time = los_dt.time()

        for rule in self.shift_hours_rules:
            if rule["start_date"] <= pass_date <= rule["end_date"]:
                if rule.get("is_24h", False):
                    return True
                
                s_time = rule["start_time"]
                e_time = rule["end_time"]

                if s_time <= e_time:
                    if s_time <= pass_start_time and pass_end_time <= e_time:
                        return True
                else:
                    if pass_start_time >= s_time or pass_end_time <= e_time:
                        return True
                return False

        return True

    def run_scheduling(self):
        self.save_settings()
        selected_files = [item.text() for item in self.tle_file_list.selectedItems()]
        tle_data = parse_tle_from_dir(self.tle_dir, selected_files)
        selected_stations = [self.main_app.station_data[self.gs_list.row(item)] for item in self.gs_list.selectedItems()]
        
        start_dt = self.start_time_edit.dateTime().toPyDateTime()
        end_dt = self.end_time_edit.dateTime().toPyDateTime()
        if start_dt >= end_dt:
            QMessageBox.critical(self, "Time Window Error", "Start Time must be earlier than End Time!")
            return
            
        min_el = self.min_el_spin.value()
        min_dur = self.min_dur_spin.value()
        start_pass_no = self.start_pass_spin.value()
        equalize = self.chk_equalize_sat.isChecked()
        
        if not tle_data or not selected_stations:
            QMessageBox.warning(self, "Warning", "No TLE files or Ground Stations selected.")
            return
            
        raw_passes = calculate_passes(
            tle_data, selected_stations, start_dt, end_dt, min_el, min_dur, start_pass_no,
            equalize_allocation=equalize,
            equalize_target_sats=self.equalize_target_sats,
            min_pass_targets=self.min_pass_targets,
            max_pass_targets=self.max_pass_targets
        )

        if self.chk_use_shift_hours.isChecked():
            filtered_passes = [
                p for p in raw_passes if self.is_pass_in_shift_hours(p['aos'], p['los'])
            ]
            self.main_app.calculated_passes = filtered_passes
        else:
            self.main_app.calculated_passes = raw_passes

        self.populate_table()

    def click_open_equalize_dialog(self):
        selected_files = [item.text() for item in self.tle_file_list.selectedItems()]
        tle_data = parse_tle_from_dir(self.tle_dir, selected_files)
        
        if not tle_data:
            QMessageBox.warning(self, "Warning", "Please select at least one TLE file first.")
            return
            
        all_sats = list(tle_data.keys())
        
        dialog = EqualizeRuleDialog(
            all_satellites=all_sats,
            current_targets=self.equalize_target_sats,
            current_min_targets=self.min_pass_targets,
            current_max_targets=self.max_pass_targets,
            parent=self
        )
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.equalize_target_sats, self.min_pass_targets, self.max_pass_targets = dialog.get_results()
            self.save_settings()
            
            target_info_tokens = []
            for sat in sorted(self.equalize_target_sats):
                mn = self.min_pass_targets.get(sat, 1)
                mx = self.max_pass_targets.get(sat, 0)
                mx_str = "No Limit" if mx == 0 else f"{mx} max"
                target_info_tokens.append(f"• {sat}: Min {mn} / Max ({mx_str})")
                
            info_msg = "Updated Allocation Rules:\n" + "\n".join(target_info_tokens) if target_info_tokens else "No satellites targeted."
            QMessageBox.information(self, "Rules Updated", info_msg)

    def on_color_mode_changed(self):
        if self.radio_color_sat.isChecked():
            self.color_mode = "SATELLITE"
        else:
            self.color_mode = "STATION"
            
        self.save_settings()
        if getattr(self.main_app, 'calculated_passes', None):
            self.populate_table()

    def click_generate_tle_from_vector(self):
        dialog = TleFromSepVectorDialog(tle_dir=self.tle_dir, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh_tle_files()

    def open_local_folder(self, folder_path):
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        abs_path = os.path.abspath(folder_path)
        QDesktopServices.openUrl(QUrl.fromLocalFile(abs_path))

    def refresh_tle_files(self):
        self.tle_file_list.blockSignals(True)
        try:
            self.tle_file_list.clear()
            parse_tle_from_dir(self.tle_dir)
            if os.path.exists(self.tle_dir):
                for filename in os.listdir(self.tle_dir):
                    if filename.endswith(".tle") or filename.endswith(".txt"):
                        self.tle_file_list.addItem(filename)
        finally:
            self.tle_file_list.blockSignals(False)

    def refresh_stations(self):
        self.gs_list.blockSignals(True)
        try:
            self.gs_list.clear()
            self.main_app.station_data = parse_stations_from_dir(self.stations_dir)
            for cfg in self.main_app.station_data:
                self.gs_list.addItem(f"{cfg[0]} (Lat: {cfg[1]}, Lon: {cfg[2]}) [Down:{cfg[3]} / Cmd:{cfg[4]}]")
        finally:
            self.gs_list.blockSignals(False)

    def click_fetch_online_tle(self):
        query, ok = QInputDialog.getText(
            self, "CelesTrak Satellite Search", "Enter Satellite Keyword or NORAD CatNR (e.g. NEONSAT, ISS, 39634):"
        )
        if not ok or not query.strip(): return

        success, sat_list, msg = search_satellites_from_celestrak(query)
        if not success or not sat_list:
            QMessageBox.warning(self, "Search Failed", f"Search results for '{query}':\n{msg}\n\n(No changes were made.)")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Select Satellites to Fetch ({len(sat_list)} found)")
        dialog.resize(500, 360)
        
        dlg_layout = QVBoxLayout(dialog)
        dlg_layout.addWidget(QLabel(f"<b>Search Results for '{query}':</b><br>(Use Ctrl / Shift or 'Select All' to download multiple satellites)"))
        
        list_widget = QListWidget()
        list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        
        for sat in sat_list:
            display_text = f"🛰️  {sat['sat_name']}  |  NORAD ID: {sat['norad_id']}  ({sat['int_designator']})"
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, sat)
            list_widget.addItem(item)
            
        dlg_layout.addWidget(list_widget)
        
        select_ctrl_layout = QHBoxLayout()
        btn_sel_all = QPushButton("☑ Select All")
        btn_sel_all.clicked.connect(list_widget.selectAll)
        select_ctrl_layout.addWidget(btn_sel_all)
        
        btn_desel_all = QPushButton("☒ Unselect All")
        btn_desel_all.clicked.connect(list_widget.clearSelection)
        select_ctrl_layout.addWidget(btn_desel_all)
        
        dlg_layout.addLayout(select_ctrl_layout)
        
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        dlg_layout.addWidget(button_box)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_items = list_widget.selectedItems()
            if not selected_items: return
            
            success_count = 0
            failed_sats = []
            
            for item in selected_items:
                sat_data = item.data(Qt.ItemDataRole.UserRole)
                target_norad_id = sat_data['norad_id']
                target_sat_name = sat_data['sat_name']
                
                dl_success, save_path = download_tle_by_norad_id(target_norad_id, target_sat_name, self.tle_dir)
                if dl_success:
                    success_count += 1
                else:
                    failed_sats.append(target_sat_name)
            
            if success_count > 0:
                msg = f"Successfully fetched TLE files for {success_count} satellite(s)."
                if failed_sats:
                    msg += f"\n\nFailed satellites: {', '.join(failed_sats)}"
                QMessageBox.information(self, "Download Complete", msg)
                self.refresh_tle_files()
            else:
                QMessageBox.critical(self, "Download Error", f"Failed to download selected satellites.")    

    def update_summary_dashboard(self):
        if not self.main_app.calculated_passes:
            self.lbl_summary_bar.setText("📊 Satellite Pass Distribution Summary: No data calculated.")
            return
            
        sat_stats = {}
        for p in self.main_app.calculated_passes:
            sat_clean = p['satellite'].split("(")[0].strip()
            if sat_clean not in sat_stats:
                sat_stats[sat_clean] = {'selected_count': 0, 'total_count': 0, 'total_duration_sec': 0.0}
                
            sat_stats[sat_clean]['total_count'] += 1
            if p.get('selected', False):
                sat_stats[sat_clean]['selected_count'] += 1
                sat_stats[sat_clean]['total_duration_sec'] += float(p.get('duration', 0))
                
        summary_tokens = []
        for sat_name, stats in sorted(sat_stats.items()):
            dur_min = stats['total_duration_sec'] / 60.0
            summary_tokens.append(f"🛰️ <b>{sat_name}</b>: {stats['selected_count']}/{stats['total_count']} passes ({dur_min:.1f} min)")
            
        summary_text = "📊 <b>Pass Allocation Summary:</b> &nbsp;&nbsp;|&nbsp;&nbsp; " + " &nbsp;&nbsp;|&nbsp;&nbsp; ".join(summary_tokens)
        self.lbl_summary_bar.setText(summary_text)

    def populate_table(self):
        if getattr(self.main_app, 'is_populating', False): return
        self.table.setRowCount(0)
        if not self.main_app.calculated_passes: return
            
        self.main_app.is_populating = True
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(self.main_app.calculated_passes))
            from core.color_manager import color_manager
            
            show_conflict_highlight = self.chk_highlight_conflict.isChecked()
            
            for row_idx, p in enumerate(self.main_app.calculated_passes):
                chk_item = QTableWidgetItem()
                chk_item.setCheckState(Qt.CheckState.Checked if p.get('selected', True) else Qt.CheckState.Unchecked)
                chk_item.setData(Qt.ItemDataRole.UserRole, (row_idx, p.get('conflict_group', None), p['station']))
                self.table.setItem(row_idx, 0, chk_item)
                
                self.table.setItem(row_idx, 1, QTableWidgetItem(p['station']))
                self.table.setItem(row_idx, 2, QTableWidgetItem(p['satellite']))
                self.table.setItem(row_idx, 3, QTableWidgetItem(f"Pass {p['pass_no']}"))
                
                # 💡 [핵심] tz_manager를 연동한 동적 타임존 시각 문자열 변환
                aos_val = tz_manager.format_datetime(p['aos'])
                los_val = tz_manager.format_datetime(p['los'])
                
                self.table.setItem(row_idx, 4, QTableWidgetItem(aos_val))
                self.table.setItem(row_idx, 5, QTableWidgetItem(los_val))
                self.table.setItem(row_idx, 6, QTableWidgetItem(str(p['duration'])))
                self.table.setItem(row_idx, 7, QTableWidgetItem(str(p['max_el'])))
                
                status_text = p.get('status', 'Normal')
                status_item = QTableWidgetItem(status_text)
                
                if self.color_mode == "SATELLITE":
                    sat_raw = str(p['satellite'])
                    _, base_color = color_manager.get_colors(sat_raw)
                else:
                    st_raw = str(p['station'])
                    _, base_color = color_manager.get_station_colors(st_raw)

                if "Conflict" in status_text and show_conflict_highlight:
                    status_item.setText(f"⚠️ {status_text}")
                    status_item.setForeground(QColor(180, 0, 0))
                    status_item.setFont(QFont("", -1, QFont.Weight.Bold))
                    row_color = QColor(
                        min(255, base_color.red() + 25),
                        max(0, base_color.green() - 25),
                        max(0, base_color.blue() - 25)
                    )
                else:
                    row_color = base_color

                self.table.setItem(row_idx, 8, status_item)

                for col_idx in range(self.table.columnCount()):
                    cell = self.table.item(row_idx, col_idx)
                    if cell:
                        cell.setBackground(row_color)
                    
            self.update_summary_dashboard()
        finally:
            self.table.blockSignals(False)
            self.main_app.is_populating = False

    def click_view_gantt_chart(self):
        if not self.main_app.calculated_passes:
            QMessageBox.warning(self, "Warning", "Please calculate or import pass schedule first.")
            return
        # 💡 [수정] color_mode 매개변수 함께 전달
        dialog = GanttChartDialog(
            calculated_passes=self.main_app.calculated_passes,
            color_mode=self.color_mode,
            parent=self
        )
        dialog.exec()

    def click_view_orbit_map(self):
        if not self.main_app.calculated_passes:
            QMessageBox.warning(self, "Warning", "Please calculate or import pass schedule first.")
            return

        dialog = OrbitMapDialog(
            calculated_passes=self.main_app.calculated_passes,
            station_data=self.main_app.station_data,
            color_mode=self.color_mode,
            parent=self
        )
        dialog.exec()

    def handle_table_lock(self, item):
        if self.main_app.is_populating or item.column() != 0: return
        user_data = item.data(Qt.ItemDataRole.UserRole)
        if not user_data: return
            
        current_row, group_id, station_name = user_data
        if group_id is None:
            self.main_app.calculated_passes[current_row]['selected'] = (item.checkState() == Qt.CheckState.Checked)
            self.update_summary_dashboard()
            return
            
        if item.checkState() == Qt.CheckState.Checked:
            self.main_app.is_populating = True
            try:
                for r in range(self.table.rowCount()):
                    if r == current_row:
                        self.main_app.calculated_passes[r]['selected'] = True
                        continue
                    other_item = self.table.item(r, 0)
                    if other_item is not None and other_item.data(Qt.ItemDataRole.UserRole) is not None:
                        o_row, o_group, o_station = other_item.data(Qt.ItemDataRole.UserRole)
                        if o_station == station_name and o_group == group_id:
                            other_item.setCheckState(Qt.CheckState.Unchecked)
                            self.main_app.calculated_passes[r]['selected'] = False
            finally:
                self.main_app.is_populating = False
            self.populate_table()
        else:
            self.main_app.calculated_passes[current_row]['selected'] = False
            self.main_app.is_populating = True
            try: self.populate_table()
            finally: self.main_app.is_populating = False

    def click_export_csv(self):
        if not self.main_app.calculated_passes: return
        path, _ = QFileDialog.getSaveFileName(self, "Save CSV Schedule", self.pass_output_dir, "CSV Files (*.csv)")
        if path: export_to_csv(path, self.main_app.calculated_passes)

    def click_export_yaml(self):
        if not self.main_app.calculated_passes: return
        path, _ = QFileDialog.getSaveFileName(self, "Save YAML Schedule", self.pass_output_dir, "YAML Files (*.yaml)")
        if path: export_to_yaml(path, self.main_app.calculated_passes)

    def set_all_checkboxes(self, check_state):
        if not self.main_app.calculated_passes: return
        self.main_app.is_populating = True
        target_state = Qt.CheckState.Checked if check_state else Qt.CheckState.Unchecked
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item:
                item.setCheckState(target_state)
                self.main_app.calculated_passes[r]['selected'] = check_state
        self.main_app.is_populating = False
        self.populate_table()

    def click_export_excel(self):
        if not self.main_app.calculated_passes: return
        if not any(p['selected'] for p in self.main_app.calculated_passes):
            QMessageBox.warning(self, "Warning", "No passes are selected.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Colorized Excel Schedule", self.pass_output_dir, "Excel Files (*.xlsx)")
        if path:
            success, msg = export_to_excel_with_color(path, self.main_app.calculated_passes)
            if success:
                QMessageBox.information(self, "Export Success", "Excel file generated successfully!")
            else:
                QMessageBox.critical(self, "Export Error", f"Failed to save Excel file:\n{msg}")