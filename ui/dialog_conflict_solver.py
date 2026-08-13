from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QRadioButton, QGroupBox, QPushButton, QTableWidget, 
                             QTableWidgetItem, QSpinBox, QHeaderView)
from PyQt6.QtCore import Qt


class ConflictSolverDialog(QDialog):
    def __init__(self, all_satellites, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚡ Auto Conflict Resolution Rules")
        self.resize(520, 450)
        self.all_satellites = sorted(list(all_satellites))
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 1. 규칙 선택 라디오 버튼
        group_rule = QGroupBox("🎯 Conflict Resolution Strategy")
        rule_layout = QVBoxLayout(group_rule)

        self.radio_fair = QRadioButton("⚖️ Cluster Launch Fair Distribution (Equalize Preserving)")
        self.radio_fair.setChecked(True)
        self.radio_fair.setToolTip("동시 발사 위성군 추천: 누적 선택 패스가 적은 위성에게 우선권을 부여하여 특정 위성의 고도각 독점을 방지합니다.")
        rule_layout.addWidget(self.radio_fair)

        self.radio_max_el = QRadioButton("📐 Max Elevation Priority (Best SNR)")
        self.radio_max_el.setToolTip("충돌 패스 중 최대 고도각이 가장 높은 위성을 선택합니다.")
        rule_layout.addWidget(self.radio_max_el)

        self.radio_dur = QRadioButton("⏱️ Longest Pass Duration Priority")
        self.radio_dur.setToolTip("충돌 패스 중 교신 가능 시간이 가장 긴 위성을 선택합니다.")
        rule_layout.addWidget(self.radio_dur)

        self.radio_prio = QRadioButton("⭐ Fixed Satellite Rank / Priority")
        self.radio_prio.toggled.connect(self.on_prio_toggled)
        rule_layout.addWidget(self.radio_prio)

        layout.addWidget(group_rule)

        # 2. 위성별 우선순위 지정 테이블 (SAT_PRIORITY 선택 시 활성화)
        self.table_prio = QTableWidget()
        self.table_prio.setColumnCount(2)
        self.table_prio.setHorizontalHeaderLabels(["Satellite", "Priority Rank (1 = Highest)"])
        self.table_prio.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_prio.setEnabled(False)

        self.table_prio.setRowCount(len(self.all_satellites))
        for idx, sat in enumerate(self.all_satellites):
            self.table_prio.setItem(idx, 0, QTableWidgetItem(sat))
            
            spin = QSpinBox()
            spin.setRange(1, 99)
            spin.setValue(idx + 1)
            self.table_prio.setCellWidget(idx, 1, spin)

        layout.addWidget(QLabel("<b>Satellite Priority Ranks (if Rank Mode selected):</b>"))
        layout.addWidget(self.table_prio)

        # 3. 하단 버튼
        btn_layout = QHBoxLayout()
        btn_apply = QPushButton("⚡ Apply Auto Resolution")
        btn_apply.setStyleSheet("background-color: #2E7D32; color: white; font-weight: bold; padding: 6px;")
        btn_apply.clicked.connect(self.accept)
        btn_layout.addWidget(btn_apply)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        layout.addLayout(btn_layout)

    def on_prio_toggled(self, checked):
        self.table_prio.setEnabled(checked)

    def get_results(self):
        if self.radio_fair.isChecked():
            rule = "FAIR_EQUAL"
        elif self.radio_max_el.isChecked():
            rule = "MAX_EL"
        elif self.radio_dur.isChecked():
            rule = "DURATION"
        else:
            rule = "SAT_PRIORITY"

        sat_priorities = {}
        for row in range(self.table_prio.rowCount()):
            sat = self.table_prio.item(row, 0).text()
            spin = self.table_prio.cellWidget(row, 1)
            sat_priorities[sat] = spin.value()

        return rule, sat_priorities