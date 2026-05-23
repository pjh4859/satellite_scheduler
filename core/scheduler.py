import os
from datetime import datetime, timezone, timedelta
from skyfield.api import load, wgs84, EarthSatellite

def parse_tle_from_dir(tle_dir, selected_files=None):
    """tle/ 폴더 내부에서 선택된 TLE 파일만 읽어 파싱합니다."""
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
                if lines[idx].startswith("1 ") and (idx + 1) < len(lines) and lines[idx+1].startswith("2 "):
                    line1 = lines[idx]
                    line2 = lines[idx+1]
                    sat_id = line1[2:7].strip()
                    sat_name = f"SAT_{sat_id}"
                    if idx > 0 and not lines[idx-1].startswith("1 ") and not lines[idx-1].startswith("2 "):
                        sat_name = lines[idx-1]
                    satellites[sat_name] = (line1, line2)
                    idx += 2
                else:
                    idx += 1
    return satellites

def parse_stations_from_dir(stations_dir):
    """🔥 지상국 속성 확장: 이름, 위도, 경도, 다운로드 가능여부, 커맨딩 가능여부를 읽어옵니다."""
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
                            # 뒤쪽 필드가 누락되었을 경우를 대비한 기본값(Y) 방어 코드
                            is_down = parts[3].upper() if len(parts) > 3 else "Y"
                            is_cmd = parts[4].upper() if len(parts) > 4 else "Y"
                            
                            if not any(s[0] == name for s in stations_list):
                                # 세 번째 할당 엔진에서 조회할 수 있도록 다 들고 있도록 확장
                                stations_list.append((name, lat, lon, is_down, is_cmd))
                        except ValueError:
                            continue
    return stations_list

def find_orbit_starts_at_north_pole(satellite, ts, t0, t1):
    """시간 윈도우 내에서 위성이 북극점(최고 위도)을 통과하는 시점들을 추적해 궤도 카운트를 생성합니다."""
    orbit_starts = []
    start_dt = t0.utc_datetime()
    end_dt = t1.utc_datetime()
    current_dt = start_dt
    prev_lat = -999.0
    is_ascending = True
    step = timedelta(seconds=60)
    
    orbit_counter = 1
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

def get_orbit_number(aos_time, orbit_timeline):
    for orbit_no, start_dt in reversed(orbit_timeline):
        if aos_time >= start_dt:
            return orbit_no
    return 1

def calculate_passes(tle_data, station_configs, start_dt, end_dt, min_el, min_dur):
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=timezone.utc)

    # 🛠️ 수정본 (Skyfield 최신 규격 반영):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # 1. 파일들을 읽어올 경로를 Loader 객체에 먼저 주입합니다.
    from skyfield.api import Loader
    custom_loader = Loader(base_dir)

    # 2. 생성된 로더를 통해 timescale을 호출합니다.
    # 수동으로 복사해 둔 4개 파일(de421.bsp 등)이 base_dir에 있다면 
    # builtin=False 설정에 의해 인터넷을 켜지 않고 해당 파일들을 곧바로 파싱합니다.
    ts = custom_loader.timescale(builtin=False)
    t0 = ts.from_datetime(start_dt)
    t1 = ts.from_datetime(end_dt)
    
    # station_configs는 이제 (name, lat, lon, is_down, is_cmd) 구조임
    stations = {cfg[0]: wgs84.latlon(cfg[1], cfg[2]) for cfg in station_configs}
    raw_passes = []
    
    for sat_name, lines in tle_data.items():
        try:
            satellite = EarthSatellite(lines[0], lines[1], sat_name, ts)
        except Exception:
            continue
            
        orbit_timeline = find_orbit_starts_at_north_pole(satellite, ts, t0, t1)
            
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
                        pass_no = get_orbit_number(current_pass['aos'], orbit_timeline)
                        raw_passes.append({
                            'satellite': sat_name,
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