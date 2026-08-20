def resolve_conflicts(passes, weights=None, sat_priorities=None, 
                      equalize_target_sats=None, min_pass_targets=None, max_pass_targets=None,
                      excluded_stations=None):
    """
    Weighted Multi-Criteria Conflict Resolution Engine
    - excluded_stations: list or set of station names to exclude from auto-resolution
    """
    if not passes:
        return passes

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
    for idx in non_conflict_indices:
        passes[idx]['selected'] = True
        sat_clean = passes[idx]['satellite'].split('(')[0].strip()
        sat_selected_counts[sat_clean] += 1

    sorted_group_keys = sorted(
        groups.keys(), 
        key=lambda k: min(item[1]['aos'] for item in groups[k])
    )

    for key in sorted_group_keys:
        group_items = groups[key]
        best_idx = None
        best_score = -float('inf')

        # 그룹 내 최대 고도각 및 최대 패스 시간 계산 (정규화용)
        max_el_in_grp = max([float(item[1].get('max_el', 1)) for item in group_items] or [1.0])
        max_dur_in_grp = max([float(item[1].get('duration', 1)) for item in group_items] or [1.0])

        for idx, p in group_items:
            sat_clean = p['satellite'].split('(')[0].strip()
            curr_count = sat_selected_counts.get(sat_clean, 0)
            max_limit = max_pass_targets.get(sat_clean, 0)
            min_target = min_pass_targets.get(sat_clean, 1)

            # Max Target 상한 초과 페널티
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

            if total_score > best_score:
                best_score = total_score
                best_idx = idx

        for idx, p in group_items:
            if idx == best_idx:
                passes[idx]['selected'] = True
                winner_sat = passes[idx]['satellite'].split('(')[0].strip()
                sat_selected_counts[winner_sat] += 1
            else:
                passes[idx]['selected'] = False

    return passes