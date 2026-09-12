from core.scheduler import resolve_station_group_with_capacity


def resolve_conflicts(passes, weights=None, sat_priorities=None, 
                      equalize_target_sats=None, min_pass_targets=None, max_pass_targets=None,
                      excluded_stations=None, station_capacity=None, is_pass_eligible=None):
    """
    Weighted Multi-Criteria Conflict Resolution Engine
    - excluded_stations: list or set of station names to exclude from auto-resolution
    - station_capacity: {station_name: rx_capacity} 형태의 딕셔너리.
      지상국별 동시 처리(안테나) 가능 개수를 의미하며, 지정하지 않은 지상국은 기본값 1로 취급합니다.
      💡 [안테나 점검 일정 지원] 값은 정수를 그대로 줘도 되고(상시 고정 용량, 기존과 동일),
      datetime 하나를 받아 그 시점의 용량(int)을 반환하는 콜러블을 줘도 됩니다
      (core.scheduler.build_capacity_lookup으로 만든 함수를 그대로 넣으면 됩니다).
      💡 이 값은 core/scheduler.py의 calculate_passes()가 최초 계산할 때 사용한 것과
         동일한 값을 넘겨줘야, 사용자가 "Auto Resolve"를 나중에 다시 눌러도
         안테나 용량 제약이 일관되게 유지됩니다.
    - is_pass_eligible: 💡 [기능2 후속 개선] pass dict 1개를 받아 "이 패스가 애초에 선택 후보가
      될 자격이 있는가"를 반환하는 콜백 (예: 근무시간 체크). None이면 전부 자격 있음으로 간주합니다.
      calculate_passes()가 최초 계산할 때 넘긴 것과 동일한 함수를 넘겨줘야, 사용자가 "Auto Resolve"를
      다시 눌러도 근무시간 밖 패스가 실수로 재선정되지 않습니다.
    """
    if not passes:
        return passes

    station_capacity = station_capacity or {}

    weights = weights or {
        'use_fairness': True, 'weight_fairness': 50,
        'use_elevation': True, 'weight_elevation': 25,
        'use_duration': False, 'weight_duration': 0,
        'use_priority': False, 'weight_priority': 0
    }
    sat_priorities = sat_priorities or {}
    min_pass_targets = min_pass_targets or {}
    max_pass_targets = max_pass_targets or {}
    excluded_set = set(excluded_stations or [])

    sat_selected_counts = {}
    for p in passes:
        sat_clean = p['satellite'].split('(')[0].strip()
        if sat_clean not in sat_selected_counts:
            sat_selected_counts[sat_clean] = 0

    groups = {}
    non_conflict_indices = []

    for idx, p in enumerate(passes):
        st_name = str(p.get('station', 'UNKNOWN')).split('(')[0].strip()
        
        # 💡 제외 대상 지상국인 경우 충돌 분배 연산에서 배제하고 체크 해제
        if st_name in excluded_set:
            passes[idx]['selected'] = False
            continue

        grp_id = p.get('conflict_group')
        if grp_id is not None:
            key = (st_name, grp_id)
            if key not in groups:
                groups[key] = []
            groups[key].append((idx, p))
        else:
            non_conflict_indices.append(idx)

    # 비충돌 패스 기본 선택 처리
    #
    # 💡 [버그 수정 + 기능2 후속 개선] 예전에는 이 루프가 무조건 selected=True로 되돌렸습니다.
    #    이러면 (1) calculate_passes()가 애초에 "Capped(상한 초과)"로 표시해둔 단독 패스나
    #    (2) "Shift Hours Blocked(근무시간 밖)"로 표시해둔 패스까지 Auto Resolve를 누르는 순간
    #    전부 부활해버리는 문제가 있었습니다. 이제는 자격(eligible)과 상한(max_pass_targets)을
    #    다시 한번 확인한 뒤에만 선택합니다.
    for idx in non_conflict_indices:
        p = passes[idx]
        sat_clean = p['satellite'].split('(')[0].strip()
        curr_count = sat_selected_counts.get(sat_clean, 0)
        max_limit = max_pass_targets.get(sat_clean, 0)

        if is_pass_eligible is not None and not is_pass_eligible(p):
            p['selected'] = False
            p['status'] = "Shift Hours Blocked"
            continue

        if max_limit > 0 and curr_count >= max_limit:
            p['selected'] = False
            p['status'] = f"Capped (Max {max_limit})"
            continue

        p['selected'] = True
        sat_selected_counts[sat_clean] = curr_count + 1

    sorted_group_keys = sorted(
        groups.keys(), 
        key=lambda k: min(item[1]['aos'] for item in groups[k])
    )

    for key in sorted_group_keys:
        st_name_of_group, _grp_id = key
        group_items = groups[key]

        # 💡 [기능2 후속 개선] 여기서도 경합 시작 전에 자격 없는 후보를 먼저 걸러냅니다.
        #    (보통은 scheduler.py 단계에서 이미 걸러져 conflict_group=None으로 빠지지만,
        #     외부에서 불러온 스케줄 등 다른 경로로 들어온 데이터에 대비한 방어 코드입니다)
        if is_pass_eligible is not None:
            ineligible_items = [(idx, p) for idx, p in group_items if not is_pass_eligible(p)]
            group_items = [(idx, p) for idx, p in group_items if is_pass_eligible(p)]
            for idx, p in ineligible_items:
                passes[idx]['selected'] = False
                passes[idx]['status'] = "Shift Hours Blocked"

        if not group_items:
            continue  # 이 그룹 전체가 자격 미달이면 더 처리할 것 없음

        # 💡 이 지상국의 동시 처리(안테나) 가능 개수. 지정 안 된 지상국은 기본값 1.
        #    값이 정수면 "그 값을 항상 돌려주는 함수"로 감싸서, 아래 로직은 항상 콜러블만
        #    다루면 되도록 통일합니다 (시간대별 용량이든 고정 용량이든 동일하게 처리).
        raw_capacity = station_capacity.get(st_name_of_group, 1)
        capacity_fn = raw_capacity if callable(raw_capacity) else (lambda dt, v=raw_capacity: v)

        # 그룹 내 최대 고도각 및 최대 패스 시간 계산 (정규화용 - 그룹 전체 기준으로 한 번만 계산)
        max_el_in_grp = max([float(item[1].get('max_el', 1)) for item in group_items] or [1.0])
        max_dur_in_grp = max([float(item[1].get('duration', 1)) for item in group_items] or [1.0])

        def _score_fn(item):
            """(idx, pass_dict) 튜플 하나를 받아 '작을수록 우선순위가 높은' 점수를 반환.
            기존 로직은 '클수록 좋음(total_score)'이었으므로, 정렬 규칙 통일을 위해 부호를 뒤집습니다."""
            idx, p = item
            sat_clean = p['satellite'].split('(')[0].strip()
            curr_count = sat_selected_counts.get(sat_clean, 0)
            max_limit = max_pass_targets.get(sat_clean, 0)
            min_target = min_pass_targets.get(sat_clean, 1)

            # Max Target 상한 초과 페널티 (hard_reject_fn이 이미 이 경우를 걸러내지만, 방어적으로 이중 체크)
            is_over_max = (max_limit > 0 and curr_count >= max_limit)
            hard_penalty = -10000.0 if is_over_max else 0.0

            total_score = hard_penalty

            # 1. Fairness 점수
            if weights.get('use_fairness', False):
                w_fair = weights.get('weight_fairness', 50)
                under_min_bonus = 50.0 if curr_count < min_target else 0.0
                target_bonus = 20.0 if (equalize_target_sats and sat_clean in equalize_target_sats) else 0.0
                fairness_component = (-curr_count * 15.0) + under_min_bonus + target_bonus
                total_score += (fairness_component * (w_fair / 10.0))

            # 2. Max Elevation 점수 (0~100 정규화 후 가중치 반영)
            if weights.get('use_elevation', False):
                w_el = weights.get('weight_elevation', 25)
                el_val = float(p.get('max_el', 0))
                el_norm = (el_val / max(max_el_in_grp, 1.0)) * 100.0
                total_score += (el_norm * (w_el / 100.0))

            # 3. Pass Duration 점수 (0~100 정규화 후 가중치 반영)
            if weights.get('use_duration', False):
                w_dur = weights.get('weight_duration', 25)
                dur_val = float(p.get('duration', 0))
                dur_norm = (dur_val / max(max_dur_in_grp, 1.0)) * 100.0
                total_score += (dur_norm * (w_dur / 100.0))

            # 4. Satellite Priority 점수
            if weights.get('use_priority', False):
                w_prio = weights.get('weight_priority', 50)
                rank = sat_priorities.get(sat_clean, 99)
                prio_norm = max(0.0, 100.0 - (rank - 1) * 20.0)
                total_score += (prio_norm * (w_prio / 100.0))

            # total_score는 "클수록 좋음"이므로, resolve_station_group_with_capacity가
            # 기대하는 "작을수록 좋음" 규칙에 맞춰 부호를 뒤집어 반환합니다.
            return -total_score

        # 💡 [버그 수정] pass dict -> idx 매핑 (score_fn/hard_reject_fn이 pass dict만 받으므로 필요)
        item_by_pass_id = {id(p): idx for idx, p in group_items}

        def _score_fn_for_pass(p):
            idx = item_by_pass_id[id(p)]
            return _score_fn((idx, p))

        def _hard_reject(p):
            # 💡 [버그 수정] 슬롯이 남아돌아도, 이미 상한을 넘긴 위성은 절대 수용하지 않습니다.
            #    (예전에는 그룹 크기<=capacity일 때만 이 체크를 했고, 실제 경합 시 이벤트
            #     스윕에서 "빈 슬롯"으로 처리되는 첫 후보는 이 체크를 안 거치는 구멍이 있었습니다)
            sat_clean = p['satellite'].split('(')[0].strip()
            curr_count = sat_selected_counts.get(sat_clean, 0)
            max_limit = max_pass_targets.get(sat_clean, 0)
            return max_limit > 0 and curr_count >= max_limit

        def _on_admit(p):
            sat_clean = p['satellite'].split('(')[0].strip()
            sat_selected_counts[sat_clean] = sat_selected_counts.get(sat_clean, 0) + 1

        def _on_evict(p):
            sat_clean = p['satellite'].split('(')[0].strip()
            sat_selected_counts[sat_clean] = max(0, sat_selected_counts.get(sat_clean, 0) - 1)

        group_pass_dicts = [p for _idx, p in group_items]
        resolve_station_group_with_capacity(
            group_pass_dicts, capacity_fn, _score_fn_for_pass,
            on_admit=_on_admit, on_evict=_on_evict, hard_reject_fn=_hard_reject
        )
        # resolve_station_group_with_capacity가 각 pass dict의 'selected'를 직접 갱신했으므로,
        # passes 리스트 내 원본도 이미 갱신되어 있음 (동일 dict 참조이기 때문에 별도 반영 불필요)

    return passes