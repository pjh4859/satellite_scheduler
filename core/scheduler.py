import os
import sys
from datetime import datetime, timezone, timedelta
from skyfield.api import load, wgs84, EarthSatellite

# ==============================================================================
# [유틸리티] PyInstaller 번들 실행 환경 대응 리소스 경로 탐색 함수
# ==============================================================================
def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


# ==============================================================================
# [파싱] TLE 궤도 요소 파일 다중 로더
# ==============================================================================
def parse_tle_from_dir(tle_dir, selected_files=None):
    satellites = {}
    if not os.path.exists(tle_dir):
        os.makedirs(tle_dir)
        default_file = os.path.join(tle_dir, "default_sat.tle")
        with open(default_file, "w", encoding="utf-8") as f:
            f.write("1 67614U 26019A   26137.32169963  .00001371  00000-0  92367-4 0  9993\n")
            f.write("2 67614  97.4232 258.5203 0011879 301.7573  58.2497 15.08241787 16162\n")

    for filename in os.listdir(tle_dir):
        if filename.endswith(".tle") or filename.endswith(".txt"):
            if selected_files is not None and filename not in selected_files:
                continue
            file_path = os.path.join(tle_dir, filename)
            
            lines = []
            for enc in ['utf-8', 'utf-8-sig', 'cp949', 'euc-kr', 'latin-1']:
                try:
                    with open(file_path, "r", encoding=enc) as f:
                        lines = [line.strip() for line in f.readlines() if line.strip()]
                    break
                except Exception:
                    continue
                
            idx = 0
            while idx < len(lines):
                if lines[idx].startswith("1 ") and (idx + 1) < len(lines) and lines[idx+1].startswith("2 "):
                    line1 = lines[idx]
                    line2 = lines[idx+1]
                    norad_id = line1[2:7].strip()
                    
                    sat_name = None
                    if idx > 0 and not lines[idx-1].startswith("1 ") and not lines[idx-1].startswith("2 "):
                        sat_name = lines[idx-1].strip()
                    else:
                        sat_name = os.path.splitext(filename)[0].strip()
                        
                    satellites[sat_name] = {
                        'lines': (line1, line2),
                        'norad_id': norad_id,
                        'sat_name': sat_name
                    }
                    idx += 2
                else:
                    idx += 1
                    
    return satellites


# ==============================================================================
# [파싱] 지상국 설정 파일 다중 로더
# ==============================================================================
def parse_stations_from_dir(stations_dir):
    stations_list = []
    if not os.path.exists(stations_dir):
        os.makedirs(stations_dir)
        default_file = os.path.join(stations_dir, "default_stations.txt")
        with open(default_file, "w", encoding="utf-8") as f:
            f.write("# Station_Name, Latitude, Longitude, Is_Download_Capable(Y/N), Is_Command_Capable(Y/N)\n")
            f.write("Daejeon, 36.35, 127.38, Y, Y\n")
            f.write("Jeju, 33.50, 126.52, Y, N\n")
            f.write("Svalbard, 78.23, 15.49, Y, Y\n")
            f.write("King Sejong, -62.22, -58.78, N, N\n")

    for filename in os.listdir(stations_dir):
        if filename.endswith(".txt") or filename.endswith(".cfg"):
            file_path = os.path.join(stations_dir, filename)
            for enc in ['utf-8', 'utf-8-sig', 'cp949', 'euc-kr']:
                try:
                    with open(file_path, "r", encoding=enc) as f:
                        for line in f:
                            line = line.strip()
                            if not line or line.startswith("#"):
                                continue
                            parts = [p.strip() for p in line.split(",")]
                            if len(parts) >= 3:
                                try:
                                    name = parts[0]
                                    lat = float(parts[1])
                                    lon = float(parts[2])
                                    is_down = parts[3].upper() if len(parts) > 3 else "Y"
                                    is_cmd = parts[4].upper() if len(parts) > 4 else "Y"
                                    
                                    if not any(s[0] == name for s in stations_list):
                                        stations_list.append((name, lat, lon, is_down, is_cmd))
                                except ValueError:
                                    continue
                    break
                except Exception:
                    continue
    return stations_list


