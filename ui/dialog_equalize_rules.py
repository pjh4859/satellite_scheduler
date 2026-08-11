from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QTableWidget, QTableWidgetItem, QSpinBox, 
                             QPushButton, QDialogButtonBox, QHeaderView)
from PyQt6.QtCore import Qt


class EqualizeRuleDialog(QDialog):
    def __init__(self, all_satellites, current_targets=None, current_min_targets=None, current_max_targets=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ Satellite Allocation Rules (Min Guarantee & Max Cap)")
        self.resize(620, 480)
        self.all_satellites = sorted(all_satellites)
        
        if current_targets is None:
            self.current_targets = set(self.all_satellites)
        else:
            self.current_targets = set(current_targets)
            
        if current_min_targets is None:
            self.current_min_targets = {sat: 1 for sat in self.all_satellites}
        else:
            self.current_min_targets = current_min_targets

        if current_max_targets is None:
            self.current_max_targets = {sat: 0 for sat in self.all_satellites}
        else:
            self.current_max_targets = current_max_targets
            
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("<b>Set Individual Min Guarantee & Max Pass Limit per Satellite:</b><br><font color='#555555'>• Min Guarantee: 0 ~ 50 (0 = No Guarantee)<br>• Max Limit: 0 ~ 999 (0 = No Limit / Uncapped)</font>"))
        
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Include", "Satellite Name", "Min Guarantee", "Max Limit (0=No Limit)"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        
        self.table.setRowCount(len(self.all_satellites))
        
        for idx, sat in enumerate(self.all_satellites):
            chk_item = QTableWidgetItem()
            chk_item.setCheckState(Qt.CheckState.Checked if sat in self.current_targets else Qt.CheckState.Unchecked)
            self.table.setItem(idx, 0, chk_item)
            
            sat_item = QTableWidgetItem(f"🛰️  {sat}")
            sat_item.setFlags(sat_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(idx, 1, sat_item)
            
            min_spin = QSpinBox()
            min_spin.setRange(0, 50)
            min_spin.setValue(self.current_min_targets.get(sat, 1))
            self.table.setCellWidget(idx, 2, min_spin)

            max_spin = QSpinBox()
            max_spin.setRange(0, 999)
            max_spin.setValue(self.current_max_targets.get(sat, 0))
            self.table.setCellWidget(idx, 3, max_spin)
            
        layout.addWidget(self.table)
        
        btn_ctrl_layout = QHBoxLayout()
        btn_sel_all = QPushButton("☑ Select All")
        btn_sel_all.clicked.connect(lambda: self.set_all_checks(True))
        btn_ctrl_layout.addWidget(btn_sel_all)
        
        btn_unsel_all = QPushButton("☒ Clear All")
        btn_unsel_all.clicked.connect(lambda: self.set_all_checks(False))
        btn_ctrl_layout.addWidget(btn_unsel_all)
        layout.addLayout(btn_ctrl_layout)
        
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def set_all_checks(self, checked):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for idx in range(self.table.rowCount()):
            item = self.table.item(idx, 0)
            if item: item.setCheckState(state)

    def get_results(self):
        selected_sats = set()
        min_targets = {}
        max_targets = {}
        for idx in range(self.table.rowCount()):
            item_chk = self.table.item(idx, 0)
            sat_name = self.all_satellites[idx]
            min_spin = self.table.cellWidget(idx, 2)
            max_spin = self.table.cellWidget(idx, 3)
            
            if item_chk and item_chk.checkState() == Qt.CheckState.Checked:
                selected_sats.add(sat_name)
                
            if min_spin: min_targets[sat_name] = min_spin.value()
            if max_spin: max_targets[sat_name] = max_spin.value()
                
        return selected_sats, min_targets, max_targets