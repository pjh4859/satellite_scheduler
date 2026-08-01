import os
import sys
from datetime import datetime, timezone, timedelta
from skyfield.api import load, wgs84, EarthSatellite

# ==============================================================================
# [유틸리티] PyInstaller 번들 실행 환경 대응 리소스 경로 탐색 함수
# ==============================================================================
def get_resource_path(relative_path):
    """
    PyInstaller 패키징 환경 지원 함수
    
    [기능 설명]
    - PyInstaller로 배포용 단일 파일/폴더(.exe) 생성 시, 임시 자원 폴더(sys._MEIPASS)를
      우선 탐색하여 skyfield 천체 데이터 디렉토리를 안전하게 로드합니다.
    - 일반 개발 환경일 경우 현재 프로젝트 루트 경로를 반환합니다.
    """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


# ==============================================================================
# [파싱] TLE 궤도 요소 파일 다중 로더 (인코딩 예외 안전 방어)
# ==============================================================================
def parse_tle_from_dir(tle_dir, selected_files=None):
    """
    TLE(Two-Line Element) 궤도 파일 로더
    
    [기능 설명]
    - tle 폴더 내의 모든 .tle 및 .txt 파일을 탐색하여 위성 정보(NORAD ID, 위성명, TLE 2줄)를 읽어옵니다.
    - UTF-8, UTF-8-SIG, CP949, EUC-KR, LATIN-1 다중 인코딩 시도를 통해 
      한글/특수문자 DecodeError 발생을 100% 차단합니다.
    - 폴더가 없을 경우 기본 샘플 TLE 파일(default_sat.tle)을 자동 생성합니다.
    """
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
            
            # 다중 인코딩 시도를 통한 안전한 파일 읽기
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
                # TLE 표준 format인 "1 "과 "2 " 행 탐색
                if lines[idx].startswith("1 ") and (idx + 1) < len(lines) and lines[idx+1].startswith("2 "):
                    line1 = lines[idx]
                    line2 = lines[idx+1]
                    norad_id = line1[2:7].strip()
                    
                    # 위성 이름 추출 (1번 라인 바로 위 상단 행이 위성명인 경우 감지)
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
    """
    지상국(Ground Station) 환경 설정 파일 로더
    
    [기능 설명]
    - stations 폴더 내의 .txt 및 .cfg 설정 파일에서 지상국 명칭, 위도, 경도,
      수신(Download) 가능 여부, 송신(Command) 가능 여부를 파싱합니다.
    - 다중 인코딩을 지원하며, 파싱 에러 시 해당 행을 예외 처리하여 차단합니다.
    """
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
            
            # 다중 인코딩 시도를 통한 지상국 데이터 파싱
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
# [궤도 계산] 위성 궤도 회차(Orbit Pass No.) 타임라인 구축 함수
# ==============================================================================
def find_orbit_starts_at_north_pole(satellite, ts, t0, t1, start_pass_no=1):
    """
    북극 통과 시점 기준 궤도 회차(Orbit Pass Number) 타임라인 산출
    
    [기능 설명]
    - Skyfield의 위도 변환을 추적하여 위성이 남쪽에서 북쪽으로 상승(Ascending) 후 
      최북단(북극 근처)을 통과하는 순간을 카운트하여 궤도 번호를 1씩 증가시킵니다.
    - 시간대별 궤도 시작 시점 리스트 [(orbit_counter, start_datetime), ...]를 구축합니다.
    """
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
            # 위도가 정점을 찍고 다시 감소하기 시작하는 지점(최북단) 감지
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
    """AOS(가시 시작 시점)에 해당하는 궤도 회차 번호 매칭 함수"""
    for orbit_no, start_dt in reversed(orbit_timeline):
        if aos_time >= start_dt:
            return orbit_no
    return default_start_pass


# ==============================================================================
# [스케줄링 핵심 엔진] 패스 계산 및 동시 발사 균등 배정 알고리즘
# ==============================================================================
def calculate_passes(tle_data, station_configs, start_dt, end_dt, min_el, min_dur, 
                     start_pass_no=1, equalize_allocation=True, 
                     equalize_target_sats=None, min_pass_targets=None):
    """
    지상국 가시 패스 연산 및 군집/동시 발사 위성 Round-Robin 공평 배정 엔진
    
    [신규 파라미터 추가]
    - equalize_target_sats (set/list): 균등 배정을 적용할 대상 위성 이름 목록 (None 시 전체 위성 대상)
    - min_pass_targets (dict): 위성별 최소 필수 보장 패스 수량 (예: {'SAT-1': 2, 'SAT-2': 1})
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

    # 지상국별 시간 경합 그룹핑
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
    
    # 위성별 누적 선택 횟수 트래커
    sat_selected_counts = {}
    for sat_key in tle_data.keys():
        clean_name = sat_key.split("(")[0].strip()
        sat_selected_counts[clean_name] = 0

    # 파라미터 정제
    if equalize_target_sats is None:
        equalize_target_sats = set(sat_selected_counts.keys())
    else:
        equalize_target_sats = set(equalize_target_sats)

    if min_pass_targets is None:
        min_pass_targets = {}

    # 경합 해결 및 고급 공평 배정 연산
    for g in raw_groups:
        if len(g) > 1:
            group_counter += 1
            
            if equalize_allocation:
                def fairness_sort_key(p):
                    sat_clean = p['satellite'].split("(")[0].strip()
                    is_target = sat_clean in equalize_target_sats
                    
                    curr_cnt = sat_selected_counts.get(sat_clean, 0)
                    min_req = min_pass_targets.get(sat_clean, 0)
                    
                    # (1) 최소 요구 수량을 아직 채우지 못한 위성에게 최고 우선순위(0) 부여
                    need_more = 0 if (is_target and curr_cnt < min_req) else 1
                    
                    # (2) 균등 대상 위성 여부 (대상 위성을 대상이 아닌 위성보다 우선 고려)
                    target_flag = 0 if is_target else 1
                    
                    # (3) 현재 선택된 횟수 (오름차순)
                    # (4) 교신 시간 Duration (내림차순)
                    return (need_more, target_flag, curr_cnt, -p['duration'])
                
                sorted_candidates = sorted(g, key=fairness_sort_key)
                winning_pass = sorted_candidates[0]
            else:
                winning_pass = max(g, key=lambda x: x['duration'])

            for p in g:
                p['conflict_group'] = group_counter
                p['status'] = f"Conflict (Grp {group_counter})"
                is_win = (p == winning_pass)
                p['selected'] = is_win
                
                if is_win:
                    sat_clean = p['satellite'].split("(")[0].strip()
                    sat_selected_counts[sat_clean] = sat_selected_counts.get(sat_clean, 0) + 1
        else:
            for p in g:
                p['selected'] = True
                sat_clean = p['satellite'].split("(")[0].strip()
                sat_selected_counts[sat_clean] = sat_selected_counts.get(sat_clean, 0) + 1
                
        calculated_passes.extend(g)

    calculated_passes.sort(key=lambda x: (x['aos'], x['station']))
    return calculated_passes