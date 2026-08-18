# 🛰️ LEOP Multi-Satellite Pass Scheduler

> **Advanced Multi-Satellite & Ground Station Pass Prediction, Conflict Resolution, and Mission Scheduling System**

![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![PyQt6](https://img.shields.io/badge/GUI-PyQt6-green.svg)
![Astrodynamics](https://img.shields.io/badge/Engine-Skyfield-orange.svg)
![License](https://img.shields.io/badge/License-MIT-lightgrey.svg)

**LEOP Multi-Satellite Pass Scheduler**는 발사 및 초기 궤도 운용(LEOP) 및 군집 위성(Swarm/Constellation) 운용 시 지상국 안테나 자원 할당과 위성 교신 일정을 자동으로 계획하고 최적화하는 데스크톱 애플리케이션입니다.

---

## 🌟 주요 기능 (Key Features)

### 1. 정밀 궤도 전파 및 패스 예측 (Pass Prediction)

- **SGP4/Skyfield 엔진 기반**: TLE 기반 고정밀 지상 궤적 및 안테나 가시 영역(AOS, LOS, Duration, Max Elevation) 계산[cite: 1, 2]
- **온라인 TLE 자동 수집**: CelesTrak 연동 검색 및 자동 다운로드
- **발사 분리 벡터(Separation Vector) TLE 생성**: 발사체 분리 궤도 벡터로부터 가상 TLE 자동 모델링[cite: 1]

### 2. 복합 교대 근무 및 지상국 예외 관리 (Shift & Exemption Rules)

- **기간별 일일 교대 근무(Recurring Shifts)**: 시작일~종료일 구간 내 지정 시간대만 패스 추출
- **자정 넘김(Overnight +1d) 지원**: 23:00 ~ 익일 07:00 등 날짜를 넘어가는 야간 근무 완벽 판정
- **요일 마스크(Day-of-Week Mask)**: 특정 Phase별 평일/주말 선택 적용
- **24/7 지상국 예외(Exemption)**: 무인 자동화/해외 네트워크 지상국은 근무 시간 제약 없이 24시간 가동

### 3. 지능형 자원 할당 및 충돌 해결 (Fairness & Auto-Resolve)

- **군집 위성 균등 분배(Equalization)**: 특정 위성의 독점을 방지하고 위성별 Min/Max 패스 횟수 보장[cite: 1]
- **가중치 기반 자동 충돌 해결(Weighted Solver)**: 안테나 중복 패스 발생 시 가중치(우선순위, 패스 시간, 최대 고도각, 균등성)를 기반으로 최적화[cite: 1]
- **수동 스케줄 조정**: 타임라인 테이블 및 잠금 기능을 통한 개별 패스 선택/해제[cite: 1]

### 4. 시각화 및 분석 리포트 (Visualization & Analytics)

- **Gantt Chart 타임라인**: 지상국/위성별 교신 타임라인 시각화[cite: 1]
- **2D 궤도 맵(Orbit Map)**: Cartopy 기반 세계 지도 위성 지하고도 및 안테나 커버리지 뷰[cite: 1, 2]
- **스케줄 분석 대시보드(Analytics Dashboard)**: 일일 패스 분포, 안테나 점유율, 위성별 누적 통신 시간 차트 제공[cite: 1]
- **실시간 카운트다운**: 다음 교신(AOS) 및 현재 진행 중인 패스 잔여 시간 표시[cite: 1]

### 5. 다채로운 내보내기 & DRM 호환 (Export & Interoperability)

- **컬러링 Excel (.xlsx)**: 지상국/위성별 테마 색상 및 충돌 하이라이트 반영[cite: 1]
- **CSV / YAML 지원**: 외부 지상국 제어 시스템 및 자동화 툴 연동[cite: 1]
- **사내 보안 DRM 우회 로더**: 사내 암호화 엑셀을 위한 `xlwings` 백엔드 지원[cite: 1, 2]

---

## 📂 프로젝트 구조 (Architecture)

```text
LEOP_Pass_Scheduler/
├── core/                       # 핵심 비즈니스 로직 및 알고리즘
│   ├── scheduler.py            # TLE/지상국 파싱 및 SGP4 패스 계산[cite: 1]
│   ├── conflict_resolver.py    # 다목적 가중치 기반 충돌 해결 엔진[cite: 1]
│   ├── schedule_processor.py   # 충돌 그룹 식별 및 스케줄 정렬[cite: 1]
│   ├── config_manager.py       # UI 상태 및 규칙 config.json 관리[cite: 1]
│   ├── timezone_manager.py     # UTC / KST 타임존 변환[cite: 1]
│   ├── color_manager.py        # 지상국/위성 고유 컬러 매핑[cite: 1]
│   ├── tle_fetcher.py          # CelesTrak API 통신[cite: 1]
│   └── exporter.py             # Excel, CSV, YAML 내보내기[cite: 1]
├── ui/                         # PyQt6 기반 사용자 인터페이스
│   ├── tab1_pass_predict.py    # 메인 스케줄링 대시보드[cite: 1]
│   ├── dialog_shift_rules.py   # 교대 근무 및 24/7 지상국 예외 설정 다이얼로그[cite: 1]
│   ├── dialog_conflict_solver.py # 가중치 기반 충돌 해결 전략 설정[cite: 1]
│   ├── dialog_equalize_rules.py  # 위성별 균등 분배 타겟 설정[cite: 1]
│   ├── dialog_gantt_chart.py   # 간트 차트 시각화[cite: 1]
│   ├── dialog_orbit_map.py     # 2D 궤도 맵 뷰어[cite: 1]
│   ├── dialog_analytics.py     # 통계 및 분석 리포트 대시보드[cite: 1]
│   └── tab1_file_loader.py     # 외부 스케줄 파일(DRM 대응) 로더[cite: 1]
├── tle/                        # TLE 궤도 데이터 폴더 (.tle, .txt)[cite: 1, 2]
├── stations/                   # 지상국 좌표 및 파라미터 정의 폴더[cite: 1, 2]
├── plans/                      # 내부 계획 저장 폴더[cite: 1, 2]
├── pass_output/                # 스케줄 결과물 내보내기 기본 경로[cite: 1, 2]
├── assets/                     # 앱 아이콘 및 정적 리소스
├── main.py                     # 메인 애플리케이션 진입점
├── build.py                    # PyInstaller 배포 빌드 스크립트[cite: 2]
└── requirements.txt            # 의존성 패키지 목록
```
