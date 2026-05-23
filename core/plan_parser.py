import os
import csv
import yaml
from datetime import datetime, timezone
from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill, Font

# 🔥 운영 도중 항목이 언제든 추가/삭제될 수 있도록 표준 키-헤더 매핑 구조를 단일화합니다.
PLAN_HEADERS = {
    "satellite": "Satellite",
    "activity": "Activity",
    "activity_sequence_id": "Activity Sequence ID",
    "pre_activity_sequence_id": "Pre Activity Sequence ID",
    "min_pass_contact": "최소 pass contact 시간",
    "x_band_req": "X-Band 여부",
    "priority": "Priority"
}

def create_default_plan_csv(plans_dir):
    """기존 CSV 양식 생성 함수를 유저님의 새로운 동적 항목 규격에 맞게 리뉴얼"""
    if not os.path.exists(plans_dir):
        os.makedirs(plans_dir)
        
    csv_path = os.path.join(plans_dir, "default_mission_plan.csv")
    if not os.path.exists(csv_path):
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            f.write("# LEOP 미션 제약조건 및 액티비티 명세 규칙\n")
            f.write("# X-Band 여부: Y / N, Priority: High / Medium / Low\n")
            writer.writerow(list(PLAN_HEADERS.values()))
            
            # 새 기준의 샘플 데이터 주입
            writer.writerow(["NEONSAT1", "TC_히터_온", "101", "None", "120", "N", "High"])
            writer.writerow(["NEONSAT1", "TM_덤프_X밴드", "102", "101", "300", "Y", "Medium"])
            writer.writerow(["SPACEEYE-T1", "안테나_전개", "201", "None", "60", "N", "High"])

def create_default_plan_excel(plans_dir):
    """🔥 [신규] 위성별로 가로 줄 색상이 다르게 구분된 기본 엑셀(.xlsx) 템플릿 파일 생성"""
    if not os.path.exists(plans_dir):
        os.makedirs(plans_dir)
        
    xlsx_path = os.path.join(plans_dir, "default_mission_plan.xlsx")
    if os.path.exists(xlsx_path):
        return
        
    wb = Workbook()
    ws = wb.active
    ws.title = "Mission Plan Constraints"
    
    # 헤더 작성 및 딥그레이 테마
    headers = list(PLAN_HEADERS.values())
    ws.append(headers)
    
    header_fill = PatternFill(start_color="2A2A2A", end_color="2A2A2A", fill_type="solid")
    header_font = Font(name="맑은 고딕", size=11, bold=True, color="FFFFFF")
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        
    # 샘플 데이터 정의
    sample_data = [
        ["NEONSAT1", "TC_히터_온", "101", "None", "120", "N", "High"],
        ["NEONSAT1", "TM_덤프_X밴드", "102", "101", "300", "Y", "Medium"],
        ["SPACEEYE-T1", "안테나_전개", "201", "None", "60", "N", "High"],
        ["SPACEEYE-T1", "배터리_초기화", "202", "201", "90", "N", "Low"]
    ]
    
    # 🔥 위성 이름별 부드러운 파스텔톤 가로줄 색상 분기 딕셔너리
    sat_colors = {
        "NEONSAT1": "F2F9FF",      # 연한 청회색
        "SPACEEYE-T1": "FFFBF0",   # 연한 샌드 베이지
        "DEFAULT": "FFFFFF"
    }
    
    data_font = Font(name="맑은 고딕", size=10)
    for row_idx, row_data in enumerate(sample_data, start=2):
        ws.append(row_data)
        sat_name = row_data[0].upper().strip()
        color_hex = sat_colors.get(sat_name, sat_colors["DEFAULT"])
        row_fill = PatternFill(start_color=color_hex, end_color=color_hex, fill_type="solid")
        
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.fill = row_fill
            cell.font = data_font
            
    # 열 너비 자동 보정
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = col[0].column_letter
        ws.column_dimensions[col_letter].width = max(max_len + 4, 15)
        
    wb.save(xlsx_path)

def load_plan_csv(file_path):
    """동적 항목 변동성에 안전한 하이브리드 CSV 파서"""
    encodings = ['utf-8-sig', 'utf-8', 'cp949', 'euc-kr']
    lines = []
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc) as f:
                lines = [line for line in f if not line.strip().startswith("#")]
            break
        except:
            continue

    if not lines:
        raise ValueError("CSV 파일을 읽어올 수 없습니다.")

    parsed_rows = []
    reader = csv.DictReader(lines)
    
    # 동적으로 원본 CSV의 실제 헤더 리스트를 분석하여 룩업 매핑
    field_names = reader.fieldnames if reader.fieldnames else []
    
    for row in reader:
        data = {}
        for key, header_name in PLAN_HEADERS.items():
            # 사용자가 나중에 항목명을 지우거나 추가하더라도 에러가 나지 않고 유연하게 공백/기본값 처리
            data[key] = row.get(header_name, "").strip() if header_name in field_names else ""
        parsed_rows.append(data)
    return parsed_rows

def load_plan_excel(file_path):
    """🔥 [신규] 사용자가 수정한 엑셀 파일(.xlsx)을 동적으로 읽어 데이터셋으로 파싱하는 스캐너"""
    wb = load_workbook(file_path, data_only=True)
    ws = wb.active
    
    # 1행에서 헤더 인덱스 매핑 관계 추적 (항목 배치 순서가 바뀌어도 자동 대응)
    headers = [str(cell.value).strip() if cell.value else "" for cell in ws[1]]
    
    parsed_rows = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not any(row):  # 완전히 비어있는 행 패스
            continue
        
        data = {}
        for key, header_name in PLAN_HEADERS.items():
            if header_name in headers:
                col_idx = headers.index(header_name)
                val = row[col_idx]
                data[key] = str(val).strip() if val is not None else ""
            else:
                data[key] = ""
        parsed_rows.append(data)
    return parsed_rows

def save_plan_to_yaml(dest_path, plan_data_list):
    """최종 제약조건 명세를 YAML 파일로 변환 보관"""
    payload = {
        "generation_timestamp": datetime.now(timezone.utc).isoformat(),
        "total_constraints_count": len(plan_data_list),
        "mission_constraints": plan_data_list
    }
    with open(dest_path, "w", encoding="utf-8") as f:
        yaml.dump(payload, f, default_flow_style=False, sort_keys=False, allow_unicode=True)