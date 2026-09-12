"""
[신규] 지상국 관리 다이얼로그 (Station Manager)

[배경]
기존에는 지상국을 추가/수정하려면 "📂 Open Folder" 버튼으로 stations 폴더를 열어
메모장 등 외부 텍스트 편집기로 .txt 파일을 직접 고쳐야 했습니다.
RX/TX 안테나 동시 처리 대수(capacity) 기능이 생기면서, 매번 텍스트 파일 포맷을
기억해서 손으로 컬럼을 추가하는 건 번거롭고 오타 위험도 있습니다.

그래서 이 다이얼로그는 "표(테이블) 형태로 지상국 목록을 보고,
셀을 클릭해서 값을 바꾸고, 저장 버튼 한 번으로 파일에 반영"할 수 있게 해줍니다.

[동작 방식 - 중요]
- core/scheduler.py의 parse_stations_from_dir()로 stations_dir 안의 모든 .txt/.cfg
  파일을 읽어서 "하나로 합쳐진" 목록을 보여줍니다.
- 저장(Save)을 누르면, 그 합쳐진 목록 전체를 stations_dir 안의 단일 파일
  (기본값: default_stations.txt)에 "한꺼번에" 다시 씁니다.
  ⚠️ 즉, 만약 지상국 정보가 여러 개의 .txt 파일에 나뉘어 저장되어 있었다면,
     이 다이얼로그로 저장하는 순간 전부 default_stations.txt 하나로 합쳐집니다.
     (기존에 있던 다른 지상국 파일 자체가 삭제되진 않지만, 그 파일의 지상국들도
      결과적으로 default_stations.txt에 중복 기록됩니다.)
     여러 파일로 나눠 관리하고 계셨다면, 저장 전에 이 안내를 참고해주세요.
"""

import os
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QTableWidget, QTableWidgetItem, QSpinBox, QDoubleSpinBox,
                             QPushButton, QDialogButtonBox, QHeaderView, QComboBox,
                             QMessageBox)
from PyQt6.QtCore import Qt

from core.scheduler import parse_stations_from_dir

# 테이블 컬럼 인덱스를 이름으로 관리 (숫자를 직접 쓰면 나중에 컬럼 순서 바꿀 때 실수하기 쉬움)
COL_NAME, COL_LAT, COL_LON, COL_DOWN, COL_CMD, COL_RX, COL_TX = range(7)


