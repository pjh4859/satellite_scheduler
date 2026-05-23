from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTableWidget, QTableWidgetItem, QLabel, QFileDialog, QHeaderView)

class FinalSchedulerTab(QWidget):
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        top_ctrl = QHBoxLayout()
        self.btn_generate_final = QPushButton("⚡ Generate Final Mission Schedule")
        self.btn_generate_final.setStyleSheet("background-color: #008CBA; color: white; font-weight: bold; padding: 8px;")
        top_ctrl.addWidget(self.btn_generate_final)
        
        self.btn_export_final = QPushButton("💾 Export Final Schedule")
        top_ctrl.addWidget(self.btn_export_final)
        
        top_ctrl.addStretch()
        layout.addLayout(top_ctrl)
        
        # 3번 마스터 타임라인 그리드 설정
        self.final_table = QTableWidget()
        self.final_table.setColumnCount(8)
        self.final_table.setHorizontalHeaderLabels([
            "Assigned Time (UTC)", "Ground Station", "Satellite ID", "Pass No.", "Assigned Activity Name", "Act ID", "Priority", "Duration"
        ])
        self.final_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.final_table.horizontalHeader().setDefaultSectionSize(160)
        layout.addWidget(self.final_table)