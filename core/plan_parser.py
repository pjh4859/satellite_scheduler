import os
import csv
import yaml
import re
from datetime import datetime, timezone
from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill, Font

# ==============================================================================
# [설정] 미션 플랜(제약 조건) 표준 헤더 정의
# ==============================================================================
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


# ==============================================================================
# [유틸리티] 위성 이름 정규화 함수
# ==============================================================================
def normalize_sat_name(sat_str):
    """
    위성 이름 정규화 처리 함수
    
    [기능 설명]
    - 입력된 위성명(예: 'NEONSAT-1A(67614)')에서 괄호 및 특수문자/공백을 제거합니다.
    - 순수 영문자와 숫자로만 구성된 대문자 문자열(예: 'NEONSAT1A')로 정규화하여 
      위성 매칭 시 100% 일치성을 보장합니다.
    """
    if not sat_str:
        return ""
    # 괄호 및 NORAD ID 부분 제거
    clean = str(sat_str).split("(")[0].strip()
    # 특수문자 및 공백 제거 후 대문자 변환
    clean = re.sub(r'[^A-Za-z0-9]', '', clean).upper()
    return clean


# ==============================================================================
# [파싱] 단일 행(Row) 유연 매핑 및 자료형 안전 변환 함수
# ==============================================================================
def parse_row_flexible(row_dict):
    """
    다양한 양식의 CSV / Excel / YAML 데이터 행(Row)을 표준 딕셔너리로 변환
    
    [기능 설명]
    - 영문/한글, 대소문자, 언더바(_), 공백이 섞여 있는 다양한 헤더명을 감지합니다.
    - 미션 플랜에 필요한 8가지 필수 제약 조건 항목으로 자동 매핑합니다.
    - 수치형 데이터(최고 고도각, 최소 통신시간, 시퀀스 ID 등)는 안전하게 float/int로 변환하며,
      None 값이나 변환 실패 시 기본값을 적용하여 오류를 방지합니다.
    """
    if not isinstance(row_dict, dict):
        row_dict = {}

    # 공백 및 특수문자를 제거한 소문자 비교용 맵 생성
    col_map = {str(k).strip().lower().replace("_", "").replace(" ", ""): v for k, v in row_dict.items() if k is not None}
    
    # 1. Sat_ID (위성 식별자) 탐색
    sat = (row_dict.get('Sat_ID') or row_dict.get('sat_id') or 
           row_dict.get('Satellite') or row_dict.get('satellite') or 
           col_map.get('satid') or col_map.get('satellite') or '')
    
    # 2. Main Activity (주 태스크명) 탐색
    main = (row_dict.get('Main') or row_dict.get('main') or 
            row_dict.get('Activity') or row_dict.get('activity') or 
            col_map.get('mainactivity') or col_map.get('activity') or '')
    
    # 3. Sub Activity (부 태스크/상세 내용) 탐색
    sub = (row_dict.get('Sub') or row_dict.get('sub') or 
           col_map.get('subactivity') or '')
    
    # 4. Min_El (최소 요구 고도각, deg) 탐색
    min_el = (row_dict.get('Min_El') or row_dict.get('min_el') or 
              col_map.get('minel') or 0)
    
    # 5. Required_Cap (요구 안테나 기능: CMD, DOWN, NONE 등) 탐색
    req_cap = (row_dict.get('Required_Cap') or row_dict.get('req_cap') or 
               row_dict.get('required_cap') or row_dict.get('X-Band 여부') or 
               col_map.get('requiredcap') or col_map.get('xband여부') or 'NONE')
    
    # 6. Min_Duration (최소 요구 교신 시간, sec) 탐색
    min_dur = (row_dict.get('Min_Duration') or row_dict.get('min_dur') or 
               row_dict.get('min_duration') or row_dict.get('최소 pass contact 시간') or 
               col_map.get('minduration') or col_map.get('최소passcontact시간') or 0)
    
    # 7. Pre_Req_Main (선행 요구 태스크명) 탐색
    pre_req = (row_dict.get('Pre_Req_Main') or row_dict.get('pre_req_main') or 
               row_dict.get('Pre Activity Sequence ID') or 
               col_map.get('prereqmain') or col_map.get('preactivitysequenceid') or 'NONE')
    
    # 8. Sequence_ID (태스크 순서 ID) 탐색
    seq_id = (row_dict.get('Sequence_ID') or row_dict.get('sequence_id') or 
              row_dict.get('activity_sequence_id') or 
              col_map.get('sequenceid') or col_map.get('activitysequenceid') or 999)

    # --------------------------------------------------------------------------
    # 데이터 표준화 및 예외 방지 수치 변환
    # --------------------------------------------------------------------------
    # X-Band 여부 표기(Y/N) 변환 처리
    req_cap_str = str(req_cap).strip().upper() if req_cap is not None else 'NONE'
    if req_cap_str == 'Y':
        req_cap_str = 'DOWN'
    elif req_cap_str == 'N':
        req_cap_str = 'NONE'

    # 수치형 변환 예외 처리 (None 또는 잘못된 문자열 파싱 대비)
    try:
        float_el = float(min_el) if min_el is not None else 0.0
    except (ValueError, TypeError):
        float_el = 0.0
    
    try:
        float_dur = float(min_dur) if min_dur is not None else 0.0
    except (ValueError, TypeError):
        float_dur = 0.0

    try:
        int_seq = int(seq_id) if seq_id is not None else 999
    except (ValueError, TypeError):
        int_seq = 999

    return {
        'sat_id': str(sat).strip() if sat is not None else '',
        'main': str(main).strip() if main is not None else '',
        'sub': str(sub).strip() if sub is not None else '',
        'min_el': float_el,
        'req_cap': req_cap_str,
        'min_dur': float_dur,
        'pre_req_main': str(pre_req).strip() if pre_req is not None else 'NONE',
        'sequence_id': int_seq
    }


