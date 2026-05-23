import sys
import os
from PyQt6.QtWidgets import QMainWindow, QTabWidget, QApplication
from core.plan_parser import create_default_plan_csv, create_default_plan_excel

# 분할 마운트한 서브 컴포넌트 탭 임포트
from ui.tab1_pass_predict import PassPredictTab
from ui.tab2_constraints_planner import ConstraintsPlannerTab
from ui.tab3_final_scheduler import FinalSchedulerTab

class SatelliteSchedulerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LEOP Ground Segment Integrated Operations Planner")
        self.setGeometry(100, 100, 1400, 750)
        
        # 전역 탭 공유 메모리 데이터셋 보관창 정의
        self.calculated_passes = []
        self.is_populating = False
        self.station_data = []
        self.plans_dir = "plans"
        
        # 기본 템플릿 환경 구성 자동 가동
        create_default_plan_csv(self.plans_dir)
        create_default_plan_excel(self.plans_dir)
        
        self.init_ui()
        
    def init_ui(self):
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # 각 분할 탭 인스턴스에 self(메인 허브 주소)를 주입하며 바인딩
        self.tab1 = PassPredictTab(self)
        self.tab2 = ConstraintsPlannerTab(self)
        self.tab3 = FinalSchedulerTab(self)
        
        self.tabs.addTab(self.tab1, "1. Ground Station Pass Prediction")
        self.tabs.addTab(self.tab2, "2. Mission Constraints Planner")
        self.tabs.addTab(self.tab3, "3. Final Mission Scheduler")

if __name__ == "__main__":
    app = sys.argv
    q_app = QApplication(app)
    window = SatelliteSchedulerApp()
    window.show()
    sys.exit(q_app.exec())