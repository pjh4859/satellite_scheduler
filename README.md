# 🛰️ LEOP Multi-Satellite Pass Scheduler

> **Advanced Multi-Satellite & Ground Station Pass Prediction, Conflict Resolution, and Mission Scheduling System**

![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![PyQt6](https://img.shields.io/badge/GUI-PyQt6-green.svg)
![Astrodynamics](https://img.shields.io/badge/Engine-Skyfield-orange.svg)
![License](https://img.shields.io/badge/License-MIT-lightgrey.svg)

**LEOP Multi-Satellite Pass Scheduler**는 발사 및 초기 궤도 운용(LEOP) 및 군집 위성(Swarm/Constellation) 운용 시 지상국 안테나 자원 할당과 위성 교신 일정을 자동으로 계획하고 최적화하는 데스크톱 애플리케이션입니다. 인터넷 연결 없이(오프라인 환경) 동작하도록 설계되었습니다.

---

## 🌟 주요 기능 (Key Features)

### 1. 정밀 궤도 전파 및 패스 예측 (Pass Prediction)

- **SGP4/Skyfield 엔진 기반**: TLE 기반 고정밀 지상 궤적 및 안테나 가시 영역(AOS, LOS, Duration, Max Elevation) 계산
- **온라인 TLE 자동 수집**: CelesTrak 연동 검색 및 자동 다운로드
- **발사 분리 벡터(Separation Vector) TLE 생성**: 발사체 분리 궤도 벡터로부터 가상 TLE 자동 모델링
- **⚡ 벡터화된 궤도 전파**: 궤도 회차 번호 계산을 numpy 벡터 연산으로 처리하여, 기존 대비 최대 **9배 이상 빠른** 스케줄 계산 속도 제공 (1주일 분석 기준 약 18초 → 약 2초)
- **📊 실시간 진행률 표시**: 계산 중인 위성 수 / 전체 위성 수를 진행 표시줄로 실시간 확인 가능

### 2. 지상국 안테나 자원 관리 (Ground Station Antenna Resource Management)

- **다중 안테나 동시성(Multi-Antenna Concurrency)**: 지상국별로 동시 수신(RX) 가능 안테나 대수와 동시 커맨딩(TX) 가능 채널 수를 개별 설정하고, 스케줄링 알고리즘이 이를 정확히 반영
- **🔧 안테나 점검 일정(Maintenance Schedule)**: 특정 기간에만 안테나 대수가 일시적으로 줄어드는 상황(점검·고장 등)을 등록하면, 그 시간대에만 정확히 반영되는 시간대별 용량 관리
- **TX 사전 경고**: 패스 예측 단계에서부터 "이 시간대는 TX 채널이 부족할 수 있다"는 경고를 미리 확인 가능
- **🛰️ 지상국 관리 UI**: 텍스트 파일을 직접 편집하지 않고, 화면에서 지상국 추가/수정/삭제 및 안테나 대수 설정 가능

### 3. 복합 교대 근무 및 지상국 예외 관리 (Shift & Exemption Rules)

- **기간별 일일 교대 근무(Recurring Shifts)**: 시작일~종료일 구간 내 지정 시간대만 패스 추출
- **지상국별 개별 근무시간 규칙**: 규칙마다 적용 대상 지상국을 지정할 수 있어, 지상국마다 서로 다른 근무 패턴 설정 가능
- **자정 넘김(Overnight +1d) 지원**: 23:00 ~ 익일 07:00 등 날짜를 넘어가는 야간 근무 완벽 판정
- **요일 마스크(Day-of-Week Mask)**: 특정 Phase별 평일/주말 선택 적용
- **24/7 지상국 예외(Exemption)**: 무인 자동화/해외 네트워크 지상국은 근무 시간 제약 없이 24시간 가동
- **차점자 자동 승격**: 근무시간 밖 후보 때문에 그 시간대가 통째로 비는 대신, 근무시간 안의 차점자가 자동으로 슬롯을 차지

### 4. 지능형 자원 할당 및 충돌 해결 (Fairness & Auto-Resolve)

- **군집 위성 균등 분배(Equalization)**: 특정 위성의 독점을 방지하고 위성별 Min/Max 패스 횟수 보장
- **가중치 기반 자동 충돌 해결(Weighted Solver)**: 안테나 중복 패스 발생 시 가중치(우선순위, 패스 시간, 최대 고도각, 균등성)를 기반으로 최적화
- **다중 안테나 인지 경합 해결**: 안테나가 여러 대인 지상국에서는 경합 없이 동시 수용하고, 용량을 초과할 때만 우선순위 경합
- **TX 자원 추적 및 스왑**: 룩어헤드/스탠바이/Cross-Satellite Swap 전략이 지상국의 실제 TX 채널 여유를 정확히 추적하여 배정
- **수동 스케줄 조정**: 타임라인 테이블 및 잠금 기능을 통한 개별 패스 선택/해제 (안테나 용량 초과 시 경고 표시)

### 5. 시각화 및 분석 리포트 (Visualization & Analytics)

- **Gantt Chart 타임라인**: 지상국/위성별 교신 타임라인 시각화, 다중 안테나 지상국은 서브레인으로 겹치지 않게 표시
- **2D 궤도 맵(Orbit Map)**: Cartopy 기반 세계 지도 위성 지하고도 및 안테나 커버리지 뷰
- **스케줄 분석 대시보드(Analytics Dashboard)**: 일일 패스 분포, 안테나 점유율(점검 일정 반영한 정확한 가동률), 위성별 누적 통신 시간 차트 제공
- **실시간 카운트다운**: 다음 교신(AOS) 및 현재 진행 중인 패스 잔여 시간 표시

### 6. 다채로운 내보내기 & DRM 호환 (Export & Interoperability)

- **컬러링 Excel (.xlsx)**: 지상국/위성별 테마 색상 및 충돌 하이라이트 반영, 지상국 용량 정보 별도 시트 포함
- **CSV / YAML 지원**: 외부 지상국 제어 시스템 및 자동화 툴 연동 (YAML은 계산 당시의 지상국 용량 스냅샷도 함께 기록)
- **외부 스케줄 Import 검증**: 불러온 스케줄이 현재 설정된 지상국 용량을 초과하는지 자동 검사 및 경고
- **사내 보안 DRM 우회 로더**: 사내 암호화 엑셀을 위한 `xlwings` 백엔드 지원

---

## 📂 프로젝트 구조 (Architecture)

```text
LEOP_Pass_Scheduler/
├── core/                            # 핵심 비즈니스 로직 및 알고리즘
│   ├── scheduler.py                 # TLE/지상국 파싱, SGP4 패스 계산, 다중 안테나·시간대별 용량 배정 엔진
│   ├── conflict_resolver.py         # 다목적 가중치 기반 충돌 해결 엔진 (다중 안테나 인지)
│   ├── schedule_processor.py        # 충돌 그룹 식별 및 스케줄 정렬
│   ├── config_manager.py            # UI 상태 및 규칙 config.json 관리
│   ├── timezone_manager.py          # UTC / KST 타임존 변환
│   ├── color_manager.py             # 지상국/위성 고유 컬러 매핑
│   ├── tle_fetcher.py               # CelesTrak API 통신
│   └── exporter.py                  # Excel, CSV, YAML 내보내기 (지상국 용량 정보 포함)
├── ui/                               # PyQt6 기반 사용자 인터페이스
│   ├── tab1_pass_predict.py         # 메인 스케줄링 대시보드 (진행률 표시, TX 사전 경고 포함)
│   ├── dialog_shift_rules.py        # 교대 근무, 지상국별 적용 규칙, 24/7 예외 설정 다이얼로그
│   ├── dialog_conflict_solver.py    # 가중치 기반 충돌 해결 전략 설정 (지상국 용량 표시 포함)
│   ├── dialog_equalize_rules.py     # 위성별 균등 분배 타겟 설정
│   ├── dialog_gantt_chart.py        # 간트 차트 시각화 (다중 안테나 서브레인 지원)
│   ├── dialog_orbit_map.py          # 2D 궤도 맵 뷰어
│   ├── dialog_analytics.py          # 통계 및 분석 리포트 대시보드 (점검 일정 반영 가동률)
│   ├── dialog_station_manager.py    # 지상국 추가/수정/삭제 및 RX/TX 안테나 대수 관리 UI
│   ├── dialog_antenna_overrides.py  # 안테나 점검 일정(시간대별 용량 변경) 관리 UI
│   └── tab1_file_loader.py          # 외부 스케줄 파일(DRM 대응) 로더 및 용량 검증
├── tle/                              # TLE 궤도 데이터 폴더 (.tle, .txt)
├── stations/                         # 지상국 좌표 및 파라미터(RX/TX 용량 포함) 정의 폴더
├── plans/                            # 내부 계획 저장 폴더
├── pass_output/                      # 스케줄 결과물 내보내기 기본 경로
├── assets/                           # 앱 아이콘 및 정적 리소스
├── main.py                          # 메인 애플리케이션 진입점
├── build.py                         # PyInstaller 배포 빌드 스크립트
└── requirements.txt                  # 의존성 패키지 목록
```

---

## 🧪 테스트

프로젝트 루트에서 다음 명령으로 핵심 로직 회귀 테스트를 실행할 수 있습니다.

```bash
python run_constraints_tests.py
```

---

## 📦 빌드 (Windows .exe)

```bash
pip install -r requirements.txt
pip install pyinstaller
python build.py
```

빌드 결과물은 `dist/LEOP_Pass_Scheduler/` 폴더에 생성됩니다 (폴더 전체가 필요합니다).

---

## 📄 License

MIT License
