# 🔧 기술 설명서: 안테나 자원 관리 시스템 (v1.1.0)

이 문서는 v1.1.0에서 새로 추가된 "지상국 안테나 자원 관리" 시스템의 내부 구조를 설명합니다.
사용법이 아니라 **왜 이렇게 짜여 있는지, 다음에 수정하려면 어디를 봐야 하는지**를 위한 문서입니다.

---

## 1. 핵심 개념: 용량(Capacity)은 "숫자"가 아니라 "함수"다

기존(v1.0.7까지)에는 지상국의 동시 처리 가능 개수가 정수 하나(`rx_capacity`, `tx_capacity`)였습니다.
v1.1.0부터는 "점검 일정"으로 인해 이 값이 **시간에 따라 달라질 수 있게** 되면서, 내부적으로는
"정수"가 아니라 **"datetime을 받아서 그 시점의 유효 용량(int)을 돌려주는 함수"**로 다루는 곳이 많습니다.

- `core/scheduler.py :: build_capacity_lookup(base_capacity, overrides, value_key)`
  기본값 + 오버라이드 리스트를 받아서 이런 함수를 만들어주는 팩토리 함수입니다.
  오버라이드가 없으면 그냥 항상 `base_capacity`만 반환하는 함수가 나오므로, 이 개념을 몰라도
  기존 코드는 100% 동일하게 동작합니다 (하위 호환의 핵심).

- 어디서 이 함수를 만드는지 헷갈리면: `station_data`(지상국 튜플 리스트)와
  `antenna_overrides`(점검 일정 리스트, 아래 2번 참고)를 같이 갖고 있는 곳이면 어디서든
  `build_capacity_lookup(base, [ov for ov in overrides if ov['station']==name], 'rx_capacity')`
  형태로 만들 수 있습니다.

---

## 2. 데이터 모델: `antenna_overrides`

```python
{
    "station": "Daejeon",           # 지상국 이름 (station_data의 이름과 문자열이 정확히 일치해야 함)
    "start_dt": datetime(...),      # 시작 시각 (naive 또는 aware 둘 다 허용 - 내부에서 정규화함)
    "end_dt": datetime(...),        # 종료 시각
    "rx_capacity": 1,               # 이 기간의 RX 용량. None이면 "RX는 안 건드림"
    "tx_capacity": None,            # 이 기간의 TX 용량. None이면 "TX는 안 건드림"
    "reason": "안테나 1대 점검"      # 사람이 보는 용도, 로직에는 안 씀
}
```

- **저장 위치**: `main_app.antenna_overrides` (리스트). `main_window.py`의 `SatelliteSchedulerApp.__init__`에서
  빈 리스트로 초기화됩니다. Tab1(RX)과 Tab3(TX) 양쪽이 다 참조해야 해서, 특정 탭 소유가 아니라
  이 공유 허브(main_app)에 둡니다. **다른 상태(예: `shift_hours_rules`)는 Tab1 전용이라 `self`에
  있는데, `antenna_overrides`만 유독 `main_app`에 있는 이유가 이것입니다.**
- **저장/불러오기**: `ui/tab1_pass_predict.py`의 `save_settings()` / `restore_settings()`가
  `config.json`에 직렬화합니다 (datetime은 ISO 문자열로 변환 후 저장, 불러올 때 다시 파싱).
- **편집 UI**: `ui/dialog_antenna_overrides.py` (`AntennaOverrideDialog`)

---

## 3. 핵심 알고리즘: `resolve_station_group_with_capacity()`

`core/scheduler.py`에 있는 이 함수가 M1(안테나 동시성)부터 지금까지 계속 확장되어 온 핵심 엔진입니다.

**동작 원리 (이벤트 스윕)**
1. 같은 지상국에서 시간이 겹치는 패스들의 AOS(시작)/LOS(종료) 이벤트를 시간순으로 정렬
2. 슬롯이 비어있으면 즉시 수용, 꽉 차 있으면 `score_fn`으로 가장 우선순위 낮은 점유자와 비교해서 교체 여부 결정
3. `capacity` 인자는 정수를 줘도 되고(고정 용량), `build_capacity_lookup()`으로 만든 함수를 줘도 됩니다(시간대별 용량) — `callable(capacity)`로 내부에서 자동 분기합니다.

**⚠️ hard_reject_fn을 꼭 이해하고 넘어가야 하는 이유**

이 함수는 원래 "슬롯이 비어있으면 무조건 즉시 수용"했습니다. 그런데 이러면 이미 Max Pass 상한을
넘긴 위성이라도, 마침 슬롯이 비어있으면 점수 비교 없이 그냥 선택되어버리는 버그가 있었습니다
(실제로 v1.1.0 개발 중 발견해서 고침). `hard_reject_fn(p) -> bool`을 넘기면, 슬롯 여유와
무관하게 이 검사를 **가장 먼저** 통과시킵니다. **앞으로 "이 조건이면 절대 선택되면 안 된다"는
새로운 규칙을 추가할 때는 score_fn 안에 페널티 점수로 녹이지 말고, hard_reject_fn으로 넣으세요.**
그래야 이 버그가 재발하지 않습니다.

