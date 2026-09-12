"""
[신규] 안테나 점검 일정 관리 다이얼로그 (Antenna Maintenance Override Manager)

[배경]
core/scheduler.py의 build_capacity_lookup()과 resolve_station_group_with_capacity()가
"시간대별로 달라지는 안테나 용량"을 지원하도록 확장되었습니다. 이 다이얼로그는 그 데이터를
사용자가 직접 입력/수정/삭제할 수 있는 화면입니다.

[데이터 형태]
{"station": str, "start_dt": datetime, "end_dt": datetime,
 "rx_capacity": int|None, "tx_capacity": int|None, "reason": str}
- rx_capacity/tx_capacity가 None이면 "이 항목은 해당 자원엔 영향 없음"이라는 뜻입니다.
  (예: RX만 줄이고 TX는 그대로 두는 점검 -> tx_capacity=None)

[간단한 사용성 개선]
- 지금 이 순간(now) 기준으로 "진행 중 / 예정 / 종료"를 색으로 구분해서 보여줍니다.
- 시작 시각이 종료 시각보다 늦거나 같으면 저장을 막고 안내합니다.
- 목록은 항상 시작 시각 순으로 정렬해서 보여줍니다.
"""

from datetime import datetime, timezone
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QTableWidget, QTableWidgetItem, QSpinBox, QCheckBox,
                             QPushButton, QDialogButtonBox, QHeaderView, QComboBox,
                             QDateTimeEdit, QLineEdit, QMessageBox)
from PyQt6.QtCore import Qt, QDateTime

COL_STATION, COL_START, COL_END, COL_RX, COL_TX, COL_REASON, COL_STATUS = range(7)