class StationManagerDialog(QDialog):
    def __init__(self, stations_dir, parent=None):
        super().__init__(parent)
        self.stations_dir = stations_dir
        self.setWindowTitle("🛰️ Ground Station Manager (지상국 관리)")
        self.resize(760, 480)

        # 다이얼로그를 열 때마다 최신 상태를 다시 읽어옵니다.
        self.stations = parse_stations_from_dir(self.stations_dir)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        info_label = QLabel(
            "<b>지상국 목록을 표에서 직접 편집한 뒤 [Save]를 누르세요.</b><br>"
            "<font color='#555555'>"
            "• RX Capacity: 이 지상국의 동시 수신(다운로드) 가능 안테나 대수 (기본 1)<br>"
            "• TX Capacity: 이 지상국의 동시 커맨딩(송신) 가능 채널 수 (보통 1, 특수한 경우만 변경)"
            "</font>"
        )
        layout.addWidget(info_label)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Station Name", "Latitude", "Longitude", "Download(Y/N)", "Command(Y/N)",
            "RX Capacity", "TX Capacity"
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        for col in (COL_LAT, COL_LON, COL_DOWN, COL_CMD, COL_RX, COL_TX):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)

        self._populate_table(self.stations)
        layout.addWidget(self.table)

        # --- 행 추가/삭제 버튼 ---
        row_btn_layout = QHBoxLayout()
        btn_add_row = QPushButton("➕ Add Station")
        btn_add_row.clicked.connect(self.add_empty_row)
        row_btn_layout.addWidget(btn_add_row)

        btn_del_row = QPushButton("🗑️ Delete Selected Row")
        btn_del_row.clicked.connect(self.delete_selected_row)
        row_btn_layout.addWidget(btn_del_row)
        layout.addLayout(row_btn_layout)

        # --- 최종 확인/취소 버튼 ---
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.on_save_clicked)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    # --------------------------------------------------------------------
    # 테이블 채우기 / 행 조작
    # --------------------------------------------------------------------
    def _populate_table(self, stations):
        """station tuple 리스트를 받아 테이블 행으로 그려줍니다."""
        self.table.setRowCount(len(stations))
        for row_idx, cfg in enumerate(stations):
            name = cfg[0]
            lat = cfg[1]
            lon = cfg[2]
            is_down = cfg[3] if len(cfg) > 3 else "Y"
            is_cmd = cfg[4] if len(cfg) > 4 else "Y"
            rx_cap = int(cfg[5]) if len(cfg) > 5 else 1  # 구버전 파일 호환: 없으면 기본값 1
            tx_cap = int(cfg[6]) if len(cfg) > 6 else 1
            self._set_row(row_idx, name, lat, lon, is_down, is_cmd, rx_cap, tx_cap)

    def _set_row(self, row_idx, name, lat, lon, is_down, is_cmd, rx_cap, tx_cap):
        """한 행(row)에 필요한 위젯/아이템들을 채워 넣는 헬퍼 함수."""
        self.table.setItem(row_idx, COL_NAME, QTableWidgetItem(str(name)))

        lat_spin = QDoubleSpinBox()
        lat_spin.setRange(-90.0, 90.0)
        lat_spin.setDecimals(4)
        lat_spin.setValue(float(lat))
        self.table.setCellWidget(row_idx, COL_LAT, lat_spin)

        lon_spin = QDoubleSpinBox()
        lon_spin.setRange(-180.0, 180.0)
        lon_spin.setDecimals(4)
        lon_spin.setValue(float(lon))
        self.table.setCellWidget(row_idx, COL_LON, lon_spin)

        down_combo = QComboBox()
        down_combo.addItems(["Y", "N"])
        down_combo.setCurrentText("Y" if str(is_down).upper().startswith("Y") else "N")
        self.table.setCellWidget(row_idx, COL_DOWN, down_combo)

        cmd_combo = QComboBox()
        cmd_combo.addItems(["Y", "N"])
        cmd_combo.setCurrentText("Y" if str(is_cmd).upper().startswith("Y") else "N")
        self.table.setCellWidget(row_idx, COL_CMD, cmd_combo)

        # 💡 안테나 대수는 최소 1대 이상이어야 의미가 있으므로(0대는 "아예 못 씀"과 같음),
        #    스핀박스 최솟값을 1로 강제해서 애초에 잘못된 값을 못 넣게 막습니다.
        rx_spin = QSpinBox()
        rx_spin.setRange(1, 99)
        rx_spin.setValue(max(1, rx_cap))
        rx_spin.setToolTip("이 지상국이 동시에 수신 가능한 안테나 대수")
        self.table.setCellWidget(row_idx, COL_RX, rx_spin)

        tx_spin = QSpinBox()
        tx_spin.setRange(1, 99)
        tx_spin.setValue(max(1, tx_cap))
        tx_spin.setToolTip("이 지상국이 동시에 커맨딩(송신) 가능한 채널 수 (보통 1)")
        self.table.setCellWidget(row_idx, COL_TX, tx_spin)

    def add_empty_row(self):
        """빈 지상국 행을 하나 추가합니다. 사용자가 이름/좌표를 직접 채워 넣으면 됩니다."""
        row_idx = self.table.rowCount()
        self.table.insertRow(row_idx)
        self._set_row(row_idx, "New_Station", 0.0, 0.0, "Y", "Y", 1, 1)

    def delete_selected_row(self):
        """현재 선택(클릭)된 행을 삭제합니다. 여러 행이 선택됐으면 전부 삭제합니다."""
        selected_rows = sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True)
        if not selected_rows:
            QMessageBox.information(self, "안내", "삭제할 행을 먼저 클릭해서 선택해주세요.")
            return
        for row_idx in selected_rows:
            self.table.removeRow(row_idx)

    # --------------------------------------------------------------------
    # 저장
    # --------------------------------------------------------------------
    def _collect_rows(self):
        """테이블 위젯들의 현재 값을 읽어 station tuple 리스트로 변환합니다."""
        rows = []
        for row_idx in range(self.table.rowCount()):
            name_item = self.table.item(row_idx, COL_NAME)
            name = name_item.text().strip() if name_item else ""
            if not name:
                continue  # 이름이 비어있는 행은 저장 대상에서 조용히 제외

            lat = self.table.cellWidget(row_idx, COL_LAT).value()
            lon = self.table.cellWidget(row_idx, COL_LON).value()
            is_down = self.table.cellWidget(row_idx, COL_DOWN).currentText()
            is_cmd = self.table.cellWidget(row_idx, COL_CMD).currentText()
            rx_cap = self.table.cellWidget(row_idx, COL_RX).value()
            tx_cap = self.table.cellWidget(row_idx, COL_TX).value()
            rows.append((name, lat, lon, is_down, is_cmd, rx_cap, tx_cap))
        return rows

    def on_save_clicked(self):
        rows = self._collect_rows()

        # 이름 중복 검사 (같은 이름의 지상국이 2개면 스케줄링 로직이 어느 쪽인지 구분 못 함)
        names = [r[0] for r in rows]
        duplicates = {n for n in names if names.count(n) > 1}
        if duplicates:
            QMessageBox.warning(
                self, "저장 실패",
                f"지상국 이름이 중복되었습니다: {', '.join(sorted(duplicates))}\n"
                f"중복된 이름을 수정한 뒤 다시 저장해주세요."
            )
            return

        if not os.path.exists(self.stations_dir):
            os.makedirs(self.stations_dir)

        target_file = os.path.join(self.stations_dir, "default_stations.txt")
        try:
            with open(target_file, "w", encoding="utf-8") as f:
                f.write("# Station_Name, Latitude, Longitude, Is_Download_Capable(Y/N), Is_Command_Capable(Y/N), RX_Capacity, TX_Capacity\n")
                f.write("# (이 파일은 Ground Station Manager 다이얼로그에 의해 자동 생성/갱신되었습니다)\n")
                for name, lat, lon, is_down, is_cmd, rx_cap, tx_cap in rows:
                    f.write(f"{name}, {lat}, {lon}, {is_down}, {is_cmd}, {rx_cap}, {tx_cap}\n")
        except Exception as e:
            QMessageBox.critical(self, "저장 실패", f"파일 저장 중 오류가 발생했습니다:\n{e}")
            return

        self.accept()
