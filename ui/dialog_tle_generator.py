import os
import math
from datetime import datetime, timezone
import numpy as np
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QDateTimeEdit, QPushButton, QMessageBox, 
                             QGroupBox, QRadioButton)
from PyQt6.QtCore import Qt
# 💡 skyfield.positionlib import 제거 및 wgs84, Distance, Velocity 사용
from skyfield.api import load, wgs84, Distance, Velocity


def ecef_to_eci_skyfield(r_ecef, v_ecef, epoch_dt):
    """
    Skyfield 정밀 천체 연산 엔진 기반 ECEF (ITRF) -> ECI (J2000/GCRS) 변환
    - 지구 세차(Precession), 장동(Nutation), 자전(UT1/GMST) 정밀 반영
    
    :param r_ecef: (x, y, z) [km]
    :param v_ecef: (vx, vy, vz) [km/s]
    :param epoch_dt: datetime object (UTC)
    :return: (r_eci, v_eci) [km], [km/s]
    """
    from skyfield.framelib import itrs
    
    ts = load.timescale()
    t = ts.from_datetime(epoch_dt)

    px, py, pz = r_ecef
    vx, vy, vz = v_ecef

    r_m = np.array([px, py, pz], dtype=float) * 1000.0
    v_ms = np.array([vx, vy, vz], dtype=float) * 1000.0

    # 💡 ITRS -> GCRS (ECI J2000) 회전 행렬 R(t) 직접 추출 (itrs.at 대신 rotation_at 사용)

    R = itrs.rotation_at(t)
    R_inv = R.T  # ECEF -> ECI 방향으로 전치

    # 1. 위치 변환
    r_eci_m = R_inv.dot(r_m)
    r_eci_km = r_eci_m / 1000.0

    # 2. 속도 변환
    omega_vec = np.array([0.0, 0.0, 7.292115146706979e-5])
    v_eci_m = R_inv.dot(v_ms) + np.cross(omega_vec, r_eci_m)
    v_eci_kms = v_eci_m / 1000.0      

    return tuple(r_eci_km), tuple(v_eci_kms)


def clamp(val, low=-1.0, high=1.0):
    """acos 부동소수점 초과 방지용 Safe Clamp"""
    return max(low, min(high, val))


