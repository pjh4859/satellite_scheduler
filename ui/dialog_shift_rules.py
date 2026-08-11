from datetime import datetime, timedelta, timezone, time
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QTableWidget, QLineEdit, QDateEdit, QTimeEdit, 
                             QCheckBox, QPushButton, QDialogButtonBox, QWidget, QHeaderView)
from PyQt6.QtCore import Qt


class ShiftRuleDialog(QDialog):
    def __init__(self, current_rules=None, base_start_dt=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ Ground Station Shift Hours Rules (UTC)")
        self.resize(720, 420)
        
        today_utc = (base_start_dt or datetime.now(timezone.utc)).date()
        
        if not current_rules:
            self.rules = [
                {
                    "phase_name": "Phase 1",
                    "start_date": today_utc,
                    "end_date": today_utc + timedelta(days=2),
                    "start_time": time(0, 0),
                    "end_time": time(23, 59),
                    "is_24h": True
                },
                {
                    "phase_name": "Phase 2",
                    "start_date": today_utc + timedelta(days=3),
                    "end_date": today_utc + timedelta(days=365),
                    "start_time": time(9, 0),
                    "end_time": time(19, 0),
                    "is_24h": False
                }
            ]
        else:
            self.rules = [dict(r) for r in current_rules]
            
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel(
            "<b>Define Shift Window Rules per Operation Phase (All times in UTC):</b><br>"
            "<font color='#555555'>• Pass schedule will be generated ONLY for passes within active shift hours.<br>"
            "• Initial Phase 1 defaults to 24-hour operation (00:00 ~ 23:59 UTC).</font>"
        ))

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Phase Name", "Start Date (UTC)", "End Date (UTC)", "Start Time (UTC)", "End Time (UTC)", "24H Full"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in range(1, 6):
            self.table.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
            
        layout.addWidget(self.table)
        self.populate_rule_table()

        btn_ctrl = QHBoxLayout()
        btn_add = QPushButton("➕ Add Phase Rule")
        btn_add.setStyleSheet("background-color: #2E7D32; color: white; font-weight: bold;")
        btn_add.clicked.connect(self.click_add_rule)
        btn_ctrl.addWidget(btn_add)

        btn_del = QPushButton("❌ Delete Selected Rule")
        btn_del.clicked.connect(self.click_delete_rule)
        btn_ctrl.addWidget(btn_del)
        
        btn_ctrl.addStretch()
        layout.addLayout(btn_ctrl)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def populate_rule_table(self):
        self.table.setRowCount(len(self.rules))
        for r_idx, rule in enumerate(self.rules):
            txt_name = QLineEdit(rule.get("phase_name", f"Phase {r_idx+1}"))
            self.table.setCellWidget(r_idx, 0, txt_name)

            dt_start = QDateEdit(rule.get("start_date", datetime.now(timezone.utc).date()))
            dt_start.setCalendarPopup(True)
            self.table.setCellWidget(r_idx, 1, dt_start)

            dt_end = QDateEdit(rule.get("end_date", datetime.now(timezone.utc).date() + timedelta(days=3)))
            dt_end.setCalendarPopup(True)
            self.table.setCellWidget(r_idx, 2, dt_end)

            tm_start = QTimeEdit(rule.get("start_time", time(9, 0)))
            self.table.setCellWidget(r_idx, 3, tm_start)

            tm_end = QTimeEdit(rule.get("end_time", time(19, 0)))
            self.table.setCellWidget(r_idx, 4, tm_end)

            chk_24 = QCheckBox()
            chk_24.setChecked(rule.get("is_24h", False))
            chk_24.toggled.connect(lambda checked, row=r_idx: self.toggle_24h(row, checked))
            
            cell_widget = QWidget()
            cell_layout = QHBoxLayout(cell_widget)
            cell_layout.addWidget(chk_24)
            cell_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(r_idx, 5, cell_widget)

            if rule.get("is_24h", False):
                tm_start.setEnabled(False)
                tm_end.setEnabled(False)

    def toggle_24h(self, row, is_24h):
        tm_start = self.table.cellWidget(row, 3)
        tm_end = self.table.cellWidget(row, 4)
        if tm_start and tm_end:
            tm_start.setEnabled(not is_24h)
            tm_end.setEnabled(not is_24h)

    def click_add_rule(self):
        last_end = datetime.now(timezone.utc).date()
        if self.rules:
            last_end = self.rules[-1]["end_date"] + timedelta(days=1)
            
        new_rule = {
            "phase_name": f"Phase {len(self.rules) + 1}",
            "start_date": last_end,
            "end_date": last_end + timedelta(days=30),
            "start_time": time(9, 0),
            "end_time": time(19, 0),
            "is_24h": False
        }
        self.rules.append(new_rule)
        self.populate_rule_table()

    def click_delete_rule(self):
        curr_row = self.table.currentRow()
        if 0 <= curr_row < len(self.rules):
            self.rules.pop(curr_row)
            self.populate_rule_table()

    def get_results(self):
        extracted_rules = []
        for r_idx in range(self.table.rowCount()):
            name_widget = self.table.cellWidget(r_idx, 0)
            s_date_widget = self.table.cellWidget(r_idx, 1)
            e_date_widget = self.table.cellWidget(r_idx, 2)
            s_time_widget = self.table.cellWidget(r_idx, 3)
            e_time_widget = self.table.cellWidget(r_idx, 4)
            chk_widget = self.table.cellWidget(r_idx, 5).findChild(QCheckBox)

            phase_name = name_widget.text().strip() if name_widget else f"Phase {r_idx+1}"
            s_date = s_date_widget.date().toPyDate() if s_date_widget else datetime.now(timezone.utc).date()
            e_date = e_date_widget.date().toPyDate() if e_date_widget else datetime.now(timezone.utc).date()
            is_24h = chk_widget.isChecked() if chk_widget else False

            s_time = time(0, 0) if is_24h else s_time_widget.time().toPyTime()
            e_time = time(23, 59, 59) if is_24h else e_time_widget.time().toPyTime()

            extracted_rules.append({
                "phase_name": phase_name,
                "start_date": s_date,
                "end_date": e_date,
                "start_time": s_time,
                "end_time": e_time,
                "is_24h": is_24h
            })
        return extracted_rules