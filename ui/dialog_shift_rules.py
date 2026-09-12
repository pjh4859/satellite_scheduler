from datetime import datetime, timedelta, timezone, time, date
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QTableWidget, QLineEdit, QDateEdit, QTimeEdit, 
                             QCheckBox, QPushButton, QDialogButtonBox, QWidget, 
                             QHeaderView, QMessageBox, QGroupBox, QListWidget, QListWidgetItem)
from PyQt6.QtCore import Qt


# ==============================================================================
# 💡 [기능 2 신규] 규칙별 "적용 지상국" 선택 팝업
# ------------------------------------------------------------------------------
# 규칙 테이블의 셀 하나에 체크리스트 전체를 넣기엔 공간이 좁으므로, 버튼을 눌러
# 작은 팝업 다이얼로그에서 지상국을 고르는 방식으로 만들었습니다.
# applies_to_stations가 None이면 "전체 지상국에 적용"이라는 뜻이고(기존 동작과 동일,
# 하위 호환), 특정 지상국들만 리스트로 담겨있으면 그 지상국들에만 이 규칙이 적용됩니다.
# ==============================================================================
class StationApplyPickerDialog(QDialog):
    def __init__(self, all_stations, selected_stations, parent=None):
        super().__init__(parent)
        self.setWindowTitle("이 규칙을 적용할 지상국 선택")
        self.resize(280, 320)
        self.all_stations = all_stations
        self.selected_stations = set(selected_stations) if selected_stations is not None else None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "<b>이 규칙을 어느 지상국에 적용할까요?</b><br>"
            "<font color='#555555' size='-1'>아무것도 특정하지 않으면(전체 선택) 기존과 동일하게<br>"
            "모든 지상국에 적용됩니다.</font>"
        ))

        self.list_widget = QListWidget()
        # applies_to_stations가 None(전체 적용)이면 전부 체크된 상태로 보여줌
        is_all = (self.selected_stations is None)
        for st_name in self.all_stations:
            item = QListWidgetItem(f"🛰️ {st_name}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            checked = is_all or (st_name in self.selected_stations)
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, st_name)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)

        btn_all = QPushButton("전체 선택")
        btn_all.clicked.connect(lambda: self._set_all(True))
        btn_none = QPushButton("전체 해제")
        btn_none.clicked.connect(lambda: self._set_all(False))
        quick_lay = QHBoxLayout()
        quick_lay.addWidget(btn_all)
        quick_lay.addWidget(btn_none)
        layout.addLayout(quick_lay)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _set_all(self, checked):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(self.list_widget.count()):
            self.list_widget.item(i).setCheckState(state)

    def get_selected_stations(self):
        """
        전부 체크되어 있으면 None(=전체 적용, 하위 호환 표현)을 반환하고,
        일부만 체크되어 있으면 그 지상국 이름 리스트를 반환합니다.
        아무것도 선택되지 않았다면 빈 리스트(= 이 규칙이 어떤 지상국에도 적용 안 됨)를 반환합니다.
        """
        checked = [
            self.list_widget.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.list_widget.count())
            if self.list_widget.item(i).checkState() == Qt.CheckState.Checked
        ]
        if len(checked) == len(self.all_stations) and len(self.all_stations) > 0:
            return None  # 전체 선택 = "전체 적용"과 동일하게 취급 (표현 단순화)
        return checked


