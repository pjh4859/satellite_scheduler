from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QGroupBox, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QCheckBox, QSlider, QMessageBox, QFrame,
                             QListWidget, QListWidgetItem)
from PyQt6.QtCore import Qt
from ui.dialog_equalize_rules import EqualizeRuleDialog

class ConflictSolverDialog(QDialog):
    def __init__(self, all_satellites, equalize_target_sats=None, min_pass_targets=None, 
                 max_pass_targets=None, saved_weights=None, saved_priorities=None,
                 all_stations=None, saved_excluded_stations=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚡ Multi-Weighted Auto Conflict Resolution")
        self.resize(580, 820)
        
        self.all_satellites = sorted(list(all_satellites))
        self.all_stations = sorted(list(all_stations or []))
        self.equalize_target_sats = equalize_target_sats
        self.min_pass_targets = min_pass_targets or {}
        self.max_pass_targets = max_pass_targets or {}
        self.saved_weights = saved_weights or {}
        self.saved_priorities = saved_priorities or {}
        self.saved_excluded_stations = set(saved_excluded_stations or [])
        
        self.init_ui()
        self.restore_saved_inputs()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Configure Auto-Resolve criteria, weights, and station exclusions:</b>"))

        # 1. Fairness 가중치 섹션
        self.box_fairness = QGroupBox()
        box_fair_lay = QVBoxLayout(self.box_fairness)
        
        h1 = QHBoxLayout()
        self.chk_fairness = QCheckBox("Cluster Fairness (Equal Allocation)")
        self.chk_fairness.setChecked(True)
        self.chk_fairness.setStyleSheet("font-weight: bold; color: #2E7D32;")
        self.chk_fairness.toggled.connect(self.update_ui_state)
        h1.addWidget(self.chk_fairness)
        
        self.lbl_fair_val = QLabel("Weight: 50%")
        self.lbl_fair_val.setFixedWidth(80)
        h1.addWidget(self.lbl_fair_val)
        
        self.slider_fairness = QSlider(Qt.Orientation.Horizontal)
        self.slider_fairness.setRange(1, 100)
        self.slider_fairness.setValue(50)
        self.slider_fairness.valueChanged.connect(lambda v: self.lbl_fair_val.setText(f"Weight: {v}%"))
        h1.addWidget(self.slider_fairness)
        box_fair_lay.addLayout(h1)
        
        self.btn_edit_fairness = QPushButton("⚙️ Set Min / Max Targets & Equalize Rules")
        self.btn_edit_fairness.setStyleSheet("background-color: #388E3C; color: white; font-size: 11px;")
        self.btn_edit_fairness.clicked.connect(self.open_equalize_dialog)
        box_fair_lay.addWidget(self.btn_edit_fairness)
        layout.addWidget(self.box_fairness)

        # 2. Max Elevation 가중치 섹션
        self.box_elevation = QGroupBox()
        box_el_lay = QHBoxLayout(self.box_elevation)
        
        self.chk_elevation = QCheckBox("Max Elevation Angle (Geometry / SNR)")
        self.chk_elevation.setChecked(True)
        self.chk_elevation.setStyleSheet("font-weight: bold; color: #0288D1;")
        self.chk_elevation.toggled.connect(self.update_ui_state)
        box_el_lay.addWidget(self.chk_elevation)
        
        self.lbl_el_val = QLabel("Weight: 25%")
        self.lbl_el_val.setFixedWidth(80)
        box_el_lay.addWidget(self.lbl_el_val)
        
        self.slider_elevation = QSlider(Qt.Orientation.Horizontal)
        self.slider_elevation.setRange(1, 100)
        self.slider_elevation.setValue(25)
        self.slider_elevation.valueChanged.connect(lambda v: self.lbl_el_val.setText(f"Weight: {v}%"))
        box_el_lay.addWidget(self.slider_elevation)
        layout.addWidget(self.box_elevation)

        # 3. Duration 가중치 섹션
        self.box_duration = QGroupBox()
        box_dur_lay = QHBoxLayout(self.box_duration)
        
        self.chk_duration = QCheckBox("Longest Contact Duration (Time Window)")
        self.chk_duration.setChecked(False)
        self.chk_duration.setStyleSheet("font-weight: bold; color: #7B1FA2;")
        self.chk_duration.toggled.connect(self.update_ui_state)
        box_dur_lay.addWidget(self.chk_duration)
        
        self.lbl_dur_val = QLabel("Weight: 20%")
        self.lbl_dur_val.setFixedWidth(80)
        box_dur_lay.addWidget(self.lbl_dur_val)
        
        self.slider_duration = QSlider(Qt.Orientation.Horizontal)
        self.slider_duration.setRange(1, 100)
        self.slider_duration.setValue(20)
        self.slider_duration.valueChanged.connect(lambda v: self.lbl_dur_val.setText(f"Weight: {v}%"))
        box_dur_lay.addWidget(self.slider_duration)
        layout.addWidget(self.box_duration)

        # 4. Satellite Priority 가중치 섹션
        self.box_priority = QGroupBox()
        box_prio_lay = QVBoxLayout(self.box_priority)
        
        h4 = QHBoxLayout()
        self.chk_priority = QCheckBox("Satellite Fixed Priority (Rank Based)")
        self.chk_priority.setChecked(False)
        self.chk_priority.setStyleSheet("font-weight: bold; color: #E65100;")
        self.chk_priority.toggled.connect(self.update_ui_state)
        h4.addWidget(self.chk_priority)
        
        self.lbl_prio_val = QLabel("Weight: 50%")
        self.lbl_prio_val.setFixedWidth(80)
        h4.addWidget(self.lbl_prio_val)
        
        self.slider_priority = QSlider(Qt.Orientation.Horizontal)
        self.slider_priority.setRange(1, 100)
        self.slider_priority.setValue(50)
        self.slider_priority.valueChanged.connect(lambda v: self.lbl_prio_val.setText(f"Weight: {v}%"))
        h4.addWidget(self.slider_priority)
        box_prio_lay.addLayout(h4)

        self.priority_table = QTableWidget()
        self.priority_table.setColumnCount(2)
        self.priority_table.setHorizontalHeaderLabels(["Satellite Name", "Priority Rank (1 = Top)"])
        self.priority_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.priority_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.priority_table.setRowCount(len(self.all_satellites))
        
        for row, sat in enumerate(self.all_satellites):
            item_sat = QTableWidgetItem(sat)
            item_sat.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item_rank = QTableWidgetItem(str(row + 1))
            item_rank.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.priority_table.setItem(row, 0, item_sat)
            self.priority_table.setItem(row, 1, item_rank)
            
        box_prio_lay.addWidget(self.priority_table)
        layout.addWidget(self.box_priority)

        # 5. 지상국 제외(Excluded Ground Stations) 섹션
        self.box_stations = QGroupBox("🚫 Exclude Ground Stations from Auto-Resolve")
        self.box_stations.setStyleSheet("QGroupBox { font-weight: bold; color: #C62828; }")
        box_st_lay = QVBoxLayout(self.box_stations)
        
        lbl_ex_desc = QLabel("Checked stations will be <b>bypassed from auto-resolution</b> (Unselected):")
        lbl_ex_desc.setStyleSheet("color: #555555; font-size: 11px;")
        box_st_lay.addWidget(lbl_ex_desc)

        self.list_stations = QListWidget()
        self.list_stations.setMaximumHeight(95)
        for st_name in self.all_stations:
            item = QListWidgetItem(f"📡 {st_name}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if st_name in self.saved_excluded_stations else Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, st_name)
            self.list_stations.addItem(item)
        box_st_lay.addWidget(self.list_stations)
        layout.addWidget(self.box_stations)

        # 안내 가이드
        self.frame_guide = QFrame()
        self.frame_guide.setStyleSheet(
            "background-color: #F8F9FA; border: 1px solid #E0E0E0; border-radius: 6px; padding: 6px;"
        )
        guide_lay = QVBoxLayout(self.frame_guide)
        guide_lay.setContentsMargins(6, 4, 6, 4)
        guide_lay.setSpacing(2)
        
        lbl_guide_title = QLabel("<b>📐 Score Evaluation & Decision Rule</b>")
        lbl_guide_title.setStyleSheet("color: #212121; font-size: 11px;")
        guide_lay.addWidget(lbl_guide_title)
        
        formula_html = (
            "<div style='font-size: 10px; color: #424242; line-height: 130%;'>"
            "• <b>Total Score</b> = &Sigma; (<b>Weight</b> &times; <b>Normalized Score</b>) + <b>Hard Constraints</b><br>"
            "&nbsp;&nbsp;- <b>Fairness</b>: (-Pass Count &times; 15) + Target Bonus (+20) + Min Target Bonus (+50)<br>"
            "&nbsp;&nbsp;- <b>Elevation / Duration</b>: (Pass Value / Group Max) &times; 100% (Normalized 0~100)<br>"
            "&nbsp;&nbsp;- <b>Priority</b>: Max 100 - (Rank - 1) &times; 20 (Rank 1 = 100 pts)<br>"
            "&nbsp;&nbsp;- <b>Hard Penalty (-10,000)</b>: Applied if satellite exceeds its <code>Max Pass Limit</code>.<br>"
            "<i>* Excluded stations are completely skipped and set to unselected.</i>"
            "</div>"
        )
        lbl_guide_desc = QLabel(formula_html)
        lbl_guide_desc.setWordWrap(True)
        guide_lay.addWidget(lbl_guide_desc)
        layout.addWidget(self.frame_guide)

        # 하단 버튼
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_ok = QPushButton("Apply Weighted Strategy")
        self.btn_ok.setStyleSheet("background-color: #1976D2; color: white; font-weight: bold; padding: 6px 16px;")
        self.btn_ok.clicked.connect(self.on_apply)
        btn_layout.addWidget(self.btn_ok)
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

    def restore_saved_inputs(self):
        """저장된 가중치와 우선순위 복원"""
        if self.saved_weights:
            self.chk_fairness.setChecked(self.saved_weights.get('use_fairness', True))
            w_fair = self.saved_weights.get('weight_fairness', 50)
            self.slider_fairness.setValue(w_fair)
            self.lbl_fair_val.setText(f"Weight: {w_fair}%")

            self.chk_elevation.setChecked(self.saved_weights.get('use_elevation', True))
            w_el = self.saved_weights.get('weight_elevation', 25)
            self.slider_elevation.setValue(w_el)
            self.lbl_el_val.setText(f"Weight: {w_el}%")

            self.chk_duration.setChecked(self.saved_weights.get('use_duration', False))
            w_dur = self.saved_weights.get('weight_duration', 20)
            self.slider_duration.setValue(w_dur)
            self.lbl_dur_val.setText(f"Weight: {w_dur}%")

            self.chk_priority.setChecked(self.saved_weights.get('use_priority', False))
            w_prio = self.saved_weights.get('weight_priority', 50)
            self.slider_priority.setValue(w_prio)
            self.lbl_prio_val.setText(f"Weight: {w_prio}%")

        if self.saved_priorities:
            for row in range(self.priority_table.rowCount()):
                sat_name = self.priority_table.item(row, 0).text()
                if sat_name in self.saved_priorities:
                    self.priority_table.item(row, 1).setText(str(self.saved_priorities[sat_name]))

        self.update_ui_state()

    def update_ui_state(self):
        self.slider_fairness.setEnabled(self.chk_fairness.isChecked())
        self.btn_edit_fairness.setEnabled(self.chk_fairness.isChecked())
        self.slider_elevation.setEnabled(self.chk_elevation.isChecked())
        self.slider_duration.setEnabled(self.chk_duration.isChecked())
        self.slider_priority.setEnabled(self.chk_priority.isChecked())
        self.priority_table.setEnabled(self.chk_priority.isChecked())

    def open_equalize_dialog(self):
        dialog = EqualizeRuleDialog(
            all_satellites=self.all_satellites,
            current_targets=self.equalize_target_sats,
            current_min_targets=self.min_pass_targets,
            current_max_targets=self.max_pass_targets,
            parent=self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.equalize_target_sats, self.min_pass_targets, self.max_pass_targets = dialog.get_results()

    def on_apply(self):
        if not any([self.chk_fairness.isChecked(), self.chk_elevation.isChecked(), 
                    self.chk_duration.isChecked(), self.chk_priority.isChecked()]):
            QMessageBox.warning(self, "Warning", "Please select at least one criteria.")
            return
        self.accept()

    def get_results(self):
        weights = {
            'use_fairness': self.chk_fairness.isChecked(),
            'weight_fairness': self.slider_fairness.value(),
            'use_elevation': self.chk_elevation.isChecked(),
            'weight_elevation': self.slider_elevation.value(),
            'use_duration': self.chk_duration.isChecked(),
            'weight_duration': self.slider_duration.value(),
            'use_priority': self.chk_priority.isChecked(),
            'weight_priority': self.slider_priority.value(),
        }
        sat_priorities = {}
        for row in range(self.priority_table.rowCount()):
            sat_name = self.priority_table.item(row, 0).text()
            try:
                rank = int(self.priority_table.item(row, 1).text())
            except ValueError:
                rank = 999
            sat_priorities[sat_name] = rank

        excluded_stations = []
        for i in range(self.list_stations.count()):
            item = self.list_stations.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                excluded_stations.append(item.data(Qt.ItemDataRole.UserRole))
            
        return weights, sat_priorities, self.equalize_target_sats, self.min_pass_targets, self.max_pass_targets, excluded_stations