# ==============================================================================
# [초기화] 기본 미션 플랜 샘플 파일 생성 함수들
# ==============================================================================
def create_default_plan_csv(plans_dir):
    """
    기본 미션 플랜 CSV 샘플 생성 함수
    
    [기능 설명]
    - plans 폴더가 없으면 생성하고, default_mission_plan.csv 기본 파일이 없는 경우 
      초기 샘플 데이터 2행을 포함하여 생성합니다.
    """
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
    """
    기본 미션 플랜 Excel 샘플 생성 함수
    
    [기능 설명]
    - default_mission_plan.xlsx 기본 파일이 없는 경우 엑셀 워크북을 생성하고 
      표준 헤더 행을 작성합니다.
    """
    if not os.path.exists(plans_dir):
        os.makedirs(plans_dir)
    xlsx_path = os.path.join(plans_dir, "default_mission_plan.xlsx")
    if os.path.exists(xlsx_path): 
        return
    wb = Workbook()
    ws = wb.active
    ws.title = "Mission Plan Constraints"
    headers = list(PLAN_HEADERS.values())
    ws.append(headers)
    wb.save(xlsx_path)


# ==============================================================================
# [로더] 포맷별 미션 플랜 로딩 함수들
# ==============================================================================
def load_plan_yaml(file_path):
    """
    YAML 파일 전용 로더 (DRM 회피 및 보안 내부망 환경 최적화)
    
    [기능 설명]
    - 보안 시스템(DRM)으로 인해 엑셀 파일 접근이 차단되는 환경을 위한 최적의 로더입니다.
    - 리스트 형태 형태이거나 'mission_constraints' / 'constraints' 키로 래핑된 
      YAML 문서를 안전하게 읽어와 표준 제약조건 리스트로 변환합니다.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = yaml.safe_load(f) or {}
        
    if isinstance(content, list):
        raw_list = content
    elif isinstance(content, dict):
        raw_list = content.get("mission_constraints", content.get("constraints", []))
    else:
        raw_list = []
        
    parsed_rows = [parse_row_flexible(item) for item in raw_list if isinstance(item, dict)]
    return parsed_rows


def load_plan_csv(file_path):
    """
    CSV 파일 전용 로더 (다중 인코딩 지원)
    
    [기능 설명]
    - UTF-8, UTF-8-SIG, CP949(EUC-KR) 등 다양한 한글 인코딩을 순차 시도하여 
      한글 깨짐 및 DecodeError를 완벽하게 차단합니다.
    - 주석 처리된 행('#'으로 시작하는 행)은 자동으로 건너뜁니다.
    """
    encodings = ['utf-8-sig', 'utf-8', 'cp949', 'euc-kr']
    lines = []
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc) as f:
                lines = [line for line in f if not line.strip().startswith("#")]
            break
        except Exception:
            continue

    if not lines:
        return []
        
    reader = csv.DictReader(lines)
    parsed_rows = [parse_row_flexible(row) for row in reader]
    return parsed_rows


def load_plan_excel(file_path):
    """
    Excel (.xlsx, .xls) 파일 전용 로더
    
    [기능 설명]
    - openpyxl 라이브러리를 통해 첫 번째 행의 헤더를 읽고, 두 번째 행부터 
      데이터 셀 값을 추출하여 유연하게 매핑합니다.
    """
    wb = load_workbook(file_path, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
        
    # 첫 번째 행을 헤더로 추출
    headers = [str(cell).strip() if cell is not None else "" for cell in rows[0]]
    parsed_rows = []
    
    # 두 번째 행부터 데이터 매핑 진행
    for row in rows[1:]:
        if not any(row): 
            continue
        row_dict = {headers[i]: row[i] for i in range(min(len(headers), len(row)))}
        parsed_rows.append(parse_row_flexible(row_dict))
    return parsed_rows


def load_plan_file(file_path):
    """
    통합 미션 플랜 파일 로더 (확장자 자동 판별)
    
    [기능 설명]
    - 입력된 파일 경로의 확장자(.yaml, .yml, .xlsx, .xls, .csv)를 자동으로 감지하여 
      알맞은 파서(YAML, Excel, CSV)를 호출합니다.
    - 파일이 존재하지 않는 경우 빈 리스트를 안전하게 반환합니다.
    """
    if not file_path or not os.path.exists(file_path):
        return []
        
    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".yaml", ".yml"]:
        return load_plan_yaml(file_path)
    elif ext in [".xlsx", ".xls"]:
        return load_plan_excel(file_path)
    elif ext == ".csv":
        return load_plan_csv(file_path)
    else:
        # 기타 파일 형태는 CSV 기본 로더로 처리 시도
        return load_plan_csv(file_path)


# ==============================================================================
# [저장] 미션 플랜 제약 조건 YAML 저장 함수
# ==============================================================================
def save_plan_to_yaml(dest_path, plan_data_list):
    """
    제약 조건 데이터를 표준 YAML 문서로 출력/저장
    
    [기능 설명]
    - Tab 2에서 편집되거나 생성된 미션 플랜 데이터를 전달받아,
      생성 시각(UTC Timestamp) 및 수량 메타데이터와 함께 정돈된 YAML 파일로 저장합니다.
    - allow_unicode=True 설정을 적용하여 한글 태스크명이 깨지지 않고 선명하게 저장됩니다.
    """
    # 저장 전 각 항목의 타입을 안전하게 변환
    sanitized_list = [parse_row_flexible(item) if isinstance(item, dict) else item for item in plan_data_list]
    
    payload = {
        "generation_timestamp": datetime.now(timezone.utc).isoformat(),
        "total_constraints_count": len(sanitized_list),
        "mission_constraints": sanitized_list
    }
    
    # 출력 대상 폴더 존재 확인
    dest_dir = os.path.dirname(dest_path)
    if dest_dir and not os.path.exists(dest_dir):
        os.makedirs(dest_dir)
        
    with open(dest_path, "w", encoding="utf-8") as f:
        yaml.dump(payload, f, default_flow_style=False, sort_keys=False, allow_unicode=True)