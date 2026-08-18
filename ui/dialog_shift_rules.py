from datetime import datetime, timedelta, timezone, time, date
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QTableWidget, QLineEdit, QDateEdit, QTimeEdit, 
                             QCheckBox, QPushButton, QDialogButtonBox, QWidget, 
                             QHeaderView, QMessageBox, QGroupBox, QListWidget, QListWidgetItem)
from PyQt6.QtCore import Qt


class ShiftRuleDialog(QDialog):
    def __init__(self, current_rules=None, base_start_dt=None, all_stations=None, exempt_stations=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ Ground Station Shift Hours & 24/7 Exemption Rules (UTC)")
        self.resize(1020, 560)
        
        self.all_stations = all_stations or []
        self.exempt_stations = set(exempt_stations or [])
        today_utc = (base_start_dt or datetime.now(timezone.utc)).date()
        
        if not current_rules:
            self.rules = [
                {
                    "phase_name": "Phase 1 (LEOP 24H)",
                    "start_date": today_utc,
                    "end_date": today_utc + timedelta(days=2),
                    "start_time": time(0, 0),
                    "end_time": time(23, 59),
                    "is_24h": True,
                    "days": [0, 1, 2, 3, 4, 5, 6]
                },
                {
                    "phase_name": "Phase 2 (Routine Night Shift)",
                    "start_date": today_utc + timedelta(days=3),
                    "end_date": today_utc + timedelta(days=30),
                    "start_time": time(23, 0),
                    "end_time": time(7, 0),
                    "is_24h": False,
                    "days": [0, 1, 2, 3, 4]
                }
            ]
        else:
            self.rules = []
            for r in current_rules:
                # 구형 데이터 호환성 보정
                s_date = r.get("start_date") or (r["start_dt"].date() if "start_dt" in r else today_utc)
                e_date = r.get("end_date") or (r["end_dt"].date() if "end_dt" in r else today_utc + timedelta(days=30))
                s_time = r.get("start_time") or (r["start_dt"].time() if "start_dt" in r else time(9, 0))
                e_time = r.get("end_time") or (r["end_dt"].time() if "end_dt" in r else time(18, 0))

                self.rules.append({
                    "phase_name": r.get("phase_name", "Shift"),
                    "start_date": s_date,
                    "end_date": e_date,
                    "start_time": s_time,
                    "end_time": e_time,
                    "is_24h": r.get("is_24h", False),
                    "days": r.get("days", [0, 1, 2, 3, 4, 5, 6])
                })
            
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel(
            "<b>1. Define Shift Periods, Daily Working Hours & Active Days (All times in UTC):</b><br>"
            "<font color='#555555'>• You can specify date ranges (Date ~ Date) with daily recurring shift times.<br>"
            "• Overnight shifts (e.g. 23:00 ~ 07:00 UTC) automatically handle next-day transitions.</font>"
        ))

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Phase / Shift Name", "Date Range (UTC)", "Daily Shift Hours (UTC)", "Active Days (Mon~Sun)", "24H Full", "Night Shift"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        
        self.table.horizontalHeader().resizeSection(0, 140)
        self.table.horizontalHeader().resizeSection(1, 220)
        self.table.horizontalHeader().resizeSection(2, 170)
            
        layout.addWidget(self.table)
        self.populate_rule_table()

        btn_ctrl = QHBoxLayout()
        btn_add = QPushButton("➕ Add Shift Rule")
        btn_add.setStyleSheet("background-color: #2E7D32; color: white; font-weight: bold;")
        btn_add.clicked.connect(self.click_add_rule)
        btn_ctrl.addWidget(btn_add)

        btn_del = QPushButton("❌ Delete Selected Rule")
        btn_del.clicked.connect(self.click_delete_rule)
        btn_ctrl.addWidget(btn_del)
        btn_ctrl.addStretch()
        layout.addLayout(btn_ctrl)

        # 24/7 Exemption Ground Stations 섹션
        group_exempt = QGroupBox("🌐 2. 24/7 Always Active Ground Stations (Bypass Shift / Weekend Constraints)")
        group_exempt.setStyleSheet("QGroupBox { font-weight: bold; color: #0D47A1; margin-top: 6px; }")
        exempt_lay = QVBoxLayout(group_exempt)
        
        lbl_exempt_desc = QLabel(
            "Checked stations will <b>bypass all shift hours and weekend limits</b> (Active 24 Hours / 7 Days)."
        )
        lbl_exempt_desc.setStyleSheet("color: #424242; font-size: 11px;")
        exempt_lay.addWidget(lbl_exempt_desc)

        self.list_exempt_stations = QListWidget()
        self.list_exempt_stations.setMaximumHeight(90)
        for st_name in self.all_stations:
            item = QListWidgetItem(f"🛰️ {st_name}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if st_name in self.exempt_stations else Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, st_name)
            self.list_exempt_stations.addItem(item)
        exempt_lay.addWidget(self.list_exempt_stations)
        layout.addWidget(group_exempt)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def populate_rule_table(self):
        self.table.setRowCount(len(self.rules))
        day_names = ["M", "T", "W", "T", "F", "S", "S"]
        
        for r_idx, rule in enumerate(self.rules):
            # 0. Phase Name
            txt_name = QLineEdit(rule.get("phase_name", f"Shift {r_idx+1}"))
            self.table.setCellWidget(r_idx, 0, txt_name)

            # 1. Date Range (Date ~ Date)
            date_widget = QWidget()
            date_lay = QHBoxLayout(date_widget)
            date_lay.setContentsMargins(2, 2, 2, 2)
            date_lay.setSpacing(4)
            
            dt_start = QDateEdit(rule.get("start_date"))
            dt_start.setDisplayFormat("yyyy-MM-dd")
            dt_start.setCalendarPopup(True)
            date_lay.addWidget(dt_start)
            
            date_lay.addWidget(QLabel("~"))
            
            dt_end = QDateEdit(rule.get("end_date"))
            dt_end.setDisplayFormat("yyyy-MM-dd")
            dt_end.setCalendarPopup(True)
            date_lay.addWidget(dt_end)
            
            date_widget.dt_start = dt_start
            date_widget.dt_end = dt_end
            self.table.setCellWidget(r_idx, 1, date_widget)

            # 2. Daily Shift Hours (Time ~ Time)
            time_widget = QWidget()
            time_lay = QHBoxLayout(time_widget)
            time_lay.setContentsMargins(2, 2, 2, 2)
            time_lay.setSpacing(4)
            
            tm_start = QTimeEdit(rule.get("start_time"))
            tm_start.setDisplayFormat("HH:mm")
            time_lay.addWidget(tm_start)
            
            time_lay.addWidget(QLabel("~"))
            
            tm_end = QTimeEdit(rule.get("end_time"))
            tm_end.setDisplayFormat("HH:mm")
            time_lay.addWidget(tm_end)
            
            time_widget.tm_start = tm_start
            time_widget.tm_end = tm_end
            self.table.setCellWidget(r_idx, 2, time_widget)

            # 3. Active Days
            days_widget = QWidget()
            days_layout = QHBoxLayout(days_widget)
            days_layout.setContentsMargins(4, 2, 4, 2)
            days_layout.setSpacing(6)
            
            selected_days = rule.get("days", [0, 1, 2, 3, 4, 5, 6])
            days_widget.chk_list = []
            for d_idx, d_label in enumerate(day_names):
                chk = QCheckBox(d_label)
                chk.setChecked(d_idx in selected_days)
                if d_idx in [5, 6]:
                    chk.setStyleSheet("color: #D32F2F; font-weight: bold;")
                days_layout.addWidget(chk)
                days_widget.chk_list.append(chk)
            self.table.setCellWidget(r_idx, 3, days_widget)

            # 4. 24H Checkbox
            chk_24 = QCheckBox()
            chk_24.setChecked(rule.get("is_24h", False))
            
            cell_24_widget = QWidget()
            cell_24_lay = QHBoxLayout(cell_24_widget)
            cell_24_lay.addWidget(chk_24)
            cell_24_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cell_24_lay.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(r_idx, 4, cell_24_widget)

            # 5. Night Shift Indicator
            lbl_night = QLabel("🌙 (+1d)" if rule.get("start_time", time(0,0)) > rule.get("end_time", time(0,0)) else "")
            lbl_night.setStyleSheet("color: #7B1FA2; font-weight: bold; font-size: 11px;")
            lbl_night.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setCellWidget(r_idx, 5, lbl_night)

            # 이벤트 바인딩
            def update_row_state(row=r_idx):
                is_24 = self.table.cellWidget(row, 4).findChild(QCheckBox).isChecked()
                t_w = self.table.cellWidget(row, 2)
                t_w.tm_start.setEnabled(not is_24)
                t_w.tm_end.setEnabled(not is_24)
                
                n_lbl = self.table.cellWidget(row, 5)
                if not is_24 and t_w.tm_start.time() > t_w.tm_end.time():
                    n_lbl.setText("🌙 (+1d)")
                else:
                    n_lbl.setText("")

            chk_24.toggled.connect(lambda _, r=r_idx: update_row_state(r))
            tm_start.timeChanged.connect(lambda _, r=r_idx: update_row_state(r))
            tm_end.timeChanged.connect(lambda _, r=r_idx: update_row_state(r))
            update_row_state(r_idx)

    def click_add_rule(self):
        last_end = datetime.now(timezone.utc).date()
        if self.rules:
            last_end = self.rules[-1]["end_date"] + timedelta(days=1)
            
        new_rule = {
            "phase_name": f"Shift {len(self.rules) + 1}",
            "start_date": last_end,
            "end_date": last_end + timedelta(days=14),
            "start_time": time(9, 0),
            "end_time": time(18, 0),
            "is_24h": False,
            "days": [0, 1, 2, 3, 4, 5, 6]
        }
        self.rules.append(new_rule)
        self.populate_rule_table()

    def click_delete_rule(self):
        curr_row = self.table.currentRow()
        if 0 <= curr_row < len(self.rules):
            self.rules.pop(curr_row)
            self.populate_rule_table()

    def on_accept(self):
        extracted_rules = []
        for r_idx in range(self.table.rowCount()):
            name_widget = self.table.cellWidget(r_idx, 0)
            date_widget = self.table.cellWidget(r_idx, 1)
            time_widget = self.table.cellWidget(r_idx, 2)
            days_widget = self.table.cellWidget(r_idx, 3)
            chk_widget = self.table.cellWidget(r_idx, 4).findChild(QCheckBox)

            phase_name = name_widget.text().strip() if name_widget else f"Shift {r_idx+1}"
            s_date = date_widget.dt_start.date().toPyDate()
            e_date = date_widget.dt_end.date().toPyDate()
            s_time = time_widget.tm_start.time().toPyTime()
            e_time = time_widget.tm_end.time().toPyTime()
            is_24h = chk_widget.isChecked() if chk_widget else False

            active_days = [idx for idx, chk in enumerate(days_widget.chk_list) if chk.isChecked()]
            if not active_days:
                QMessageBox.critical(self, "Invalid Days", f"Row {r_idx+1} ('{phase_name}'): Please select at least one active day.")
                return

            if s_date > e_date:
                QMessageBox.critical(self, "Invalid Date Range", f"Row {r_idx+1} ('{phase_name}'): Start Date must be earlier than or equal to End Date.")
                return

            extracted_rules.append({
                "phase_name": phase_name,
                "start_date": s_date,
                "end_date": e_date,
                "start_time": s_time,
                "end_time": e_time,
                "is_24h": is_24h,
                "days": active_days
            })

        exempt_stations = []
        for i in range(self.list_exempt_stations.count()):
            item = self.list_exempt_stations.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                exempt_stations.append(item.data(Qt.ItemDataRole.UserRole))

        self.extracted_results = (extracted_rules, exempt_stations)
        self.accept()

    def get_results(self):
        return getattr(self, "extracted_results", ([], []))