이 함수는 `core/conflict_resolver.py`(수동 Auto Resolve)에서도 그대로 재사용됩니다.
**새 자원 제약을 추가할 때 절대 두 곳에 따로 구현하지 마세요** — 여기 한 곳만 고치면 양쪽에
자동으로 반영되도록 설계되어 있습니다.

---

## 4. Tab3의 TX 자원 추적

`ui/tab3_final_scheduler.py`의 `click_generate_schedule()`은 커맨딩(CMD/BOTH) 요구 작업을
배정할 때마다 `tx_occupied_intervals` 딕셔너리(`{station: [(aos, los), ...]}`)에 그 시간 구간을
기록해두고, 새 작업을 배정하기 전에 `_count_tx_overlaps()`로 이미 몇 개가 겹치는지 확인합니다.

**주의할 점 (실수하기 쉬운 지점)**
- Tab3는 패스의 aos/los를 **문자열**(YAML에서 불러온 ISO 8601 형식)로 다룹니다. 반면
  `antenna_overrides`의 `start_dt`/`end_dt`는 **실제 datetime 객체**입니다. 이 둘을 그대로
  비교하면 `TypeError`가 납니다 (v1.1.0 개발 중 실제로 겪은 버그). `_parse_iso_dt()` 헬퍼로
  항상 먼저 datetime으로 변환한 뒤 `capacity_fn()`에 넘기세요.
- Cross-Satellite Swap(전략 3)에서 TX 용량을 확인할 때는 **현재 처리 중인 패스(p)가 아니라
  스왑 대상 패스(other_p) 자신의 시각 기준**으로 확인해야 합니다. 같은 지상국이어도 시각이
  다르면 유효 용량이 다를 수 있기 때문입니다 (점검 일정 도입 이후 특히 중요해짐).
- 최종 표에 표시되는 시각/기간/고도각(`assigned_aos_str` 등)도 스왑이 성공하면 반드시
  `other_p` 자신의 값으로 덮어써야 합니다 (예전엔 원래 패스의 값을 그대로 보여주는 버그가 있었음).

---

## 5. 정확도가 중요한 통계/경고 계산

아래 세 곳은 전부 "동시 겹침이 용량을 초과하는지"를 계산해야 하는데, 예전에는 각자 따로
구현되어 있어서 그중 두 곳이 점검 일정을 반영 못하는 버그가 있었습니다. 지금은 공용 함수로
통일되어 있으니, **비슷한 계산이 또 필요하면 새로 만들지 말고 이 두 함수를 재사용하세요.**

- `find_capacity_overflow(passes_for_one_station, capacity_fn)` → `(peak_concurrent, worst_excess)`
  TX 사전 경고 배너(`update_tx_warning_banner`), Import 검증(`_validate_import_capacity`)에서 사용.
- `compute_time_weighted_avg_capacity(base_capacity, overrides, value_key, window_start, window_end)`
  분석 기간에 점검 일정이 섞여 있을 때 "시간 가중 평균 용량"을 정확히 계산. Analytics 가동률(%) 계산에서 사용.

---

## 6. 성능: 궤도 전파 벡터화

`find_orbit_starts_at_north_pole()`이 예전엔 60초 간격으로 Python 루프를 돌며 스카이필드를
한 시점씩 개별 호출했습니다 (분석 기간이 길수록 수천~수만 번). 지금은 `ts.from_datetimes()`로
전체 시간 배열을 한 번에 만들어 `satellite.at()`을 딱 1번만 호출합니다 (numpy 벡터 연산).

- 여러 위성이 있을 때 이 시간 배열 자체는 위성과 무관하게 동일하므로,
  `build_orbit_sampling_times()`로 한 번만 만들어서 `calculate_passes()`의 위성 루프 전체에서
  재사용합니다. **위성마다 이 배열을 새로 만들면 안 됩니다** (성능 이점이 대부분 사라집니다).
- 진행률 콜백(`progress_callback`)은 위성 하나(궤도 전파 + 모든 지상국 패스 탐색)가 끝날 때마다
  호출됩니다. 콜백 안에서 예외가 나도 실제 계산에는 영향 없도록 try/except로 감싸져 있습니다.

---

## 7. 테스트

`test_*.py` 파일들이 이번 작업 과정에서 하나씩 쌓인 회귀 테스트입니다. 저장소에는 기본적으로
포함하지 않도록 `.gitignore`에 넣었지만(용량 문제 아니라 "결과 검증용 스크립트"라는 성격 때문),
**삭제하지 말고 별도로 보관하시길 권장**합니다 — 다음에 이 영역을 다시 수정할 때 회귀 여부를
바로 확인할 수 있는 유일한 방법입니다. `tests/` 폴더를 새로 만들어서 옮겨두고, `.gitignore`에서
그 폴더만 제외하는 것도 좋은 방법입니다.
