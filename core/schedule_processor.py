import re

def parse_conflict_group_from_status(status_str):
    """
    다양한 형태의 문자열에서 Conflict Group ID를 파싱
    매칭 예시:
      - 'Conflict (Grp 5)', 'Conflict (Grp_5)'
      - 'Conflict (G5)', 'Conflict (Group 5)'
      - 'Conflict (5)', '⚠️ Conflict (Grp 5)'
      - 'Conflict-5', 'G5', 'Grp 5'
    """
    if not status_str:
        return None

    status_str = str(status_str).strip()

    # 1. 괄호 안의 Grp / Group / G 키워드 포함 패턴 파싱
    match = re.search(r'Conflict\s*\(\s*(?:Grp|Group|G)?\s*([A-Za-z0-9_]+)\s*\)', status_str, re.IGNORECASE)
    if match:
        val = match.group(1)
        return int(val) if val.isdigit() else val

    # 2. 'Conflict 5', 'Conflict-5' 패턴 파싱
    match = re.search(r'Conflict[\s\-_]+(?:Grp|Group|G)?\s*([A-Za-z0-9_]+)', status_str, re.IGNORECASE)
    if match:
        val = match.group(1)
        return int(val) if val.isdigit() else val

    # 3. 독립적인 'Grp 5', 'G5' 패턴 파싱
    match = re.search(r'\b(?:Grp|Group|G)\s*([0-9]+)\b', status_str, re.IGNORECASE)
    if match:
        return int(match.group(1))

    return None

def assign_conflict_groups(passes):
    """
    1. 수동 지정된 Conflict Group(또는 Status 컬럼)에서 식별자를 우선 추출
    2. 그룹이 비어있는 패스는 지상국별 AOS/LOS 시간 겹침(Overlap)을 검사해 자동 할당
    """
    if not passes:
        return passes

    # Step 1: 수동 입력된 Status 문자열 파싱
    for p in passes:
        if p.get('conflict_group') is not None:
            continue

        status_str = p.get('status', '')
        parsed_grp = parse_conflict_group_from_status(status_str)
        if parsed_grp is not None:
            p['conflict_group'] = parsed_grp
            p['status'] = f"Conflict (Grp {parsed_grp})"

    # Step 2: 미할당 패스 대상 시간 겹침 자동 감지
    station_map = {}
    for p in passes:
        st = p.get('station', 'UNKNOWN')
        if st not in station_map:
            station_map[st] = []
        station_map[st].append(p)

    existing_numeric_groups = [p['conflict_group'] for p in passes if isinstance(p.get('conflict_group'), int)]
    group_counter = max(existing_numeric_groups, default=0) + 1

    for st, p_list in station_map.items():
        p_list.sort(key=lambda x: x['aos'])
        n = len(p_list)

        for i in range(n):
            for j in range(i + 1, n):
                p1 = p_list[i]
                p2 = p_list[j]

                # 시간 중복 검사
                if p1['aos'] < p2['los'] and p2['aos'] < p1['los']:
                    grp_id = p1.get('conflict_group') or p2.get('conflict_group') or group_counter
                    if grp_id == group_counter:
                        group_counter += 1

                    p1['conflict_group'] = grp_id
                    p2['conflict_group'] = grp_id
                    p1['status'] = f"Conflict (Grp {grp_id})"
                    p2['status'] = f"Conflict (Grp {grp_id})"
                else:
                    if p2['aos'] >= p1['los']:
                        break

    return passes