class AntennaOverrideDialog(QDialog):
    def __init__(self, current_overrides, all_stations, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔧 Antenna Maintenance Schedule (안테나 점검 일정 관리)")
        self.resize(920, 480)
        self.all_stations = all_stations or []

        # 시작 시각 순으로 정렬해서 보여줌 (사용성 개선)
        self.overrides = sorted(list(current_overrides or []), key=lambda ov: ov["start_dt"])

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel(
            "<b>지상국의 안테나가 일시적으로 줄어드는(점검/고장 등) 기간을 등록하세요.</b><br>"
            "<font color='#555555' size='-1'>"
            "RX/TX 중 하나만 바꾸고 싶으면 다른 하나는 체크 해제(No Change)로 두면 됩니다. "
            "이 기간 동안은 등록한 값이 평소 용량을 대신합니다."
            "</font>"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Station", "Start (UTC)", "End (UTC)", "RX Override", "TX Override", "Reason", "Status"
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_STATION, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(COL_START, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(COL_END, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(COL_RX, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(COL_TX, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(COL_REASON, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_STATUS, QHeaderView.ResizeMode.ResizeToContents)
        header.resizeSection(COL_STATION, 110)
        header.resizeSection(COL_START, 150)
        header.resizeSection(COL_END, 150)
        header.resizeSection(COL_RX, 110)
        header.resizeSection(COL_TX, 110)

        self._populate_table(self.overrides)
        layout.addWidget(self.table)

        row_btn_layout = QHBoxLayout()
        btn_add = QPushButton("➕ Add Maintenance Window")
        btn_add.clicked.connect(self.add_empty_row)
        row_btn_layout.addWidget(btn_add)

        btn_del = QPushButton("🗑️ Delete Selected Row")
        btn_del.clicked.connect(self.delete_selected_row)
        row_btn_layout.addWidget(btn_del)
        layout.addLayout(row_btn_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.on_save_clicked)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    # --------------------------------------------------------------------
    def _populate_table(self, overrides):
        self.table.setRowCount(len(overrides))
        for row_idx, ov in enumerate(overrides):
            self._set_row(row_idx, ov)

    def _set_row(self, row_idx, ov):
        station_combo = QComboBox()
        station_combo.setEditable(True)  # 목록에 없는 지상국 이름도 직접 입력 가능
        station_combo.addItems(self.all_stations)
        if ov.get("station") in self.all_stations:
            station_combo.setCurrentText(ov["station"])
        else:
            station_combo.setCurrentText(ov.get("station", ""))
        self.table.setCellWidget(row_idx, COL_STATION, station_combo)

        start_edit = QDateTimeEdit(QDateTime(ov["start_dt"]))
        start_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        start_edit.setCalendarPopup(True)
        self.table.setCellWidget(row_idx, COL_START, start_edit)

        end_edit = QDateTimeEdit(QDateTime(ov["end_dt"]))
        end_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        end_edit.setCalendarPopup(True)
        self.table.setCellWidget(row_idx, COL_END, end_edit)

        rx_widget = self._make_capacity_override_widget(ov.get("rx_capacity"))
        self.table.setCellWidget(row_idx, COL_RX, rx_widget)

        tx_widget = self._make_capacity_override_widget(ov.get("tx_capacity"))
        self.table.setCellWidget(row_idx, COL_TX, tx_widget)

        self.table.setItem(row_idx, COL_REASON, QTableWidgetItem(ov.get("reason", "")))

        status_item = QTableWidgetItem("")
        status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row_idx, COL_STATUS, status_item)
        self._refresh_status_cell(row_idx, ov["start_dt"], ov["end_dt"])

    def _make_capacity_override_widget(self, current_value):
        """체크박스(변경 여부) + 스핀박스(값)를 한 셀에 담은 위젯.
        체크 해제 상태면 '이 자원은 안 건드림(None)'을 의미합니다.
        💡 점검으로 완전히 0대(전면 불가)가 되는 경우도 표현할 수 있도록 최솟값은 0으로 둡니다."""
        container = QCheckBox()
        spin = QSpinBox()
        spin.setRange(0, 99)
        spin.setFixedWidth(50)

        has_override = current_value is not None
        container.setChecked(has_override)
        spin.setValue(current_value if has_override else 0)
        spin.setEnabled(has_override)
        container.toggled.connect(spin.setEnabled)

        # 체크박스+스핀박스를 한 셀 안에 나란히 넣기 위한 얇은 래퍼
        from PyQt6.QtWidgets import QWidget
        wrapper = QWidget()
        wlay = QHBoxLayout(wrapper)
        wlay.setContentsMargins(4, 0, 4, 0)
        wlay.addWidget(container)
        wlay.addWidget(spin)
        wrapper._checkbox = container  # 나중에 값 추출할 때 쓰기 위해 참조 보관
        wrapper._spinbox = spin
        return wrapper

    def _refresh_status_cell(self, row_idx, start_dt, end_dt):
        """💡 [사용성 개선] 지금 이 순간(now) 기준으로 진행 중/예정/종료를 색으로 표시."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        start_naive = start_dt.replace(tzinfo=None) if start_dt.tzinfo else start_dt
        end_naive = end_dt.replace(tzinfo=None) if end_dt.tzinfo else end_dt

        item = self.table.item(row_idx, COL_STATUS)
        if not item:
            return
        if start_naive <= now < end_naive:
            item.setText("🔴 진행 중")
            item.setBackground(Qt.GlobalColor.yellow)
        elif now < start_naive:
            item.setText("🔵 예정")
            item.setBackground(Qt.GlobalColor.white)
        else:
            item.setText("⚪ 종료됨")
            item.setBackground(Qt.GlobalColor.lightGray)

    def add_empty_row(self):
        row_idx = self.table.rowCount()
        self.table.insertRow(row_idx)
        now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0, second=0)
        default_station = self.all_stations[0] if self.all_stations else ""
        self._set_row(row_idx, {
            "station": default_station, "start_dt": now, "end_dt": now,
            "rx_capacity": None, "tx_capacity": None, "reason": ""
        })

    def delete_selected_row(self):
        selected_rows = sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True)
        if not selected_rows:
            QMessageBox.information(self, "안내", "삭제할 행을 먼저 클릭해서 선택해주세요.")
            return
        for row_idx in selected_rows:
            self.table.removeRow(row_idx)

    # --------------------------------------------------------------------
    def _collect_rows(self):
        rows = []
        problems = []
        for row_idx in range(self.table.rowCount()):
            station = self.table.cellWidget(row_idx, COL_STATION).currentText().strip()
            if not station:
                continue  # 지상국 이름이 비어있는 행은 조용히 제외

            start_dt = self.table.cellWidget(row_idx, COL_START).dateTime().toPyDateTime()
            end_dt = self.table.cellWidget(row_idx, COL_END).dateTime().toPyDateTime()

            # 💡 [사용성 개선] 종료가 시작보다 빠르거나 같으면 저장 전에 걸러서 안내
            if end_dt <= start_dt:
                problems.append(f"{row_idx + 1}번째 행 ({station}): 종료 시각이 시작 시각보다 나중이어야 합니다.")
                continue

            rx_wrapper = self.table.cellWidget(row_idx, COL_RX)
            tx_wrapper = self.table.cellWidget(row_idx, COL_TX)
            rx_val = rx_wrapper._spinbox.value() if rx_wrapper._checkbox.isChecked() else None
            tx_val = tx_wrapper._spinbox.value() if tx_wrapper._checkbox.isChecked() else None

            if rx_val is None and tx_val is None:
                problems.append(f"{row_idx + 1}번째 행 ({station}): RX/TX 둘 다 'No Change'면 아무 효과가 없습니다. 최소 하나는 체크해주세요.")
                continue

            reason_item = self.table.item(row_idx, COL_REASON)
            reason = reason_item.text().strip() if reason_item else ""

            rows.append({
                "station": station, "start_dt": start_dt, "end_dt": end_dt,
                "rx_capacity": rx_val, "tx_capacity": tx_val, "reason": reason
            })
        return rows, problems

    def on_save_clicked(self):
        rows, problems = self._collect_rows()
        if problems:
            QMessageBox.warning(self, "입력 확인 필요", "\n".join(problems))
            return

        self.overrides = sorted(rows, key=lambda ov: ov["start_dt"])
        self.accept()

    def get_results(self):
        return self.overrides
