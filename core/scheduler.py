import os
from datetime import datetime, timezone, timedelta
from skyfield.api import load, wgs84, EarthSatellite

def parse_tle_from_dir(tle_dir, selected_files=None):
    """
    tle/ 폴더 내부에서 TLE 파일들을 읽어 파싱합니다.
    3-Line (Header + Line1 + Line2) 및 2-Line (Line1 + Line2) 모두 대응하며,
    Line1[2:7]에서 순수 NORAD ID(위성 번호)를 정확히 추출합니다.
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
            with open(file_path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
                
            idx = 0
            while idx < len(lines):
                # Line 1과 Line 2의 위치 탐색
                if lines[idx].startswith("1 ") and (idx + 1) < len(lines) and lines[idx+1].startswith("2 "):
                    line1 = lines[idx]
                    line2 = lines[idx+1]
                    
                    # Line 1의 3번째~7번째 글자에서 5자리 NORAD ID(위성 번호) 추출
                    norad_id = line1[2:7].strip()
                    
                    # Line 1 바로 앞줄에 위성 이름(Header)이 존재하는지 확인
                    sat_name = None
                    if idx > 0 and not lines[idx-1].startswith("1 ") and not lines[idx-1].startswith("2 "):
                        sat_name = lines[idx-1].strip()
                    else:
                        # Header가 없는 2-line 형태일 경우 파일명에서 추출
                        sat_name = os.path.splitext(filename)[0].strip()
                        
                    # 딕셔너리 Key 및 데이터 저장 (위성 이름과 5자리 위성 번호 분리 명시)
                    satellites[sat_name] = {
                        'lines': (line1, line2),
                        'norad_id': norad_id,
                        'sat_name': sat_name
                    }
                    idx += 2
                else:
                    idx += 1
                    
    return satellites

def parse_stations_from_dir(stations_dir):
    """지상국 속성 확장: 이름, 위도, 경도, 다운로드 가능여부, 커맨딩 가능여부를 읽어옵니다."""
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
            with open(file_path, "r", encoding="utf-8") as f:
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
    return stations_list

def find_orbit_starts_at_north_pole(satellite, ts, t0, t1, start_pass_no=1):
    """시간 윈도우 내에서 위성이 북극점(최고 위도)을 통과하는 시점들을 추적해 궤도 카운트를 생성합니다."""
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

def calculate_passes(tle_data, station_configs, start_dt, end_dt, min_el, min_dur, start_pass_no=1):
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=timezone.utc)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    from skyfield.api import Loader
    custom_loader = Loader(base_dir)

    ts = custom_loader.timescale(builtin=False)
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
                            'max_el': round(current_pass['max_el'], 2),
                            'conflict_group': None,
                            'selected': True,
                            'status': "Normal",
                            'pass_no': pass_no
                        })
                    current_pass = {}

    calculated_passes = []
    group_counter = 0
    for gs_name in stations.keys():
        station_passes = [p for p in raw_passes if p['station'] == gs_name]
        station_passes.sort(key=lambda x: x['aos'])
        groups = []
        current_group = []
        for p in station_passes:
            if not current_group:
                current_group.append(p)
            else:
                max_los_in_group = max(x['los'] for x in current_group)
                if p['aos'] < max_los_in_group:
                    current_group.append(p)
                else:
                    groups.append(current_group)
                    current_group = [p]
        if current_group:
            groups.append(current_group)
            
        for g in groups:
            if len(g) > 1:
                group_counter += 1
                longest_pass = max(g, key=lambda x: x['duration'])
                for p in g:
                    p['conflict_group'] = group_counter
                    p['status'] = f"Conflict (Grp {group_counter})"
                    p['selected'] = (p == longest_pass)
            else:
                for p in g:
                    p['selected'] = True
            calculated_passes.extend(g)
            
    calculated_passes.sort(key=lambda x: (x['aos'], x['station']))
    return calculated_passes