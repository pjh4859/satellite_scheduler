import os
import csv
import yaml
import re
from datetime import datetime, timezone
from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill, Font

PLAN_HEADERS = {
    "sat_id": "Sat_ID",
    "main": "Main",
    "sub": "Sub",
    "min_el": "Min_El",
    "req_cap": "Required_Cap",
    "min_dur": "Min_Duration",
    "pre_req_main": "Pre_Req_Main",
    "sequence_id": "Sequence_ID"
}

def normalize_sat_name(sat_str):
    """'NEONSAT-1A(67614)' -> 'NEONSAT1A'로 정규화하여 매칭 정확도 100% 보장"""
    if not sat_str:
        return ""
    clean = str(sat_str).split("(")[0].strip()
    clean = re.sub(r'[^A-Za-z0-9]', '', clean).upper()
    return clean

def parse_row_flexible(row_dict):
    """다양한 형태의 CSV/Excel/YAML 헤더 명칭을 표준 키로 매핑"""
    col_map = {str(k).strip().lower().replace("_", "").replace(" ", ""): v for k, v in row_dict.items()}
    
    sat = row_dict.get('Sat_ID', row_dict.get('sat_id', row_dict.get('Satellite', row_dict.get('satellite', ''))))
    main = row_dict.get('Main', row_dict.get('main', row_dict.get('Activity', row_dict.get('activity', ''))))
    sub = row_dict.get('Sub', row_dict.get('sub', ''))
    min_el = row_dict.get('Min_El', row_dict.get('min_el', 0))
    req_cap = row_dict.get('Required_Cap', row_dict.get('req_cap', row_dict.get('required_cap', row_dict.get('X-Band 여부', 'NONE'))))
    min_dur = row_dict.get('Min_Duration', row_dict.get('min_dur', row_dict.get('min_duration', row_dict.get('최소 pass contact 시간', 0))))
    pre_req = row_dict.get('Pre_Req_Main', row_dict.get('pre_req_main', row_dict.get('Pre Activity Sequence ID', 'NONE')))
    seq_id = row_dict.get('Sequence_ID', row_dict.get('sequence_id', row_dict.get('activity_sequence_id', 999)))

    # X-Band Y/N 값 대응
    req_cap_str = str(req_cap).strip().upper()
    if req_cap_str == 'Y':
        req_cap_str = 'DOWN'
    elif req_cap_str == 'N':
        req_cap_str = 'NONE'

    try: float_el = float(min_el)
    except: float_el = 0.0
    
    try: float_dur = float(min_dur)
    except: float_dur = 0.0

    try: int_seq = int(seq_id)
    except: int_seq = 999

    return {
        'sat_id': str(sat).strip(),
        'main': str(main).strip(),
        'sub': str(sub).strip(),
        'min_el': float_el,
        'req_cap': req_cap_str,
        'min_dur': float_dur,
        'pre_req_main': str(pre_req).strip(),
        'sequence_id': int_seq
    }

def create_default_plan_csv(plans_dir):
    if not os.path.exists(plans_dir):
        os.makedirs(plans_dir)
    csv_path = os.path.join(plans_dir, "default_mission_plan.csv")
    if not os.path.exists(csv_path):
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(list(PLAN_HEADERS.values()))
            writer.writerow(["SAT_A", "First Contact", "TM 확인 / Panel 전개", "10", "CMD", "300", "NONE", "1"])
            writer.writerow(["SAT_A", "Health check", "EPS / AOCS 상태 점검", "10", "NONE", "180", "First Contact", "2"])

def create_default_plan_excel(plans_dir):
    if not os.path.exists(plans_dir):
        os.makedirs(plans_dir)
    xlsx_path = os.path.join(plans_dir, "default_mission_plan.xlsx")
    if os.path.exists(xlsx_path): return
    wb = Workbook()
    ws = wb.active
    ws.title = "Mission Plan Constraints"
    headers = list(PLAN_HEADERS.values())
    ws.append(headers)
    wb.save(xlsx_path)

def load_plan_yaml(file_path):
    """DRM 방지 및 보안 환경 대응용 YAML 파일 로더"""
    with open(file_path, "r", encoding="utf-8") as f:
        content = yaml.safe_load(f) or {}
        
    if isinstance(content, list):
        raw_list = content
    else:
        raw_list = content.get("mission_constraints", content.get("constraints", []))
        
    parsed_rows = [parse_row_flexible(item) for item in raw_list]
    return parsed_rows

def load_plan_csv(file_path):
    encodings = ['utf-8-sig', 'utf-8', 'cp949', 'euc-kr']
    lines = []
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc) as f:
                lines = [line for line in f if not line.strip().startswith("#")]
            break
        except:
            continue

    if not lines: raise ValueError("CSV 파일을 읽어올 수 없습니다.")
    reader = csv.DictReader(lines)
    parsed_rows = [parse_row_flexible(row) for row in reader]
    return parsed_rows

def load_plan_excel(file_path):
    wb = load_workbook(file_path, data_only=True)
    ws = wb.active
    headers = [str(cell.value).strip() if cell.value else "" for cell in ws[1]]
    parsed_rows = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not any(row): continue
        row_dict = {headers[i]: row[i] for i in range(min(len(headers), len(row)))}
        parsed_rows.append(parse_row_flexible(row_dict))
    return parsed_rows

def load_plan_file(file_path):
    """확장자(.yaml, .yml, .xlsx, .csv) 자동 판별 로더"""
    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".yaml", ".yml"]:
        return load_plan_yaml(file_path)
    elif ext == ".xlsx":
        return load_plan_excel(file_path)
    else:
        return load_plan_csv(file_path)

def save_plan_to_yaml(dest_path, plan_data_list):
    payload = {
        "generation_timestamp": datetime.now(timezone.utc).isoformat(),
        "total_constraints_count": len(plan_data_list),
        "mission_constraints": plan_data_list
    }
    with open(dest_path, "w", encoding="utf-8") as f:
        yaml.dump(payload, f, default_flow_style=False, sort_keys=False, allow_unicode=True)