class ShiftRuleDialog(QDialog):
    def __init__(self, current_rules=None, base_start_dt=None, all_stations=None, exempt_stations=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ Ground Station Shift Hours & 24/7 Exemption Rules (UTC)")
        # 💡 전체 창 너비를 1240px로 여유 있게 확장
        self.resize(1240, 580)
        self.setMinimumWidth(1180)
        
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
                    "days": [0, 1, 2, 3, 4, 5, 6],
                    "applies_to_stations": None  # None = 전체 지상국 적용
                },
                {
                    "phase_name": "Phase 2 (Routine Night Shift)",
                    "start_date": today_utc + timedelta(days=3),
                    "end_date": today_utc + timedelta(days=30),
                    "start_time": time(23, 0),
                    "end_time": time(7, 0),
                    "is_24h": False,
                    "days": [0, 1, 2, 3, 4],
                    "applies_to_stations": None
                }
            ]
        else:
            self.rules = []
            for r in current_rules:
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
                    "days": r.get("days", [0, 1, 2, 3, 4, 5, 6]),
                    # 💡 구버전 저장 파일(이 필드가 아예 없던 시절)을 불러오면 기본값 None(전체 적용)
                    "applies_to_stations": r.get("applies_to_stations", None)
                })
            
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel(
            "<b>1. Define Shift Periods, Daily Working Hours & Active Days (All times in UTC):</b><br>"
            "<font color='#555555'>• Specify date ranges (Date ~ Date) with daily recurring shift times.<br>"
            "• Overnight shifts (e.g. 23:00 ~ 07:00 UTC) automatically handle next-day transitions.</font>"
        ))

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Phase / Shift Name", "Date Range (UTC)", "Daily Shift Hours (UTC)", "Active Days (Mon~Sun)",
            "24H Full", "Night Shift", "Apply To Stations"
        ])
        
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Interactive)
        
        # 💡 컬럼 너비 재조정 (Daily Shift Hours: 240px, Apply To Stations: 160px)
        self.table.horizontalHeader().resizeSection(0, 150)  # Phase Name
        self.table.horizontalHeader().resizeSection(1, 270)  # Date Range
        self.table.horizontalHeader().resizeSection(2, 240)  # Daily Shift Hours
        self.table.horizontalHeader().resizeSection(6, 160)  # Apply To Stations
            
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
            date_lay.setContentsMargins(4, 2, 4, 2)
            date_lay.setSpacing(6)
            
            dt_start = QDateEdit(rule.get("start_date"))
            dt_start.setDisplayFormat("yyyy-MM-dd")
            dt_start.setCalendarPopup(True)
            dt_start.setMinimumWidth(110)
            date_lay.addWidget(dt_start)
            
            lbl_tilde1 = QLabel("~")
            lbl_tilde1.setAlignment(Qt.AlignmentFlag.AlignCenter)
            date_lay.addWidget(lbl_tilde1)
            
            dt_end = QDateEdit(rule.get("end_date"))
            dt_end.setDisplayFormat("yyyy-MM-dd")
            dt_end.setCalendarPopup(True)
            dt_end.setMinimumWidth(110)
            date_lay.addWidget(dt_end)
            
            date_widget.dt_start = dt_start
            date_widget.dt_end = dt_end
            self.table.setCellWidget(r_idx, 1, date_widget)

            # 2. Daily Shift Hours (Time ~ Time) - 💡 가로 폭 95px로 넉넉하게 확장
            time_widget = QWidget()
            time_lay = QHBoxLayout(time_widget)
            time_lay.setContentsMargins(6, 2, 6, 2)
            time_lay.setSpacing(8)
            
            tm_start = QTimeEdit(rule.get("start_time"))
            tm_start.setDisplayFormat("HH:mm")
            tm_start.setMinimumWidth(95)
            time_lay.addWidget(tm_start)
            
            lbl_tilde2 = QLabel("~")
            lbl_tilde2.setAlignment(Qt.AlignmentFlag.AlignCenter)
            time_lay.addWidget(lbl_tilde2)
            
            tm_end = QTimeEdit(rule.get("end_time"))
            tm_end.setDisplayFormat("HH:mm")
            tm_end.setMinimumWidth(95)
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

            # 6. 💡 [기능 2 신규] 적용 지상국 선택 버튼
            btn_apply_to = QPushButton()
            btn_apply_to.setProperty("rule_idx", r_idx)
            self._refresh_apply_to_button_text(btn_apply_to, rule.get("applies_to_stations"))
            btn_apply_to.clicked.connect(lambda _, row=r_idx: self.click_pick_stations(row))
            self.table.setCellWidget(r_idx, 6, btn_apply_to)

            # 상태 업데이트 이벤트
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

    def _refresh_apply_to_button_text(self, btn, applies_to_stations):
        """버튼 라벨을 현재 선택 상태에 맞게 갱신 (None=전체, 리스트=일부, 빈 리스트=아무데도 적용 안됨)"""
        if applies_to_stations is None:
            btn.setText("🌐 All Stations")
            btn.setStyleSheet("color: #1565C0;")
        elif len(applies_to_stations) == 0:
            btn.setText("⚠️ None Selected")
            btn.setStyleSheet("color: #C62828; font-weight: bold;")
        else:
            names_preview = ", ".join(applies_to_stations[:2])
            more = f" +{len(applies_to_stations)-2}" if len(applies_to_stations) > 2 else ""
            btn.setText(f"📍 {names_preview}{more}")
            btn.setStyleSheet("color: #2E7D32;")

    def click_pick_stations(self, row_idx):
        """'Apply To Stations' 버튼 클릭 -> 팝업에서 지상국 선택 -> self.rules[row_idx]에 즉시 반영"""
        current = self.rules[row_idx].get("applies_to_stations")
        picker = StationApplyPickerDialog(self.all_stations, current, parent=self)
        if picker.exec() == QDialog.DialogCode.Accepted:
            new_selection = picker.get_selected_stations()
            self.rules[row_idx]["applies_to_stations"] = new_selection
            btn = self.table.cellWidget(row_idx, 6)
            self._refresh_apply_to_button_text(btn, new_selection)

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
            "days": [0, 1, 2, 3, 4, 5, 6],
            "applies_to_stations": None
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
                "days": active_days,
                # 💡 [기능 2] 버튼 클릭 시 self.rules[r_idx]에 바로 반영해뒀으므로 그대로 읽어옴
                "applies_to_stations": self.rules[r_idx].get("applies_to_stations")
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