# ==============================================================================
# [궤도 계산] 위성 궤도 회차 타임라인 구축 함수
# ==============================================================================
def find_orbit_starts_at_north_pole(satellite, ts, t0, t1, start_pass_no=1):
    orbit_starts = []
    start_dt = t0.utc_datetime()
    end_dt = t1.utc_datetime()
    current_dt = start_dt
    prev_lat = -999.0
    is_ascending = True
    step = timedelta(seconds=60)
    
    orbit_counter = start_pass_no
    orbit_starts.append((orbit_counter, start_dt))
    
    while current_dt <= end_dt:
        t_now = ts.from_datetime(current_dt)
        geocentric = satellite.at(t_now)
        lat = wgs84.subpoint(geocentric).latitude.degrees
        if prev_lat != -999.0:
            if lat < prev_lat and is_ascending:
                orbit_counter += 1
                orbit_starts.append((orbit_counter, current_dt))
                is_ascending = False
            elif lat > prev_lat:
                is_ascending = True
        prev_lat = lat
        current_dt += step
    return orbit_starts


def get_orbit_number(aos_time, orbit_timeline, default_start_pass=1):
    for orbit_no, start_dt in reversed(orbit_timeline):
        if aos_time >= start_dt:
            return orbit_no
    return default_start_pass


