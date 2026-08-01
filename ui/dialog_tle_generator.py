import os
import math
import re
from datetime import datetime, timedelta, timezone

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QDoubleSpinBox, QDateTimeEdit, 
                             QPushButton, QMessageBox, QGroupBox, QFormLayout, QDialogButtonBox)

# ==============================================================================
# [팝업 창] 발사체 분리 벡터(State Vector) 기반 TLE 자동 생성 다이얼로그
# ==============================================================================
class TleFromSepVectorDialog(QDialog):
    """
    로켓 발사 시각, 분리 T+ 경과시간, 위치(Px, Py, Pz), 속도(Vx, Vy, Vz) 벡터 정보를 
    전달받아 케플러 요소 변환 후 tle 폴더에 표준 TLE 파일을 자동 생성하는 팝업 클래스
    """
    def __init__(self, tle_dir="tle", parent=None):
        super().__init__(parent)
        self.setWindowTitle("🚀 Generate TLE from Rocket Separation Vector")
        self.resize(580, 520)
        self.tle_dir = tle_dir
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 1. 미션 및 위성 식별 메타데이터
        group_meta = QGroupBox("1. Satellite Information & Launch Time")
        form_meta = QFormLayout(group_meta)
        
        self.txt_sat_name = QLineEdit("SAT_NEW_1")
        form_meta.addRow("Satellite Name:", self.txt_sat_name)
        
        self.txt_norad_id = QLineEdit("90001")
        form_meta.addRow("NORAD ID (Catalog No):", self.txt_norad_id)

        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        self.dt_launch = QDateTimeEdit(now_utc)
        self.dt_launch.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.dt_launch.setCalendarPopup(True)
        form_meta.addRow("Rocket Launch Time (UTC):", self.dt_launch)

        self.spin_elapsed_sec = QDoubleSpinBox()
        self.spin_elapsed_sec.setRange(0.0, 864000.0)
        self.spin_elapsed_sec.setValue(540.0)  # 기본값 T+540초
        self.spin_elapsed_sec.setSuffix(" sec (T+ Elapsed Time)")
        form_meta.addRow("Separation Elapsed Time:", self.spin_elapsed_sec)

        layout.addWidget(group_meta)

        # 2. 분리 시점 관성 위치 벡터 (Position Vector in ECI, km)
        group_pos = QGroupBox("2. Position Vector at Separation (ECI J2000, km)")
        layout_pos = QHBoxLayout(group_pos)
        
        self.spin_px = QDoubleSpinBox()
        self.spin_px.setRange(-50000.0, 50000.0)
        self.spin_px.setValue(4500.0)
        layout_pos.addWidget(QLabel("Px:"))
        layout_pos.addWidget(self.spin_px)

        self.spin_py = QDoubleSpinBox()
        self.spin_py.setRange(-50000.0, 50000.0)
        self.spin_py.setValue(2200.0)
        layout_pos.addWidget(QLabel("Py:"))
        layout_pos.addWidget(self.spin_py)

        self.spin_pz = QDoubleSpinBox()
        self.spin_pz.setRange(-50000.0, 50000.0)
        self.spin_pz.setValue(4800.0)
        layout_pos.addWidget(QLabel("Pz:"))
        layout_pos.addWidget(self.spin_pz)

        layout.addWidget(group_pos)

        # 3. 분리 시점 관성 속도 벡터 (Velocity Vector in ECI, km/s)
        group_vel = QGroupBox("3. Velocity Vector at Separation (ECI J2000, km/s)")
        layout_vel = QHBoxLayout(group_vel)

        self.spin_vx = QDoubleSpinBox()
        self.spin_vx.setRange(-20.0, 20.0)
        self.spin_vx.setValue(-2.5)
        self.spin_vx.setDecimals(4)
        layout_vel.addWidget(QLabel("Vx:"))
        layout_vel.addWidget(self.spin_vx)

        self.spin_vy = QDoubleSpinBox()
        self.spin_vy.setRange(-20.0, 20.0)
        self.spin_vy.setValue(6.8)
        self.spin_vy.setDecimals(4)
        layout_vel.addWidget(QLabel("Vy:"))
        layout_vel.addWidget(self.spin_vy)

        self.spin_vz = QDoubleSpinBox()
        self.spin_vz.setRange(-20.0, 20.0)
        self.spin_vz.setValue(2.1)
        self.spin_vz.setDecimals(4)
        layout_vel.addWidget(QLabel("Vz:"))
        layout_vel.addWidget(self.spin_vz)

        layout.addWidget(group_vel)

        # 안내 문구
        lbl_info = QLabel("<i>ℹ️ Window remains open for multi-satellite creation. Sat Name and NORAD ID auto-increment.</i>")
        lbl_info.setStyleSheet("color: #666666; font-size: 11px;")
        layout.addWidget(lbl_info)

        # 하단 버튼 구성 (Generate & Add / Close)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_generate = QPushButton("➕ Generate & Add TLE")
        self.btn_generate.setStyleSheet("background-color: #0D47A1; color: white; font-weight: bold; padding: 6px 16px;")
        self.btn_generate.clicked.connect(self.generate_and_save_tle)
        btn_layout.addWidget(self.btn_generate)

        self.btn_close = QPushButton("Close Window")
        self.btn_close.setStyleSheet("background-color: #555555; color: white; font-weight: bold; padding: 6px 16px;")
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

    def compute_tle_checksum(self, line):
        """TLE 표준 Checksum 계산 함수"""
        checksum = 0
        for char in line:
            if char.isdigit():
                checksum += int(char)
            elif char == '-':
                checksum += 1
        return str(checksum % 10)

    def auto_increment_sat_info(self):
        """연속 생성을 위해 위성 이름 및 NORAD ID 숫자를 1씩 자동 증가"""
        # NORAD ID 증가
        curr_id_str = self.txt_norad_id.text().strip()
        if curr_id_str.isdigit():
            self.txt_norad_id.setText(str(int(curr_id_str) + 1))

        # 위성 이름 끝의 숫자 증가 (예: SAT_NEW_1 -> SAT_NEW_2)
        curr_name = self.txt_sat_name.text().strip()
        match = re.search(r'(\d+)$', curr_name)
        if match:
            num_str = match.group(1)
            next_num = int(num_str) + 1
            new_name = curr_name[:match.start(1)] + str(next_num)
            self.txt_sat_name.setText(new_name)

    def generate_and_save_tle(self):
        """위치/속도 벡터 ➔ 케플러 요소 연산 ➔ TLE 파일 저장 (창을 닫지 않음)"""
        sat_name = self.txt_sat_name.text().strip() or "SAT_NEW_1"
        norad_id_raw = self.txt_norad_id.text().strip() or "90001"
        try:
            norad_id = f"{int(norad_id_raw):05d}"
        except ValueError:
            norad_id = "90001"

        # 분리 시각 계산 (발사 시각 + 경과시간)
        launch_dt = self.dt_launch.dateTime().toPyDateTime()
        sep_dt = launch_dt + timedelta(seconds=self.spin_elapsed_sec.value())

        # Px, Py, Pz (km) & Vx, Vy, Vz (km/s)
        rx, ry, rz = self.spin_px.value(), self.spin_py.value(), self.spin_pz.value()
        vx, vy, vz = self.spin_vx.value(), self.spin_vy.value(), self.spin_vz.value()

        # ----------------------------------------------------------------------
        # 케플러 6대 궤도 요소 계산 (Orbital Mechanics)
        # ----------------------------------------------------------------------
        mu = 398600.4418  # 지구 중력 상수 (km^3/s^2)
        r_mag = math.sqrt(rx**2 + ry**2 + rz**2)
        v_mag = math.sqrt(vx**2 + vy**2 + vz**2)

        if r_mag == 0:
            QMessageBox.critical(self, "Calculation Error", "Position vector magnitude cannot be 0.")
            return

        # 각운동량 벡터 h = r x v
        hx = ry * vz - rz * vy
        hy = rz * vx - rx * vz
        hz = rx * vy - ry * vx
        h_mag = math.sqrt(hx**2 + hy**2 + hz**2)

        # 궤도경사각 (Inclination, deg)
        inc_rad = math.acos(max(-1.0, min(1.0, hz / h_mag)))
        inc_deg = math.degrees(inc_rad)

        # 승교점 벡터 n = k x h
        nx = -hy
        ny = hx
        n_mag = math.sqrt(nx**2 + ny**2)

        # 승교점 적경 (RAAN, deg)
        if n_mag != 0:
            raan_rad = math.acos(max(-1.0, min(1.0, nx / n_mag)))
            if ny < 0:
                raan_rad = 2 * math.pi - raan_rad
        else:
            raan_rad = 0.0
        raan_deg = math.degrees(raan_rad)

        # 이심률 벡터 e
        v_r = (rx * vx + ry * vy + rz * vz) / r_mag
        ex = (1 / mu) * ((v_mag**2 - mu / r_mag) * rx - r_mag * v_r * vx)
        ey = (1 / mu) * ((v_mag**2 - mu / r_mag) * ry - r_mag * v_r * vy)
        ez = (1 / mu) * ((v_mag**2 - mu / r_mag) * rz - r_mag * v_r * vz)
        ecc = math.sqrt(ex**2 + ey**2 + ez**2)

        # 장반경 (Semi-major axis a, km) 및 Mean Motion (n, rev/day)
        sma = 1.0 / ((2.0 / r_mag) - (v_mag**2 / mu))
        if sma <= 0:
            QMessageBox.critical(self, "Calculation Error", "Calculated orbit is hyperbolic or invalid.")
            return

        period_sec = 2.0 * math.pi * math.sqrt((sma**3) / mu)
        mean_motion = 86400.0 / period_sec

        # 근점 인수 (Argument of Perigee, deg)
        if n_mag != 0 and ecc != 0:
            n_dot_e = nx * ex + ny * ey
            argp_rad = math.acos(max(-1.0, min(1.0, n_dot_e / (n_mag * ecc))))
            if ez < 0:
                argp_rad = 2 * math.pi - argp_rad
        else:
            argp_rad = 0.0
        argp_deg = math.degrees(argp_rad)

        # 진이상/평이상 (Mean Anomaly M, deg)
        if ecc != 0:
            e_dot_r = ex * rx + ey * ry + ez * rz
            nu_rad = math.acos(max(-1.0, min(1.0, e_dot_r / (ecc * r_mag))))
            if v_r < 0:
                nu_rad = 2 * math.pi - nu_rad
            E_rad = 2.0 * math.atan(math.tan(nu_rad / 2.0) / math.sqrt((1 + ecc) / (1 - ecc)))
            M_rad = E_rad - ecc * math.sin(E_rad)
            if M_rad < 0: M_rad += 2 * math.pi
        else:
            M_rad = 0.0
        ma_deg = math.degrees(M_rad)

        # ----------------------------------------------------------------------
        # TLE 표준 포맷팅 (Line 1 & Line 2)
        # ----------------------------------------------------------------------
        year_two_digit = sep_dt.strftime("%y")
        day_of_year = sep_dt.timetuple().tm_yday
        fraction_of_day = (sep_dt.hour * 3600 + sep_dt.minute * 60 + sep_dt.second + sep_dt.microsecond / 1e6) / 86400.0
        epoch_str = f"{year_two_digit}{day_of_year:03d}.{int(fraction_of_day * 1e8):08d}"

        l1_base = f"1 {norad_id}U 26019A   {epoch_str}  .00001000  00000-0  10000-3 0  999"
        l1_full = l1_base + self.compute_tle_checksum(l1_base)

        ecc_str = f"{int(round(ecc * 1e7)):07d}"
        l2_base = f"2 {norad_id} {inc_deg:8.4f} {raan_deg:8.4f} {ecc_str} {argp_deg:8.4f} {ma_deg:8.4f} {mean_motion:11.8f}    0"
        l2_full = l2_base + self.compute_tle_checksum(l2_base)

        # ----------------------------------------------------------------------
        # 파일 저장
        # ----------------------------------------------------------------------
        if not os.path.exists(self.tle_dir):
            os.makedirs(self.tle_dir)

        safe_filename = re.sub(r'[^A-Za-z0-9_]', '_', sat_name) + ".tle"
        file_path = os.path.join(self.tle_dir, safe_filename)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"{sat_name}\n")
            f.write(f"{l1_full}\n")
            f.write(f"{l2_full}\n")

        # 메인 창의 TLE 파일 목록 즉시 갱신
        if self.parent() and hasattr(self.parent(), 'refresh_tle_files'):
            self.parent().refresh_tle_files()

        # 알림 후 다음 생성을 위해 위성 이름 및 NORAD ID 자동 증가 (창은 유지)
        QMessageBox.information(self, "TLE Generated", f"Successfully generated TLE for '{sat_name}'!\nSaved to: {file_path}")
        self.auto_increment_sat_info()