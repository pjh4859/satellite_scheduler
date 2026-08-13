def resolve_conflicts(passes, rule="EQUAL_PRIORITY", sat_priorities=None):
    """
    passes: main_app.calculated_passes (list of dict)
    rule: 
      - "FAIR_EQUAL": Equalize 미달 및 누적 패스 수 적은 위성 우선 (동시발사 강력 추천!)
      - "MAX_EL": 최대 고도각(Max Elevation) 우선
      - "DURATION": 교신 시간(Duration) 우선
      - "SAT_PRIORITY": 위성 우선순위 지정 방식 우선
    sat_priorities: dict {"SAT_A": 1, "SAT_B": 2, ...} (숫자가 작을수록 높은 우선순위)
    """
    if not passes:
        return passes

    if sat_priorities is None:
        sat_priorities = {}

    # 1. conflict_group별로 패스들을 묶음
    groups = {}
    for idx, p in enumerate(passes):
        grp_id = p.get('conflict_group', None)
        st_name = p.get('station', '')
        
        if grp_id is not None:
            key = (st_name, grp_id)
            if key not in groups:
                groups[key] = []
            groups[key].append((idx, p))
        else:
            # 충돌 없는 패스는 기본 선택 상태 유지
            passes[idx]['selected'] = True

    # 위성별 실시간 선택 누적 카운트 추적용
    sat_selected_counts = {}

    # 시간순으로 충돌 그룹 정렬
    sorted_group_keys = sorted(groups.keys(), key=lambda k: groups[k][0][1]['aos'])

    for key in sorted_group_keys:
        group_passes = groups[key] # [(orig_idx, pass_dict), ...]
        
        # 기본적으로 그룹 내 모든 패스를 Unselect 처리
        for orig_idx, p in group_passes:
            passes[orig_idx]['selected'] = False

        winner_idx = None

        # ----------------------------------------------------------------------
        # 🎯 규칙 1: FAIR_EQUAL (동시 발사 맞춤형: 누적 균등 최우선)
        # ----------------------------------------------------------------------
        if rule == "FAIR_EQUAL":
            def fair_sort_key(item):
                orig_idx, p = item
                sat_clean = p['satellite'].split('(')[0].strip()
                sel_count = sat_selected_counts.get(sat_clean, 0)
                max_el = float(p.get('max_el', 0))
                dur = float(p.get('duration', 0))
                # 누적 선택 횟수가 적은 위성 우선 (-sel_count), 그 다음 Max El, Duration
                return (sel_count, -max_el, -dur)

            sorted_candidates = sorted(group_passes, key=fair_sort_key)
            winner_idx = sorted_candidates[0][0]

        # ----------------------------------------------------------------------
        # 🎯 규칙 2: MAX_EL (최대 고도각 우선)
        # ----------------------------------------------------------------------
        elif rule == "MAX_EL":
            sorted_candidates = sorted(group_passes, key=lambda x: float(x[1].get('max_el', 0)), reverse=True)
            winner_idx = sorted_candidates[0][0]

        # ----------------------------------------------------------------------
        # 🎯 규칙 3: DURATION (교신 시간 우선)
        # ----------------------------------------------------------------------
        elif rule == "DURATION":
            sorted_candidates = sorted(group_passes, key=lambda x: float(x[1].get('duration', 0)), reverse=True)
            winner_idx = sorted_candidates[0][0]

        # ----------------------------------------------------------------------
        # 🎯 규칙 4: SAT_PRIORITY (위성 우선순위)
        # ----------------------------------------------------------------------
        elif rule == "SAT_PRIORITY":
            def prio_sort_key(item):
                orig_idx, p = item
                sat_clean = p['satellite'].split('(')[0].strip()
                prio = sat_priorities.get(sat_clean, 999)
                max_el = float(p.get('max_el', 0))
                return (prio, -max_el)

            sorted_candidates = sorted(group_passes, key=prio_sort_key)
            winner_idx = sorted_candidates[0][0]

        # 승자 패스 선택 확정 및 누적 카운트 증가
        if winner_idx is not None:
            passes[winner_idx]['selected'] = True
            win_sat = passes[winner_idx]['satellite'].split('(')[0].strip()
            sat_selected_counts[win_sat] = sat_selected_counts.get(win_sat, 0) + 1

    return passes