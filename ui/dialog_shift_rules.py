from datetime import datetime, timedelta, timezone
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QTableWidget, QLineEdit, QDateTimeEdit, 
                             QCheckBox, QPushButton, QDialogButtonBox, QWidget, QHeaderView, QMessageBox)
from PyQt6.QtCore import Qt


class ShiftRuleDialog(QDialog):
    def __init__(self, current_rules=None, base_start_dt=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ Ground Station Shift Hours Windows (UTC)")
        self.resize(920, 440)
        
        now_dt = base_start_dt or datetime.now(timezone.utc).replace(tzinfo=None)
        
        if not current_rules:
            self.rules = [
                {
                    "phase_name": "Phase 1 (LEOP 24H)",
                    "start_dt": now_dt,
                    "end_dt": now_dt + timedelta(days=3),
                    "is_24h": True,
                    "days": [0, 1, 2, 3, 4, 5, 6]  # 전체 요일 (0=월 ~ 6=일)
                },
                {
                    "phase_name": "Phase 2 (Routine Weekday)",
                    "start_dt": now_dt + timedelta(days=3),
                    "end_dt": now_dt + timedelta(days=30),
                    "is_24h": False,
                    "days": [0, 1, 2, 3, 4]  # 평일만 (월~금)
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
            "<b>Define Absolute Shift Time Windows & Active Days (All times in UTC):</b><br>"
            "<font color='#555555'>• Uncheck Sat / Sun on any shift row to exclude weekend passes during that phase.<br>"
            "• Initial Phase 1 can be configured for 7 days, while Routine phase runs on Weekdays only.</font>"
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

            # 요일 선택 위젯 (Mon ~ Sun)
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
                    chk.setStyleSheet("color: #D32F2F; font-weight: bold;")  # 주말 강조
                days_layout.addWidget(chk)
                days_widget.chk_list.append(chk)
                
            self.table.setCellWidget(r_idx, 3, days_widget)

            # 24H Full 체크박스
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

        self.extracted_results = extracted_rules
        self.accept()

    def get_results(self):
        return getattr(self, "extracted_results", [])