# ==============================================================================
# [스케줄링 핵심 엔진] 최소/최대 패스 제한 및 공평 배정 연산
# ==============================================================================
def calculate_passes(tle_data, station_configs, start_dt, end_dt, min_el, min_dur, 
                     start_pass_no=1, equalize_allocation=True, 
                     equalize_target_sats=None, min_pass_targets=None, max_pass_targets=None):
    """
    :param min_pass_targets: 위성별 개별 최소 보장 패스 (예: {'NEONSAT1': 0, 'NEONSAT-1A': 2})
    :param max_pass_targets: 위성별 개별 최대 제한 패스 (예: {'NEONSAT1': 5, 'NEONSAT-1A': 0(상한 없음)})
    """
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=timezone.utc)

    skyfield_dir = get_resource_path("skyfield_data")
    if not os.path.exists(skyfield_dir):
        skyfield_dir = os.path.abspath(".")

    from skyfield.api import Loader
    custom_loader = Loader(skyfield_dir)

    ts = custom_loader.timescale(builtin=True)
    t0 = ts.from_datetime(start_dt)
    t1 = ts.from_datetime(end_dt)
    
    stations = {cfg[0]: wgs84.latlon(cfg[1], cfg[2]) for cfg in station_configs}
    raw_passes = []
    
    for sat_key, sat_info in tle_data.items():
        if isinstance(sat_info, dict):
            lines = sat_info['lines']
            norad_id = sat_info['norad_id']
            sat_name = sat_info['sat_name']
        else:
            lines = sat_info
            norad_id = lines[0][2:7].strip()
            sat_name = sat_key
            
        try:
            satellite = EarthSatellite(lines[0], lines[1], sat_name, ts)
        except Exception:
            continue
            
        orbit_timeline = find_orbit_starts_at_north_pole(satellite, ts, t0, t1, start_pass_no=start_pass_no)
            
        for gs_name, gs_loc in stations.items():
            times, events = satellite.find_events(gs_loc, t0, t1, altitude_degrees=min_el)
            current_pass = {}
            for t, event in zip(times, events):
                if event == 0:
                    current_pass['aos'] = t.utc_datetime()
                elif event == 1:
                    difference = satellite - gs_loc
                    alt, _, _ = difference.at(t).altaz()
                    current_pass['max_el'] = alt.degrees
                elif event == 2 and 'aos' in current_pass:
                    current_pass['los'] = t.utc_datetime()
                    duration = (current_pass['los'] - current_pass['aos']).total_seconds()
                    
                    if duration >= min_dur:
                        pass_no = get_orbit_number(current_pass['aos'], orbit_timeline, default_start_pass=start_pass_no)
                        raw_passes.append({
                            'satellite': f"{sat_name}({norad_id})",
                            'station': gs_name,
                            'aos': current_pass['aos'],
                            'los': current_pass['los'],
                            'duration': round(duration, 1),
                            'max_el': round(current_pass.get('max_el', 0.0), 2),
                            'conflict_group': None,
                            'selected': True,
                            'status': "Normal",
                            'pass_no': pass_no
                        })
                    current_pass = {}

    if not raw_passes:
        return []

    raw_groups = []
    for gs_name in stations.keys():
        station_passes = [p for p in raw_passes if p['station'] == gs_name]
        station_passes.sort(key=lambda x: x['aos'])
        current_group = []
        for p in station_passes:
            if not current_group:
                current_group.append(p)
            else:
                max_los_in_group = max(x['los'] for x in current_group)
                if p['aos'] < max_los_in_group:
                    current_group.append(p)
                else:
                    raw_groups.append(current_group)
                    current_group = [p]
        if current_group:
            raw_groups.append(current_group)

    if not raw_groups:
        return []

    raw_groups.sort(key=lambda g: min(x['aos'] for x in g))

    calculated_passes = []
    group_counter = 0
    
    sat_selected_counts = {}
    for sat_key in tle_data.keys():
        clean_name = sat_key.split("(")[0].strip()
        sat_selected_counts[clean_name] = 0

    if equalize_target_sats is None:
        equalize_target_sats = set(sat_selected_counts.keys())
    else:
        equalize_target_sats = set(equalize_target_sats)

    if min_pass_targets is None: min_pass_targets = {}
    if max_pass_targets is None: max_pass_targets = {}

    # 경합 해결 및 최소/최대 패스 연산
    for g in raw_groups:
        if len(g) > 1:
            group_counter += 1
            
            def fairness_sort_key(p):
                sat_clean = p['satellite'].split("(")[0].strip()
                is_target = sat_clean in equalize_target_sats
                
                curr_cnt = sat_selected_counts.get(sat_clean, 0)
                min_req = min_pass_targets.get(sat_clean, 0)
                max_cap = max_pass_targets.get(sat_clean, 0) # 0이면 상한 없음
                
                # (0) 이미 최대 상한 횟수(Max Cap)에 도달한 위성은 최후순위로 격하(99)
                if max_cap > 0 and curr_cnt >= max_cap:
                    return (99, 99, 99, 0)
                
                if equalize_allocation:
                    need_more = 0 if (is_target and curr_cnt < min_req) else 1
                    target_flag = 0 if is_target else 1
                    return (need_more, target_flag, curr_cnt, -p['duration'])
                else:
                    return (0, 0, 0, -p['duration'])

            sorted_candidates = sorted(g, key=fairness_sort_key)
            winning_pass = sorted_candidates[0]

            for p in g:
                p['conflict_group'] = group_counter
                p['status'] = f"Conflict (Grp {group_counter})"
                
                sat_clean = p['satellite'].split("(")[0].strip()
                curr_cnt = sat_selected_counts.get(sat_clean, 0)
                max_cap = max_pass_targets.get(sat_clean, 0)
                
                # 상한에 걸린 후보는 경합 시 자동 탈락
                if max_cap > 0 and curr_cnt >= max_cap:
                    is_win = False
                else:
                    is_win = (p == winning_pass)
                    
                p['selected'] = is_win
                if is_win:
                    sat_selected_counts[sat_clean] = curr_cnt + 1
        else:
            for p in g:
                sat_clean = p['satellite'].split("(")[0].strip()
                curr_cnt = sat_selected_counts.get(sat_clean, 0)
                max_cap = max_pass_targets.get(sat_clean, 0)
                
                # 단독 패스인 경우에도 Max Cap 초과 여부 검증
                if max_cap > 0 and curr_cnt >= max_cap:
                    p['selected'] = False
                    p['status'] = f"Capped (Max {max_cap})"
                else:
                    p['selected'] = True
                    sat_selected_counts[sat_clean] = curr_cnt + 1
                
        calculated_passes.extend(g)

    calculated_passes.sort(key=lambda x: (x['aos'], x['station']))
    return calculated_passes