class TleFromSepVectorDialog(QDialog):
    def __init__(self, tle_dir="tle", parent=None):
        super().__init__(parent)
        self.setWindowTitle("🚀 Generate TLE from Separation Vector")
        self.resize(520, 580)
        self.tle_dir = tle_dir
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("<b>Generate TLE File from Separation Vector State</b>"))
        
        # 1. 위성 명칭
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Satellite Name:"))
        self.txt_sat_name = QLineEdit("NEONSAT-1B")
        name_layout.addWidget(self.txt_sat_name)
        layout.addLayout(name_layout)

        # 2. NORAD Catalog ID
        norad_layout = QHBoxLayout()
        norad_layout.addWidget(QLabel("NORAD ID (5-digit):"))
        self.txt_norad_id = QLineEdit("99999")
        norad_layout.addWidget(self.txt_norad_id)
        layout.addLayout(norad_layout)
        
        # 3. 분리 시각 (UTC)
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("Separation Epoch (UTC):"))
        self.time_edit = QDateTimeEdit(datetime.now(timezone.utc).replace(tzinfo=None))
        self.time_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.time_edit.setCalendarPopup(True)
        time_layout.addWidget(self.time_edit)
        layout.addLayout(time_layout)

        # 4. 좌표계 선택 라디오 버튼 (ECI vs ECEF)
        group_frame = QGroupBox("Coordinate Frame Selection")
        frame_layout = QHBoxLayout(group_frame)
        
        self.radio_eci = QRadioButton("ECI (J2000 / Inertial)")
        self.radio_eci.setChecked(True)
        self.radio_eci.toggled.connect(self.on_frame_changed)
        frame_layout.addWidget(self.radio_eci)

        self.radio_ecef = QRadioButton("ECEF (ITRF / Earth-Fixed)")
        self.radio_ecef.toggled.connect(self.on_frame_changed)
        frame_layout.addWidget(self.radio_ecef)
        
        layout.addWidget(group_frame)

        # 5. 위치 벡터 (Position Vector)
        self.lbl_pos_header = QLabel("<b>Position Vector (ECI / J2000) [km]:</b>")
        layout.addWidget(self.lbl_pos_header)
        
        pos_layout = QHBoxLayout()
        self.txt_px = QLineEdit("-2431.123")
        self.txt_py = QLineEdit("4812.456")
        self.txt_pz = QLineEdit("4310.789")
        pos_layout.addWidget(QLabel("X:"))
        pos_layout.addWidget(self.txt_px)
        pos_layout.addWidget(QLabel("Y:"))
        pos_layout.addWidget(self.txt_py)
        pos_layout.addWidget(QLabel("Z:"))
        pos_layout.addWidget(self.txt_pz)
        layout.addLayout(pos_layout)

        # 6. 속도 벡터 (Velocity Vector)
        self.lbl_vel_header = QLabel("<b>Velocity Vector (ECI / J2000) [km/s]:</b>")
        layout.addWidget(self.lbl_vel_header)
        
        vel_layout = QHBoxLayout()
        self.txt_vx = QLineEdit("-5.123")
        self.txt_vy = QLineEdit("-3.456")
        self.txt_vz = QLineEdit("4.789")
        vel_layout.addWidget(QLabel("Vx:"))
        vel_layout.addWidget(self.txt_vx)
        vel_layout.addWidget(QLabel("Vy:"))
        vel_layout.addWidget(self.txt_vy)
        vel_layout.addWidget(QLabel("Vz:"))
        vel_layout.addWidget(self.txt_vz)
        layout.addLayout(vel_layout)

        # 안내 문구
        self.lbl_info = QLabel(
            "<font color='#555555'><i>ℹ️ ECI (J2000) 관성 좌표계 기준 state vector입니다.</i></font>"
        )
        self.lbl_info.setWordWrap(True)
        layout.addWidget(self.lbl_info)

        # 7. 버튼
        btn_layout = QHBoxLayout()
        btn_gen = QPushButton("🚀 Generate & Save TLE")
        btn_gen.setStyleSheet("background-color: #2E7D32; color: white; font-weight: bold; padding: 8px;")
        btn_gen.clicked.connect(self.generate_and_save_tle)
        btn_layout.addWidget(btn_gen)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        layout.addLayout(btn_layout)

    def on_frame_changed(self):
        if self.radio_ecef.isChecked():
            self.lbl_pos_header.setText("<b>Position Vector (ECEF / ITRF) [km]:</b>")
            self.lbl_vel_header.setText("<b>Velocity Vector (ECEF / ITRF) [km/s]:</b>")
            self.lbl_info.setText(
                "<font color='#0D47A1'><i>ℹ️ ECEF 입력 시 Skyfield 고정밀 천체 변환 엔진으로 ECI 관성 좌표계로 자동 변환됩니다.</i></font>"
            )
        else:
            self.lbl_pos_header.setText("<b>Position Vector (ECI / J2000) [km]:</b>")
            self.lbl_vel_header.setText("<b>Velocity Vector (ECI / J2000) [km/s]:</b>")
            self.lbl_info.setText(
                "<font color='#555555'><i>ℹ️ ECI (J2000) 관성 좌표계 기준 state vector입니다.</i></font>"
            )

    def generate_and_save_tle(self):
        sat_name = self.txt_sat_name.text().strip()
        norad_id = self.txt_norad_id.text().strip()
        epoch_dt = self.time_edit.dateTime().toPyDateTime().replace(tzinfo=timezone.utc)

        try:
            px = float(self.txt_px.text())
            py = float(self.txt_py.text())
            pz = float(self.txt_pz.text())
            vx = float(self.txt_vx.text())
            vy = float(self.txt_vy.text())
            vz = float(self.txt_vz.text())
        except ValueError:
            QMessageBox.critical(self, "Input Error", "Please enter valid numeric values for Position and Velocity vectors.")
            return

        if not sat_name or not norad_id:
            QMessageBox.critical(self, "Input Error", "Satellite Name and NORAD ID are required.")
            return

        # 💡 ECEF 선택 시 Skyfield 정밀 변환 적용
        if self.radio_ecef.isChecked():
            r_eci, v_eci = ecef_to_eci_skyfield((px, py, pz), (vx, vy, vz), epoch_dt)
            r_x, r_y, r_z = r_eci
            v_x, v_y, v_z = v_eci
        else:
            r_x, r_y, r_z = px, py, pz
            v_x, v_y, v_z = vx, vy, vz

        try:
            # 표준 중력 상수 (WGS84 Earth gravitational constant)
            mu = 398600.4418 # km^3/s^2
            r_mag = math.sqrt(r_x**2 + r_y**2 + r_z**2)
            v_mag = math.sqrt(v_x**2 + v_y**2 + v_z**2)
            
            # 장반경 (a)
            energy = (v_mag**2 / 2.0) - (mu / r_mag)
            a = -mu / (2.0 * energy)
            
            # 평균 운동 (n - rad/s -> rev/day)
            n_rad_s = math.sqrt(mu / (a**3))
            n_rev_day = n_rad_s * 86400.0 / (2.0 * math.pi)
            
            # 각운동량 벡터 (h = r x v)
            hx = r_y * v_z - r_z * v_y
            hy = r_z * v_x - r_x * v_z
            hz = r_x * v_y - r_y * v_x
            h_mag = math.sqrt(hx**2 + hy**2 + hz**2)
            
            # 경사각 (inc)
            inc_deg = math.degrees(math.acos(clamp(hz / h_mag)))
            
            # 승교점 적경 (RAAN)
            nx = -hy
            ny = hx
            n_mag = math.sqrt(nx**2 + ny**2)
            if n_mag != 0:
                raan_rad = math.acos(clamp(nx / n_mag))
                if ny < 0: raan_rad = 2.0 * math.pi - raan_rad
                raan_deg = math.degrees(raan_rad)
            else:
                raan_deg = 0.0
                
            # 이심률 벡터 (e_vec)
            v_cross_h_x = v_y * hz - v_z * hy
            v_cross_h_y = v_z * hx - v_x * hz
            v_cross_h_z = v_x * hy - v_y * hx
            ex = (v_cross_h_x / mu) - (r_x / r_mag)
            ey = (v_cross_h_y / mu) - (r_y / r_mag)
            ez = (v_cross_h_z / mu) - (r_z / r_mag)
            e_mag = math.sqrt(ex**2 + ey**2 + ez**2)
            
            # 근점 인수 (arg_pe)
            if n_mag != 0 and e_mag != 0:
                arg_pe_rad = math.acos(clamp((nx * ex + ny * ey) / (n_mag * e_mag)))
                if ez < 0: arg_pe_rad = 2.0 * math.pi - arg_pe_rad
                arg_pe_deg = math.degrees(arg_pe_rad)
            else:
                arg_pe_deg = 0.0
                
            # 진근점이각 (nu) -> 편심이각 (E) -> 평균 근점이각 (M)
            if e_mag != 0:
                r_dot_v = r_x * v_x + r_y * v_y + r_z * v_z
                nu_rad = math.acos(clamp((ex * r_x + ey * r_y + ez * r_z) / (e_mag * r_mag)))
                if r_dot_v < 0: nu_rad = 2.0 * math.pi - nu_rad
                
                # 편심이각 (E)
                E_rad = 2.0 * math.atan(math.tan(nu_rad / 2.0) * math.sqrt((1.0 - e_mag) / (1.0 + e_mag)))
                # 평균 근점이각 (M)
                M_rad = E_rad - e_mag * math.sin(E_rad)
                M_deg = math.degrees(M_rad % (2.0 * math.pi))
            else:
                M_deg = 0.0

            # TLE 텍스트 라인 포맷팅
            epoch_year_2d = epoch_dt.year % 100
            start_of_year = datetime(epoch_dt.year, 1, 1, tzinfo=timezone.utc)
            day_of_year = (epoch_dt - start_of_year).total_seconds() / 86400.0 + 1.0
            
            norad_str = f"{int(norad_id):05d}"
            
            line1_raw = f"1 {norad_str}U 26001A   {epoch_year_2d:02d}{day_of_year:012.8f}  .00001000  00000-0  10000-4 0  999"
            line2_raw = f"2 {norad_str} {inc_deg:8.4f} {raan_deg:8.4f} {int(e_mag*1e7):07d} {arg_pe_deg:8.4f} {M_deg:8.4f} {n_rev_day:11.8f}    1"

            # Checksum 연산
            def calc_checksum(line_str):
                s = 0
                for ch in line_str[:68]:
                    if ch.isdigit(): s += int(ch)
                    elif ch == '-': s += 1
                return s % 10

            line1 = line1_raw + str(calc_checksum(line1_raw))
            line2 = line2_raw + str(calc_checksum(line2_raw))

            # 저장
            if not os.path.exists(self.tle_dir):
                os.makedirs(self.tle_dir)
                
            file_path = os.path.join(self.tle_dir, f"{sat_name}.tle")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"{sat_name}\n")
                f.write(f"{line1}\n")
                f.write(f"{line2}\n")

            frame_str = "ECEF (ITRF)" if self.radio_ecef.isChecked() else "ECI (J2000)"
            QMessageBox.information(
                self, "TLE Generated", 
                f"Successfully generated TLE for {sat_name}!\n\n"
                f"• Frame: {frame_str}\n"
                f"• Inc: {inc_deg:.4f} deg, RAAN: {raan_deg:.4f} deg\n"
                f"• File saved to: {file_path}"
            )
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Generation Error", f"Failed to compute orbit elements:\n{str(e)}")