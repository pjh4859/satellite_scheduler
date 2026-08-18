from datetime import datetime, timedelta, timezone
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QTableWidget, QLineEdit, QDateTimeEdit, 
                             QCheckBox, QPushButton, QDialogButtonBox, QWidget, 
                             QHeaderView, QMessageBox, QGroupBox, QListWidget, QListWidgetItem)
from PyQt6.QtCore import Qt


class ShiftRuleDialog(QDialog):
    def __init__(self, current_rules=None, base_start_dt=None, all_stations=None, exempt_stations=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ Ground Station Shift Hours & 24/7 Exemption Rules (UTC)")
        self.resize(920, 560)
        
        self.all_stations = all_stations or []
        self.exempt_stations = set(exempt_stations or [])
        now_dt = base_start_dt or datetime.now(timezone.utc).replace(tzinfo=None)
        
        if not current_rules:
            self.rules = [
                {
                    "phase_name": "Phase 1 (LEOP 24H)",
                    "start_dt": now_dt,
                    "end_dt": now_dt + timedelta(days=3),
                    "is_24h": True,
                    "days": [0, 1, 2, 3, 4, 5, 6]
                },
                {
                    "phase_name": "Phase 2 (Routine Weekday)",
                    "start_dt": now_dt + timedelta(days=3),
                    "end_dt": now_dt + timedelta(days=30),
                    "is_24h": False,
                    "days": [0, 1, 2, 3, 4]
                }
            ]
        else:
            self.rules = []
            for r in current_rules:
                s_dt = r.get("start_dt")
                e_dt = r.get("end_dt")
                if s_dt is None and "start_date" in r:
                    s_dt = datetime.combine(r["start_date"], r.get("start_time", datetime.min.time()))
                if e_dt is None and "end_date" in r:
                    e_dt = datetime.combine(r["end_date"], r.get("end_time", datetime.max.time()))

                self.rules.append({
                    "phase_name": r.get("phase_name", "Shift"),
                    "start_dt": s_dt or now_dt,
                    "end_dt": e_dt or (now_dt + timedelta(hours=8)),
                    "is_24h": r.get("is_24h", False),
                    "days": r.get("days", [0, 1, 2, 3, 4, 5, 6])
                })
            
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel(
            "<b>1. Define Shift Windows & Active Days (All times in UTC):</b><br>"
            "<font color='#555555'>• Shift constraints apply only to Ground Stations that are <b>not</b> checked as 24/7 Exempt.</font>"
        ))

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Phase / Shift Name", "Start DateTime (UTC)", "End DateTime (UTC)", "Active Days (Mon~Sun)", "24H Full"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().resizeSection(0, 150)
        self.table.horizontalHeader().resizeSection(1, 160)
        self.table.horizontalHeader().resizeSection(2, 160)
            
        layout.addWidget(self.table)
        self.populate_rule_table()

        btn_ctrl = QHBoxLayout()
        btn_add = QPushButton("➕ Add Shift Window")
        btn_add.setStyleSheet("background-color: #2E7D32; color: white; font-weight: bold;")
        btn_add.clicked.connect(self.click_add_rule)
        btn_ctrl.addWidget(btn_add)

        btn_del = QPushButton("❌ Delete Selected Window")
        btn_del.clicked.connect(self.click_delete_rule)
        btn_ctrl.addWidget(btn_del)
        btn_ctrl.addStretch()
        layout.addLayout(btn_ctrl)

        # 💡 2. 24/7 Exemption Ground Stations 섹션
        group_exempt = QGroupBox("🌐 2. 24/7 Always Active Ground Stations (Bypass Shift / Weekend Constraints)")
        group_exempt.setStyleSheet("QGroupBox { font-weight: bold; color: #0D47A1; margin-top: 6px; }")
        exempt_lay = QVBoxLayout(group_exempt)
        
        lbl_exempt_desc = QLabel(
            "Checked stations will <b>bypass all shift hours and weekend limits</b> (Active 24 Hours / 7 Days)."
        )
        lbl_exempt_desc.setStyleSheet("color: #424242; font-size: 11px;")
        exempt_lay.addWidget(lbl_exempt_desc)

        self.list_exempt_stations = QListWidget()
        self.list_exempt_stations.setMaximumHeight(100)
        for st_name in self.all_stations:
            item = QListWidgetItem(f"🛰️ {st_name}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if st_name in self.exempt_stations else Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, st_name)
            self.list_exempt_stations.addItem(item)
        exempt_lay.addWidget(self.list_exempt_stations)
        layout.addWidget(group_exempt)

        # 다이얼로그 버튼
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def populate_rule_table(self):
        self.table.setRowCount(len(self.rules))
        day_names = ["M", "T", "W", "T", "F", "S", "S"]
        
        for r_idx, rule in enumerate(self.rules):
            txt_name = QLineEdit(rule.get("phase_name", f"Shift {r_idx+1}"))
            self.table.setCellWidget(r_idx, 0, txt_name)

            dt_start = QDateTimeEdit(rule.get("start_dt"))
            dt_start.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
            dt_start.setCalendarPopup(True)
            self.table.setCellWidget(r_idx, 1, dt_start)

            dt_end = QDateTimeEdit(rule.get("end_dt"))
            dt_end.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
            dt_end.setCalendarPopup(True)
            self.table.setCellWidget(r_idx, 2, dt_end)

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

            chk_24 = QCheckBox()
            chk_24.setChecked(rule.get("is_24h", False))
            
            cell_widget = QWidget()
            cell_layout = QHBoxLayout(cell_widget)
            cell_layout.addWidget(chk_24)
            cell_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(r_idx, 4, cell_widget)

    def click_add_rule(self):
        last_end = datetime.now(timezone.utc).replace(tzinfo=None)
        if self.rules:
            last_end = self.rules[-1]["end_dt"]
            
        new_rule = {
            "phase_name": f"Shift {len(self.rules) + 1}",
            "start_dt": last_end,
            "end_dt": last_end + timedelta(hours=8),
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
            s_dt_widget = self.table.cellWidget(r_idx, 1)
            e_dt_widget = self.table.cellWidget(r_idx, 2)
            days_widget = self.table.cellWidget(r_idx, 3)
            chk_widget = self.table.cellWidget(r_idx, 4).findChild(QCheckBox)

            phase_name = name_widget.text().strip() if name_widget else f"Shift {r_idx+1}"
            s_dt = s_dt_widget.dateTime().toPyDateTime()
            e_dt = e_dt_widget.dateTime().toPyDateTime()
            is_24h = chk_widget.isChecked() if chk_widget else False

            active_days = [idx for idx, chk in enumerate(days_widget.chk_list) if chk.isChecked()]
            if not active_days:
                QMessageBox.critical(self, "Invalid Days", f"Row {r_idx+1} ('{phase_name}'): Please select at least one active day.")
                return

            if s_dt >= e_dt and not is_24h:
                QMessageBox.critical(self, "Invalid Time Window", f"Row {r_idx+1} ('{phase_name}'): Start DateTime must be earlier than End DateTime.")
                return

            extracted_rules.append({
                "phase_name": phase_name,
                "start_dt": s_dt,
                "end_dt": e_dt,
                "is_24h": is_24h,
                "days": active_days
            })

        # 24/7 예외 지상국 추출
        exempt_stations = []
        for i in range(self.list_exempt_stations.count()):
            item = self.list_exempt_stations.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                exempt_stations.append(item.data(Qt.ItemDataRole.UserRole))

        self.extracted_results = (extracted_rules, exempt_stations)
        self.accept()

    def get_results(self):
        return getattr(self, "extracted_results", ([], []))